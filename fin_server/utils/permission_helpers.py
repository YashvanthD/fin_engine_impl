"""Permission utility functions for role-based access control.

Uses database-backed roles and permissions from user_db collections:
- roles: Role definitions
- permissions: Permission catalog
- user_permissions: User-specific overrides
"""
from typing import Optional, List, Set, Dict, Any
from flask import g

from fin_server.repository.user.permission_repository import get_permission_repository


def get_current_user_role() -> str:
    """Get current user's role from Flask g object.

    Returns:
        Role string or 'worker' as default
    """
    if hasattr(g, 'current_user') and g.current_user:
        return g.current_user.get('role', 'worker')
    return 'worker'


def get_current_user_account_key() -> Optional[str]:
    """Get current user's account_key from Flask g object."""
    if hasattr(g, 'current_user') and g.current_user:
        return g.current_user.get('account_key')
    return None


def get_current_user_key() -> Optional[str]:
    """Get current user's user_key from Flask g object."""
    if hasattr(g, 'current_user') and g.current_user:
        return g.current_user.get('user_key')
    return None


def get_current_user_permissions() -> Set[str]:
    """Get current user's effective permissions from database.

    Returns:
        Set of permission strings
    """
    if not hasattr(g, 'current_user') or not g.current_user:
        return set()

    user_key = g.current_user.get('user_key')
    account_key = g.current_user.get('account_key')
    role = g.current_user.get('role', 'worker')

    if not user_key or not account_key:
        return set()

    repo = get_permission_repository()
    effective = repo.get_effective_permissions(user_key, account_key, role)

    return set(effective.get('effective_permissions', []))


def current_user_has_permission(permission: str) -> bool:
    """Check if current user has a specific permission.

    Args:
        permission: Permission string to check

    Returns:
        True if user has permission
    """
    if not hasattr(g, 'current_user') or not g.current_user:
        return False

    user_key = g.current_user.get('user_key')
    account_key = g.current_user.get('account_key')
    role = g.current_user.get('role', 'worker')

    if not user_key or not account_key:
        return False

    repo = get_permission_repository()
    return repo.user_has_permission(user_key, account_key, role, permission)


def current_user_has_any_permission(*permissions: str) -> bool:
    """Check if current user has any of the specified permissions.

    Args:
        *permissions: Permission strings to check

    Returns:
        True if user has at least one permission
    """
    user_perms = get_current_user_permissions()
    for perm in permissions:
        if perm.lower() in user_perms:
            return True
    return False


def current_user_has_all_permissions(*permissions: str) -> bool:
    """Check if current user has all of the specified permissions.

    Args:
        *permissions: Permission strings to check

    Returns:
        True if user has all permissions
    """
    user_perms = get_current_user_permissions()
    for perm in permissions:
        if perm.lower() not in user_perms:
            return False
    return True


def current_user_is_admin() -> bool:
    """Check if current user has admin role (owner or manager).

    Returns:
        True if user is admin
    """
    role = get_current_user_role()
    return role in {'owner', 'manager'}


def current_user_is_owner() -> bool:
    """Check if current user is owner.

    Returns:
        True if user is owner
    """
    return get_current_user_role() == 'owner'


def get_current_user_assigned_ponds() -> Optional[List[str]]:
    """Get ponds assigned to current user from database.

    Returns:
        List of pond IDs, or None if user can access all ponds
    """
    if not hasattr(g, 'current_user') or not g.current_user:
        return []

    user_key = g.current_user.get('user_key')
    account_key = g.current_user.get('account_key')
    role = g.current_user.get('role', 'worker')

    if not user_key or not account_key:
        return []

    # Admins can access all ponds
    if role in {'owner', 'manager', 'analyst', 'accountant'}:
        return None

    # Get from database
    repo = get_permission_repository()
    user_perms = repo.get_user_permissions(user_key, account_key)

    if user_perms:
        return user_perms.get('assigned_ponds', [])

    return []


def can_current_user_access_pond(pond_id: str) -> bool:
    """Check if current user can access a specific pond.

    Args:
        pond_id: Pond ID to check

    Returns:
        True if user can access pond
    """
    assigned_ponds = get_current_user_assigned_ponds()

    if assigned_ponds is None:
        return True  # Can access all ponds

    return pond_id in assigned_ponds


def filter_query_by_role(query: Dict[str, Any], pond_field: str = 'pond_id') -> Dict[str, Any]:
    """Add pond filter to query based on user's role.

    For field roles, adds filter to only show assigned ponds.
    For admin/office roles, returns query unchanged.

    Args:
        query: MongoDB query dict
        pond_field: Name of the pond ID field in the collection

    Returns:
        Modified query with pond filter if needed
    """
    assigned_ponds = get_current_user_assigned_ponds()

    if assigned_ponds is None:
        return query  # No filter needed

    if not assigned_ponds:
        # User has no assigned ponds - return impossible query
        query[pond_field] = {'$in': []}
        return query

    # Add pond filter
    query[pond_field] = {'$in': assigned_ponds}
    return query


def filter_query_by_ownership(
    query: Dict[str, Any],
    user_field: str = 'user_key'
) -> Dict[str, Any]:
    """Add user filter to query based on ownership.

    For non-admin roles, filters to only show user's own records.

    Args:
        query: MongoDB query dict
        user_field: Name of the user key field

    Returns:
        Modified query with user filter if needed
    """
    if current_user_is_admin():
        return query

    if hasattr(g, 'current_user') and g.current_user:
        query[user_field] = g.current_user.get('user_key')

    return query


def get_permission_summary() -> Dict[str, Any]:
    """Get a summary of current user's permissions.

    Returns:
        Dict with role info and permission summary
    """
    if not hasattr(g, 'current_user') or not g.current_user:
        return {
            'authenticated': False,
            'role': None,
            'permissions': []
        }

    role = g.current_user.get('role', 'worker')
    permissions = get_current_user_permissions()

    return {
        'authenticated': True,
        'role': role,
        'is_admin': role in {'owner', 'manager'},
        'is_owner': role == 'owner',
        'permission_count': len(permissions),
        'assigned_ponds': get_current_user_assigned_ponds(),
        'can_manage_users': current_user_has_permission('user:create'),
        'can_manage_ponds': current_user_has_permission('pond:create'),
        'can_manage_finances': current_user_has_permission('expense:approve'),
        'can_create_reports': current_user_has_permission('report:create'),
    }


def role_can_create_role(creator_role: str, target_role: str, account_key: Optional[str] = None) -> bool:
    """Check if a role can create another role.

    Args:
        creator_role: Role of the user creating
        target_role: Role being created
        account_key: Account context

    Returns:
        True if creation is allowed
    """
    if creator_role == 'owner':
        return True

    if creator_role == 'manager':
        return target_role not in {'owner', 'manager'}

    return False


def get_creatable_roles(creator_role: str, account_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get list of roles that a role can create.

    Args:
        creator_role: Role of the creator
        account_key: Account context

    Returns:
        List of role documents that can be created
    """
    repo = get_permission_repository()
    all_roles = repo.get_all_roles(account_key)

    if creator_role == 'owner':
        return all_roles

    if creator_role == 'manager':
        return [r for r in all_roles if r.get('role_code') not in {'owner', 'manager'}]

    return []

