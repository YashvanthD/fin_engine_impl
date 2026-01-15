"""Role service for managing user roles and permissions.

This service uses database-backed roles and permissions from:
- roles collection: Role definitions
- permissions collection: Permission catalog
- user_permissions collection: User-specific overrides
- permission_requests collection: Access requests

Falls back to JSON file defaults if database is empty.
"""
import logging
from typing import Optional, Dict, Any, List, Tuple

from fin_server.repository.user.permission_repository import get_permission_repository, PermissionRepository
from fin_server.repository.user.role_repository import get_role_repository, RoleRepository

logger = logging.getLogger(__name__)


def _get_defaults():
    """Lazy import defaults to avoid circular imports."""
    try:
        from config.defaults import defaults
        return defaults
    except ImportError:
        return None


class RoleService:
    """Service for role and permission management using database-backed storage."""

    def __init__(
        self,
        perm_repo: Optional[PermissionRepository] = None,
        role_repo: Optional[RoleRepository] = None
    ):
        self.perm_repo = perm_repo or get_permission_repository()
        self.role_repo = role_repo or get_role_repository()

    # =========================================================================
    # ROLE OPERATIONS
    # =========================================================================

    def create_role(
        self,
        role_code: str,
        name: str,
        description: str,
        permissions: List[str],
        level: int,
        account_key: Optional[str],
        created_by: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Create a new role.

        Args:
            role_code: Unique role code
            name: Display name
            description: Role description
            permissions: List of permission codes
            level: Hierarchy level (1=highest)
            account_key: Account scope (None for global)
            created_by: User creating the role

        Returns:
            Tuple of (success, message, role_doc)
        """
        # Validate permissions exist
        for perm in permissions:
            if not self.perm_repo.get_permission(perm):
                return False, f"Invalid permission: {perm}", None

        role = self.perm_repo.create_role(
            role_code=role_code,
            name=name,
            description=description,
            permissions=permissions,
            level=level,
            account_key=account_key,
            created_by=created_by
        )

        if role:
            return True, f"Role '{role_code}' created successfully", role
        return False, "Failed to create role", None

    def get_role(self, role_code: str, account_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get role by code. Falls back to defaults if not in DB."""
        role = self.perm_repo.get_role(role_code, account_key)
        if role:
            return role

        # Fallback to defaults
        defaults = _get_defaults()
        if defaults:
            for r in defaults.get_roles():
                if r.get('role_code') == role_code:
                    return r
        return None

    def get_all_roles(self, account_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all available roles. Falls back to defaults if DB is empty."""
        roles = self.perm_repo.get_all_roles(account_key, include_global=True)
        if roles:
            return roles

        # Fallback to defaults
        defaults = _get_defaults()
        if defaults:
            return defaults.get_roles()
        return []

    def update_role_permissions(
        self,
        role_code: str,
        permissions: List[str],
        account_key: Optional[str],
        updated_by: str
    ) -> Tuple[bool, str]:
        """Update a role's permissions."""
        # Validate permissions
        for perm in permissions:
            if not self.perm_repo.get_permission(perm):
                return False, f"Invalid permission: {perm}"

        success = self.perm_repo.update_role(
            role_code=role_code,
            updates={'permissions': permissions},
            account_key=account_key,
            updated_by=updated_by
        )

        if success:
            return True, "Role permissions updated"
        return False, "Failed to update role"

    def delete_role(
        self,
        role_code: str,
        account_key: Optional[str],
        deleted_by: str
    ) -> Tuple[bool, str]:
        """Delete a role (soft delete)."""
        success = self.perm_repo.delete_role(
            role_code=role_code,
            account_key=account_key,
            deleted_by=deleted_by
        )

        if success:
            return True, "Role deleted"
        return False, "Failed to delete role (may be a system role)"

    # =========================================================================
    # PERMISSION CATALOG OPERATIONS
    # =========================================================================

    def create_permission(
        self,
        permission_code: str,
        name: str,
        description: str,
        category: str,
        account_key: Optional[str],
        created_by: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Create a new permission."""
        perm = self.perm_repo.create_permission(
            permission_code=permission_code,
            name=name,
            description=description,
            category=category,
            account_key=account_key,
            created_by=created_by
        )

        if perm:
            return True, f"Permission '{permission_code}' created", perm
        return False, "Failed to create permission", None

    def get_all_permissions(self, account_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all permissions."""
        return self.perm_repo.get_all_permissions(account_key)

    def get_permissions_by_category(self, account_key: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get permissions grouped by category."""
        return self.perm_repo.get_permissions_by_category(account_key)

    # =========================================================================
    # USER ROLE ASSIGNMENT
    # =========================================================================

    def assign_role(
        self,
        user_key: str,
        new_role: str,
        assigned_by: str,
        assigner_role: str,
        account_key: str,
        reason: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Assign a role to a user.

        Args:
            user_key: User to assign role to
            new_role: Role code to assign
            assigned_by: User making the assignment
            assigner_role: Role of the assigner
            account_key: Account context
            reason: Reason for assignment

        Returns:
            Tuple of (success, message)
        """
        # Validate role exists
        role = self.perm_repo.get_role(new_role, account_key)
        if not role:
            return False, f"Invalid role: {new_role}"

        # Check if assigner can assign this role
        assigner_role_doc = self.perm_repo.get_role(assigner_role, account_key)
        if not assigner_role_doc:
            return False, "Invalid assigner role"

        # Assigner must have higher level (lower number) than target role
        if assigner_role_doc.get('level', 99) >= role.get('level', 0):
            if assigner_role != 'owner':  # Owner can assign any role
                return False, "Cannot assign role at same or higher level than your own"

        # Update user's role in users collection
        success = self.role_repo.update_user_role(
            user_key=user_key,
            role=new_role,
            assigned_by=assigned_by,
            reason=reason
        )

        if success:
            return True, f"Role '{new_role}' assigned successfully"
        return False, "Failed to assign role"

    # =========================================================================
    # USER PERMISSION OPERATIONS
    # =========================================================================

    def get_user_effective_permissions(
        self,
        user_key: str,
        account_key: str,
        role_code: str
    ) -> Dict[str, Any]:
        """Get user's effective permissions (role + overrides)."""
        return self.perm_repo.get_effective_permissions(user_key, account_key, role_code)

    def grant_permission_to_user(
        self,
        user_key: str,
        account_key: str,
        permission_code: str,
        granted_by: str,
        granter_role: str
    ) -> Tuple[bool, str]:
        """Grant a specific permission to a user."""
        # Validate permission exists
        if not self.perm_repo.get_permission(permission_code):
            return False, f"Invalid permission: {permission_code}"

        # Check granter has permission to grant
        granter_perms = self.perm_repo.get_effective_permissions(
            granted_by, account_key, granter_role
        )
        if 'permission:grant' not in granter_perms.get('effective_permissions', []):
            return False, "You don't have permission to grant permissions"

        success = self.perm_repo.grant_permission_to_user(
            user_key=user_key,
            account_key=account_key,
            permission_code=permission_code,
            granted_by=granted_by
        )

        if success:
            return True, f"Permission '{permission_code}' granted"
        return False, "Failed to grant permission"

    def revoke_permission_from_user(
        self,
        user_key: str,
        account_key: str,
        permission_code: str,
        revoked_by: str,
        revoker_role: str
    ) -> Tuple[bool, str]:
        """Revoke a specific permission from a user."""
        # Check revoker has permission
        revoker_perms = self.perm_repo.get_effective_permissions(
            revoked_by, account_key, revoker_role
        )
        if 'permission:revoke' not in revoker_perms.get('effective_permissions', []):
            return False, "You don't have permission to revoke permissions"

        success = self.perm_repo.revoke_permission_from_user(
            user_key=user_key,
            account_key=account_key,
            permission_code=permission_code,
            revoked_by=revoked_by
        )

        if success:
            return True, f"Permission '{permission_code}' revoked"
        return False, "Failed to revoke permission"

    def check_permission(
        self,
        user_key: str,
        account_key: str,
        role_code: str,
        permission_code: str
    ) -> bool:
        """Check if user has a specific permission."""
        return self.perm_repo.user_has_permission(user_key, account_key, role_code, permission_code)

    def check_permissions(
        self,
        user_key: str,
        account_key: str,
        role_code: str,
        permissions: List[str],
        require_all: bool = True
    ) -> Tuple[bool, List[str]]:
        """Check multiple permissions.

        Returns:
            Tuple of (has_access, missing_permissions)
        """
        effective = self.perm_repo.get_effective_permissions(user_key, account_key, role_code)
        effective_perms = set(effective.get('effective_permissions', []))

        missing = [p for p in permissions if p.lower() not in effective_perms]

        if require_all:
            return len(missing) == 0, missing
        else:
            return len(missing) < len(permissions), missing

    # =========================================================================
    # POND ASSIGNMENT
    # =========================================================================

    def assign_ponds(
        self,
        user_key: str,
        account_key: str,
        pond_ids: List[str],
        assigned_by: str,
        replace: bool = False
    ) -> Tuple[bool, str]:
        """Assign ponds to a user."""
        success = self.perm_repo.assign_ponds_to_user(
            user_key=user_key,
            account_key=account_key,
            pond_ids=pond_ids,
            assigned_by=assigned_by,
            replace=replace
        )

        if success:
            return True, f"Assigned {len(pond_ids)} pond(s)"
        return False, "Failed to assign ponds"

    def get_user_assigned_ponds(self, user_key: str, account_key: str) -> Optional[List[str]]:
        """Get ponds assigned to user. Returns None if user can access all."""
        user_perms = self.perm_repo.get_user_permissions(user_key, account_key)
        return user_perms.get('assigned_ponds') if user_perms else None

    # =========================================================================
    # PERMISSION REQUESTS
    # =========================================================================

    def request_permission(
        self,
        user_key: str,
        account_key: str,
        permission_code: str,
        reason: str,
        duration: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Create a permission access request."""
        # Validate permission exists
        if not self.perm_repo.get_permission(permission_code):
            return False, f"Invalid permission: {permission_code}", None

        request = self.perm_repo.create_permission_request(
            user_key=user_key,
            account_key=account_key,
            permission_code=permission_code,
            reason=reason,
            requested_duration=duration
        )

        if request:
            return True, "Permission request submitted", request
        return False, "Failed to submit request", None

    def get_pending_requests(
        self,
        account_key: str,
        permission_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get pending permission requests."""
        return self.perm_repo.get_pending_requests(account_key, permission_code)

    def get_user_requests(self, user_key: str, account_key: str) -> List[Dict[str, Any]]:
        """Get user's permission requests."""
        return self.perm_repo.get_user_requests(user_key, account_key)

    def approve_request(
        self,
        request_id: str,
        reviewed_by: str,
        notes: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Approve a permission request."""
        success = self.perm_repo.approve_request(
            request_id=request_id,
            reviewed_by=reviewed_by,
            notes=notes
        )

        if success:
            return True, "Request approved"
        return False, "Failed to approve request"

    def reject_request(
        self,
        request_id: str,
        reviewed_by: str,
        notes: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Reject a permission request."""
        success = self.perm_repo.reject_request(
            request_id=request_id,
            reviewed_by=reviewed_by,
            notes=notes
        )

        if success:
            return True, "Request rejected"
        return False, "Failed to reject request"

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def get_role_hierarchy(self) -> List[Dict[str, Any]]:
        """Get all roles sorted by hierarchy level."""
        roles = self.perm_repo.get_all_roles()
        return sorted(roles, key=lambda r: r.get('level', 99))

    def can_user_assign_role(
        self,
        assigner_role: str,
        target_role: str,
        account_key: Optional[str] = None
    ) -> bool:
        """Check if a role can assign another role."""
        assigner = self.perm_repo.get_role(assigner_role, account_key)
        target = self.perm_repo.get_role(target_role, account_key)

        if not assigner or not target:
            return False

        # Owner can assign any role
        if assigner.get('role_code') == 'owner':
            return True

        # Otherwise, assigner must have higher level (lower number)
        return assigner.get('level', 99) < target.get('level', 0)



# Singleton instance
_role_service_instance: Optional[RoleService] = None


def get_role_service() -> RoleService:
    """Get singleton RoleService instance."""
    global _role_service_instance
    if _role_service_instance is None:
        _role_service_instance = RoleService()
    return _role_service_instance

