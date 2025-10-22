"""
Migration script to convert sessions and session records from JSON to database.
This script reads the persistent_data/sessions.json file and migrates all sessions
and their records to the database tables.
"""

import json
import os
import sys
from datetime import datetime

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from routes.golden_plate_recorder_db.db import (
    Session as SessionModel,
    SessionRecord,
    Student,
    db_session,
    engine,
)


def parse_datetime(dt_str):
    """Parse datetime string to datetime object."""
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    except Exception:
        return None


def get_or_create_student(record):
    """Get or create a student in the database based on record data."""
    student_id = record.get('student_id', '').strip()
    preferred_name = record.get('preferred_name', '').strip()
    last_name = record.get('last_name', '').strip()
    
    if not student_id:
        # Extract student_id from student_key if present
        student_key = record.get('student_key', '')
        if student_key and '|' in student_key:
            parts = student_key.split('|')
            if len(parts) >= 3:
                student_id = parts[2]
    
    # Try to find existing student by student_id
    if student_id:
        student = db_session.query(Student).filter_by(student_identifier=student_id).first()
        if student:
            return student
    
    # Create new student if has student_id
    if student_id:
        student = Student(
            student_identifier=student_id,
            preferred_name=preferred_name,
            last_name=last_name,
            grade=record.get('grade', ''),
            advisor=record.get('advisor', ''),
            house=record.get('house', ''),
            clan=record.get('clan', '')
        )
        db_session.add(student)
        db_session.flush()
        return student
    
    return None


def create_dedupe_key(record, category):
    """Create a dedupe key for a record."""
    if category == 'dirty':
        timestamp = record.get('timestamp', datetime.now().isoformat())
        return f"dirty_{timestamp}"
    elif category == 'faculty':
        preferred = record.get('preferred_name', '').lower()
        last = record.get('last_name', '').lower()
        return f"faculty_{preferred}_{last}"
    else:
        # For clean and red records
        student_key = record.get('student_key', '')
        if student_key:
            return student_key.lower()
        
        preferred = record.get('preferred_name', '').lower()
        last = record.get('last_name', '').lower()
        grade = record.get('grade', '')
        house = record.get('house', '')
        return f"{preferred}_{last}_{grade}_{house}"


def migrate_sessions():
    """Migrate all sessions from JSON to database."""
    json_file = 'persistent_data/sessions.json'
    
    if not os.path.exists(json_file):
        print(f"No sessions file found at {json_file}")
        return
    
    with open(json_file, 'r', encoding='utf-8') as f:
        sessions_data = json.load(f)
    
    print(f"Found {len(sessions_data)} sessions to migrate")
    
    migrated_sessions = 0
    migrated_records = 0
    skipped_sessions = 0
    
    for session_id, session_info in sessions_data.items():
        session_name = session_info.get('session_name', '')
        
        # Check if session already exists
        existing = db_session.query(SessionModel).filter_by(id=session_id).first()
        if existing:
            print(f"  Session '{session_name}' already exists in database, skipping...")
            skipped_sessions += 1
            continue
        
        print(f"  Migrating session: {session_name}")
        
        # Determine status
        status = 'active'
        if session_info.get('is_discarded', False):
            status = 'discarded'
        
        # Create session
        created_at = parse_datetime(session_info.get('created_at'))
        discarded_at = parse_datetime(session_info.get('discard_metadata', {}).get('discarded_at'))
        
        # Count records by category
        clean_count = len(session_info.get('clean_records', []))
        red_count = len(session_info.get('red_records', []))
        faculty_count = len(session_info.get('faculty_clean_records', []))
        dirty_count = session_info.get('dirty_count', 0)
        
        # Calculate totals
        total_records = clean_count + dirty_count + red_count + faculty_count
        total_clean = clean_count + faculty_count
        total_dirty = dirty_count + red_count
        
        new_session = SessionModel(
            id=session_id,
            session_name=session_name,
            created_by=session_info.get('owner', 'unknown'),
            is_public=1 if session_info.get('is_public', True) else 0,
            status=status,
            created_at=created_at or datetime.now(),
            discarded_at=discarded_at,
            discarded_by=session_info.get('discard_metadata', {}).get('discarded_by'),
            clean_number=clean_count,
            dirty_number=dirty_count,
            red_number=red_count,
            faculty_number=faculty_count,
            total_records=total_records,
            total_clean=total_clean,
            total_dirty=total_dirty
        )
        
        db_session.add(new_session)
        db_session.flush()
        migrated_sessions += 1
        
        # Migrate clean records
        for record in session_info.get('clean_records', []):
            student = get_or_create_student(record)
            dedupe_key = create_dedupe_key(record, 'clean')
            
            # Check if record already exists
            existing_record = db_session.query(SessionRecord).filter_by(
                session_id=session_id,
                dedupe_key=dedupe_key
            ).first()
            
            if not existing_record:
                recorded_at = parse_datetime(record.get('timestamp'))
                db_record = SessionRecord(
                    session_id=session_id,
                    student_id=student.id if student else None,
                    category='clean',
                    grade=record.get('grade', ''),
                    house=record.get('house', ''),
                    recorded_by=record.get('recorded_by', 'unknown'),
                    is_manual_entry=1 if record.get('is_manual_entry', False) else 0,
                    recorded_at=recorded_at or datetime.now(),
                    dedupe_key=dedupe_key
                )
                db_session.add(db_record)
                migrated_records += 1
        
        # Migrate red records
        for record in session_info.get('red_records', []):
            student = get_or_create_student(record)
            dedupe_key = create_dedupe_key(record, 'red')
            
            # Check if record already exists
            existing_record = db_session.query(SessionRecord).filter_by(
                session_id=session_id,
                dedupe_key=dedupe_key
            ).first()
            
            if not existing_record:
                recorded_at = parse_datetime(record.get('timestamp'))
                db_record = SessionRecord(
                    session_id=session_id,
                    student_id=student.id if student else None,
                    category='red',
                    grade=record.get('grade', ''),
                    house=record.get('house', ''),
                    recorded_by=record.get('recorded_by', 'unknown'),
                    is_manual_entry=1 if record.get('is_manual_entry', False) else 0,
                    recorded_at=recorded_at or datetime.now(),
                    dedupe_key=dedupe_key
                )
                db_session.add(db_record)
                migrated_records += 1
        
        # Migrate faculty records
        for record in session_info.get('faculty_clean_records', []):
            dedupe_key = create_dedupe_key(record, 'faculty')
            
            # Check if record already exists
            existing_record = db_session.query(SessionRecord).filter_by(
                session_id=session_id,
                dedupe_key=dedupe_key
            ).first()
            
            if not existing_record:
                recorded_at = parse_datetime(record.get('timestamp'))
                db_record = SessionRecord(
                    session_id=session_id,
                    student_id=None,
                    category='faculty',
                    grade='',
                    house='',
                    recorded_by=record.get('recorded_by', 'unknown'),
                    is_manual_entry=1,
                    recorded_at=recorded_at or datetime.now(),
                    dedupe_key=dedupe_key
                )
                db_session.add(db_record)
                migrated_records += 1
        
        # Migrate dirty records (stored as count)
        dirty_count = session_info.get('dirty_count', 0)
        for i in range(dirty_count):
            dedupe_key = f"dirty_{session_id}_{i}"
            
            # Check if record already exists
            existing_record = db_session.query(SessionRecord).filter_by(
                session_id=session_id,
                dedupe_key=dedupe_key
            ).first()
            
            if not existing_record:
                db_record = SessionRecord(
                    session_id=session_id,
                    student_id=None,
                    category='dirty',
                    grade='',
                    house='',
                    recorded_by='unknown',
                    is_manual_entry=0,
                    dedupe_key=dedupe_key
                )
                db_session.add(db_record)
                migrated_records += 1
        
        # Commit after each session
        db_session.commit()
        print(f"    ✓ Migrated session with records")
    
    print(f"\nMigration complete!")
    print(f"  Sessions migrated: {migrated_sessions}")
    print(f"  Sessions skipped: {skipped_sessions}")
    print(f"  Records migrated: {migrated_records}")


if __name__ == '__main__':
    print("Starting migration of sessions from JSON to database...")
    print("=" * 60)
    
    try:
        migrate_sessions()
        print("\n✓ Migration completed successfully!")
    except Exception as e:
        print(f"\n✗ Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        db_session.rollback()
        sys.exit(1)
