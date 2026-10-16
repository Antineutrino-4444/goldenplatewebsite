def session_metrics(db_sess):
    """The dashboard's counts, including faculty in clean and red in dirty."""
    clean = db_sess.clean_number or 0
    dirty = db_sess.dirty_number or 0
    red = db_sess.red_number or 0
    faculty = db_sess.faculty_number or 0
    total = clean + dirty + red + faculty
    return {
        'clean_count': clean,
        'dirty_count': dirty,
        'red_count': red,
        'combined_dirty_count': dirty + red,
        'faculty_clean_count': faculty,
        'total_recorded': total,
        'clean_percentage': round((clean + faculty) / total * 100, 1) if total else 0,
        'dirty_percentage': round((dirty + red) / total * 100, 1) if total else 0,
    }
