from flask import jsonify

from . import recorder_bp
from .app_config import serialize_app_environment


@recorder_bp.route('/app/environment', methods=['GET'])
def app_environment():
    return jsonify({
        'status': 'success',
        **serialize_app_environment(),
    }), 200


__all__ = []
