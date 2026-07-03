import os
import shutil
import sys
import uuid
from pathlib import Path

import pytest

# Ensure the application package can be imported
sys.path.insert(0, os.path.abspath('.'))


def _cleanup_sqlite_sidecars(db_path: Path) -> None:
    """Remove SQLite sidecar files so snapshots stay consistent."""
    for suffix in ('-journal', '-wal', '-shm'):
        sidecar = db_path.with_name(db_path.name + suffix)
        if sidecar.exists():
            sidecar.unlink()


def _make_workspace_temp_dir(root: Path, prefix: str) -> Path:
    for _ in range(10):
        candidate = root / f'{prefix}{uuid.uuid4().hex}'
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError('Unable to create workspace temporary directory')


def _prepare_test_database():
    project_root = Path(__file__).resolve().parent.parent
    db_path = project_root / 'data' / 'golden_plate_recorder.db'
    backup_source = project_root / 'data' / 'golden_plate_recorder.db.backup'

    if not db_path.exists():
        if backup_source.exists():
            db_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_source, db_path)
        else:
            return None

    _cleanup_sqlite_sidecars(db_path)

    temp_root = project_root / '.tmp'
    temp_root.mkdir(exist_ok=True)

    backup_dir = _make_workspace_temp_dir(temp_root, 'goldenplate-db-backup-')
    backup_path = backup_dir / db_path.name
    try:
        shutil.copy2(db_path, backup_path)
    except OSError as exc:  # pragma: no cover - defensive guard
        raise RuntimeError(
            'Unable to snapshot the database for testing. '
            'Close any application that keeps the SQLite file open and retry.'
        ) from exc

    test_dir = _make_workspace_temp_dir(temp_root, 'goldenplate-pytest-db-')
    test_db_path = test_dir / db_path.name
    test_map_db_path = test_dir / 'golden_plate_map.db'
    shutil.copy2(backup_path, test_db_path)

    previous_database_url = os.environ.get('DATABASE_URL')
    previous_map_database_url = os.environ.get('MAP_DATABASE_URL')
    os.environ['DATABASE_URL'] = f'sqlite:///{test_db_path.as_posix()}'
    os.environ['MAP_DATABASE_URL'] = f'sqlite:///{test_map_db_path.as_posix()}'

    def _finalize() -> None:
        try:
            from src.routes.golden_plate_recorder_db import db as db_module
        except Exception:  # pragma: no cover - best effort cleanup
            db_module = None
        else:
            db_module.db_session.remove()
            db_module.engine.dispose()

        try:
            from src.routes.golden_plate_recorder_db import map_db as map_db_module
        except Exception:  # pragma: no cover - best effort cleanup
            map_db_module = None
        else:
            map_db_module.map_db_session.remove()
            map_db_module.map_engine.dispose()

        if previous_database_url is None:
            os.environ.pop('DATABASE_URL', None)
        else:
            os.environ['DATABASE_URL'] = previous_database_url

        if previous_map_database_url is None:
            os.environ.pop('MAP_DATABASE_URL', None)
        else:
            os.environ['MAP_DATABASE_URL'] = previous_map_database_url

        if backup_path.exists():
            db_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_path, db_path)
        _cleanup_sqlite_sidecars(db_path)
        _cleanup_sqlite_sidecars(test_db_path)
        _cleanup_sqlite_sidecars(test_map_db_path)

        shutil.rmtree(test_dir, ignore_errors=True)
        shutil.rmtree(backup_dir, ignore_errors=True)

    return _finalize


_DB_CLEANUP_CALLBACK = _prepare_test_database()

from src.main import app

TEST_SUPERADMIN_USERNAME = 'antineutrino'
TEST_SUPERADMIN_PASSWORD = 'pytest-superadmin-password'
TEST_SUPERADMIN_PASSWORD_HASH = 'pbkdf2:sha256:1000000$pytestsuperadminseed2026$5f5f27b9cdbfe89a6094f76b14e9cce3a4b557f3bb5fd70606630d7773f5f703'
TEST_INTERSCHOOL_USERNAME = 'inter-school-admin'
TEST_INTERSCHOOL_PASSWORD = 'pytest-interschool-password'
TEST_INTERSCHOOL_PASSWORD_HASH = 'pbkdf2:sha256:1000000$pytestinterschoolseed2026$0d64cd3efe24867d8b049404cfe1966a6261bd10c7493049d9697f911c289b90'


def ensure_test_account_passwords():
    from src.routes.golden_plate_recorder_db.users import (
        ensure_default_superadmin,
        ensure_interschool_user,
        update_user_credentials,
    )

    default_user = ensure_default_superadmin()
    interschool_user = ensure_interschool_user()
    update_user_credentials(default_user, password=TEST_SUPERADMIN_PASSWORD_HASH, password_is_hash=True)
    update_user_credentials(interschool_user, password=TEST_INTERSCHOOL_PASSWORD_HASH, password_is_hash=True)


def _clear_ticket_tables():
    """Remove ticket-related rows so tests start from a clean slate."""
    # Import lazily to avoid circular imports during module load.
    from src.routes.golden_plate_recorder_db.db import (
        DraftPool,
        Session,
        SessionDrawEvent,
        SessionRecord,
        SessionTicketEvent,
        db_session,
    )

    # Delete in dependency order to avoid FK constraint issues.
    for model in (SessionTicketEvent, SessionDrawEvent, SessionRecord, DraftPool):
        db_session.query(model).delete()

    db_session.query(Session).update({
        Session.draw_number: 1,
        Session.winner_student_id: None,
        Session.method: None,
        Session.finalized: 0,
        Session.finalized_by: None,
        Session.finalized_at: None,
        Session.tickets_at_selection: None,
        Session.probability_at_selection: None,
        Session.eligible_pool_size: None,
        Session.override_applied: 0,
    })

    db_session.commit()


@pytest.fixture(autouse=True)
def _reset_ticket_state():
    """Ensure each test sees an empty ticket state."""
    _clear_ticket_tables()
    try:
        yield
    finally:
        _clear_ticket_tables()


@pytest.fixture(scope='session', autouse=True)
def _restore_database_after_tests():
    """Ensure the production database is restored after the pytest session."""
    try:
        yield
    finally:
        if _DB_CLEANUP_CALLBACK:
            _DB_CLEANUP_CALLBACK()


@pytest.fixture
def client():
    """Flask test client"""
    with app.test_client() as client:
        yield client


@pytest.fixture
def login(client):
    """Helper to log in a user"""
    def _login(username=TEST_SUPERADMIN_USERNAME, password=None):
        ensure_test_account_passwords()
        if password is None:
            password = (
                TEST_INTERSCHOOL_PASSWORD
                if username == TEST_INTERSCHOOL_USERNAME
                else TEST_SUPERADMIN_PASSWORD
            )
        return client.post('/api/auth/login', json={'username': username, 'password': password})

    return _login
