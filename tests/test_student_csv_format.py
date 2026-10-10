import io
import uuid

import pytest

from src.routes.golden_plate_recorder_db import storage
from src.routes.golden_plate_recorder_db.db import DEFAULT_SCHOOL_ID, Student, db_session


def upload_csv(client, content):
    return client.post('/api/csv/upload', data={
        'file': (io.BytesIO(content.encode('utf-8')), 'students.csv'),
    })


@pytest.mark.parametrize('content, expected_name, expected_grade, expected_house', [
    ('Preferred,Student ID,Last\nAlex,987654321,Smith\n', 'Alex', None, None),
    ('Last,First,Student ID\nSmith,Alex,987654321\n', 'Alex', None, None),
    ('First,Last,Student ID,Preferred\nAlexander,Smith,987654321,Alex\n', 'Alex', None, None),
    ('Clan,House,Advisor,Grade,Last,Student ID,Preferred\n,,,,Smith,987654321,Alex\n', 'Alex', None, None),
    ('House,First,Last,Grade,Student ID,Advisor,Clan\nBarn,Alex,Smith,9,987654321,Johnson,Alpha\n', 'Alex', '9', 'Barn'),
    ('\ufeff Last , Student ID , First \nSmith,987654321,Alex\n', 'Alex', None, None),
    ('last,STUDENT id,pReFeRrEd,FIRST\nSmith,987654321,Alex,Alexander\n', 'Alex', None, None),
    ('cLaN,HOUSE,advisor,GRADE,LAST,Student id,first\nAlpha,Barn,Johnson,9,Smith,987654321,Alex\n', 'Alex', '9', 'Barn'),
])
def test_student_roster_accepts_flexible_columns(client, login, content, expected_name, expected_grade, expected_house):
    login()
    response = upload_csv(client, content)
    assert response.status_code == 200
    assert response.get_json()['students_processed'] == 1
    student = db_session.query(Student).filter_by(
        school_id=DEFAULT_SCHOOL_ID, student_identifier='987654321',
    ).one()
    assert student.preferred_name == expected_name
    assert student.last_name == 'Smith'
    assert student.grade == expected_grade
    assert student.house == expected_house
    assert student.is_active == 1
    assert storage.global_csv_data[DEFAULT_SCHOOL_ID]['data'][0]['Preferred'] == expected_name
    preview = client.get('/api/csv/preview').get_json()
    assert preview['data'][0]['Preferred'] == expected_name
    names = client.get('/api/csv/student-names').get_json()['names']
    assert names[0]['preferred'] == expected_name
    # Barcode recording must use the selected name and work without optional fields.
    assert client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).status_code == 200
    recorded = client.post('/api/record/clean', json={'input_value': '987654321'})
    assert recorded.status_code == 200
    assert recorded.get_json()['preferred_name'] == expected_name


@pytest.mark.parametrize('content', [
    'Last,Preferred\nSmith,Alex\n',
    'Student ID,First\ncsv-format-2,Alex\n',
    'Student ID,Last\ncsv-format-2,Smith\n',
    'Student ID,Last,Preferred,First\ncsv-format-2,Smith,,Alexander\n',
    'STUDENT ID,last,pReFeRrEd,FIRST\ncsv-format-2,Smith,,Alexander\n',
    'STUDENT ID,last,Preferred,preferred\ncsv-format-2,Smith,Alex,Alexander\n',
])
def test_student_roster_requires_id_last_and_selected_name(client, login, content):
    login()
    assert upload_csv(client, 'Student ID,Last,Preferred\ncsv-format-kept,Smith,Alex\n').status_code == 200
    response = upload_csv(client, content)
    assert response.status_code == 400
    student = db_session.query(Student).filter_by(
        school_id=DEFAULT_SCHOOL_ID, student_identifier='csv-format-kept',
    ).one()
    assert student.is_active == 1
    assert 'id:csv-format-kept' in storage.get_student_lookup_for_school(DEFAULT_SCHOOL_ID)
