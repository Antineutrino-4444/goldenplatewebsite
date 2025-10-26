from flask import Blueprint

recorder_bp = Blueprint('recorder', __name__)

# Ensure storage initialization happens on import
from . import storage  # noqa: F401

# Register hooks and routes
from . import hooks  # noqa: F401
from . import auth_routes  # noqa: F401
from . import admin_routes  # noqa: F401
from . import session_routes  # noqa: F401
from . import csv_routes  # noqa: F401
from . import teacher_routes  # noqa: F401
from . import draw_routes  # noqa: F401
from . import superadmin_routes  # noqa: F401

__all__ = ["recorder_bp"]
