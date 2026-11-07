import logging
import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from flask import Flask, got_request_exception, send_from_directory
from flask_cors import CORS

from src.api_errors import log_api_response, note_api_exception, start_api_request
from src.routes.golden_plate_recorder_db import recorder_bp
from src.routes.golden_plate_recorder_db.db import db_session
from src.routes.golden_plate_recorder_db.map_db import map_db_session
from src.services.release_notifications import start_release_notifications
from src.services.account_lifecycle import start_account_lifecycle


app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-change-me')
app.config['API_ERROR_LOG_PATH'] = os.environ.get('API_ERROR_LOG_PATH', 'data/api_errors.sqlite3')

# Enable CORS for all routes
CORS(app, supports_credentials=True)

app.register_blueprint(recorder_bp, url_prefix='/api')
app.before_request(start_api_request)
app.after_request(log_api_response)


@got_request_exception.connect_via(app)
def _note_unhandled_api_exception(sender, exception):
    note_api_exception(exception)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path == 'api' or path.startswith('api/'):
        return {'error': 'This API endpoint could not be found.'}, 404
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404


@app.teardown_appcontext
def _shutdown_scoped_session(exception=None):
    db_session.remove()
    map_db_session.remove()


reloader_parent = (
    (__name__ == '__main__' or (
        os.environ.get('FLASK_RUN_FROM_CLI') == 'true'
        and os.environ.get('FLASK_DEBUG', '').lower() in {'1', 'true'}
    ))
    and os.environ.get('WERKZEUG_RUN_MAIN') != 'true'
)
start_release_notifications(app, reloader_parent=reloader_parent)
start_account_lifecycle(app, reloader_parent=reloader_parent)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '59237')), debug=True)
