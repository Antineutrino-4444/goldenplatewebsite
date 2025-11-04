from flask import session

from .users import get_user_by_id, get_user_by_username, serialize_user_model


def get_current_user():
    """Get current logged in user."""
    user_uuid = session.get('user_uuid')
    if user_uuid:
        user = get_user_by_id(user_uuid)
        if user:
            return serialize_user_model(user)

    username = session.get('username') or session.get('user_id')
    if not username:
        return None
    user = get_user_by_username(username)
    return serialize_user_model(user)


def require_auth():
    """Check if user is authenticated."""
    user_uuid = session.get('user_uuid')
    if user_uuid and get_user_by_id(user_uuid):
        return True
    username = session.get('username')
    if username and get_user_by_username(username):
        return True
    return False


def require_auth_or_guest():
    """Check if user is authenticated or is a guest."""
    return require_auth() or session.get('guest_access', False)


def is_guest():
    """Check if current user is a guest."""
    return session.get('guest_access', False) and 'user_id' not in session


def require_admin():
    """Check if user is admin or super admin."""
    user = get_current_user()
    return user and user['role'] in ['admin', 'superadmin']


def require_superadmin():
    """Check if user is super admin."""
    user = get_current_user()
    return user and user['role'] == 'superadmin'


def is_interschool_user():
    user = get_current_user()
    return user and user['role'] == 'inter_school'


__all__ = [
    'get_current_user',
    'is_guest',
    'is_interschool_user',
    'require_admin',
    'require_auth',
    'require_auth_or_guest',
    'require_superadmin',
]
