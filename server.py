"""AquaFarm Pro Backend Server.

This is the main entry point for the Flask application.
"""

import argparse
import warnings
import logging

# Import config first to get logging settings
from config import config


def setup_logging():
    """Configure logging based on config settings."""
    log_format = config.LOG_FORMAT
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    date_format = config.LOG_DATE_FORMAT if config.LOG_INCLUDE_DATETIME else None

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format
    )

    # Set level for specific loggers to reduce noise
    if not config.LOG_DEBUG:
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        logging.getLogger('engineio').setLevel(logging.WARNING)
        logging.getLogger('socketio').setLevel(logging.WARNING)


# Configure logging FIRST before any other imports
setup_logging()
logger = logging.getLogger(__name__)

from flask import Flask, request, jsonify
from flask_cors import CORS
# Import blueprints from route modules
from fin_server.routes.auth import auth_bp
from fin_server.routes.user import user_bp
from fin_server.routes.task import task_bp
from fin_server.routes.company import company_bp
from fin_server.routes.pond import pond_bp
from fin_server.routes.fish import fish_bp
from fin_server.routes.pond_event import pond_event_bp
from fin_server.routes.public import public_bp
from fin_server.routes.feeding import feeding_bp
from fin_server.routes.sampling import sampling_bp
from fin_server.routes.expenses import expenses_bp
from fin_server.routes.dashboard import dashboard_bp
from fin_server.routes.role import role_bp
from fin_server.routes.notification import notification_bp
from fin_server.routes.chat import chat_bp
from fin_server.routes.ai import openai_bp
from fin_server.security.authentication import AuthSecurity
from fin_server.notification.scheduler import TaskScheduler
from fin_server.messaging.socket_server import socketio, start_notification_worker
from fin_server.websocket.hub import init_websocket_hub
from fin_server.utils.metrics import collector as metrics_collector
from fin_server.utils.helpers import respond_error
from werkzeug.exceptions import Unauthorized, Forbidden

# Suppress urllib3 warnings
try:
    from urllib3.exceptions import NotOpenSSLWarning
    warnings.filterwarnings('ignore', category=NotOpenSSLWarning)
except Exception:
    pass


def configure_auth_from_env():
    """Configure AuthSecurity from centralized config."""
    if not config.JWT_SECRET:
        raise RuntimeError('JWT_SECRET environment variable is required')

    AuthSecurity.configure(
        secret_key=config.JWT_SECRET,
        algorithm=config.JWT_ALGORITHM,
        access_token_expire_minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_token_expire_days=config.REFRESH_TOKEN_EXPIRE_DAYS,
    )


def create_app() -> Flask:
    """Application factory used by server.py and tests.

    Registers all blueprints and configures CORS.
    """
    app = Flask(__name__, template_folder='templates')
    CORS(app, resources={r"/*": {"origins": config.CORS_ORIGINS_LIST}})

    # Register canonical blueprints
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
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(role_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(openai_bp)

    # Initialize SocketIO with Flask app FIRST
    print("=" * 60)
    print("INITIALIZING SOCKETIO WITH FLASK APP")
    logger.info("=" * 60)
    logger.info("INITIALIZING SOCKETIO WITH FLASK APP")
    socketio.init_app(app, cors_allowed_origins="*", async_mode='threading')
    print(f"SocketIO initialized with async_mode: {getattr(socketio, 'async_mode', 'unknown')}")
    logger.info(f"SocketIO initialized with async_mode: {getattr(socketio, 'async_mode', 'unknown')}")
    print("=" * 60)
    logger.info("=" * 60)

    # THEN Initialize WebSocket hub for real-time notifications/alerts/chat
    print("INITIALIZING WEBSOCKET HUB")
    logger.info("INITIALIZING WEBSOCKET HUB")
    init_websocket_hub(app, socketio)
    print("WEBSOCKET HUB INITIALIZED")
    logger.info("WEBSOCKET HUB INITIALIZED")
    print("=" * 60)
    logger.info("=" * 60)

    # Error handlers
    @app.errorhandler(Unauthorized)
    def _handle_unauthorized(exc):
        return respond_error(str(exc), status=401)

    @app.errorhandler(Forbidden)
    def _handle_forbidden(exc):
        return respond_error(str(exc), status=403)

    @app.errorhandler(404)
    def _handle_not_found(exc):
        return respond_error('Resource not found', status=404)

    @app.errorhandler(500)
    def _handle_server_error(exc):
        app.logger.exception('Internal server error')
        return respond_error('Internal server error', status=500)

    # Metrics middleware
    @app.before_request
    def _metrics_before_request():
        from time import perf_counter
        request._metrics_start = perf_counter()

    @app.after_request
    def _metrics_after_request(response):
        try:
            from time import perf_counter
            start = getattr(request, '_metrics_start', None)
            duration_ms = (perf_counter() - start) * 1000.0 if start else 0.0
            route = request.endpoint or request.path
            metrics_collector.record(request.method, route, response.status_code, duration_ms)
        except Exception:
            pass
        return response


    @app.route('/metrics', methods=['GET'])
    def _metrics_endpoint():
        logger.info("Metrics endpoint called")
        return jsonify(metrics_collector.get_metrics())

    @app.route('/')
    def index():
        logger.info("Index endpoint called")
        from flask import redirect
        return redirect('/docs')

    @app.route('/docs')
    @app.route('/docs/')
    def api_docs():
        logger.info("API docs endpoint called")
        from flask import send_from_directory
        import os
        docs_dir = os.path.join(os.path.dirname(__file__), 'static', 'api_docs')
        return send_from_directory(docs_dir, 'index.html')

    @app.route('/docs/<path:filename>')
    def api_docs_static(filename):
        logger.info(f"API docs static file requested: {filename}")
        from flask import send_from_directory
        import os
        docs_dir = os.path.join(os.path.dirname(__file__), 'static', 'api_docs')
        return send_from_directory(docs_dir, filename)

    return app


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description='Run AquaFarm Pro backend server')
    parser.add_argument('--port', type=int, default=config.PORT, help='TCP port')
    parser.add_argument('--no-scheduler', action='store_true', help='Disable TaskScheduler')
    parser.add_argument('--no-worker', action='store_true', help='Disable notification worker')
    return parser.parse_args()


# Initialize at import time
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
        logger.info("=" * 70)
        logger.info("SERVER: Starting AquaFarm Pro Backend...")
        logger.info(f"SERVER: Port: {args.port}")
        logger.info(f"SERVER: Debug: {config.DEBUG}")
        logger.info(f"SERVER: CORS Origins: {config.CORS_ORIGINS}")
        logger.info("=" * 70)

        logger.info("SERVER: ★★★ WEBSOCKET READY ★★★")
        logger.info(f"SERVER: WebSocket URL: ws://localhost:{args.port}")
        logger.info(f"SERVER: WebSocket Path: /socket.io")
        logger.info("SERVER: Auth methods: auth.token, ?token=, Authorization header")
        logger.info("=" * 70)

        logger.info(f"SERVER: Starting on http://0.0.0.0:{args.port}")
        socketio.run(app, host="0.0.0.0", port=args.port, debug=config.DEBUG, allow_unsafe_werkzeug=True)
    except Exception as exc:
        logger.exception('Server failed to start: %s', exc)
