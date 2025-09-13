import os
import sys

import pytest

# Ensure the application package can be imported
sys.path.insert(0, os.path.abspath('.'))

from src.main import app


@pytest.fixture
def client():
    """Flask test client"""
    with app.test_client() as client:
        yield client


@pytest.fixture
def login(client):
    """Helper to log in a user"""
    def _login(username='admin', password='admin123'):
        return client.post('/api/auth/login', json={'username': username, 'password': password})

    return _login

