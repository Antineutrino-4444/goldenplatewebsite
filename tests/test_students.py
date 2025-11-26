import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from src.routes.golden_plate_recorder_db.db import (
    DEFAULT_SCHOOL_ID,
    School,
    Student,
    db_session,
)


def test_student_identifier_unique_within_school():
    identifier = f"dup-{uuid.uuid4().hex[:8]}"
    try:
        first_student = Student(
            id=str(uuid.uuid4()),
            school_id=DEFAULT_SCHOOL_ID,
            student_identifier=identifier,
            preferred_name='Alpha',
            last_name='Tester',
        )
        db_session.add(first_student)
        db_session.flush()

        duplicate_student = Student(
            id=str(uuid.uuid4()),
            school_id=DEFAULT_SCHOOL_ID,
            student_identifier=identifier,
            preferred_name='Beta',
            last_name='Tester',
        )
        db_session.add(duplicate_student)

        with pytest.raises(IntegrityError):
            db_session.flush()
    finally:
        db_session.rollback()


def test_student_identifier_allowed_for_different_schools():
    identifier = f"shared-{uuid.uuid4().hex[:8]}"
    new_school_id = f"test-school-{uuid.uuid4().hex[:8]}"
    new_school_slug = f"test-school-{uuid.uuid4().hex[:8]}"

    try:
        temp_school = School(
            id=new_school_id,
            name=f"Test School {uuid.uuid4().hex[:6]}",
            slug=new_school_slug,
            status='active',
        )
        db_session.add(temp_school)
        db_session.flush()

        first_student = Student(
            id=str(uuid.uuid4()),
            school_id=DEFAULT_SCHOOL_ID,
            student_identifier=identifier,
            preferred_name='Alpha',
            last_name='Tester',
        )
        second_student = Student(
            id=str(uuid.uuid4()),
            school_id=new_school_id,
            student_identifier=identifier,
            preferred_name='Gamma',
            last_name='Tester',
        )

        db_session.add_all([first_student, second_student])
        db_session.flush()

        count = (
            db_session.query(Student)
            .filter(Student.student_identifier == identifier)
            .count()
        )
        assert count == 2
    finally:
        db_session.rollback()
