"""Route decorators for common patterns like error handling and authentication.

This module provides reusable decorators to reduce boilerplate in route handlers.
"""
import functools
import logging
from typing import Callable

from flask import request

from fin_server.exception.UnauthorizedError import UnauthorizedError
from fin_server.utils.helpers import respond_error
from fin_server.security.authentication import get_auth_payload

logger = logging.getLogger(__name__)


def handle_errors(func: Callable) -> Callable:
    """Decorator to handle common exceptions in route handlers.

    Catches:
    - UnauthorizedError -> 401
    - ValueError with 'expired'/'invalid token' -> 401
    - ValueError -> 400
    - Other exceptions -> 500

    Usage:
        @app.route('/example')
        @handle_errors
        def example_route():
            ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except UnauthorizedError as e:
            logger.warning("Unauthorized: %s", e)
            return respond_error(str(e), status=401)
        except ValueError as e:
            msg = str(e).lower()
            if 'expired' in msg or 'invalid token' in msg or 'signature' in msg:
                logger.warning("Auth error: %s", e)
                return respond_error(str(e), status=401)
            logger.warning("Validation error: %s", e)
            return respond_error(str(e), status=400)
        except Exception as e:
            logger.exception("Unexpected error in %s", func.__name__)
            return respond_error('Server error', status=500)
    return wrapper


def require_auth(func: Callable) -> Callable:
    """Decorator to require authentication and inject payload into handler.

    The decorated function receives `auth_payload` as a keyword argument.

    Usage:
        @app.route('/protected')
        @require_auth
        def protected_route(auth_payload):
            user_key = auth_payload.get('user_key')
            ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        payload = get_auth_payload(request)
        kwargs['auth_payload'] = payload
        return func(*args, **kwargs)
    return wrapper


def require_role(*required_roles: str) -> Callable:
    """Decorator to require specific roles.

    Usage:
        @app.route('/admin-only')
        @require_role('admin')
        def admin_route(auth_payload):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            payload = get_auth_payload(request)
            user_roles = payload.get('roles', [])

            if not any(role in user_roles for role in required_roles):
                logger.warning("Access denied: required roles %s, user has %s", required_roles, user_roles)
                return respond_error('Insufficient permissions', status=403)

            kwargs['auth_payload'] = payload
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_admin(func: Callable) -> Callable:
    """Shortcut decorator to require admin role."""
    return require_role('admin')(func)


def validate_json(*required_fields: str) -> Callable:
    """Decorator to validate that required JSON fields are present.

    Usage:
        @app.route('/create', methods=['POST'])
        @validate_json('name', 'email')
        def create_item():
            data = request.get_json()
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True)

            if not data:
                return respond_error('Request body must be JSON', status=400)

            missing = [f for f in required_fields if f not in data or data[f] is None]
            if missing:
                return respond_error(f'Missing required fields: {", ".join(missing)}', status=400)

            return func(*args, **kwargs)
        return wrapper
    return decorator


def log_request(func: Callable) -> Callable:
    """Decorator to log request details."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger.info("%s %s called", request.method, request.path)
        return func(*args, **kwargs)
    return wrapper


# Composite decorators for common patterns

def protected_route(func: Callable) -> Callable:
    """Composite decorator: handle_errors + require_auth + log_request."""
    return handle_errors(require_auth(log_request(func)))


def admin_route(func: Callable) -> Callable:
    """Composite decorator: handle_errors + require_admin + log_request."""
    return handle_errors(require_admin(log_request(func)))

