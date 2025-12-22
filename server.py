import argparse
import os
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

try:
    # urllib3 v2 issues a NotOpenSSLWarning when the ssl module uses LibreSSL.
    # We suppress this specific warning here; for production prefer rebuilding Python
    # against OpenSSL 1.1.1+ or pinning urllib3 to a compatible 1.x release.
    from urllib3.exceptions import NotOpenSSLWarning
    warnings.filterwarnings('ignore', category=NotOpenSSLWarning)
except Exception:
    # If urllib3 or the warning class is unavailable, ignore and continue
    pass

# Allow debug mode to be controlled by environment variable FLASK_DEBUG (true/false)
APP_DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() in ('1', 'true', 'yes')


def configure_auth_from_env():
    """Configure AuthSecurity from environment variables.

    JWT_SECRET (required): secret key for signing tokens.
    JWT_ALGORITHM (optional): default HS256.
    ACCESS_TOKEN_MINUTES (optional): default 7 days.
    REFRESH_TOKEN_DAYS (optional): default 90 days.
    """
    secret = os.getenv('JWT_SECRET')
    if not secret:
        # Fail fast in production; for local dev you can set a simple value.
        raise RuntimeError('JWT_SECRET environment variable is required')
    algorithm = os.getenv('JWT_ALGORITHM', 'HS256')
    access_minutes = int(os.getenv('ACCESS_TOKEN_MINUTES', str(7 * 24 * 60)))
    refresh_days = int(os.getenv('REFRESH_TOKEN_DAYS', '90'))
    AuthSecurity.configure(
        secret_key=secret,
        algorithm=algorithm,
        access_token_expire_minutes=access_minutes,
        refresh_token_expire_days=refresh_days,
    )


def create_app() -> Flask:
    """Application factory used by server.py and tests.

    Registers all blueprints and configures CORS. Auth/JWT is configured
    separately via configure_auth_from_env().
    """
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
    def index():  # type: ignore[func-returns-value]
        return render_template('API_DOC.html')

    return app


def parse_args():
    """Parse simple CLI arguments for running the server.

    Supports overriding the port and disabling scheduler/worker threads
    in environments where they are managed separately.
    """
    parser = argparse.ArgumentParser(description='Run fin_engine_impl backend server')
    parser.add_argument('--port', type=int, default=int(os.getenv('PORT', '5000')), help='TCP port to bind (default: 5000 or PORT env)')
    parser.add_argument('--no-scheduler', action='store_true', help='Do not start background TaskScheduler')
    parser.add_argument('--no-worker', action='store_true', help='Do not start notification worker thread')
    return parser.parse_args()


# Initialize auth configuration and app instance at import time for backward compatibility
configure_auth_from_env()
app = create_app()


if __name__ == "__main__":
    args = parse_args()
    if not args.no_scheduler:
        scheduler = TaskScheduler(interval_seconds=60)
        scheduler.start()
    if not args.no_worker:
        start_notification_worker()
    try:
        logging.info('Starting server with Socket.IO on port %s', args.port)
        socketio.init_app(app, cors_allowed_origins="*")
        socketio.run(app, host="0.0.0.0", port=args.port, debug=APP_DEBUG)
    except Exception as exc:
        logging.exception('Socket.IO server failed to start (falling back to Flask.run): %s', exc)
        app.run(host="0.0.0.0", port=args.port, debug=APP_DEBUG)
