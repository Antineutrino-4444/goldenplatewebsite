import os
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path


def _remove_with_retries(path: Path) -> None:
    for _ in range(5):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError:
            time.sleep(0.1)


def test_empty_sqlite_database_bootstraps_successfully():
    project_root = Path(__file__).resolve().parent.parent
    temp_dir = project_root / '.tmp-bootstrap-tests'
    temp_dir.mkdir(exist_ok=True)
    db_path = temp_dir / f'fresh-local-{uuid.uuid4().hex}.db'
    db_path.touch()

    env = os.environ.copy()
    env['DATABASE_URL'] = f"sqlite:///{db_path.as_posix()}"

    try:
        result = subprocess.run(
            [
                sys.executable,
                '-c',
                (
                    "import sys; "
                    f"sys.path.insert(0, {str(project_root)!r}); "
                    "import src.routes.golden_plate_recorder_db.db; "
                    "from src.routes.golden_plate_recorder_db.users import ensure_default_superadmin; "
                    "ensure_default_superadmin()"
                ),
            ],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr

        with sqlite3.connect(db_path) as connection:
            table_names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            superadmin_row = connection.execute(
                "SELECT password_hash FROM users WHERE username = 'greenguys'"
            ).fetchone()

        assert 'user_invite_codes' in table_names
        assert 'schools' in table_names
        assert superadmin_row is not None
        assert superadmin_row[0].startswith(('pbkdf2:', 'scrypt:'))
    finally:
        _remove_with_retries(db_path)
        for suffix in ('-journal', '-wal', '-shm'):
            _remove_with_retries(db_path.with_name(db_path.name + suffix))
        try:
            temp_dir.rmdir()
        except OSError:
            pass
