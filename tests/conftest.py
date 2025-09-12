import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.main import app as flask_app
from src.models.user import db, User


@pytest.fixture
def app(tmp_path):
    flask_app.config['TESTING'] = True
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{tmp_path / 'test.db'}"
    with flask_app.app_context():
        db.create_all()
    yield flask_app
    with flask_app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_user(app):
    with app.app_context():
        user = User(username='sample', email='sample@example.com', role='admin')
        db.session.add(user)
        db.session.commit()
        return user


@pytest.fixture
def sample_recorder_user():
    from src.routes import golden_plate_recorder
    golden_plate_recorder.users_db['admin'] = {
        'password': 'secret',
        'name': 'Admin',
        'role': 'admin'
    }
    yield {'username': 'admin', 'password': 'secret'}
    golden_plate_recorder.users_db.clear()


@pytest.fixture
def sample_session(client):
    response = client.post('/api/csv/session/create')
    assert response.status_code == 201
    return response.get_json()['session_id']

