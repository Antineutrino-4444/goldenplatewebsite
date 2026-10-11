from flask import Response, jsonify, request

from . import recorder_bp
from .db import Session as SessionModel, db_session
from .security import get_current_user, require_admin
from .session_exports import EXPORT_COLUMNS, detailed_sessions_export, record_counts_for_sessions
from .users import readable_user_label, user_labels_for_school


@recorder_bp.route('/admin/sessions/export', methods=['GET', 'POST'])
def export_sessions():
    if not require_admin():
        return jsonify({'error': 'Admin access required'}), 403
    school_id = get_current_user()['school_id']
    query = db_session.query(SessionModel).filter(SessionModel.school_id == school_id)

    if request.method == 'GET':
        sessions = query.order_by(SessionModel.created_at.desc(), SessionModel.id).all()
        labels = user_labels_for_school(school_id)
        counts = record_counts_for_sessions(sessions, school_id)
        return jsonify({
            'columns': [{'key': key, 'label': label} for key, label in EXPORT_COLUMNS],
            'sessions': [{
                'session_id': item.id, 'session_name': item.session_name,
                'owner': readable_user_label(item.created_by, labels=labels),
                'is_discarded': item.status == 'discarded',
                'record_count': counts[item.id]['included'],
            } for item in sessions],
        })

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Export options must be a JSON object'}), 400
    session_ids = data.get('session_ids')
    columns = data.get('anonymize_columns', [])
    exclude_discarded = data.get('exclude_discarded', False)
    export_format = data.get('format', 'csv')
    if (not isinstance(session_ids, list) or not session_ids
            or any(not isinstance(value, str) or not value for value in session_ids)):
        return jsonify({'error': 'Select at least one session'}), 400
    if (not isinstance(columns, list) or any(not isinstance(value, str) for value in columns)
            or not set(columns).issubset({key for key, _ in EXPORT_COLUMNS})):
        return jsonify({'error': 'Unknown anonymization column'}), 400
    if not isinstance(exclude_discarded, bool):
        return jsonify({'error': 'Exclude discarded sessions must be true or false'}), 400
    if export_format not in ('csv', 'zip'):
        return jsonify({'error': 'Choose CSV or ZIP as the export format'}), 400
    sessions = query.filter(SessionModel.id.in_(set(session_ids))).order_by(SessionModel.created_at.desc(), SessionModel.id).all()
    if {item.id for item in sessions} != set(session_ids):
        return jsonify({'error': 'One or more selected sessions are unavailable. Refresh the session list.'}), 404
    if exclude_discarded:
        sessions = [item for item in sessions if item.status != 'discarded']
    if not sessions:
        return jsonify({'error': 'No sessions remain after excluding discarded sessions'}), 400
    content, record_count = detailed_sessions_export(sessions, school_id, set(columns), export_format)
    return Response(content, mimetype='application/zip' if export_format == 'zip' else 'text/csv', headers={
        'Content-Disposition': f'attachment; filename="all_sessions_detailed_records.{export_format}"',
        'Cache-Control': 'no-store',
        'X-Export-Session-Count': str(len(sessions)),
        'X-Export-Record-Count': str(record_count),
    })
