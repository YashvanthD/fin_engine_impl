import argparse
import warnings
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

from config import config
from fin_server.repository.mongo_helper import MongoRepo
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
from fin_server.routes.expenses import expenses_bp, expenses_api_bp
from fin_server.routes.ai import openai_bp
from fin_server.security.authentication import AuthSecurity
from fin_server.notification.scheduler import TaskScheduler
from fin_server.messaging.socket_server import socketio, start_notification_worker
from fin_server.utils.metrics import collector as metrics_collector
from fin_server.utils.helpers import respond_error
from werkzeug.exceptions import Unauthorized, Forbidden
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


def configure_auth_from_env():
    """Configure AuthSecurity from centralized config.

    Uses config.JWT_SECRET, config.JWT_ALGORITHM, etc.
    """
    if not config.JWT_SECRET:
        # Fail fast in production; for local dev you can set a simple value.
        raise RuntimeError('JWT_SECRET environment variable is required')

    AuthSecurity.configure(
        secret_key=config.JWT_SECRET,
        algorithm=config.JWT_ALGORITHM,
        access_token_expire_minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_token_expire_days=config.REFRESH_TOKEN_EXPIRE_DAYS,
    )


def create_app() -> Flask:
    """Application factory used by server.py and tests.

    Registers all blueprints and configures CORS. Auth/JWT is configured
    separately via configure_auth_from_env().
    """
    app = Flask(__name__, template_folder='templates')
    # Enable CORS for all routes using config
    CORS(app, resources={r"/*": {"origins": config.CORS_ORIGINS_LIST}})

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
    app.register_blueprint(expenses_bp)

    # AI routes
    app.register_blueprint(openai_bp)

    # Register API blueprints provided by modules (no ad-hoc app.add_url_rule)
    app.register_blueprint(auth_api_bp)
    app.register_blueprint(user_api_bp)
    app.register_blueprint(task_api_bp)
    app.register_blueprint(pond_api_bp)
    app.register_blueprint(feeding_api_bp)
    app.register_blueprint(sampling_api_bp)
    app.register_blueprint(expenses_api_bp)

    logging.basicConfig(level=logging.INFO)

    # Global error handlers: return JSON error payloads for auth/permission failures
    @app.errorhandler(Unauthorized)
    def _handle_unauthorized(exc):
        try:
            return respond_error(str(exc), status=401)
        except Exception:
            app.logger.exception('Failed to handle Unauthorized')
            return respond_error('Unauthorized', status=401)

    @app.errorhandler(Forbidden)
    def _handle_forbidden(exc):
        try:
            return respond_error(str(exc), status=403)
        except Exception:
            app.logger.exception('Failed to handle Forbidden')
            return respond_error('Forbidden', status=403)

    # Middleware: record request start time and capture metrics in after_request
    @app.before_request
    def _metrics_before_request():
        # store start time in the flask global request context
        from time import perf_counter
        request._metrics_start = perf_counter()

    @app.after_request
    def _metrics_after_request(response):
        try:
            from time import perf_counter
            start = getattr(request, '_metrics_start', None)
            if start is not None:
                duration_ms = (perf_counter() - start) * 1000.0
            else:
                duration_ms = 0.0
            # Determine a route identifier: prefer endpoint (blueprint.function) if available
            route = request.endpoint or request.path
            method = request.method
            metrics_collector.record(method, route, response.status_code, duration_ms)
        except Exception:
            logging.exception('Failed to record metrics')
        return response

    @app.route('/metrics', methods=['GET'])
    def _metrics_endpoint():
        try:
            return jsonify(metrics_collector.get_metrics())
        except Exception:
            logging.exception('Failed to read metrics')
            return {}, 500

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
    parser.add_argument('--port', type=int, default=config.PORT, help='TCP port to bind (default: 5000 or PORT env)')
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
        socketio.init_app(app, cors_allowed_origins=config.CORS_ORIGINS)
        socketio.run(app, host="0.0.0.0", port=args.port, debug=config.DEBUG)
    except Exception as exc:
        logging.exception('Socket.IO server failed to start (falling back to Flask.run): %s', exc)
        app.run(host="0.0.0.0", port=args.port, debug=config.DEBUG)
