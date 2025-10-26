"""
Migration script to migrate users, teachers, and students from JSON files to the database.

This script:
1. Migrates users from persistent_data/users.json to the users table
2. Migrates teachers from persistent_data/teacher_list.json to the teachers table
3. Migrates students from persistent_data/global_csv_data.json to the students table

Run this once to populate the database with existing data.
"""
import json
import os
import sys
from pathlib import Path

# Add src to path so we can import from the app
sys.path.insert(0, str(Path(__file__).parent))

from src.routes.golden_plate_recorder_db.db import User, Teacher, Student, SessionRecord, db_session, engine, Base

DATABASE_PATH = 'data/golden_plate_recorder.db'
USERS_JSON = 'persistent_data/users.json'
TEACHERS_JSON = 'persistent_data/teacher_list.json'
STUDENTS_JSON = 'persistent_data/global_csv_data.json'


def load_json(filepath):
    """Load JSON data from file."""
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found, skipping...")
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def migrate_users():
    """Migrate users from JSON to database."""
    print("\n=== Migrating Users ===")
    
    users_data = load_json(USERS_JSON)
    if not users_data:
        return
    
    migrated = 0
    skipped = 0
    
    for username, user_info in users_data.items():
        # Check if user already exists
        existing_user = db_session.query(User).filter_by(username=username).first()
        if existing_user:
            print(f"  Skipping user '{username}' - already exists")
            skipped += 1
            continue
        
        # Create new user
        # Note: passwords in the JSON are stored as plain text (not ideal, but that's the existing format)
        # In production, these should be hashed
        new_user = User(
            username=username,
            password_hash=user_info.get('password', ''),  # Storing as-is for now
            display_name=user_info.get('name', username),
            role=user_info.get('role', 'user'),
            status=user_info.get('status', 'active')
        )
        
        db_session.add(new_user)
        print(f"  Migrated user: {username} ({user_info.get('role', 'user')})")
        migrated += 1
    
    try:
        db_session.commit()
        print(f"\n✓ Users migration complete: {migrated} migrated, {skipped} skipped")
    except Exception as e:
        db_session.rollback()
        print(f"\n✗ Error committing users: {e}")
        raise


def migrate_teachers():
    """Migrate teachers from JSON to database."""
    print("\n=== Migrating Teachers ===")
    
    teachers_data = load_json(TEACHERS_JSON)
    if not teachers_data:
        return
    
    teachers_list = teachers_data.get('teachers', [])
    migrated = 0
    skipped = 0
    
    for teacher_info in teachers_list:
        teacher_name = teacher_info.get('name')
        if not teacher_name:
            continue
        
        # Check if teacher already exists
        existing_teacher = db_session.query(Teacher).filter_by(name=teacher_name).first()
        if existing_teacher:
            print(f"  Skipping teacher '{teacher_name}' - already exists")
            skipped += 1
            continue
        
        # Create new teacher
        new_teacher = Teacher(
            name=teacher_name,
            display_name=teacher_info.get('display_name', teacher_name)
        )
        
        db_session.add(new_teacher)
        print(f"  Migrated teacher: {teacher_name}")
        migrated += 1
    
    try:
        db_session.commit()
        print(f"\n✓ Teachers migration complete: {migrated} migrated, {skipped} skipped")
    except Exception as e:
        db_session.rollback()
        print(f"\n✗ Error committing teachers: {e}")
        raise


def migrate_students():
    """Migrate students from global CSV data to database."""
    print("\n=== Migrating Students ===")
    
    students_data = load_json(STUDENTS_JSON)
    if not students_data:
        return
    
    students_list = students_data.get('data', [])
    migrated = 0
    skipped = 0
    
    for student_info in students_list:
        student_id = student_info.get('Student ID')
        if not student_id:
            continue
        
        # Check if student already exists
        existing_student = db_session.query(Student).filter_by(student_identifier=student_id).first()
        if existing_student:
            skipped += 1
            continue
        
        # Create new student
        new_student = Student(
            student_identifier=student_id,
            preferred_name=student_info.get('Preferred', ''),
            last_name=student_info.get('Last', ''),
            grade=student_info.get('Grade', ''),
            advisor=student_info.get('Advisor', ''),
            house=student_info.get('House', ''),
            clan=student_info.get('Clan', '')
        )
        
        db_session.add(new_student)
        migrated += 1
        
        # Print progress every 100 students
        if migrated % 100 == 0:
            print(f"  Migrated {migrated} students...")
    
    try:
        db_session.commit()
        print(f"\n✓ Students migration complete: {migrated} migrated, {skipped} skipped")
    except Exception as e:
        db_session.rollback()
        print(f"\n✗ Error committing students: {e}")
        raise


def migrate_session_record_names():
    """Update session records with student names from the students table."""
    print("\n=== Migrating Session Record Names ===")
    
    # Find all session records that have a student_id but missing names
    records_without_names = db_session.query(SessionRecord).filter(
        SessionRecord.student_id.isnot(None),
        (SessionRecord.preferred_name.is_(None)) | (SessionRecord.last_name.is_(None))
    ).all()
    
    if not records_without_names:
        print("  No session records need name updates")
        return
    
    updated = 0
    skipped = 0
    
    for record in records_without_names:
        # Get the student information
        student = db_session.query(Student).filter_by(id=record.student_id).first()
        
        if not student:
            print(f"  Warning: No student found for record {record.id}")
            skipped += 1
            continue
        
        # Update the name fields
        record.preferred_name = student.preferred_name
        record.last_name = student.last_name
        updated += 1
        
        if updated % 100 == 0:
            print(f"  Updated {updated} session records...")
    
    try:
        db_session.commit()
        print(f"\n✓ Session record names migration complete: {updated} updated, {skipped} skipped")
    except Exception as e:
        db_session.rollback()
        print(f"\n✗ Error committing session record updates: {e}")
        raise


def main():
    """Run all migrations."""
    print("=" * 60)
    print("Starting migration of users, teachers, and students")
    print("=" * 60)
    
    # Ensure database exists and tables are created
    if not os.path.exists(DATABASE_PATH):
        print(f"\nCreating database at {DATABASE_PATH}...")
        Base.metadata.create_all(bind=engine)
    
    try:
        migrate_users()
        migrate_teachers()
        migrate_students()
        migrate_session_record_names()
        
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        sys.exit(1)
    finally:
        db_session.close()


if __name__ == '__main__':
    main()
