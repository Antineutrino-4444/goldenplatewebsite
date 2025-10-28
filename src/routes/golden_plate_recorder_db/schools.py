import os
import os
import shutil
import uuid
from typing import Dict, List, Optional

from sqlalchemy.exc import IntegrityError

from .db import db_session, reset_current_school_id, set_current_school_id, User
from .global_db import (
    AuditLog,
    FeatureToggle,
    GlobalUser,
    School,
    UserDirectory,
    global_db_session,
    init_global_metadata,
)
LEGACY_DATABASE_PATH = os.environ.get('DATABASE_URL', 'sqlite:///data/golden_plate_recorder.db').replace('sqlite:///', '', 1)
DEFAULT_SCHOOL_CODE = 'SAC1899'
DEFAULT_SCHOOL_NAME = "St. Andrew's College"
DEFAULT_SCHOOL_DB = f'{DEFAULT_SCHOOL_CODE}.db'


FEATURE_FLAGS = {
    'student_directory': 'Student Directory Search',
    'faculty_module': 'Faculty Management Module',
    'ticket_draws': 'Ticket Draw Center',
}


def _now():
    from .db import _now_utc

    return _now_utc()


def bootstrap_global_state() -> School:
    """Initialize the global metadata store and ensure the legacy school exists."""
    init_global_metadata()
    school = (
        global_db_session.query(School)
        .filter(School.code == DEFAULT_SCHOOL_CODE, School.deleted_at.is_(None))
        .first()
    )
    if school:
        return school

    db_path = os.path.join('data', 'schools', DEFAULT_SCHOOL_DB)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    if os.path.exists(LEGACY_DATABASE_PATH) and not os.path.exists(db_path):
        shutil.copy2(LEGACY_DATABASE_PATH, db_path)

    school = School(
        id=str(uuid.uuid4()),
        code=DEFAULT_SCHOOL_CODE,
        name=DEFAULT_SCHOOL_NAME,
        address='sac.on.ca',
        public_contact='',
        db_path=db_path,
        guest_access_enabled=True,
        created_at=_now(),
        updated_at=_now(),
    )
    global_db_session.add(school)
    global_db_session.commit()

    for feature in FEATURE_FLAGS:
        toggle = FeatureToggle(
            id=str(uuid.uuid4()),
            school_id=school.id,
            feature=feature,
            enabled=True,
            updated_at=_now(),
        )
        global_db_session.add(toggle)
    global_db_session.commit()

    return school


def ensure_global_admins_from_school(school: School) -> None:
    """Ensure legacy superadmins become global admins."""
    token = set_current_school_id(school.id)
    try:
        super_admins = (
            db_session.query(User)
            .filter(User.role == 'superadmin', User.status == 'active')
            .all()
        )
        for user in super_admins:
            ensure_default_superadmin_global_user(user)
    finally:
        reset_current_school_id(token)


def ensure_default_superadmin_global_user(user: Optional[User]) -> Optional[GlobalUser]:
    if user is None:
        return None

    existing = (
        global_db_session.query(GlobalUser)
        .filter(GlobalUser.username == user.username)
        .first()
    )
    if existing:
        changed = False
        if existing.password_hash != user.password_hash:
            existing.password_hash = user.password_hash
            changed = True
        if existing.display_name != user.display_name:
            existing.display_name = user.display_name
            changed = True
        if existing.status != (user.status or 'active'):
            existing.status = user.status or 'active'
            changed = True
        if changed:
            existing.updated_at = _now()
            global_db_session.add(existing)
            global_db_session.commit()
        return existing

    global_admin = GlobalUser(
        username=user.username,
        password_hash=user.password_hash,
        display_name=user.display_name,
        status=user.status or 'active',
        created_at=_now(),
        updated_at=_now(),
    )
    global_db_session.add(global_admin)
    global_db_session.commit()
    return global_admin


def register_user_directory_entry(
    school_id: str,
    username: str,
    password_hash: str,
    display_name: str,
    role: str,
    status: str,
    user_ref: Optional[str] = None,
) -> UserDirectory:
    entry = UserDirectory(
        school_id=school_id,
        username=username,
        password_hash=password_hash,
        display_name=display_name,
        role=role,
        status=status,
        user_ref=user_ref,
        created_at=_now(),
        updated_at=_now(),
    )
    global_db_session.add(entry)
    try:
        global_db_session.commit()
    except IntegrityError:
        global_db_session.rollback()
        raise
    return entry


def sync_directory_entry(
    entry: UserDirectory,
    *,
    password_hash: Optional[str] = None,
    display_name: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
) -> None:
    changed = False
    if password_hash is not None and entry.password_hash != password_hash:
        entry.password_hash = password_hash
        changed = True
    if display_name is not None and entry.display_name != display_name:
        entry.display_name = display_name
        changed = True
    if role is not None and entry.role != role:
        entry.role = role
        changed = True
    if status is not None and entry.status != status:
        entry.status = status
        changed = True
    if changed:
        entry.updated_at = _now()
        global_db_session.add(entry)
        global_db_session.commit()


def get_directory_users_by_username(username: str) -> List[UserDirectory]:
    return (
        global_db_session.query(UserDirectory)
        .filter(UserDirectory.username == username)
        .all()
    )


def get_directory_entry(school_id: str, username: str) -> Optional[UserDirectory]:
    return (
        global_db_session.query(UserDirectory)
        .filter(
            UserDirectory.school_id == school_id,
            UserDirectory.username == username,
        )
        .first()
    )


def locate_school_by_code(code: str) -> Optional[School]:
    return (
        global_db_session.query(School)
        .filter(School.code == code, School.deleted_at.is_(None))
        .first()
    )


def log_audit_event(
    *,
    school_id: Optional[str],
    actor_id: Optional[str],
    actor_scope: str,
    action: str,
    target: Optional[str] = None,
    payload: Optional[str] = None,
) -> None:
    event = AuditLog(
        school_id=school_id,
        actor_id=actor_id,
        actor_scope=actor_scope,
        action=action,
        target=target,
        payload=payload,
        created_at=_now(),
    )
    global_db_session.add(event)
    global_db_session.commit()


def list_feature_toggles(school_id: str) -> Dict[str, bool]:
    toggles = (
        global_db_session.query(FeatureToggle)
        .filter(FeatureToggle.school_id == school_id)
        .all()
    )
    return {toggle.feature: bool(toggle.enabled) for toggle in toggles}


def set_feature_toggle(school_id: str, feature: str, enabled: bool) -> FeatureToggle:
    toggle = (
        global_db_session.query(FeatureToggle)
        .filter(FeatureToggle.school_id == school_id, FeatureToggle.feature == feature)
        .first()
    )
    if toggle:
        toggle.enabled = bool(enabled)
        toggle.updated_at = _now()
    else:
        toggle = FeatureToggle(
            id=str(uuid.uuid4()),
            school_id=school_id,
            feature=feature,
            enabled=bool(enabled),
            updated_at=_now(),
        )
    global_db_session.add(toggle)
    global_db_session.commit()
    return toggle


__all__ = [
    'FEATURE_FLAGS',
    'bootstrap_global_state',
    'ensure_global_admins_from_school',
    'get_directory_entry',
    'get_directory_users_by_username',
    'list_feature_toggles',
    'locate_school_by_code',
    'log_audit_event',
    'register_user_directory_entry',
    'set_feature_toggle',
    'sync_directory_entry',
]
