"""School contact details, managed only by the school's own superadmins."""

import re

from flask import jsonify, request

from . import recorder_bp
from .db import School, _now_utc, db_session
from .security import get_current_user


@recorder_bp.route('/school/contact-email', methods=['PUT'])
def update_school_contact_email():
    current = get_current_user()
    if not current:
        return jsonify({'error': 'Authentication required'}), 401
    if current['role'] != 'superadmin':
        return jsonify({'error': 'Superadmin access required'}), 403
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({'error': 'Enter a valid contact email address.'}), 400
    email = data.get('email')
    if not isinstance(email, str):
        return jsonify({'error': 'Enter a valid contact email address.'}), 400
    email = email.strip().lower()
    if len(email) > 320 or not re.fullmatch(r'[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+', email):
        return jsonify({'error': 'Enter a valid contact email address.'}), 400
    # Always use the authenticated school; never trust a caller-supplied ID.
    school = db_session.query(School).filter_by(id=current['school_id']).first()
    if not school:
        return jsonify({'error': 'School not found'}), 404
    school.contact_email = email
    school.updated_at = _now_utc()
    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        return jsonify({'error': 'Unable to save the contact email. Please try again.'}), 500
    return jsonify({'status': 'success', 'contact_email': email,
                    'message': 'School contact email saved.'}), 200
