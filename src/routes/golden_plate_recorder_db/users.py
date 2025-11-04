import uuid

from sqlalchemy.orm import joinedload

from .db import (
    DEFAULT_SCHOOL_ID,
    INTERSCHOOL_SCHOOL_ID,
    School,
    SchoolInviteCode,
    User,
    UserInviteCode,
    _now_utc,
    db_session,
)

DEFAULT_SUPERADMIN = {
    'username': 'antineutrino',
    'password': 'b-decay',
    'role': 'superadmin',
    'display_name': 'Lead Admin',
    'status': 'active',
    'school_id': DEFAULT_SCHOOL_ID,
}

DEFAULT_INTERSCHOOL_USER = {
    'username': 'inter-school-admin',
    'password': 'bridge-control',
    'role': 'inter_school',
    'display_name': 'Inter-School Controller',
    'status': 'active',
    'school_id': INTERSCHOOL_SCHOOL_ID,
}


def _resolve_school_id(school_id=None):
    if school_id:
        return school_id
    return DEFAULT_SCHOOL_ID


def get_school_by_id(school_id):
    if not school_id:
        return None
    return db_session.query(School).filter(School.id == school_id).first()


def get_user_by_id(user_id):
    if not user_id:
        return None
    return db_session.query(User).options(joinedload(User.school)).filter(User.id == user_id).first()


def serialize_school(school):
    if not school:
        return None
    return {
        'id': school.id,
        'name': school.name,
        'slug': school.slug,
        'status': school.status,
        'created_at': school.created_at.isoformat() if school.created_at else None,
        'updated_at': school.updated_at.isoformat() if school.updated_at else None,
    }


def serialize_user_model(user):
    if not user:
        return None
    school = getattr(user, 'school', None)
    return {
        'id': user.id,
        'username': user.username,
        'name': user.display_name,
        'role': user.role,
        'status': user.status,
        'school_id': user.school_id,
        'school': serialize_school(school) if school else None,
        'last_login_at': user.last_login_at.isoformat() if user.last_login_at else None,
    }


def get_user_by_username(username, *, school_id=None):
    if not username:
        return None
    query = db_session.query(User)
    if school_id:
        query = query.filter(User.school_id == school_id, User.username == username)
    else:
        query = query.filter(User.username == username)
    return query.options(joinedload(User.school)).first()


def list_all_users(*, school_id=None):
    query = db_session.query(User).options(joinedload(User.school)).order_by(User.username.asc())
    if school_id:
        query = query.filter(User.school_id == school_id)
    users = query.all()
    return [serialize_user_model(user) for user in users]


def create_user_record(username, password, display_name, role='user', status='active', *, school_id=None):
    school_id = _resolve_school_id(school_id)
    existing = get_user_by_username(username, school_id=school_id)
    if existing:
        return existing
    user = User(
        id=str(uuid.uuid4()),
        school_id=school_id,
        username=username,
        password_hash=password,
        display_name=display_name,
        role=role,
        status=status,
        created_at=_now_utc(),
        updated_at=_now_utc(),
    )
    try:
        db_session.add(user)
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    return user


def update_user_credentials(user, *, password=None, display_name=None, role=None, status=None, school_id=None, auto_commit=True):
    updated = False
    if password is not None and user.password_hash != password:
        user.password_hash = password
        updated = True
    if display_name is not None and user.display_name != display_name:
        user.display_name = display_name
        updated = True
    if role is not None and user.role != role:
        user.role = role
        updated = True
    if status is not None and user.status != status:
        user.status = status
        updated = True
    if school_id is not None and user.school_id != school_id:
        user.school_id = school_id
        updated = True
    if updated:
        user.updated_at = _now_utc()
        if auto_commit:
            try:
                db_session.commit()
            except Exception:
                db_session.rollback()
                raise
    return user


def ensure_default_superadmin():
    user = get_user_by_username(DEFAULT_SUPERADMIN['username'], school_id=DEFAULT_SUPERADMIN['school_id'])
    if not user:
        return create_user_record(
            DEFAULT_SUPERADMIN['username'],
            DEFAULT_SUPERADMIN['password'],
            DEFAULT_SUPERADMIN['display_name'],
            role=DEFAULT_SUPERADMIN['role'],
            status=DEFAULT_SUPERADMIN['status'],
            school_id=DEFAULT_SUPERADMIN['school_id'],
        )
    return update_user_credentials(
        user,
        password=DEFAULT_SUPERADMIN['password'],
        display_name=DEFAULT_SUPERADMIN['display_name'],
        role=DEFAULT_SUPERADMIN['role'],
        status=DEFAULT_SUPERADMIN['status'],
        school_id=DEFAULT_SUPERADMIN['school_id'],
    )


def ensure_interschool_user():
    user = get_user_by_username(
        DEFAULT_INTERSCHOOL_USER['username'],
        school_id=DEFAULT_INTERSCHOOL_USER['school_id'],
    )
    if not user:
        return create_user_record(
            DEFAULT_INTERSCHOOL_USER['username'],
            DEFAULT_INTERSCHOOL_USER['password'],
            DEFAULT_INTERSCHOOL_USER['display_name'],
            role=DEFAULT_INTERSCHOOL_USER['role'],
            status=DEFAULT_INTERSCHOOL_USER['status'],
            school_id=DEFAULT_INTERSCHOOL_USER['school_id'],
        )
    return update_user_credentials(
        user,
        password=DEFAULT_INTERSCHOOL_USER['password'],
        display_name=DEFAULT_INTERSCHOOL_USER['display_name'],
        role=DEFAULT_INTERSCHOOL_USER['role'],
        status=DEFAULT_INTERSCHOOL_USER['status'],
        school_id=DEFAULT_INTERSCHOOL_USER['school_id'],
    )


def migrate_legacy_users(legacy_users):
    if not isinstance(legacy_users, dict):
        return
    
    try:
        for username, payload in legacy_users.items():
            if not isinstance(payload, dict):
                continue
            print(f"Migrating legacy user: {username}")
            password = payload.get('password') or DEFAULT_SUPERADMIN['password']
            role = payload.get('role', 'user')
            name = payload.get('name') or username
            status = payload.get('status', 'active')
            school_id = payload.get('school_id') or DEFAULT_SCHOOL_ID
            user = get_user_by_username(username, school_id=school_id)
            if user:
                update_user_credentials(
                    user,
                    password=password,
                    display_name=name,
                    role=role,
                    status=status,
                    school_id=school_id,
                    auto_commit=False,  # Don't commit yet
                )
            else:
                user = User(
                    id=str(uuid.uuid4()),
                    school_id=school_id,
                    username=username,
                    password_hash=password,
                    display_name=name,
                    role=role,
                    status=status,
                    created_at=_now_utc(),
                    updated_at=_now_utc(),
                )
                db_session.add(user)
        
        # Commit all changes at once
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise


def create_invite_code_record(owner_user, issued_by_user, role='user', *, school_id=None):
    code = str(uuid.uuid4())
    owner = owner_user or issued_by_user
    school_id = _resolve_school_id(school_id or (owner.school_id if owner else None))
    invite = UserInviteCode(
        id=str(uuid.uuid4()),
        school_id=school_id,
        user_id=owner.id,
        code=code,
        issued_by=issued_by_user.id,
        issued_at=_now_utc(),
        status='unused',
        role=role,
    )
    try:
        db_session.add(invite)
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    return invite


def get_invite_code_record(code):
    if not code:
        return None
    return db_session.query(UserInviteCode).filter(UserInviteCode.code == code).first()


def create_school_invite_code_record(issued_by_user, *, school_id=None):
    if not issued_by_user:
        raise ValueError('issued_by_user is required')
    school_id = school_id or str(uuid.uuid4())
    code = str(uuid.uuid4())
    invite = SchoolInviteCode(
        id=str(uuid.uuid4()),
        school_id=school_id,
        code=code,
        issued_by=issued_by_user.id,
        issued_at=_now_utc(),
        status='unused',
    )
    try:
        db_session.add(invite)
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    return invite


def get_school_invite_code_record(code):
    if not code:
        return None
    return db_session.query(SchoolInviteCode).filter(SchoolInviteCode.code == code).first()


def mark_school_invite_code_used(invite, used_by_user=None):
    if not invite:
        return
    invite.status = 'used'
    invite.used_by = used_by_user.id if used_by_user else None
    invite.used_at = _now_utc()
    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise


def mark_invite_code_used(invite, used_by_user):
    invite.status = 'used'
    invite.user_id = used_by_user.id
    invite.used_by = used_by_user.id
    invite.used_at = _now_utc()
    invite.school_id = used_by_user.school_id
    invite.updated_at = _now_utc()
    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise


def migrate_legacy_invite_codes(legacy_invites, default_owner):
    if not isinstance(legacy_invites, dict):
        return
    
    try:
        for code, payload in legacy_invites.items():
            if get_invite_code_record(code):
                continue
            role = 'user'
            status = 'unused'
            issued_by_username = DEFAULT_SUPERADMIN['username']
            used_by_username = None
            if isinstance(payload, dict):
                role = payload.get('role', 'user')
                status = 'used' if payload.get('used') else payload.get('status', 'unused')
                issued_by_username = payload.get('issued_by', DEFAULT_SUPERADMIN['username'])
                used_by_username = payload.get('used_by')
            issued_by_user = get_user_by_username(issued_by_username) or default_owner
            invite = UserInviteCode(
                id=str(uuid.uuid4()),
                    school_id=default_owner.school_id,
                user_id=default_owner.id,
                code=code,
                issued_by=issued_by_user.id,
                issued_at=_now_utc(),
                status=status,
                role=role,
            )
            if status == 'used' and used_by_username:
                used_user = get_user_by_username(used_by_username)
                if used_user:
                    invite.used_by = used_user.id
                    invite.used_at = _now_utc()
            db_session.add(invite)
        
        # Commit all invite codes at once
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise


def reset_user_store():
    default_user = ensure_default_superadmin()
    ensure_interschool_user()
    try:
        db_session.query(SchoolInviteCode).delete()
        db_session.query(School).filter(School.id.notin_({
            DEFAULT_SCHOOL_ID,
            INTERSCHOOL_SCHOOL_ID,
        })).delete(synchronize_session=False)
        db_session.query(UserInviteCode).filter(UserInviteCode.school_id == default_user.school_id).delete()
        db_session.query(User).filter(User.username.notin_({
            default_user.username,
            DEFAULT_INTERSCHOOL_USER['username'],
        })).delete(synchronize_session=False)
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    update_user_credentials(
        default_user,
        password=DEFAULT_SUPERADMIN['password'],
        display_name=DEFAULT_SUPERADMIN['display_name'],
        role=DEFAULT_SUPERADMIN['role'],
        status=DEFAULT_SUPERADMIN['status'],
        school_id=DEFAULT_SUPERADMIN['school_id'],
    )


__all__ = [
    'DEFAULT_SUPERADMIN',
    'DEFAULT_INTERSCHOOL_USER',
    'create_invite_code_record',
    'create_school_invite_code_record',
    'create_user_record',
    'ensure_default_superadmin',
    'ensure_interschool_user',
    'get_user_by_id',
    'get_invite_code_record',
    'get_school_invite_code_record',
    'get_user_by_username',
    'list_all_users',
    'mark_invite_code_used',
    'mark_school_invite_code_used',
    'migrate_legacy_invite_codes',
    'migrate_legacy_users',
    'reset_user_store',
    'serialize_school',
    'serialize_user_model',
    'update_user_credentials',
]
