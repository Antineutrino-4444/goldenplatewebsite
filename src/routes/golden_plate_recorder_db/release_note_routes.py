"""Serve the published Markdown release history and record acknowledgments."""

import re
from pathlib import Path

from flask import jsonify, request
from sqlalchemy import or_, update

from . import recorder_bp
from .db import User, db_session
from .security import get_current_user

RELEASE_NOTES_PATH = Path(__file__).resolve().parents[3] / 'RELEASE_NOTES.md'
VERSION = r'(?:0|[1-9][0-9]{0,8})(?:\.(?:0|[1-9][0-9]{0,8})){3}'
RELEASE_HEADING = re.compile(rf'^## ({VERSION})[ \t]*$', re.MULTILINE)


def version_key(version):
    # Fixed-width numeric components let SQL compare versions atomically.
    return ''.join(part.zfill(9) for part in version.split('.'))


def read_release_notes():
    sections = RELEASE_HEADING.split(RELEASE_NOTES_PATH.read_text(encoding='utf-8'))
    return {
        version: body.strip()
        for version, body in zip(sections[1::2], sections[2::2])
        if body.strip()
    }


@recorder_bp.route('/release-notes', methods=['GET', 'POST'])
def release_notes():
    current = get_current_user()
    if current is None:
        return jsonify({'error': 'Sign in to view release notes.'}), 401
    if current['email_required']:
        return jsonify({'error': 'Verify your account email first.'}), 403

    notes = read_release_notes()
    user_id = current['id']
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

    history = request.args.get('view') == 'history'
    seen = db_session.get(User, user_id).seen_release_key or ''
    entries = [
        {'version': version, 'markdown': notes[version]}
        for version in sorted(notes, key=version_key, reverse=True)
        if history or version_key(version) > seen
    ]
    response = jsonify({'entries': entries})
    response.headers['Cache-Control'] = 'no-store'
    return response
