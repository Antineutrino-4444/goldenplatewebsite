from flask import session

from .global_db import GlobalUser, global_db_session
from .users import get_user_by_username, serialize_user_model


def get_current_user():
    """Get current logged in user."""
    username = session.get('user_id')
    if not username:
        return None
    if session.get('global_admin_id'):
        global_user = global_db_session.query(GlobalUser).filter(GlobalUser.username == username).first()
        if not global_user:
            return None
        return {
            'id': global_user.id,
            'username': global_user.username,
            'name': global_user.display_name,
            'role': 'global_admin',
            'status': global_user.status,
        }
    user = get_user_by_username(username)
    return serialize_user_model(user)


def require_auth():
    """Check if user is authenticated."""
    if session.get('global_admin_id'):
        return True
    username = session.get('user_id')
    if not username:
        return False
    return get_user_by_username(username) is not None


def require_auth_or_guest():
    """Check if user is authenticated or is a guest."""
    return require_auth() or session.get('guest_access', False)


def is_guest():
    """Check if current user is a guest."""
    return session.get('guest_access', False) and 'user_id' not in session


def require_admin():
    """Check if user is admin or super admin."""
    user = get_current_user()
    if not user:
        return False
    if user['role'] == 'global_admin':
        return True
    return user['role'] in ['admin', 'superadmin', 'school_admin', 'school_super_admin']


def require_superadmin():
    """Check if user is super admin."""
    user = get_current_user()
    if not user:
        return False
    if user['role'] == 'global_admin':
        return True
    return user['role'] in ['superadmin', 'school_super_admin']


__all__ = [
    'get_current_user',
    'is_guest',
    'require_admin',
    'require_auth',
    'require_auth_or_guest',
    'require_superadmin',
]
