"""Role and permission management API routes.

Endpoints for:
- Role management (create, update, delete custom roles)
- Permission management (create custom permissions)
- User permission overrides (grant/revoke individual permissions)
- Permission requests (request access, approve/reject)
"""
from flask import Blueprint, request, jsonify

from fin_server.utils.decorators import handle_errors, require_auth, require_admin, require_owner
from fin_server.services.role_service import get_role_service

role_bp = Blueprint('role', __name__, url_prefix='/role')

role_service = get_role_service()


# =============================================================================
# ROLE MANAGEMENT
# =============================================================================

@role_bp.route('/roles', methods=['GET'])
@handle_errors
@require_auth
def get_all_roles(auth_payload):
    """Get all available roles.

    Returns:
        {"roles": [...]}
    """
    account_key = auth_payload.get('account_key')

    roles = role_service.get_all_roles(account_key)

    # Clean up internal fields
    for role in roles:
        role.pop('_id', None)

    return jsonify({'roles': roles}), 200


@role_bp.route('/roles', methods=['POST'])
@handle_errors
@require_admin
def create_role(auth_payload):
    """Create a new custom role.

    Request Body:
        {
            "role_code": "quality_inspector",
            "name": "Quality Inspector",
            "description": "Inspects fish quality",
            "permissions": ["pond:read", "sampling:create"],
            "level": 4
        }

    Returns:
        {"success": true, "role": {...}}
    """
    data = request.get_json() or {}

    role_code = data.get('role_code') or data.get('roleCode')
    name = data.get('name')
    description = data.get('description', '')
    permissions = data.get('permissions', [])
    level = data.get('level', 4)

    if not role_code:
        return jsonify({'error': 'role_code is required'}), 400
    if not name:
        return jsonify({'error': 'name is required'}), 400
    if not permissions:
        return jsonify({'error': 'permissions list is required'}), 400

    success, message, role = role_service.create_role(
        role_code=role_code,
        name=name,
        description=description,
        permissions=permissions,
        level=level,
        account_key=auth_payload.get('account_key'),
        created_by=auth_payload.get('user_key')
    )

    if success:
        role.pop('_id', None)
        return jsonify({'success': True, 'message': message, 'role': role}), 201
    return jsonify({'error': message}), 400


@role_bp.route('/roles/<role_code>', methods=['PUT'])
@handle_errors
@require_admin
def update_role(role_code: str, auth_payload):
    """Update a role's permissions.

    Request Body:
        {
            "permissions": ["pond:read", "sampling:create", "fish:read"]
        }

    Returns:
        {"success": true, "message": "..."}
    """
    data = request.get_json() or {}

    permissions = data.get('permissions')
    if not permissions:
        return jsonify({'error': 'permissions list is required'}), 400

    success, message = role_service.update_role_permissions(
        role_code=role_code,
        permissions=permissions,
        account_key=auth_payload.get('account_key'),
        updated_by=auth_payload.get('user_key')
    )

    if success:
        return jsonify({'success': True, 'message': message}), 200
    return jsonify({'error': message}), 400


@role_bp.route('/roles/<role_code>', methods=['DELETE'])
@handle_errors
@require_owner
def delete_role(role_code: str, auth_payload):
    """Delete a custom role (soft delete).

    Returns:
        {"success": true, "message": "..."}
    """
    success, message = role_service.delete_role(
        role_code=role_code,
        account_key=auth_payload.get('account_key'),
        deleted_by=auth_payload.get('user_key')
    )

    if success:
        return jsonify({'success': True, 'message': message}), 200
    return jsonify({'error': message}), 400


# =============================================================================
# PERMISSION CATALOG
# =============================================================================

@role_bp.route('/permissions', methods=['GET'])
@handle_errors
@require_auth
def get_all_permissions(auth_payload):
    """Get all available permissions.

    Query Params:
        - grouped: If 'true', returns permissions grouped by category

    Returns:
        {"permissions": [...]} or {"categories": {...}}
    """
    grouped = request.args.get('grouped', 'false').lower() == 'true'

    if grouped:
        categories = role_service.get_permissions_by_category(auth_payload.get('account_key'))
        return jsonify({'categories': categories}), 200
    else:
        permissions = role_service.get_all_permissions(auth_payload.get('account_key'))
        for perm in permissions:
            perm.pop('_id', None)
        return jsonify({'permissions': permissions}), 200


@role_bp.route('/permissions', methods=['POST'])
@handle_errors
@require_owner
def create_permission(auth_payload):
    """Create a new custom permission.

    Request Body:
        {
            "permission_code": "inventory:manage",
            "name": "Manage Inventory",
            "description": "Full inventory access",
            "category": "inventory"
        }

    Returns:
        {"success": true, "permission": {...}}
    """
    data = request.get_json() or {}

    permission_code = data.get('permission_code') or data.get('permissionCode')
    name = data.get('name')
    description = data.get('description', '')
    category = data.get('category', 'custom')

    if not permission_code:
        return jsonify({'error': 'permission_code is required'}), 400
    if not name:
        return jsonify({'error': 'name is required'}), 400

    success, message, perm = role_service.create_permission(
        permission_code=permission_code,
        name=name,
        description=description,
        category=category,
        account_key=auth_payload.get('account_key'),
        created_by=auth_payload.get('user_key')
    )

    if success:
        perm.pop('_id', None)
        return jsonify({'success': True, 'message': message, 'permission': perm}), 201
    return jsonify({'error': message}), 400


# =============================================================================
# ROLE ASSIGNMENT
# =============================================================================

@role_bp.route('/assign', methods=['POST'])
@handle_errors
@require_admin
def assign_role(auth_payload):
    """Assign a role to a user.

    Request Body:
        {
            "user_key": "123456789012",
            "role": "supervisor",
            "reason": "Promoted to supervisor"
        }

    Returns:
        {"success": true, "message": "..."}
    """
    data = request.get_json() or {}

    user_key = data.get('user_key') or data.get('userKey')
    new_role = data.get('role')
    reason = data.get('reason')

    if not user_key:
        return jsonify({'error': 'user_key is required'}), 400
    if not new_role:
        return jsonify({'error': 'role is required'}), 400

    success, message = role_service.assign_role(
        user_key=user_key,
        new_role=new_role,
        assigned_by=auth_payload.get('user_key'),
        assigner_role=auth_payload.get('roles', ['worker'])[0] if auth_payload.get('roles') else 'worker',
        account_key=auth_payload.get('account_key'),
        reason=reason
    )

    if success:
        return jsonify({'success': True, 'message': message}), 200
    return jsonify({'error': message}), 400


# =============================================================================
# USER PERMISSION OPERATIONS
# =============================================================================

@role_bp.route('/user/<user_key>/permissions', methods=['GET'])
@handle_errors
@require_auth
def get_user_permissions(user_key: str, auth_payload):
    """Get user's effective permissions.

    Returns:
        {
            "role": "supervisor",
            "role_permissions": [...],
            "granted_permissions": [...],
            "denied_permissions": [...],
            "effective_permissions": [...],
            "assigned_ponds": [...]
        }
    """
    # Users can view their own permissions, admins can view anyone's
    if user_key != auth_payload.get('user_key'):
        user_roles = auth_payload.get('roles', [])
        if 'owner' not in user_roles and 'manager' not in user_roles and 'admin' not in user_roles:
            return jsonify({'error': 'Cannot view other users\' permissions'}), 403

    # Get user's role from users collection
    from fin_server.repository.user.role_repository import get_role_repository
    role_repo = get_role_repository()
    user_role_info = role_repo.get_user_role(user_key)
    role_code = user_role_info.get('role', 'worker') if user_role_info else 'worker'

    permissions = role_service.get_user_effective_permissions(
        user_key=user_key,
        account_key=auth_payload.get('account_key'),
        role_code=role_code
    )

    return jsonify(permissions), 200


@role_bp.route('/my-permissions', methods=['GET'])
@handle_errors
@require_auth
def get_my_permissions(auth_payload):
    """Get current user's effective permissions."""
    permissions = role_service.get_user_effective_permissions(
        user_key=auth_payload.get('user_key'),
        account_key=auth_payload.get('account_key'),
        role_code=auth_payload.get('roles', ['worker'])[0] if auth_payload.get('roles') else 'worker'
    )

    return jsonify(permissions), 200


@role_bp.route('/check', methods=['POST'])
@handle_errors
@require_auth
def check_permissions(auth_payload):
    """Check if current user has specific permission(s).

    Request Body:
        {
            "permissions": ["pond:create", "expense:approve"],
            "require_all": true
        }

    Returns:
        {"has_access": true/false, "missing_permissions": [...]}
    """
    data = request.get_json() or {}

    permissions = data.get('permissions', [])
    require_all = data.get('require_all', True)

    if not permissions:
        return jsonify({'error': 'permissions list required'}), 400

    has_access, missing = role_service.check_permissions(
        user_key=auth_payload.get('user_key'),
        account_key=auth_payload.get('account_key'),
        role_code=auth_payload.get('roles', ['worker'])[0] if auth_payload.get('roles') else 'worker',
        permissions=permissions,
        require_all=require_all
    )

    return jsonify({
        'has_access': has_access,
        'missing_permissions': missing
    }), 200


@role_bp.route('/grant', methods=['POST'])
@handle_errors
@require_admin
def grant_permission(auth_payload):
    """Grant a specific permission to a user.

    Request Body:
        {
            "user_key": "123456789012",
            "permission": "expense:approve"
        }

    Returns:
        {"success": true, "message": "..."}
    """
    data = request.get_json() or {}

    user_key = data.get('user_key') or data.get('userKey')
    permission = data.get('permission')

    if not user_key:
        return jsonify({'error': 'user_key is required'}), 400
    if not permission:
        return jsonify({'error': 'permission is required'}), 400

    success, message = role_service.grant_permission_to_user(
        user_key=user_key,
        account_key=auth_payload.get('account_key'),
        permission_code=permission,
        granted_by=auth_payload.get('user_key'),
        granter_role=auth_payload.get('roles', ['worker'])[0] if auth_payload.get('roles') else 'worker'
    )

    if success:
        return jsonify({'success': True, 'message': message}), 200
    return jsonify({'error': message}), 400


@role_bp.route('/revoke', methods=['POST'])
@handle_errors
@require_admin
def revoke_permission(auth_payload):
    """Revoke a specific permission from a user.

    Request Body:
        {
            "user_key": "123456789012",
            "permission": "expense:approve"
        }

    Returns:
        {"success": true, "message": "..."}
    """
    data = request.get_json() or {}

    user_key = data.get('user_key') or data.get('userKey')
    permission = data.get('permission')

    if not user_key:
        return jsonify({'error': 'user_key is required'}), 400
    if not permission:
        return jsonify({'error': 'permission is required'}), 400

    success, message = role_service.revoke_permission_from_user(
        user_key=user_key,
        account_key=auth_payload.get('account_key'),
        permission_code=permission,
        revoked_by=auth_payload.get('user_key'),
        revoker_role=auth_payload.get('roles', ['worker'])[0] if auth_payload.get('roles') else 'worker'
    )

    if success:
        return jsonify({'success': True, 'message': message}), 200
    return jsonify({'error': message}), 400


# =============================================================================
# POND ASSIGNMENT
# =============================================================================

@role_bp.route('/assign-ponds', methods=['POST'])
@handle_errors
@require_admin
def assign_ponds(auth_payload):
    """Assign ponds to a user.

    Request Body:
        {
            "user_key": "123456789012",
            "pond_ids": ["pond1", "pond2"],
            "replace": false
        }

    Returns:
        {"success": true, "message": "..."}
    """
    data = request.get_json() or {}

    user_key = data.get('user_key') or data.get('userKey')
    pond_ids = data.get('pond_ids') or data.get('pondIds') or []
    replace = data.get('replace', False)

    if not user_key:
        return jsonify({'error': 'user_key is required'}), 400
    if not pond_ids:
        return jsonify({'error': 'pond_ids list is required'}), 400

    success, message = role_service.assign_ponds(
        user_key=user_key,
        account_key=auth_payload.get('account_key'),
        pond_ids=pond_ids,
        assigned_by=auth_payload.get('user_key'),
        replace=replace
    )

    if success:
        return jsonify({'success': True, 'message': message}), 200
    return jsonify({'error': message}), 400


# =============================================================================
# PERMISSION REQUESTS
# =============================================================================

@role_bp.route('/request', methods=['POST'])
@handle_errors
@require_auth
def request_permission(auth_payload):
    """Request access to a permission.

    Request Body:
        {
            "permission": "expense:approve",
            "reason": "Need to approve expenses while manager is away",
            "duration": "7d"  // optional: "7d", "30d", "permanent"
        }

    Returns:
        {"success": true, "request": {...}}
    """
    data = request.get_json() or {}

    permission = data.get('permission')
    reason = data.get('reason')
    duration = data.get('duration')

    if not permission:
        return jsonify({'error': 'permission is required'}), 400
    if not reason:
        return jsonify({'error': 'reason is required'}), 400

    success, message, req = role_service.request_permission(
        user_key=auth_payload.get('user_key'),
        account_key=auth_payload.get('account_key'),
        permission_code=permission,
        reason=reason,
        duration=duration
    )

    if success:
        req.pop('_id', None)
        return jsonify({'success': True, 'message': message, 'request': req}), 201
    return jsonify({'error': message}), 400


@role_bp.route('/requests', methods=['GET'])
@handle_errors
@require_admin
def get_pending_requests(auth_payload):
    """Get pending permission requests.

    Query Params:
        - permission: Filter by permission code

    Returns:
        {"requests": [...]}
    """
    permission = request.args.get('permission')

    requests_list = role_service.get_pending_requests(
        account_key=auth_payload.get('account_key'),
        permission_code=permission
    )

    for req in requests_list:
        req.pop('_id', None)

    return jsonify({'requests': requests_list}), 200


@role_bp.route('/my-requests', methods=['GET'])
@handle_errors
@require_auth
def get_my_requests(auth_payload):
    """Get current user's permission requests.

    Returns:
        {"requests": [...]}
    """
    requests_list = role_service.get_user_requests(
        user_key=auth_payload.get('user_key'),
        account_key=auth_payload.get('account_key')
    )

    for req in requests_list:
        req.pop('_id', None)

    return jsonify({'requests': requests_list}), 200


@role_bp.route('/requests/<request_id>/approve', methods=['POST'])
@handle_errors
@require_admin
def approve_request(request_id: str, auth_payload):
    """Approve a permission request.

    Request Body:
        {
            "notes": "Approved for vacation coverage"  // optional
        }

    Returns:
        {"success": true, "message": "..."}
    """
    data = request.get_json() or {}

    notes = data.get('notes')

    success, message = role_service.approve_request(
        request_id=request_id,
        reviewed_by=auth_payload.get('user_key'),
        notes=notes
    )

    if success:
        return jsonify({'success': True, 'message': message}), 200
    return jsonify({'error': message}), 400


@role_bp.route('/requests/<request_id>/reject', methods=['POST'])
@handle_errors
@require_admin
def reject_request(request_id: str, auth_payload):
    """Reject a permission request.

    Request Body:
        {
            "notes": "Not required for current duties"  // optional
        }

    Returns:
        {"success": true, "message": "..."}
    """
    data = request.get_json() or {}

    notes = data.get('notes')

    success, message = role_service.reject_request(
        request_id=request_id,
        reviewed_by=auth_payload.get('user_key'),
        notes=notes
    )

    if success:
        return jsonify({'success': True, 'message': message}), 200
    return jsonify({'error': message}), 400


# =============================================================================
# HIERARCHY INFO
# =============================================================================

@role_bp.route('/hierarchy', methods=['GET'])
@handle_errors
@require_auth
def get_role_hierarchy(auth_payload):
    """Get role hierarchy information.

    Returns:
        {"roles": [...]} sorted by level
    """
    hierarchy = role_service.get_role_hierarchy()

    for role in hierarchy:
        role.pop('_id', None)

    return jsonify({'roles': hierarchy}), 200

