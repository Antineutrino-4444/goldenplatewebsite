"""School-specific point values used to calculate house rankings."""

from .db import School, db_session

SCORE_FIELDS = {
    'clean_points': 'house_clean_points',
    'dirty_penalty': 'house_dirty_penalty',
    'very_dirty_penalty': 'house_very_dirty_penalty',
}


def house_score_settings(school_id):
    school = db_session.query(School).filter_by(id=school_id).one()
    return {key: getattr(school, column) for key, column in SCORE_FIELDS.items()}
