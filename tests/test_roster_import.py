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
