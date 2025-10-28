from flask import Blueprint

recorder_bp = Blueprint('recorder', __name__)

from .schools import (
    bootstrap_global_state,
    ensure_global_admins_from_school,
    sync_global_superadmin_user,
)
from .db import set_default_school_id
from .users import ensure_default_superadmin

_default_school = bootstrap_global_state()
_default_superadmin = ensure_default_superadmin()
set_default_school_id(_default_school.id)
if _default_superadmin is not None:
    sync_global_superadmin_user(_default_superadmin)
ensure_global_admins_from_school(_default_school)

# Ensure storage initialization happens after default context is configured
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
