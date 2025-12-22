import warnings
from flask import Flask, render_template
from flask_cors import CORS
# Register canonical blueprints and their API blueprints from route modules
from fin_server.routes.auth import auth_bp, auth_api_bp
from fin_server.routes.user import user_bp, user_api_bp
from fin_server.routes.task import task_bp, task_api_bp
from fin_server.routes.company import company_bp
from fin_server.routes.pond import pond_bp, pond_api_bp
from fin_server.routes.fish import fish_bp
from fin_server.routes.pond_event import pond_event_bp
from fin_server.routes.public import public_bp
from fin_server.routes.feeding import feeding_bp, feeding_api_bp
from fin_server.routes.sampling import sampling_bp, sampling_api_bp
from fin_server.security.authentication import AuthSecurity
from fin_server.notification.scheduler import TaskScheduler
from fin_server.messaging.socket_server import socketio, start_notification_worker
import logging
import os

try:
    # urllib3 v2 issues a NotOpenSSLWarning when the ssl module uses LibreSSL.
    # We suppress this specific warning here; for production prefer rebuilding Python
    # against OpenSSL 1.1.1+ or pinning urllib3 to a compatible 1.x release.
    from urllib3.exceptions import NotOpenSSLWarning
    warnings.filterwarnings('ignore', category=NotOpenSSLWarning)
except Exception:
    # If urllib3 or the warning class is unavailable, ignore and continue
    pass

# Set your JWT secret key here (use a secure random string in production)
# Access token set to 7 days (in minutes) and refresh token set to ~90 days (3 months)
AuthSecurity.configure(
    secret_key="your-very-secret-key",
    algorithm="HS256",
    access_token_expire_minutes=7 * 24 * 60,   # 7 days
    refresh_token_expire_days=90               # ~3 months
)

# Allow debug mode to be controlled by environment variable FLASK_DEBUG (true/false)
debug_env = os.getenv('FLASK_DEBUG', 'false').lower()
APP_DEBUG = debug_env in ('1', 'true', 'yes')

app = Flask(__name__, template_folder='templates')
CORS(app)

# Register canonical blueprints (keep resource endpoints grouped)
app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)
app.register_blueprint(task_bp)
app.register_blueprint(company_bp)
app.register_blueprint(pond_bp)
app.register_blueprint(fish_bp)
app.register_blueprint(pond_event_bp)
app.register_blueprint(public_bp)
app.register_blueprint(feeding_bp)
app.register_blueprint(sampling_bp)

# Register API blueprints provided by modules (no ad-hoc app.add_url_rule)
app.register_blueprint(auth_api_bp)
app.register_blueprint(user_api_bp)
app.register_blueprint(task_api_bp)
app.register_blueprint(pond_api_bp)
app.register_blueprint(feeding_api_bp)
app.register_blueprint(sampling_api_bp)

logging.basicConfig(level=logging.INFO)

@app.route('/')
def index():
    return render_template('API_DOC.html')

if __name__ == "__main__":
    scheduler = TaskScheduler(interval_seconds=60)
    scheduler.start()
    start_notification_worker()
    # Use APP_DEBUG flag to enable/disable Werkzeug debugger
    # Attempt to run with Socket.IO; if initialization fails (e.g. server attribute missing
    # due to environment or library mismatch), fall back to the plain Flask development server
    # so the service still starts and serves HTTP endpoints.
    try:
        logging.info('Starting server with Socket.IO')
        socketio.run(app, host="0.0.0.0", port=5000, debug=APP_DEBUG)
    except Exception as exc:
        logging.exception('Socket.IO server failed to start (falling back to Flask.run): %s', exc)
        # Fallback to Flask's built-in server - not for production, but keeps the app running
        app.run(host="0.0.0.0", port=5000, debug=APP_DEBUG)
