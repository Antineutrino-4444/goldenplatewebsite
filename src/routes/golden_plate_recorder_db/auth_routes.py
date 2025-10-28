import json
import uuid

from flask import jsonify, request, session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from . import recorder_bp
from .db import (
    _now_utc,
    db_session,
    get_default_school_id,
    reset_current_school_id,
    set_current_school_id,
)
from .global_db import GlobalUser, School, SchoolInvite, UserDirectory, global_db_session
from .schools import (
    FEATURE_FLAGS,
    bootstrap_school_database,
    generate_school_code,
    get_directory_entry,
    get_directory_users_by_username,
    locate_school_by_code,
    log_audit_event,
    seed_feature_toggles,
)
from .security import get_current_user, is_guest, require_auth
from .users import (
    create_user_record,
    get_invite_code_record,
    get_user_by_username,
    mark_invite_code_used,
)


@recorder_bp.route('/auth/login', methods=['POST'])
def login():
    """User login."""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    global_user = (
        global_db_session.query(GlobalUser)
        .filter(GlobalUser.username == username)
        .first()
    )
    if global_user and global_user.password_hash == password:
        if global_user.status != 'active':
            return jsonify({'error': 'Account is disabled. Please contact an administrator.'}), 403

        session.clear()
        session['user_id'] = global_user.username
        session['role'] = 'global_admin'
        session['global_admin_id'] = global_user.id
        default_school_id = get_default_school_id()
        session['impersonated_school_id'] = default_school_id
        if default_school_id:
            session['school_id'] = default_school_id
            default_school = global_db_session.query(School).filter(School.id == default_school_id).first()
            session['school_code'] = default_school.code if default_school else None
        global_user.last_login_at = _now_utc()
        global_user.updated_at = _now_utc()
        global_db_session.add(global_user)
        global_db_session.commit()
        log_audit_event(
            school_id=None,
            actor_id=global_user.id,
            actor_scope='global',
            action='login',
            target=global_user.username,
        )
        return jsonify({
            'status': 'success',
            'user': {
                'username': global_user.username,
                'name': global_user.display_name,
                'role': 'global_admin',
            },
        }), 200

    directory_entries = get_directory_users_by_username(username)
    matched_entry = next((entry for entry in directory_entries if entry.password_hash == password), None)
    if not matched_entry:
        return jsonify({'error': 'Invalid username or password'}), 401

    school = global_db_session.query(School).filter(School.id == matched_entry.school_id).first()
    if not school or school.deleted_at is not None:
        return jsonify({'error': 'School account is no longer available'}), 403

    session.clear()
    session['school_id'] = matched_entry.school_id
    session['school_code'] = school.code
    token = set_current_school_id(matched_entry.school_id)
    try:
        user = get_user_by_username(username)
        if not user:
            return jsonify({'error': 'Account not found'}), 404
        if user.password_hash != password:
            return jsonify({'error': 'Invalid username or password'}), 401
        if user.status != 'active':
            return jsonify({'error': 'Account is disabled. Please contact an administrator.'}), 403
        user.last_login_at = _now_utc()
        user.updated_at = _now_utc()
        db_session.commit()
    finally:
        reset_current_school_id(token)

    session['user_id'] = username
    session['role'] = user.role
    log_audit_event(
        school_id=matched_entry.school_id,
        actor_id=user.id,
        actor_scope='school',
        action='login',
        target=username,
    )

    return jsonify({
        'status': 'success',
        'user': {
            'username': username,
            'name': user.display_name,
            'role': user.role,
            'school_code': school.code,
        }
    }), 200


@recorder_bp.route('/auth/logout', methods=['POST'])
def logout():
    """User logout."""
    session_keys = [
        'user_id',
        'session_id',
        'guest_access',
        'guest_school_id',
        'guest_school_code',
        'school_id',
        'school_code',
        'role',
        'global_admin_id',
        'impersonated_school_id',
    ]
    for key in session_keys:
        session.pop(key, None)
    return jsonify({'status': 'success', 'message': 'Logged out successfully'}), 200


@recorder_bp.route('/auth/guest', methods=['POST'])
def guest_login():
    """Guest login - allows viewing sessions for a specific school."""
    data = request.get_json(silent=True) or {}
    school_code = data.get('school_code', '').strip()
    if not school_code:
        default_id = get_default_school_id()
        if default_id:
            school = global_db_session.query(School).filter(School.id == default_id).first()
        else:
            school = locate_school_by_code('SAC1899')
    else:
        school = locate_school_by_code(school_code)
    if not school or school.deleted_at is not None:
        return jsonify({'error': 'School not found'}), 404

    if not school.guest_access_enabled:
        return jsonify({'error': 'Guest access disabled for this school'}), 403

    session['guest_access'] = True
    session['guest_school_id'] = school.id
    session['guest_school_code'] = school.code
    session.pop('school_id', None)
    session.pop('school_code', None)

    log_audit_event(
        school_id=school.id,
        actor_id=None,
        actor_scope='guest',
        action='guest_login',
        target=school.code,
    )

    return jsonify({
        'status': 'success',
        'user': {
            'username': 'guest',
            'name': 'Guest User',
            'role': 'guest',
            'school_code': school.code,
        }
    }), 200


@recorder_bp.route('/auth/signup', methods=['POST'])
def signup():
    """User signup."""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    name = data.get('name', '').strip()
    invite_code = data.get('invite_code', '').strip()

    if not username or not password or not name or not invite_code:
        return jsonify({'error': 'Username, password, name, and invite code are required'}), 400

    if len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters long'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters long'}), 400

    invite = get_invite_code_record(invite_code)
    if not invite or invite.status != 'unused':
        return jsonify({'error': 'Invalid invite code'}), 403

    if invite.expires_at and invite.expires_at < _now_utc():
        return jsonify({'error': 'Invite code has expired'}), 403

    school_id = getattr(invite, 'school_id', None)
    if not school_id:
        school_id = session.get('school_id')

    if not school_id:
        return jsonify({'error': 'Invite code is not associated with a school'}), 400

    existing_entry = get_directory_entry(school_id, username)
    if existing_entry:
        return jsonify({'error': 'Username already exists for this school'}), 409

    token = set_current_school_id(school_id)
    try:
        new_user = create_user_record(
            username,
            password,
            name,
            role=invite.role or 'user',
            status='active'
        )
    finally:
        reset_current_school_id(token)

    if not new_user:
        return jsonify({'error': 'Could not create user'}), 500

    try:
        mark_invite_code_used(invite, new_user)
    except Exception:
        token_cleanup = set_current_school_id(school_id)
        try:
            user_to_delete = get_user_by_username(username)
            if user_to_delete:
                try:
                    db_session.delete(user_to_delete)
                    db_session.commit()
                except Exception:
                    db_session.rollback()
        finally:
            reset_current_school_id(token_cleanup)
        return jsonify({'error': 'Could not update invite code'}), 500

    log_audit_event(
        school_id=school_id,
        actor_id=new_user.id,
        actor_scope='school',
        action='signup',
        target=username,
    )

    return jsonify({
        'status': 'success',
        'message': 'Account created successfully'
    }), 201


def _parse_feature_request(data):
    requested = data.get('features') or {}
    feature_states = {}
    if isinstance(requested, dict):
        feature_states.update({str(key): bool(value) for key, value in requested.items()})
    elif isinstance(requested, list):
        for entry in requested:
            if isinstance(entry, str):
                feature_states[entry] = True

    invite_features = {}
    bundle = data.get('_invite_bundle')
    if isinstance(bundle, dict):
        invite_features.update({str(key): bool(value) for key, value in bundle.items()})
    elif isinstance(bundle, (list, tuple)):
        for entry in bundle:
            if isinstance(entry, str):
                invite_features[entry] = True
    elif isinstance(bundle, str) and bundle:
        try:
            parsed = json.loads(bundle)
        except (json.JSONDecodeError, TypeError):
            parsed = None
        if isinstance(parsed, dict):
            invite_features.update({str(key): bool(value) for key, value in parsed.items()})
        elif isinstance(parsed, list):
            for entry in parsed:
                if isinstance(entry, str):
                    invite_features[entry] = True
        else:
            for token in bundle.split(','):
                token = token.strip()
                if token:
                    invite_features[token] = True

    merged = invite_features.copy()
    merged.update(feature_states)
    return merged


def _normalize_owner_payload(data):
    owner = data.get('owner') or {}
    if not isinstance(owner, dict):
        owner = {}
    fallback_username = data.get('owner_username') or data.get('username')
    fallback_password = data.get('owner_password') or data.get('password')
    fallback_name = data.get('owner_name') or data.get('name')
    return {
        'username': (owner.get('username') or fallback_username or '').strip(),
        'password': (owner.get('password') or fallback_password or '').strip(),
        'display_name': (owner.get('display_name') or owner.get('name') or fallback_name or '').strip(),
    }


@recorder_bp.route('/auth/school-signup', methods=['POST'])
def school_signup():
    """Provision a new school tenant from an invite."""

    data = request.get_json(silent=True) or {}
    invite_code = (data.get('invite_code') or '').strip()
    school_name = (data.get('school_name') or '').strip()
    school_address = (data.get('school_address') or data.get('address') or '').strip()
    public_contact = (data.get('public_contact') or '').strip()
    guest_access_enabled = data.get('guest_access_enabled')

    owner_payload = _normalize_owner_payload(data)
    owner_username = owner_payload['username']
    owner_password = owner_payload['password']
    owner_display = owner_payload['display_name']

    if not invite_code:
        return jsonify({'error': 'Invite code is required'}), 400

    invite = (
        global_db_session.query(SchoolInvite)
        .filter(SchoolInvite.code == invite_code)
        .first()
    )

    if not invite:
        return jsonify({'error': 'Invite not found'}), 404

    if not school_name:
        school_name = (invite.school_name or '').strip()

    if not school_name:
        return jsonify({'error': 'School name is required'}), 400

    if not owner_username or not owner_password or not owner_display:
        return jsonify({'error': 'Owner username, password, and display name are required'}), 400

    if len(owner_username) < 3:
        return jsonify({'error': 'Owner username must be at least 3 characters'}), 400

    if len(owner_password) < 6:
        return jsonify({'error': 'Owner password must be at least 6 characters'}), 400

    if invite.used_at is not None:
        return jsonify({'error': 'Invite has already been used'}), 409

    if invite.expires_at and invite.expires_at < _now_utc():
        return jsonify({'error': 'Invite has expired'}), 403

    feature_bundle = {}
    if invite.feature_bundle:
        try:
            feature_bundle = json.loads(invite.feature_bundle)
        except (json.JSONDecodeError, TypeError):
            feature_bundle = invite.feature_bundle

    merged_features = _parse_feature_request({
        'features': data.get('feature_toggles') or data.get('features'),
        '_invite_bundle': feature_bundle,
    })

    feature_preferences = {
        feature: bool(merged_features.get(feature, False))
        for feature in FEATURE_FLAGS.keys()
    }

    if guest_access_enabled is None:
        guest_access_enabled = bool(merged_features.get('guest_access_enabled', True))
    else:
        guest_access_enabled = bool(guest_access_enabled)

    school_code = generate_school_code(school_name)
    db_filename = f"{school_code}.db"

    new_school = School(
        id=str(uuid.uuid4()),
        code=school_code,
        name=school_name,
        address=school_address or (invite.address or ''),
        public_contact=public_contact or (getattr(invite, 'public_contact', None) or ''),
        db_path=db_filename,
        guest_access_enabled=guest_access_enabled,
        created_at=_now_utc(),
        updated_at=_now_utc(),
    )

    global_db_session.add(new_school)
    seed_feature_toggles(new_school, feature_preferences)
    invite.used_at = _now_utc()
    global_db_session.add(invite)

    try:
        global_db_session.flush()
    except IntegrityError:
        global_db_session.rollback()
        return jsonify({'error': 'School could not be created'}), 500

    bootstrap_school_database(new_school)

    token = set_current_school_id(new_school.id)
    try:
        owner_user = create_user_record(
            owner_username,
            owner_password,
            owner_display,
            role='school_super_admin',
            status='active',
        )
    except IntegrityError:
        db_session.rollback()
        global_db_session.rollback()
        return jsonify({'error': 'Owner username already exists for this school'}), 409
    except Exception:
        db_session.rollback()
        global_db_session.rollback()
        return jsonify({'error': 'Unable to create owner account'}), 500
    finally:
        reset_current_school_id(token)

    try:
        global_db_session.commit()
    except Exception:
        global_db_session.rollback()
        # Clean up the owner we just created so we do not leave an orphaned user.
        cleanup_token = set_current_school_id(new_school.id)
        try:
            existing_owner = get_user_by_username(owner_username)
            if existing_owner:
                try:
                    db_session.delete(existing_owner)
                    db_session.commit()
                except Exception:
                    db_session.rollback()
        finally:
            reset_current_school_id(cleanup_token)
        return jsonify({'error': 'Failed to finalize school provisioning'}), 500

    log_audit_event(
        school_id=new_school.id,
        actor_id=None,
        actor_scope='global',
        action='school_signup',
        target=new_school.code,
        payload=json.dumps({
            'owner': owner_username,
            'feature_toggles': {feature: bool(state) for feature, state in merged_features.items()},
            'guest_access_enabled': guest_access_enabled,
        }),
    )

    return jsonify({
        'status': 'success',
        'school': {
            'id': new_school.id,
            'code': new_school.code,
            'name': new_school.name,
            'guest_access_enabled': new_school.guest_access_enabled,
        },
        'owner': {
            'username': owner_username,
            'password': owner_password,
            'display_name': owner_display,
            'role': 'school_super_admin',
        },
    }), 201


@recorder_bp.route('/auth/global-directory', methods=['GET'])
def search_global_directory():
    if not session.get('global_admin_id'):
        return jsonify({'error': 'Global admin access required'}), 403

    query = (request.args.get('q') or '').strip()
    if not query:
        return jsonify({'results': []}), 200

    like_query = f"%{query}%"
    entries = (
        global_db_session.query(UserDirectory, School)
        .join(School, School.id == UserDirectory.school_id)
        .filter(
            School.deleted_at.is_(None),
            or_(
                UserDirectory.username.ilike(like_query),
                UserDirectory.display_name.ilike(like_query),
            ),
        )
        .order_by(UserDirectory.display_name.asc())
        .limit(25)
        .all()
    )

    results = [
        {
            'username': user.username,
            'display_name': user.display_name,
            'role': user.role,
            'status': user.status,
            'school': {
                'id': school.id,
                'code': school.code,
                'name': school.name,
            },
        }
        for user, school in entries
    ]
    return jsonify({'results': results}), 200


@recorder_bp.route('/auth/impersonate', methods=['POST'])
def impersonate_school():
    if not session.get('global_admin_id'):
        return jsonify({'error': 'Global admin access required'}), 403

    data = request.get_json(silent=True) or {}
    school_id = (data.get('school_id') or '').strip()
    if not school_id:
        return jsonify({'error': 'School identifier is required'}), 400

    school = (
        global_db_session.query(School)
        .filter(School.id == school_id, School.deleted_at.is_(None))
        .first()
    )
    if not school:
        return jsonify({'error': 'School not found'}), 404

    session['impersonated_school_id'] = school.id
    session['school_id'] = school.id
    session['school_code'] = school.code
    session.pop('guest_school_id', None)
    session.pop('guest_school_code', None)

    log_audit_event(
        school_id=school.id,
        actor_id=session.get('global_admin_id'),
        actor_scope='global',
        action='impersonate_start',
        target=school.code,
    )
    return jsonify({
        'status': 'success',
        'school': {
            'id': school.id,
            'code': school.code,
            'name': school.name,
        }
    }), 200


@recorder_bp.route('/auth/impersonation/clear', methods=['POST'])
def clear_impersonation():
    if not session.get('global_admin_id'):
        return jsonify({'error': 'Global admin access required'}), 403

    previous_school = session.get('impersonated_school_id')
    session.pop('impersonated_school_id', None)
    session.pop('school_id', None)
    session.pop('school_code', None)

    if previous_school:
        log_audit_event(
            school_id=previous_school,
            actor_id=session.get('global_admin_id'),
            actor_scope='global',
            action='impersonate_end',
            target=str(previous_school),
        )

    return jsonify({'status': 'success'}), 200


@recorder_bp.route('/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status."""
    if require_auth():
        user = get_current_user()
        school_code = session.get('school_code') or session.get('guest_school_code')

        response = {
            'authenticated': True,
            'user': {
                'username': session['user_id'],
                'name': user['name'],
                'role': user['role'],
                'school_code': school_code,
            }
        }

        if session.get('global_admin_id'):
            impersonated_school = None
            active_school = None
            impersonated_id = session.get('impersonated_school_id')
            active_school_id = session.get('school_id')
            if impersonated_id:
                impersonated_school = (
                    global_db_session.query(School)
                    .filter(School.id == impersonated_id)
                    .first()
                )
            if active_school_id:
                active_school = (
                    global_db_session.query(School)
                    .filter(School.id == active_school_id)
                    .first()
                )

            if impersonated_school:
                response['user']['school_code'] = impersonated_school.code

            response['global_admin'] = {
                'impersonating': bool(impersonated_school),
                'active_school': (
                    {
                        'id': active_school.id,
                        'code': active_school.code,
                        'name': active_school.name,
                    }
                    if active_school
                    else None
                ),
                'impersonated_school': (
                    {
                        'id': impersonated_school.id,
                        'code': impersonated_school.code,
                        'name': impersonated_school.name,
                    }
                    if impersonated_school
                    else None
                ),
                'schools': [
                    {
                        'id': school.id,
                        'code': school.code,
                        'name': school.name,
                        'guest_access_enabled': bool(school.guest_access_enabled),
                    }
                    for school in (
                        global_db_session.query(School)
                        .filter(School.deleted_at.is_(None))
                        .order_by(School.name.asc())
                        .all()
                    )
                ],
            }

        return jsonify(response), 200
    if is_guest():
        return jsonify({
            'authenticated': True,
            'user': {
                'username': 'guest',
                'name': 'Guest User',
                'role': 'guest',
                'school_code': session.get('guest_school_code'),
            }
        }), 200
    return jsonify({'authenticated': False}), 200


__all__ = []