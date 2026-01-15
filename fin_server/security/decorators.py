"""Permission decorators for role-based access control."""
from functools import wraps
from typing import Union, Callable
from flask import request, jsonify, g

from fin_server.security.roles import Role, Permission, has_permission


def require_auth(f: Callable) -> Callable:
    """Decorator to require authentication.

    Ensures user is logged in and sets g.current_user.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(g, 'current_user') or not g.current_user:
            return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401
        return f(*args, **kwargs)
    return decorated


def require_role(*roles: Union[str, Role]) -> Callable:
    """Decorator to require specific role(s).

    Args:
        *roles: One or more roles that are allowed

    Example:
        @require_role(Role.OWNER, Role.MANAGER)
        def admin_endpoint():
            pass
    """
    allowed_roles = set()
    for role in roles:
        if isinstance(role, Role):
            allowed_roles.add(role.value)
        else:
            allowed_roles.add(role)

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, 'current_user') or not g.current_user:
                return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401

            user_role = g.current_user.get('role', 'worker')

            if user_role not in allowed_roles:
                return jsonify({
                    'error': 'Insufficient permissions',
                    'code': 'FORBIDDEN',
                    'required_roles': list(allowed_roles),
                    'your_role': user_role
                }), 403

            return f(*args, **kwargs)
        return decorated
    return decorator


def require_permission(*permissions: Union[str, Permission]) -> Callable:
    """Decorator to require specific permission(s).

    Args:
        *permissions: One or more permissions required (ALL must be present)

    Example:
        @require_permission(Permission.POND_CREATE)
        def create_pond():
            pass

        @require_permission(Permission.EXPENSE_CREATE, Permission.EXPENSE_APPROVE)
        def create_and_approve_expense():
            pass
    """
    required_perms = set()
    for perm in permissions:
        if isinstance(perm, Permission):
            required_perms.add(perm.value)
        else:
            required_perms.add(perm)

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, 'current_user') or not g.current_user:
                return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401

            user_role = g.current_user.get('role', 'worker')
            custom_perms = set(g.current_user.get('permissions', []))

            # Check each required permission
            missing_perms = []
            for perm in required_perms:
                if not has_permission(user_role, perm, custom_perms):
                    missing_perms.append(perm)

            if missing_perms:
                return jsonify({
                    'error': 'Insufficient permissions',
                    'code': 'FORBIDDEN',
                    'missing_permissions': missing_perms,
                    'your_role': user_role
                }), 403

            return f(*args, **kwargs)
        return decorated
    return decorator


def require_any_permission(*permissions: Union[str, Permission]) -> Callable:
    """Decorator to require ANY of the specified permissions.

    Args:
        *permissions: Permissions to check (ANY one is sufficient)

    Example:
        @require_any_permission(Permission.EXPENSE_READ, Permission.REPORT_FINANCIAL)
        def view_financial_data():
            pass
    """
    required_perms = set()
    for perm in permissions:
        if isinstance(perm, Permission):
            required_perms.add(perm.value)
        else:
            required_perms.add(perm)

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, 'current_user') or not g.current_user:
                return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401

            user_role = g.current_user.get('role', 'worker')
            custom_perms = set(g.current_user.get('permissions', []))

            # Check if user has ANY of the required permissions
            for perm in required_perms:
                if has_permission(user_role, perm, custom_perms):
                    return f(*args, **kwargs)

            return jsonify({
                'error': 'Insufficient permissions',
                'code': 'FORBIDDEN',
                'required_any': list(required_perms),
                'your_role': user_role
            }), 403
        return decorated
    return decorator


def require_admin(f: Callable) -> Callable:
    """Shortcut decorator to require admin roles (Owner or Manager)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(g, 'current_user') or not g.current_user:
            return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401

        user_role = g.current_user.get('role', 'worker')

        if user_role not in Role.admin_roles():
            return jsonify({
                'error': 'Admin access required',
                'code': 'FORBIDDEN',
                'your_role': user_role
            }), 403

        return f(*args, **kwargs)
    return decorated


def require_owner(f: Callable) -> Callable:
    """Shortcut decorator to require owner role only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(g, 'current_user') or not g.current_user:
            return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401

        user_role = g.current_user.get('role', 'worker')

        if user_role != Role.OWNER.value:
            return jsonify({
                'error': 'Owner access required',
                'code': 'FORBIDDEN',
                'your_role': user_role
            }), 403

        return f(*args, **kwargs)
    return decorated


def check_own_resource(resource_user_key_field: str = 'user_key') -> Callable:
    """Decorator to check if user owns the resource or is admin.

    For restricted roles (🔒), this checks if the resource belongs to the user.
    Admins can access all resources.

    Args:
        resource_user_key_field: Field name in request data that contains owner's user_key

    Example:
        @check_own_resource('assignee')
        def get_task():
            pass
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, 'current_user') or not g.current_user:
                return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401

            user_role = g.current_user.get('role', 'worker')
            user_key = g.current_user.get('user_key')

            # Admins can access all resources
            if user_role in Role.admin_roles():
                return f(*args, **kwargs)

            # For field roles, check ownership
            resource_owner = None

            # Check in request args
            resource_owner = request.args.get(resource_user_key_field)

            # Check in request JSON
            if not resource_owner and request.is_json:
                resource_owner = request.json.get(resource_user_key_field)

            # Check in URL parameters
            if not resource_owner:
                resource_owner = kwargs.get(resource_user_key_field)

            # If no owner specified, allow (query will filter)
            if not resource_owner:
                # Set flag for query filtering
                g.filter_own_resources = True
                return f(*args, **kwargs)

            # Check if user owns the resource
            if resource_owner != user_key:
                return jsonify({
                    'error': 'Access denied to this resource',
                    'code': 'FORBIDDEN'
                }), 403

            return f(*args, **kwargs)
        return decorated
    return decorator


def check_assigned_ponds(f: Callable) -> Callable:
    """Decorator to filter pond access based on assigned ponds.

    For restricted roles, only allows access to assigned ponds.
    Sets g.allowed_ponds for query filtering.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(g, 'current_user') or not g.current_user:
            return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401

        user_role = g.current_user.get('role', 'worker')

        # Admins and analysts can see all ponds
        if user_role in {Role.OWNER.value, Role.MANAGER.value, Role.ANALYST.value, Role.ACCOUNTANT.value}:
            g.allowed_ponds = None  # No filter
            return f(*args, **kwargs)

        # Field roles can only see assigned ponds
        assigned_ponds = g.current_user.get('assigned_ponds', [])
        g.allowed_ponds = assigned_ponds if assigned_ponds else []

        # Check if specific pond is being accessed
        pond_id = kwargs.get('pond_id') or request.args.get('pond_id')
        if pond_id and assigned_ponds and pond_id not in assigned_ponds:
            return jsonify({
                'error': 'Access denied to this pond',
                'code': 'FORBIDDEN'
            }), 403

        return f(*args, **kwargs)
    return decorated


def log_permission_check(f: Callable) -> Callable:
    """Decorator to log permission checks for auditing."""
    @wraps(f)
    def decorated(*args, **kwargs):
        import logging
        logger = logging.getLogger('permissions')

        user_key = getattr(g, 'current_user', {}).get('user_key', 'unknown')
        user_role = getattr(g, 'current_user', {}).get('role', 'unknown')
        endpoint = request.endpoint
        method = request.method

        logger.info(f"Permission check: user={user_key} role={user_role} endpoint={endpoint} method={method}")

        return f(*args, **kwargs)
    return decorated

