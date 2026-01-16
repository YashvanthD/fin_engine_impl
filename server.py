"""AquaFarm Pro Backend Server.

This is the main entry point for the Flask application.
"""

import argparse
import warnings
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS

from config import config
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
    app.register_blueprint(openai_bp)

    # Initialize WebSocket hub for real-time notifications/alerts
    init_websocket_hub(app, socketio)

    logging.basicConfig(level=logging.INFO)

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

    logger = logging.getLogger(__name__)

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
        logging.info('Starting server on port %s', args.port)
        socketio.init_app(app, cors_allowed_origins=config.CORS_ORIGINS)
        socketio.run(app, host="0.0.0.0", port=args.port, debug=config.DEBUG)
    except Exception as exc:
        logging.exception('Server failed to start: %s', exc)
