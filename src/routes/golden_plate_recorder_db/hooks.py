import os

from flask import g, session

from . import recorder_bp
from .db import db_session, reset_current_school_id, set_current_school_id
from .storage import reset_storage_for_testing

_last_pytest_identifier = None


@recorder_bp.before_app_request
def _ensure_isolated_state_for_tests():
    """Clear persisted state when pytest moves to a new test case."""
    global _last_pytest_identifier

    pytest_identifier = os.environ.get('PYTEST_CURRENT_TEST')
    if not pytest_identifier:
        return

    current_identifier = pytest_identifier.split(' (')[0]
    if current_identifier != _last_pytest_identifier:
        reset_storage_for_testing()
        _last_pytest_identifier = current_identifier


@recorder_bp.before_app_request
def _attach_school_context():
    school_id = (
        session.get('impersonated_school_id')
        or session.get('school_id')
        or session.get('guest_school_id')
    )
    g._school_token = set_current_school_id(school_id)


__all__ = []


@recorder_bp.teardown_app_request
def _shutdown_scoped_session(exception=None):
    token = getattr(g, '_school_token', None)
    if token is not None:
        reset_current_school_id(token)
    db_session.remove()
