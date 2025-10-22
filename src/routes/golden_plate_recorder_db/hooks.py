import os

from . import recorder_bp
from .db import db_session
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


__all__ = []


@recorder_bp.teardown_app_request
def _shutdown_scoped_session(exception=None):
    db_session.remove()
