"""Resolve current labels through permanent person links, retaining saved names."""
from .db import SessionRecord, Student, Teacher, db_session
from .utils import normalize_name
from .student_history import recorded_profile


def teacher_names(teacher):
    preferred = normalize_name(teacher.preferred_name)
    last = normalize_name(teacher.last_name)
    display = normalize_name(teacher.display_name or teacher.name)
    if not preferred and not last:
        parts = display.split(maxsplit=1)
        preferred, last = (parts + [''])[:2] if parts else ('', '')
    return preferred, last, display or f'{preferred} {last}'.strip()


def record_names(record, student=None, teacher=None):
    preferred, last = normalize_name(record.preferred_name), normalize_name(record.last_name)
    if (record.category != 'faculty' and (record.student_id or record.student_profile)
            and not (record.dedupe_key or '').startswith('count:')):
        profile = recorded_profile(record, student)
        preferred, last = profile['Preferred'], profile['Last']
    recorded_name = f'{preferred} {last}'.strip()
    display = recorded_name
    if record.category == 'faculty' and record.teacher_id:
        teacher = teacher or db_session.get(Teacher, record.teacher_id)
        if teacher and teacher.school_id == record.school_id:
            preferred, last, display = teacher_names(teacher)
    elif record.student_id:
        student = student or db_session.get(Student, record.student_id)
        if student and student.school_id == record.school_id:
            preferred, last = student.preferred_name, student.last_name
            display = f'{preferred} {last}'.strip()
    return {'preferred_name': preferred, 'first_name': preferred, 'last_name': last,
            'display_name': display, 'recorded_name': recorded_name}


def faculty_pick_names(meal):
    preferred = meal.faculty_pick_preferred_name or ''
    last = meal.faculty_pick_last_name or ''
    recorded = meal.faculty_pick_display_name or f'{preferred} {last}'.strip()
    teacher_id = meal.faculty_pick_teacher_id
    if not teacher_id and meal.faculty_pick_record_id:
        record = db_session.get(SessionRecord, meal.faculty_pick_record_id)
        if record and record.school_id == meal.school_id:
            teacher_id = record.teacher_id
    teacher = db_session.get(Teacher, teacher_id) if teacher_id else None
    display = recorded
    if teacher and teacher.school_id == meal.school_id:
        preferred, last, display = teacher_names(teacher)
    return {'preferred_name': preferred, 'last_name': last, 'display_name': display,
            'recorded_name': recorded, 'teacher_id': teacher_id}
