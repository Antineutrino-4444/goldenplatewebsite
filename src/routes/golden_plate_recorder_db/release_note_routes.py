"""Serve the published Markdown release history and record acknowledgments."""

from flask import jsonify, request
from sqlalchemy import or_, update

from src.services.release_notes import read_release_notes, version_key

from . import recorder_bp
from .db import User, db_session
from .security import get_current_user


@recorder_bp.route('/release-notes', methods=['GET', 'POST'])
def release_notes():
    history = request.method in ('GET', 'HEAD') and request.args.get('view') == 'history'
    if not history:
        current = get_current_user()
        if current is None:
            return jsonify({'error': 'Sign in to view unread release notes.'}), 401
        if current['email_required']:
            return jsonify({'error': 'Verify your account email first.'}), 403
        user_id = current['id']

    notes = read_release_notes()
    if request.method == 'POST':
        data = request.get_json(silent=True)
        version = data.get('version') if isinstance(data, dict) else None
        if not isinstance(version, str) or version not in notes:
            return jsonify({'error': 'Unknown release version.'}), 400
        key = version_key(version)
        db_session.execute(
            update(User)
            .where(User.id == user_id, or_(User.seen_release_key.is_(None), User.seen_release_key < key))
            .values(seen_release_key=key)
        )
        db_session.commit()
        return '', 204

    seen = '' if history else db_session.get(User, user_id).seen_release_key or ''
    entries = [
        {'version': version, 'markdown': notes[version]}
        for version in sorted(notes, key=version_key, reverse=True)
        if version_key(version) > seen
    ]
    response = jsonify({'entries': entries})
    response.headers['Cache-Control'] = 'no-store'
    return response
