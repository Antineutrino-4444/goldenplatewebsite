import hashlib
import hmac

from flask import current_app, session

from .users import get_user_by_id, get_user_by_username, serialize_user_model
from .email_policy import account_requires_email


def password_session_token(user):
    """Bind the signed session to the stored password without exposing its hash."""
    return hmac.new(
        current_app.secret_key.encode(),
        user.password_hash.encode(),
        hashlib.sha256,
    ).hexdigest()


def get_current_user():
    """Get current logged in user."""
    user_uuid = session.get('user_uuid')
    if user_uuid:
        user = get_user_by_id(user_uuid)
    else:
        username = session.get('username') or session.get('user_id')
        user = get_user_by_username(username) if username else None
    if not user:
        return None
    token = session.get('password_token')
    if (
        user.status != 'active'
        or user.is_record_actor
        or not isinstance(token, str)
        or not hmac.compare_digest(token, password_session_token(user))
    ):
        session.clear()
        return None
    from src.services.account_lifecycle import enforce_inactivity_for_login
    from .db import _now_utc, db_session
    if enforce_inactivity_for_login(db_session, user, _now_utc()):
        db_session.commit()
        session.clear()
        return None
    result = serialize_user_model(user)
    result['email_required'] = account_requires_email(user, session.get('authenticated_at', ''))
    result['signup_email_confirmation'] = bool(
        user.role == 'superadmin' and user.email and user.email_verified_at
        and session.get('signup_email_confirmation')
    )
    return result


def require_auth():
    """Check if user is authenticated."""
    return get_current_user() is not None


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
