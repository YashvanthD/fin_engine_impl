"""Simple permission management API routes.

Endpoints for:
- Get user permissions (merged with template)
- Set/grant/revoke specific permissions
- Manage assigned ponds
"""
from flask import Blueprint, request, jsonify, g
import logging

from fin_server.security.decorators import require_auth, require_admin
from fin_server.services.permission_service import get_permission_service

permission_bp = Blueprint('permission', __name__, url_prefix='/api/permission')

service = get_permission_service()

logger = logging.getLogger(__name__)


# =============================================================================
# GET PERMISSIONS
# =============================================================================

@permission_bp.route('/my', methods=['GET'])
@require_auth
def get_my_permissions():
    """Get current user's effective permissions.

    Returns:
        Full permissions object with all features and flags
    """
    user = g.current_user

    permissions = service.get_user_permissions(
        user_key=user.get('user_key'),
        account_key=user.get('account_key'),
        role=user.get('role', 'worker')
    )

    return jsonify({
        'role': user.get('role', 'worker'),
        'permissions': permissions
    }), 200


@permission_bp.route('/user/<user_key>', methods=['GET'])
@require_auth
@require_admin
def get_user_permissions(user_key: str):
    """Get a user's effective permissions.

    Returns:
        Full permissions object with all features and flags
    """
    current_user = g.current_user

    # Get user's role from users collection
    from fin_server.repository.user.role_repository import get_role_repository
    role_repo = get_role_repository()
    user_info = role_repo.get_user_role(user_key)
    role = user_info.get('role', 'worker') if user_info else 'worker'

    permissions = service.get_user_permissions(
        user_key=user_key,
        account_key=current_user.get('account_key'),
        role=role
    )

    return jsonify({
        'user_key': user_key,
        'role': role,
        'permissions': permissions
    }), 200


@permission_bp.route('/user/<user_key>/overrides', methods=['GET'])
@require_auth
@require_admin
def get_user_overrides(user_key: str):
    """Get only the user's permission overrides (what's stored in DB).

    Returns:
        Sparse permissions - only True values
    """
    current_user = g.current_user

    overrides = service.get_user_permission_overrides(
        user_key=user_key,
        account_key=current_user.get('account_key')
    )

    return jsonify({
        'user_key': user_key,
        'overrides': overrides
    }), 200


# =============================================================================
# CHECK PERMISSIONS
# =============================================================================

@permission_bp.route('/check', methods=['POST'])
@require_auth
def check_permission():
    """Check if current user has specific permission(s).

    Request Body:
        {
            "feature": "pond_manage",
            "flag": "edit"  // optional, default: "view"
        }

        OR for multiple checks:
        {
            "checks": [
                {"feature": "pond_manage", "flag": "edit"},
                {"feature": "expense_manage", "flag": "view"}
            ]
        }

    Returns:
        {"allowed": true/false} or {"results": [...]}
    """
    data = request.get_json() or {}
    user = g.current_user

    account_key = request.headers.get('account_key')
    user_key = request.headers.get('user_key')
    logger.info(f"Checking permissions for account_key={account_key}, user_key={user_key}, data={data}")

    # Single check
    if 'feature' in data:
        allowed = service.has_permission(
            user_key=user.get('user_key'),
            account_key=user.get('account_key'),
            role=user.get('role', 'worker'),
            feature=data['feature'],
            flag=data.get('flag', 'view')
        )
        return jsonify({'allowed': allowed}), 200

    # Multiple checks
    if 'checks' in data:
        results = []
        for check in data['checks']:
            allowed = service.has_permission(
                user_key=user.get('user_key'),
                account_key=user.get('account_key'),
                role=user.get('role', 'worker'),
                feature=check.get('feature'),
                flag=check.get('flag', 'view')
            )
            results.append({
                'feature': check.get('feature'),
                'flag': check.get('flag', 'view'),
                'allowed': allowed
            })
        return jsonify({'results': results}), 200

    return jsonify({'error': 'feature or checks required'}), 400


# =============================================================================
# SET PERMISSIONS
# =============================================================================

@permission_bp.route('/grant', methods=['POST'])
@require_auth
@require_admin
def grant_permission():
    """Grant a feature to a user.

    Request Body:
        {
            "user_key": "123456789012",
            "feature": "expense_approve",
            "edit": true,
            "view": true
        }

    Returns:
        {"success": true}
    """
    data = request.get_json() or {}
    current_user = g.current_user

    user_key = data.get('user_key') or data.get('userKey')
    feature = data.get('feature')

    if not user_key:
        return jsonify({'error': 'user_key required'}), 400
    if not feature:
        return jsonify({'error': 'feature required'}), 400

    success = service.grant_feature(
        user_key=user_key,
        account_key=current_user.get('account_key'),
        feature=feature,
        set_by=current_user.get('user_key'),
        edit=data.get('edit', False),
        view=data.get('view', True)
    )

    if success:
        return jsonify({'success': True, 'message': f'Granted {feature}'}), 200
    return jsonify({'error': 'Failed to grant permission'}), 400


@permission_bp.route('/revoke', methods=['POST'])
@require_auth
@require_admin
def revoke_permission():
    """Revoke a feature from a user.

    Request Body:
        {
            "user_key": "123456789012",
            "feature": "expense_approve"
        }

    Returns:
        {"success": true}
    """
    data = request.get_json() or {}
    current_user = g.current_user

    user_key = data.get('user_key') or data.get('userKey')
    feature = data.get('feature')

    if not user_key:
        return jsonify({'error': 'user_key required'}), 400
    if not feature:
        return jsonify({'error': 'feature required'}), 400

    success = service.revoke_feature(
        user_key=user_key,
        account_key=current_user.get('account_key'),
        feature=feature,
        set_by=current_user.get('user_key')
    )

    if success:
        return jsonify({'success': True, 'message': f'Revoked {feature}'}), 200
    return jsonify({'error': 'Failed to revoke permission'}), 400


@permission_bp.route('/set', methods=['POST'])
@require_auth
@require_admin
def set_permissions():
    """Set specific permission flags for a user.

    Request Body:
        {
            "user_key": "123456789012",
            "feature": "pond_manage",
            "flags": {
                "enabled": true,
                "entitled": true,
                "edit": true,
                "view": true
            }
        }

    Returns:
        {"success": true}
    """
    data = request.get_json() or {}
    current_user = g.current_user

    user_key = data.get('user_key') or data.get('userKey')
    feature = data.get('feature')
    flags = data.get('flags', {})

    if not user_key:
        return jsonify({'error': 'user_key required'}), 400
    if not feature:
        return jsonify({'error': 'feature required'}), 400
    if not flags:
        return jsonify({'error': 'flags required'}), 400

    success = service.set_user_permission(
        user_key=user_key,
        account_key=current_user.get('account_key'),
        feature=feature,
        flags=flags,
        set_by=current_user.get('user_key')
    )

    if success:
        return jsonify({'success': True}), 200
    return jsonify({'error': 'Failed to set permission'}), 400


@permission_bp.route('/set-bulk', methods=['POST'])
@require_auth
@require_admin
def set_bulk_permissions():
    """Set multiple permissions at once.

    Request Body:
        {
            "user_key": "123456789012",
            "permissions": {
                "pond_manage": {"edit": true, "view": true},
                "expense_manage": {"view": true}
            }
        }

    Returns:
        {"success": true}
    """
    data = request.get_json() or {}
    current_user = g.current_user

    user_key = data.get('user_key') or data.get('userKey')
    permissions = data.get('permissions', {})

    if not user_key:
        return jsonify({'error': 'user_key required'}), 400
    if not permissions:
        return jsonify({'error': 'permissions required'}), 400

    success = service.set_bulk_permissions(
        user_key=user_key,
        account_key=current_user.get('account_key'),
        permissions=permissions,
        set_by=current_user.get('user_key')
    )

    if success:
        return jsonify({'success': True}), 200
    return jsonify({'error': 'Failed to set permissions'}), 400


# =============================================================================
# POND ASSIGNMENT
# =============================================================================

@permission_bp.route('/assign-ponds', methods=['POST'])
@require_auth
@require_admin
def assign_ponds():
    """Assign ponds to a user.

    Request Body:
        {
            "user_key": "123456789012",
            "pond_ids": ["pond1", "pond2"]
        }

    Returns:
        {"success": true}
    """
    data = request.get_json() or {}
    current_user = g.current_user

    user_key = data.get('user_key') or data.get('userKey')
    pond_ids = data.get('pond_ids') or data.get('pondIds') or []

    if not user_key:
        return jsonify({'error': 'user_key required'}), 400

    success = service.set_assigned_ponds(
        user_key=user_key,
        account_key=current_user.get('account_key'),
        pond_ids=pond_ids,
        set_by=current_user.get('user_key')
    )

    if success:
        return jsonify({'success': True, 'message': f'Assigned {len(pond_ids)} pond(s)'}), 200
    return jsonify({'error': 'Failed to assign ponds'}), 400


@permission_bp.route('/my-ponds', methods=['GET'])
@require_auth
def get_my_ponds():
    """Get current user's assigned ponds.

    Returns:
        {"ponds": [...]} or {"ponds": null} if can access all
    """
    user = g.current_user

    ponds = service.get_assigned_ponds(
        user_key=user.get('user_key'),
        account_key=user.get('account_key'),
        role=user.get('role', 'worker')
    )

    return jsonify({'ponds': ponds}), 200


# =============================================================================
# REFERENCE DATA
# =============================================================================

@permission_bp.route('/template', methods=['GET'])
@require_auth
def get_template():
    """Get the permission template (for reference).

    Returns:
        Full template with all features and their default flags
    """
    return jsonify({
        'template': service.get_permission_template(),
        'features': service.get_all_features()
    }), 200


@permission_bp.route('/roles', methods=['GET'])
@require_auth
def get_roles():
    """Get available roles and their default permissions.

    Returns:
        List of roles with their default permissions
    """
    roles = []
    for role in service.get_available_roles():
        roles.append({
            'role': role,
            'permissions': service.get_role_default_permissions(role)
        })

    return jsonify({'roles': roles}), 200


@permission_bp.route('/role/<role>', methods=['GET'])
@require_auth
def get_role_permissions(role: str):
    """Get default permissions for a specific role.

    Returns:
        Permissions for the role
    """
    if role not in service.get_available_roles():
        return jsonify({'error': f'Unknown role: {role}'}), 404

    return jsonify({
        'role': role,
        'permissions': service.get_role_default_permissions(role)
    }), 200

