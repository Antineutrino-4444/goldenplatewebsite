import io
from datetime import timedelta

from sqlalchemy import inspect

from src.routes.golden_plate_recorder_db.db import engine
from src.routes.golden_plate_recorder_db.map_db import (
    MapEmailVerification,
    MapSubmission,
    MapSubmitterAccount,
    _map_now_utc,
    map_db_session,
    map_engine,
)


def _reset_map_tables():
    map_db_session.query(MapSubmission).delete()
    map_db_session.query(MapEmailVerification).delete()
    map_db_session.query(MapSubmitterAccount).delete()
    map_db_session.commit()


def test_map_uses_separate_database():
    goldenplate_tables = set(inspect(engine).get_table_names())
    map_tables = set(inspect(map_engine).get_table_names())

    assert 'map_submissions' not in goldenplate_tables
    assert 'map_email_verifications' not in goldenplate_tables
    assert 'map_submitter_accounts' not in goldenplate_tables
    assert 'map_submissions' in map_tables
    assert 'map_email_verifications' in map_tables
    assert 'map_submitter_accounts' in map_tables


def test_map_submission_rejects_non_sac_email(client, login):
    _reset_map_tables()
    login()

    response = client.post('/api/map/submissions', data={
        'email': 'student@example.com',
        'text': 'A map note',
        'auth_method': 'email',
    })

    assert response.status_code == 403
    assert response.get_json()['code'] == 'MAP_EMAIL_DOMAIN_DENIED'


def test_map_submission_approval_flow(client, login):
    _reset_map_tables()
    login()

    verification = MapEmailVerification(
        email='student@sac.on.ca',
        code='123456',
        purpose='map_submission',
        expires_at=_map_now_utc() + timedelta(minutes=5),
        verified_at=_map_now_utc(),
        attempts=0,
    )
    map_db_session.add(verification)
    map_db_session.commit()

    response = client.post('/api/map/submissions', data={
        'email': 'student@sac.on.ca',
        'text': 'Visited Beijing and Shanghai.',
        'auth_method': 'email',
        'verification_code': '123456',
        'shortcut_password': 'secret123',
        'image': (io.BytesIO(b'fake-image-bytes'), 'map.png', 'image/png'),
    }, content_type='multipart/form-data')

    assert response.status_code == 201
    submission_id = response.get_json()['submission']['id']
    assert response.get_json()['password_created'] is True

    pending = client.get('/api/map/submissions/pending')
    assert pending.status_code == 200
    assert len(pending.get_json()['submissions']) == 1

    approved = client.post(f'/api/map/submissions/{submission_id}/approve')
    assert approved.status_code == 200

    visible = client.get('/api/map/submissions')
    assert visible.status_code == 200
    submissions = visible.get_json()['submissions']
    assert len(submissions) == 1
    assert submissions[0]['text'] == 'Visited Beijing and Shanghai.'
    assert submissions[0]['image_url']

    image = client.get(submissions[0]['image_url'])
    assert image.status_code == 200
    assert image.data == b'fake-image-bytes'


def test_map_submission_password_shortcut(client, login):
    _reset_map_tables()
    login()

    verification = MapEmailVerification(
        email='repeat@sac.on.ca',
        code='123456',
        purpose='map_submission',
        expires_at=_map_now_utc() + timedelta(minutes=5),
        verified_at=_map_now_utc(),
        attempts=0,
    )
    map_db_session.add(verification)
    map_db_session.commit()

    first = client.post('/api/map/submissions', data={
        'email': 'repeat@sac.on.ca',
        'text': 'First verified submission.',
        'auth_method': 'email',
        'shortcut_password': 'secret123',
    })
    assert first.status_code == 201

    second = client.post('/api/map/submissions', data={
        'email': 'repeat@sac.on.ca',
        'text': 'Second password submission.',
        'auth_method': 'password',
        'password': 'secret123',
    })
    assert second.status_code == 201
    assert second.get_json()['password_used'] is True
