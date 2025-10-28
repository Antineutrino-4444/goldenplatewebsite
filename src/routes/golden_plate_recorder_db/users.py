import uuid

from .db import User, UserInviteCode, _now_utc, db_session
from .global_meta_db import seed_default_global_user, sync_superadmins_to_global_users

DEFAULT_SUPERADMIN = {
    'username': 'antineutrino',
    'password': 'b-decay',
    'role': 'superadmin',
    'display_name': 'Lead Admin',
    'status': 'active',
}


def serialize_user_model(user):
    if not user:
        return None
    return {
        'id': user.id,
        'username': user.username,
        'name': user.display_name,
        'role': user.role,
        'status': user.status,
        'last_login_at': user.last_login_at.isoformat() if user.last_login_at else None,
    }


def get_user_by_username(username):
    if not username:
        return None
    return db_session.query(User).filter(User.username == username).first()


def list_all_users():
    users = db_session.query(User).order_by(User.username.asc()).all()
    return [serialize_user_model(user) for user in users]


def create_user_record(username, password, display_name, role='user', status='active'):
    existing = get_user_by_username(username)
    if existing:
        return existing
    user = User(
        id=str(uuid.uuid4()),
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


def update_user_credentials(user, *, password=None, display_name=None, role=None, status=None, auto_commit=True):
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
    seed_default_global_user()

    user = get_user_by_username(DEFAULT_SUPERADMIN['username'])
    if not user:
        user = create_user_record(
            DEFAULT_SUPERADMIN['username'],
            DEFAULT_SUPERADMIN['password'],
            DEFAULT_SUPERADMIN['display_name'],
            role=DEFAULT_SUPERADMIN['role'],
            status=DEFAULT_SUPERADMIN['status'],
        )
    else:
        user = update_user_credentials(
            user,
            password=DEFAULT_SUPERADMIN['password'],
            display_name=DEFAULT_SUPERADMIN['display_name'],
            role=DEFAULT_SUPERADMIN['role'],
            status=DEFAULT_SUPERADMIN['status'],
        )

    migrate_superadmins_to_global_users()
    return user


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
            user = get_user_by_username(username)
            if user:
                update_user_credentials(
                    user,
                    password=password,
                    display_name=name,
                    role=role,
                    status=status,
                    auto_commit=False,  # Don't commit yet
                )
            else:
                user = User(
                    id=str(uuid.uuid4()),
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


def migrate_superadmins_to_global_users():
    superadmins = db_session.query(User).filter(User.role == 'superadmin').all()
    sync_superadmins_to_global_users(superadmins)


def create_invite_code_record(owner_user, issued_by_user, role='user'):
    code = str(uuid.uuid4())
    owner = owner_user or issued_by_user
    invite = UserInviteCode(
        id=str(uuid.uuid4()),
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


def mark_invite_code_used(invite, used_by_user):
    invite.status = 'used'
    invite.user_id = used_by_user.id
    invite.used_by = used_by_user.id
    invite.used_at = _now_utc()
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
    try:
        db_session.query(UserInviteCode).delete()
        db_session.query(User).filter(User.username != default_user.username).delete()
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
    )


__all__ = [
    'DEFAULT_SUPERADMIN',
    'create_invite_code_record',
    'create_user_record',
    'ensure_default_superadmin',
    'get_invite_code_record',
    'get_user_by_username',
    'list_all_users',
    'mark_invite_code_used',
    'migrate_legacy_invite_codes',
    'migrate_legacy_users',
    'migrate_superadmins_to_global_users',
    'reset_user_store',
    'serialize_user_model',
    'update_user_credentials',
]
