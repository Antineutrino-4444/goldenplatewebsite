"""School guest privacy at the JSON response boundary, including legacy caches."""

from flask import current_app, jsonify, request, session
from sqlalchemy.exc import IntegrityError

from . import recorder_bp
from .db import GuestStudentAlias, School, SessionRecord, Student, db_session
from .security import get_current_user, is_guest
from .utils import extract_student_id_from_key, make_student_key


@recorder_bp.route('/admin/guest-privacy', methods=['GET', 'PUT'])
def guest_privacy_settings():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    if user['role'] not in {'admin', 'superadmin'}:
        return jsonify({'error': 'Admin access required'}), 403
    school = db_session.get(School, user['school_id'])
    if not school:
        return jsonify({'error': 'School not found'}), 404
    if request.method == 'PUT':
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or type(data.get('enabled')) is not bool:
            return jsonify({'error': 'Choose whether to anonymize guest views.'}), 400
        school.guest_privacy_enabled = int(data['enabled'])
        try:
            db_session.commit()
        except Exception:
            db_session.rollback()
            return jsonify({'error': 'Unable to save guest privacy. Please try again.'}), 500
    response = jsonify({'enabled': bool(school.guest_privacy_enabled)})
    response.headers['Cache-Control'] = 'no-store'
    return response


class GuestView:
    # Free text and account references can contain identities even when the
    # student profile itself is anonymous. Preserve field shapes for the UI.
    hidden_fields = {
        'student_identifier', 'grade', 'advisor', 'clan', 'email', 'contact_email',
        'student_profile', 'roster_conflicts', 'dedupe_key', 'comment', 'notes',
        'exclusion_reason', 'roster_filename', 'roster_snapshot_id',
        'teacher_id', 'faculty_identifier', 'recorded_name',
    }
    staff_fields = {
        'owner', 'recorded_by', 'created_by', 'selected_by', 'finalized_by',
        'excluded_by', 'changed_by', 'roster_matched_by', 'roster_uploaded_by',
    }
    name_fields = {'name', 'display_name', 'student_name', 'preferred_name', 'first_name', 'last_name'}

    def __init__(self, school_id, payload):
        self.school_id = school_id
        self.student_ids = {}
        self.student_identifiers = {}
        self.names = {}
        for student in db_session.query(Student).filter_by(school_id=school_id).all():
            identity = f'student:{student.student_identifier.casefold()}'
            self.student_ids[student.id] = identity
            self.student_identifiers[student.student_identifier.casefold()] = identity
            name_key = make_student_key(student.preferred_name, student.last_name)
            self.names.setdefault(name_key, set()).add(identity)
        record_ids = set()

        def collect(value):
            if isinstance(value, list):
                for item in value:
                    collect(item)
            elif isinstance(value, dict):
                if value.get('record_id'):
                    record_ids.add(value['record_id'])
                for item in value.values():
                    collect(item)

        collect(payload)
        self.records = {
            record.id: record for record in db_session.query(SessionRecord).filter(
                SessionRecord.school_id == school_id, SessionRecord.id.in_(record_ids),
            ).all()
        } if record_ids else {}
        self.aliases = {
            alias.identity_key: alias.id for alias in db_session.query(GuestStudentAlias)
            .filter_by(school_id=school_id).all()
        }

    def identity(self, value):
        record = self.records.get(value.get('record_id'))
        if record and record.student_id in self.student_ids:
            return self.student_ids[record.student_id]
        if record:
            identifier = extract_student_id_from_key(record.dedupe_key or '')
            if identifier:
                return f'student:{identifier.casefold()}'
        identifier = value.get('student_identifier') or extract_student_id_from_key(
            value.get('student_key') or value.get('key') or '')
        if identifier:
            return f'student:{str(identifier).casefold()}'
        reference = value.get('student_id')
        if reference:
            return self.student_ids.get(str(reference), self.student_identifiers.get(
                str(reference).casefold(), f'student:{str(reference).casefold()}'))
        if record and record.dedupe_key and not record.dedupe_key.startswith('count:'):
            key = record.dedupe_key
        else:
            key = value.get('student_key') or value.get('key') or make_student_key(
                value.get('preferred_name') or value.get('first_name'), value.get('last_name'))
            if not key:
                key = value.get('student_name') or value.get('display_name') or value.get('name')
        if not key:
            return None
        matches = self.names.get(key, set())
        if len(matches) == 1:
            return next(iter(matches))
        # Unlinked manual entries use the same identity that the recorder uses.
        return f'manual:{str(key).casefold()}'

    def alias(self, identity):
        if identity not in self.aliases:
            alias = GuestStudentAlias(school_id=self.school_id, identity_key=identity)
            try:
                # A concurrent guest may create this alias first. A savepoint
                # preserves other aliases allocated in this response.
                with db_session.begin_nested():
                    db_session.add(alias)
                    db_session.flush()
                alias_id = alias.id
            except IntegrityError:
                alias_id = db_session.query(GuestStudentAlias.id).filter_by(
                    school_id=self.school_id, identity_key=identity,
                ).one()[0]
            self.aliases[identity] = alias_id
        return self.aliases[identity]

    def sanitize(self, value, context=''):
        if isinstance(value, list):
            return [self.sanitize(item, context) for item in value]
        if not isinstance(value, dict):
            return value
        result = {key: self.sanitize(item, key) for key, item in value.items()}
        faculty = context == 'faculty_pick' or str(value.get('category', '')).lower() == 'faculty'
        person = faculty or any(key in value for key in (
            'student_id', 'student_identifier', 'student_key', 'preferred_name',
            'first_name', 'last_name', 'student_name', 'record_id',
        )) or context in {'winner', 'candidates', 'top_candidates', 'scan_history'}
        count_only = value.get('is_count_only') is True
        if person and not count_only:
            identity = None if faculty else self.identity(value)
            alias_id = self.alias(identity) if identity else None
            label = 'Faculty member' if faculty else f'Student {alias_id}' if alias_id else 'Student'
            for key in self.name_fields & value.keys():
                result[key] = '' if key == 'last_name' else label if value[key] else value[key]
            for key in {'student_id', 'student_key', 'key'} & value.keys():
                result[key] = f'student-{alias_id}' if alias_id else None
            if 'house' in result:
                result['house'] = None
        for key in self.hidden_fields & value.keys():
            result[key] = None
        for key in self.staff_fields & value.keys():
            result[key] = 'School staff' if value[key] else None
        if value.get('faculty_name'):
            result['faculty_name'] = 'Faculty member'
        if 'session_name' in result:
            # Session titles are free text and may include student names.
            result['session_name'] = 'School session'
        return result


@recorder_bp.after_request
def anonymize_guest_session_response(response):
    if not request.path.startswith('/api/session/'):
        return response
    # Privacy changes must apply on the next request, without a cached response.
    response.headers['Cache-Control'] = 'no-store'
    if not is_guest() or not response.is_json or response.status_code >= 400:
        return response
    try:
        school = db_session.get(School, session.get('school_id'))
        if not school or not school.guest_privacy_enabled:
            return response
        payload = response.get_json()
        view = GuestView(school.id, payload)
        sanitized = view.sanitize(payload)
        db_session.commit()
        response.set_data(current_app.json.dumps(sanitized))
        return response
    except Exception:
        db_session.rollback()
        current_app.logger.exception('Unable to prepare private guest view')
        # Never fall back to sending the original identifying response.
        failure = jsonify({'error': 'Unable to load the private guest view. Please try again.'})
        failure.status_code = 503
        failure.headers['Cache-Control'] = 'no-store'
        return failure
