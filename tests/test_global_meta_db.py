import tempfile
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from src.routes.golden_plate_recorder_db.db import User, db_session
from src.routes.golden_plate_recorder_db.global_meta_db import (
    GlobalUser,
    School,
    UserDirectory,
    global_meta_session,
)
from src.routes.golden_plate_recorder_db.users import (
    create_user_record,
    migrate_superadmins_to_global_users,
)


def test_user_directory_enforces_school_username_uniqueness():
    meta_session = global_meta_session

    school = School(code='uniqueschool', name='Unique School', address='123 Test', db_path='data/schools/unique.db')
    meta_session.add(school)
    meta_session.commit()

    entry = UserDirectory(
        school_id=school.id,
        username='duplicate',
        password_hash_ref='hash-a',
    )
    meta_session.add(entry)
    meta_session.commit()

    meta_session.add(
        UserDirectory(
            school_id=school.id,
            username='duplicate',
            password_hash_ref='hash-b',
        )
    )

    with pytest.raises(IntegrityError):
        meta_session.commit()

    meta_session.rollback()
    meta_session.delete(entry)
    meta_session.delete(school)
    meta_session.commit()


def test_seeded_global_user_exists():
    meta_session = global_meta_session
    user = meta_session.query(GlobalUser).filter(GlobalUser.username == 'antineutrino').one()
    assert user.display_name == 'b-decay'
    assert user.is_active is True


def test_school_db_path_can_reference_uninitialized_file():
    meta_session = global_meta_session

    with tempfile.TemporaryDirectory() as tmp_dir:
        desired_path = Path(tmp_dir) / 'not_created_yet.db'
        school = School(
            code='smoketest',
            name='Smoke Test School',
            address='456 Example',
            db_path=str(desired_path),
        )
        meta_session.add(school)
        meta_session.commit()

        assert not desired_path.exists()

        meta_session.delete(school)
        meta_session.commit()


def test_migrated_superadmins_populate_global_users():
    # Ensure the default superadmin exists locally
    create_user_record('temporary-super', 'temp-pass', 'Temporary Super', role='superadmin')

    migrate_superadmins_to_global_users()

    meta_session = global_meta_session
    global_user = (
        meta_session.query(GlobalUser)
        .filter(GlobalUser.username == 'temporary-super')
        .one()
    )
    assert global_user.display_name == 'Temporary Super'
    assert global_user.is_active is True

    # Clean up the temporary user records to avoid test leakage
    db_user = db_session.query(User).filter(User.username == 'temporary-super').one()
    db_session.delete(db_user)
    db_session.commit()

    meta_session.delete(global_user)
    meta_session.commit()
