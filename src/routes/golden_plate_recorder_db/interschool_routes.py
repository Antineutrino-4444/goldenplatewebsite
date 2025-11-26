import re
import uuid

from flask import jsonify, request
from sqlalchemy import func

from . import recorder_bp
from .db import School, SchoolInviteCode, User, _now_utc, db_session
from .security import get_current_user, is_interschool_user, require_auth
from .users import (
    create_school_invite_code_record,
    get_school_invite_code_record,
    get_user_by_username,
)


def _serialize_school_model(school, *, user_counts=None):
    user_counts = user_counts or {}
    if not school:
        return None
    return {
        'id': school.id,
        'name': school.name,
        'slug': school.slug,
        'status': school.status,
        'created_at': school.created_at.isoformat() if school.created_at else None,
        'updated_at': school.updated_at.isoformat() if school.updated_at else None,
        'user_count': user_counts.get(school.id, 0),
    }


def _serialize_invite_model(invite, user_lookup):
    if not invite:
        return None
    issued_by_user = user_lookup.get(invite.issued_by) if invite.issued_by else None
    used_by_user = user_lookup.get(invite.used_by) if invite.used_by else None
    return {
        'id': invite.id,
        'code': invite.code,
        'school_id': invite.school_id,
        'status': invite.status,
        'issued_at': invite.issued_at.isoformat() if invite.issued_at else None,
        'used_at': invite.used_at.isoformat() if invite.used_at else None,
        'issued_by': None if not issued_by_user else {
            'id': issued_by_user.id,
            'username': issued_by_user.username,
            'display_name': issued_by_user.display_name,
        },
        'used_by': None if not used_by_user else {
            'id': used_by_user.id,
            'username': used_by_user.username,
            'display_name': used_by_user.display_name,
        },
    }


def _normalize_slug(value: str) -> str:
    base = (value or '').strip().lower()
    slug = re.sub(r'[^a-z0-9]+', '-', base)
    slug = slug.strip('-')
    if not slug:
        slug = f'school-{uuid.uuid4().hex[:6]}'
    return slug


@recorder_bp.route('/interschool/school-invite', methods=['POST'])
def create_school_invite():
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    if not is_interschool_user():
        return jsonify({'error': 'Interschool access required'}), 403

    current = get_current_user()
    issued_by = get_user_by_username(current['username'], school_id=current['school_id']) if current else None
    if not issued_by:
        return jsonify({'error': 'Unable to resolve issuing user'}), 500

    try:
        invite = create_school_invite_code_record(issued_by)
    except Exception:
        return jsonify({'error': 'Unable to create school invite code'}), 500

    return jsonify({
        'status': 'success',
        'invite_code': invite.code,
        'school_id': invite.school_id,
    }), 201


@recorder_bp.route('/auth/register-school', methods=['POST'])
def register_school():
    data = request.get_json(silent=True) or {}
    invite_code = (data.get('invite_code') or '').strip()
    school_name = (data.get('school_name') or '').strip()
    school_slug = (data.get('school_slug') or '').strip()
    admin_username = (data.get('admin_username') or '').strip()
    admin_password = (data.get('admin_password') or '').strip()
    admin_display_name = (data.get('admin_display_name') or '').strip()

    if not invite_code or not school_name or not admin_username or not admin_password or not admin_display_name:
        return jsonify({'error': 'Invite code, school name, and admin credentials are required'}), 400

    invite = get_school_invite_code_record(invite_code)
    if not invite:
        return jsonify({'error': 'Invalid invite code'}), 404

    if invite.status != 'unused':
        return jsonify({'error': 'Invite code has already been used'}), 403

    # Ensure the school does not already exist.
    existing_school = db_session.query(School).filter(School.id == invite.school_id).first()
    if existing_school:
        return jsonify({'error': 'School has already been registered'}), 409

    # Normalize slug and ensure uniqueness.
    normalized_slug = _normalize_slug(school_slug or school_name)
    slug_conflict = (
        db_session.query(School)
        .filter(func.lower(School.slug) == normalized_slug.lower())
        .first()
    )
    if slug_conflict:
        return jsonify({'error': 'School slug already in use'}), 409

    # Ensure username availability.
    if get_user_by_username(admin_username):
        return jsonify({'error': 'Username already exists'}), 409

    new_school = School(
        id=invite.school_id,
        name=school_name,
        slug=normalized_slug,
        status='active',
        created_at=_now_utc(),
        updated_at=_now_utc(),
    )

    admin_user = User(
        id=str(uuid.uuid4()),
        school_id=invite.school_id,
        username=admin_username,
        password_hash=admin_password,
        display_name=admin_display_name,
        role='superadmin',
        status='active',
        created_at=_now_utc(),
        updated_at=_now_utc(),
    )

    invite.status = 'used'
    invite.used_by = admin_user.id
    invite.used_at = _now_utc()

    try:
        db_session.add(new_school)
        db_session.add(admin_user)
        db_session.commit()
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Unable to register school'}), 500

    return jsonify({
        'status': 'success',
        'school': {
            'id': new_school.id,
            'name': new_school.name,
            'slug': new_school.slug,
        },
        'admin_user': {
            'username': admin_user.username,
            'display_name': admin_user.display_name,
        }
    }), 201


@recorder_bp.route('/interschool/overview', methods=['GET'])
def get_interschool_overview():
    if not require_auth():
        return jsonify({'error': 'Authentication required'}), 401

    if not is_interschool_user():
        return jsonify({'error': 'Interschool access required'}), 403

    schools = (
        db_session.query(School)
        .order_by(func.lower(School.name).asc())
        .all()
    )

    user_counts = dict(
        db_session.query(User.school_id, func.count(User.id))
        .group_by(User.school_id)
        .all()
    )

    invites = (
        db_session.query(SchoolInviteCode)
        .order_by(SchoolInviteCode.issued_at.desc())
        .all()
    )

    user_ids = {
        ident
        for entry in invites
        for ident in [entry.issued_by, entry.used_by]
        if ident
    }

    user_lookup = {}
    if user_ids:
        user_lookup = {
            user.id: user
            for user in db_session.query(User).filter(User.id.in_(user_ids)).all()
        }

    return jsonify({
        'status': 'success',
        'schools': [_serialize_school_model(school, user_counts=user_counts) for school in schools],
        'invites': [_serialize_invite_model(invite, user_lookup) for invite in invites],
    }), 200


__all__ = []
