"""Disabled-account recovery and credential-bound two-step deletion."""

import secrets
import uuid
from datetime import timedelta

from flask import current_app, jsonify, request, session

from . import recorder_bp
from .db import AccountDeletionGrant, AccountLifecycleNotice, User, _now_utc, db_session
from .passwords import verify_password
from .security import get_current_user
from .users import get_user_by_username
from src.services.account_lifecycle import (
    EXEMPT_ROLES, activity_anchor, aware, cycle_key, grant_token, permanently_delete_account,
    policy_start, read_grant_token, restore_account,
)


@recorder_bp.route('/admin/disabled-accounts', methods=['GET'])
def disabled_accounts():
    actor = get_current_user()
    if not actor:
        return jsonify({'error': 'Authentication required'}), 401
    if actor['role'] not in {'admin', 'superadmin'}:
        return jsonify({'error': 'Admin access required'}), 403
    accounts = []
    for user in db_session.query(User).filter_by(school_id=actor['school_id'], status='disabled', is_record_actor=0).all():
        if user.role in EXEMPT_ROLES:
            continue
        notices = db_session.query(AccountLifecycleNotice).filter_by(user_id=user.id).all()
        accounts.append({
            'id': user.id, 'username': user.username, 'name': user.display_name, 'role': user.role,
            'email_verified': bool(user.email and user.email_verified_at),
            'disabled_at': aware(user.inactivity_disabled_at).isoformat() if user.inactivity_disabled_at else None,
            'delete_at': aware(user.inactivity_delete_at).isoformat() if user.inactivity_delete_at else None,
            'automatic_deletion': user.role == 'user' and bool(user.inactivity_disabled_at),
            'reason': 'Inactivity' if user.disabled_reason == 'inactivity' else 'Manually disabled',
            'notification_failures': sum(notice.status == 'failed' for notice in notices),
        })
    response = jsonify({'accounts': accounts, 'tracking_started_at': policy_start(db_session).isoformat()})
    response.headers['Cache-Control'] = 'no-store'
    return response


@recorder_bp.route('/admin/disabled-accounts/<user_id>/restore', methods=['POST'])
def recover_disabled_account(user_id):
    actor = get_current_user()
    if not actor:
        return jsonify({'error': 'Authentication required'}), 401
    if actor['role'] not in {'admin', 'superadmin'}:
        return jsonify({'error': 'Admin access required'}), 403
    target = db_session.query(User).filter_by(id=user_id, school_id=actor['school_id'], is_record_actor=0).with_for_update().first()
    if not target or target.role in EXEMPT_ROLES:
        return jsonify({'error': 'Disabled account not found'}), 404
    if target.status != 'disabled':
        return jsonify({'error': 'This account is already active.'}), 409
    try:
        restore_account(db_session, target, _now_utc())
        db_session.commit()
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Unable to recover the account.'}), 500
    return jsonify({'message': 'Account recovered. Its inactivity clock has restarted.'}), 200


def _create_grant(user, permission):
    grant = AccountDeletionGrant(
        id=str(uuid.uuid4()), user_id=user.id, school_id=user.school_id,
        cycle=cycle_key(user, policy_start(db_session)), permission=permission,
        recipient=user.email or '', expires_at=_now_utc() + timedelta(minutes=15),
    )
    db_session.add(grant)
    db_session.commit()
    return jsonify({'token': grant_token(grant.id, current_app.secret_key)})


@recorder_bp.route('/account-deletion/self', methods=['POST'])
def own_deletion_link():
    actor = get_current_user()
    if not actor:
        return jsonify({'error': 'Authentication required'}), 401
    user = db_session.get(User, actor['id'])
    if user.role in EXEMPT_ROLES:
        return jsonify({'error': 'This account is exempt from account cleanup.'}), 403
    return _create_grant(user, 'owner')


@recorder_bp.route('/admin/disabled-accounts/<user_id>/deletion-link', methods=['POST'])
def superadmin_deletion_link(user_id):
    actor = get_current_user()
    if not actor:
        return jsonify({'error': 'Authentication required'}), 401
    if actor['role'] != 'superadmin':
        return jsonify({'error': 'Superadmin access required'}), 403
    user = db_session.query(User).filter_by(id=user_id, school_id=actor['school_id'], is_record_actor=0).first()
    if not user or user.role in EXEMPT_ROLES:
        return jsonify({'error': 'Account not found'}), 404
    return _create_grant(user, 'superadmin')


def _load_deletion_grant():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get('token'), str) or len(data['token']) > 1024:
        return None, None, (jsonify({'error': 'Invalid deletion link.'}), 400)
    grant_id = read_grant_token(data['token'], current_app.secret_key)
    grant = db_session.get(AccountDeletionGrant, grant_id) if grant_id else None
    if not grant:
        return None, None, (jsonify({'error': 'Invalid deletion link.'}), 400)
    user = db_session.get(User, grant.user_id)
    if not user:
        return grant, None, None
    if (grant.revoked_at or aware(grant.expires_at) <= _now_utc()
            or grant.cycle != cycle_key(user, policy_start(db_session))):
        return None, None, (jsonify({'error': 'This deletion link expired or was cancelled. Account recovery or a new login cancels old links.'}), 410)
    if user.role in EXEMPT_ROLES or user.is_record_actor:
        return None, None, (jsonify({'error': 'This account cannot be deleted through this link.'}), 403)
    return grant, user, None


@recorder_bp.route('/account-deletion/inspect', methods=['POST'])
def inspect_deletion_link():
    grant, user, error = _load_deletion_grant()
    if error:
        return error
    if not user:
        return jsonify({'deleted': True, 'message': 'This account has already been permanently deleted.'}), 200
    return jsonify({'deleted': False, 'username': user.username, 'name': user.display_name,
                    'school': user.school.name, 'role': user.role,
                    'confirmation_role': grant.permission}), 200


@recorder_bp.route('/account-deletion/authorize', methods=['POST'])
def authorize_deletion():
    grant, user, error = _load_deletion_grant()
    if error:
        return error
    if not user:
        return jsonify({'deleted': True}), 200
    now = _now_utc()
    if grant.authorization_locked_until and aware(grant.authorization_locked_until) > now:
        return jsonify({'error': 'Too many unsuccessful sign-ins. Please wait 15 minutes.'}), 429
    data = request.get_json()
    username, password = data.get('username'), data.get('password')
    if not isinstance(username, str) or not isinstance(password, str) or len(password) > 4096:
        return jsonify({'error': 'Enter your username and password.'}), 400
    # Disabled owners may authenticate for this operation only, without a portal session.
    account = get_user_by_username(username.strip())
    if grant.permission == 'owner':
        permitted = account and account.id == user.id
    else:
        permitted = account and account.role == 'superadmin' and account.status == 'active' and account.school_id == user.school_id
    if not permitted or not verify_password(account.password_hash, password):
        if grant.authorization_locked_until and aware(grant.authorization_locked_until) <= now:
            grant.authorization_attempts = 0
        grant.authorization_attempts += 1
        if grant.authorization_attempts >= 5:
            grant.authorization_locked_until = now + timedelta(minutes=15)
        db_session.commit()
        return jsonify({'error': 'The username or password is incorrect, or this account cannot authorize this deletion.'}), 403
    grant.authorization_attempts = 0
    grant.authorization_locked_until = None
    db_session.commit()
    if grant.permission == 'owner' and user.status == 'disabled' and session.get('user_uuid') == user.id:
        session.clear()
    nonce = secrets.token_urlsafe(32)
    session['account_deletion_auth'] = {
        'grant_id': grant.id, 'user_id': user.id, 'actor_id': account.id,
        'password_hash_token': hashlib_for_password(account.password_hash),
        'nonce': nonce, 'step': 1, 'expires_at': (_now_utc() + timedelta(minutes=10)).isoformat(),
    }
    return jsonify({'nonce': nonce, 'message': 'Signed in for account deletion only.'}), 200


def hashlib_for_password(value):
    import hashlib
    import hmac
    return hmac.new(current_app.secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()


def _deletion_authorization(grant, user, step):
    proof = session.get('account_deletion_auth') or {}
    nonce = request.get_json().get('nonce')
    if (proof.get('grant_id') != grant.id or proof.get('user_id') != user.id
            or proof.get('step') != step or not isinstance(nonce, str)
            or not secrets.compare_digest(proof.get('nonce', ''), nonce)):
        return None
    from datetime import datetime
    if aware(datetime.fromisoformat(proof['expires_at'])) <= _now_utc():
        return None
    actor = db_session.get(User, proof['actor_id'])
    if not actor or not secrets.compare_digest(proof['password_hash_token'], hashlib_for_password(actor.password_hash)):
        return None
    if grant.permission == 'superadmin' and not (actor.role == 'superadmin' and actor.status == 'active' and actor.school_id == user.school_id):
        return None
    if grant.permission == 'owner' and actor.id != user.id:
        return None
    return proof


@recorder_bp.route('/account-deletion/prepare', methods=['POST'])
def first_deletion_confirmation():
    grant, user, error = _load_deletion_grant()
    if error:
        return error
    if not user:
        return jsonify({'deleted': True}), 200
    proof = _deletion_authorization(grant, user, 1)
    if not proof:
        return jsonify({'error': 'Sign in again to confirm account deletion.'}), 403
    proof['step'] = 2
    proof['nonce'] = secrets.token_urlsafe(32)
    session['account_deletion_auth'] = proof
    return jsonify({'nonce': proof['nonce'], 'message': 'Final confirmation required.'}), 200


@recorder_bp.route('/account-deletion/confirm', methods=['POST'])
def final_deletion_confirmation():
    grant, user, error = _load_deletion_grant()
    if error:
        return error
    if not user:
        return jsonify({'deleted': True}), 200
    if not _deletion_authorization(grant, user, 2):
        return jsonify({'error': 'Both confirmation steps are required. Sign in again.'}), 403
    target_id = user.id
    try:
        permanently_delete_account(db_session, user, _now_utc(), explicit=True)
        db_session.commit()
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Unable to delete the account. Please try again.'}), 500
    session.pop('account_deletion_auth', None)
    if session.get('user_uuid') == target_id:
        session.clear()
    return jsonify({'deleted': True, 'message': 'Account permanently deleted. School records and sessions are preserved.'}), 200
