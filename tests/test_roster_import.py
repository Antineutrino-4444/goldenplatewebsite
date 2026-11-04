import io
import json

from src.routes.golden_plate_recorder_db.db import DEFAULT_SCHOOL_ID, Student, db_session


def roster_file(content, filename):
    return {'file': (io.BytesIO(content.encode('utf-8')), filename)}


def test_student_review_and_generated_ids(client, login):
    source = 'Surname\tGiven name\tGrade\nNg\tAvery\t9\n\nDiaz\tRobin\t8\n'
    path = '/api/rosters/student/review'
    assert client.post(path, data=roster_file(source, 'students.tsv')).status_code == 403

    login()
    students = db_session.query(Student).filter_by(school_id=DEFAULT_SCHOOL_ID)
    # Isolate this test from the local roster snapshot.
    students.filter(Student.student_identifier.in_(['1', '2'])).delete(synchronize_session=False)
    db_session.commit()
    before = students.filter_by(is_active=1).count()

    review = client.post(path, data=roster_file(source, 'students.tsv'))
    assert review.status_code == 200
    assert review.headers['Cache-Control'] == 'no-store'
    table = review.get_json()['tables'][0]
    assert table['mapping'] == {'Preferred': 1, 'Last': 0, 'Grade': 2}
    assert table['skip_first'] is True
    assert students.filter_by(is_active=1).count() == before

    mapping = {'table': 0, 'columns': table['mapping'], 'skip_first': True, 'generate_ids': True}
    result = client.post('/api/csv/upload', data={
        **roster_file(source, 'students.tsv'), 'mapping': json.dumps(mapping),
    })
    assert result.status_code == 200
    assert result.get_json()['rows_count'] == 2
    active = students.filter_by(is_active=1).order_by(Student.student_identifier).all()
    assert [(s.student_identifier, s.preferred_name, s.last_name) for s in active] == [
        ('1', 'Avery', 'Ng'), ('2', 'Robin', 'Diaz'),
    ]
    assert all(not s.house and not s.clan for s in active)

    reordered = 'Surname\tGiven name\tGrade\nDiaz\tRobin\t8\nNg\tAvery\t9\n'
    result = client.post('/api/csv/upload', data={
        **roster_file(reordered, 'students.tsv'), 'mapping': json.dumps(mapping),
    })
    assert result.status_code == 400
    assert students.filter_by(student_identifier='1').one().preferred_name == 'Avery'


def test_headerless_faculty_csv_and_manual_assignment(client, login):
    login()
    source = 'Ng,Avery,FAC-14\nDiaz,Robin,FAC-15\n'
    review = client.post('/api/rosters/teacher/review', data=roster_file(source, 'faculty.csv'))
    table = review.get_json()['tables'][0]
    assert table['mapping'] == {} and table['skip_first'] is False
    mapping = {'table': 0, 'columns': {'Preferred': 1, 'Last': 0, 'Faculty ID': 2}}
    result = client.post('/api/teachers/upload', data={
        **roster_file(source, 'faculty.csv'), 'mapping': json.dumps(mapping),
    })
    assert result.status_code == 200
    assert result.get_json()['count'] == 2


def test_combined_roster_validates_all_files_before_replacing(client, login):
    login()
    first = 'Surname,Given name,Student ID\nNg,Avery,MERGE-1\n'
    second = 'Student ID\tFirst name\tLast name\nMERGE-2\tRobin\tDiaz\n'
    mappings = [
        {'table': 0, 'columns': {'Preferred': 1, 'Last': 0, 'Student ID': 2}, 'skip_first': True},
        {'table': 0, 'columns': {'Preferred': 1, 'Last': 2, 'Student ID': 0}, 'skip_first': True},
    ]

    def upload(second_source):
        return client.post('/api/csv/upload', data={
            'file': [(io.BytesIO(first.encode()), 'first.csv'), (io.BytesIO(second_source.encode()), 'second.tsv')],
            'mapping': json.dumps(mappings),
        })

    result = upload(second)
    assert result.status_code == 200
    assert result.get_json()['rows_count'] == 2
    result = upload(second.replace('MERGE-2', 'merge-1'))
    assert result.status_code == 400
    assert 'second.tsv' in result.get_json()['error']
    names = client.get('/api/csv/student-names').get_json()['names']
    assert {student['student_id'] for student in names} == {'MERGE-1', 'MERGE-2'}

    students = db_session.query(Student).filter_by(school_id=DEFAULT_SCHOOL_ID)
    students.filter(Student.student_identifier.in_(['1', '2'])).delete(synchronize_session=False)
    db_session.commit()
    for mapping in mappings:
        mapping['generate_ids'] = True
        del mapping['columns']['Student ID']
    assert upload(second).status_code == 200
    names = client.get('/api/csv/student-names').get_json()['names']
    assert {student['student_id']: student['preferred'] for student in names} == {'1': 'Avery', '2': 'Robin'}


def test_combined_faculty_roster_accepts_ids_in_one_file(client, login):
    login()
    files = [
        (io.BytesIO(b'Ng,Avery,FAC-MERGE-1\n'), 'first.csv'),
        (io.BytesIO(b'Robin\tDiaz\n'), 'second.tsv'),
    ]
    mappings = [
        {'table': 0, 'columns': {'Preferred': 1, 'Last': 0, 'Faculty ID': 2}},
        {'table': 0, 'columns': {'Preferred': 0, 'Last': 1}},
    ]
    result = client.post('/api/teachers/upload', data={'file': files, 'mapping': json.dumps(mappings)})
    assert result.status_code == 200
    assert result.get_json()['count'] == 2
