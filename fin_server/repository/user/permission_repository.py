"""Permission repository for flexible role-based access control.

Collections in user_db:
- roles: Role definitions with default permissions
- permissions: Permission definitions (catalog)
- user_permissions: User-specific permission overrides
- permission_requests: Access requests from users
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from fin_server.repository.mongo_helper import get_collection
from fin_server.utils.time_utils import get_time_date_dt
from fin_server.utils.generator import generate_uuid_hex

logger = logging.getLogger(__name__)


class PermissionRepository:
    """Repository for managing permissions in MongoDB."""

    def __init__(self):
        self._roles_collection = None
        self._permissions_collection = None
        self._user_permissions_collection = None
        self._permission_requests_collection = None
        self._audit_collection = None

    @property
    def roles_collection(self):
        """Get roles collection."""
        if self._roles_collection is None:
            self._roles_collection = get_collection('roles')
        return self._roles_collection

    @property
    def permissions_collection(self):
        """Get permissions collection."""
        if self._permissions_collection is None:
            self._permissions_collection = get_collection('permissions')
        return self._permissions_collection

    @property
    def user_permissions_collection(self):
        """Get user_permissions collection."""
        if self._user_permissions_collection is None:
            self._user_permissions_collection = get_collection('user_permissions')
        return self._user_permissions_collection

    @property
    def permission_requests_collection(self):
        """Get permission_requests collection."""
        if self._permission_requests_collection is None:
            self._permission_requests_collection = get_collection('permission_requests')
        return self._permission_requests_collection

    @property
    def audit_collection(self):
        """Get audit_log collection."""
        if self._audit_collection is None:
            self._audit_collection = get_collection('audit_log')
        return self._audit_collection

    # =========================================================================
    # ROLE OPERATIONS
    # =========================================================================

    def create_role(
        self,
        role_code: str,
        name: str,
        description: str,
        permissions: List[str],
        level: int = 10,
        account_key: Optional[str] = None,
        created_by: str = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new role.

        Args:
            role_code: Unique role identifier (e.g., 'supervisor', 'custom_role_1')
            name: Display name
            description: Role description
            permissions: List of permission codes
            level: Hierarchy level (1=highest, 10=lowest)
            account_key: If set, role is account-specific. If None, it's global.
            created_by: User who created the role
            metadata: Additional metadata

        Returns:
            Created role document
        """
        if not self.roles_collection:
            logger.warning('Roles collection not available')
            return None

        try:
            role_id = generate_uuid_hex(24)
            now = get_time_date_dt(include_time=True)

            role_doc = {
                '_id': role_id,
                'role_id': role_id,
                'role_code': role_code.lower(),
                'name': name,
                'description': description,
                'permissions': permissions,
                'level': level,
                'scope': 'account' if account_key else 'global',
                'account_key': account_key,
                'is_system': False,  # System roles cannot be deleted
                'active': True,
                'created_by': created_by,
                'created_at': now,
                'updated_at': now,
                'metadata': metadata or {}
            }

            self.roles_collection.insert_one(role_doc)
            logger.info(f"Created role: {role_code}")
            return role_doc
        except Exception as e:
            logger.exception(f"Error creating role: {e}")
            return None

    def get_role(self, role_code: str, account_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get role by code.

        First checks for account-specific role, then falls back to global.
        """
        if not self.roles_collection:
            return None

        try:
            # First try account-specific role
            if account_key:
                role = self.roles_collection.find_one({
                    'role_code': role_code.lower(),
                    'account_key': account_key,
                    'active': True
                })
                if role:
                    return role

            # Fall back to global role
            role = self.roles_collection.find_one({
                'role_code': role_code.lower(),
                'scope': 'global',
                'active': True
            })
            return role
        except Exception as e:
            logger.exception(f"Error getting role: {e}")
            return None

    def get_all_roles(self, account_key: Optional[str] = None, include_global: bool = True) -> List[Dict[str, Any]]:
        """Get all available roles for an account. Falls back to defaults."""
        roles = []

        if self.roles_collection:
            try:
                query = {'active': True}
                if account_key:
                    if include_global:
                        query['$or'] = [
                            {'account_key': account_key},
                            {'scope': 'global'}
                        ]
                    else:
                        query['account_key'] = account_key
                else:
                    query['scope'] = 'global'

                roles = list(self.roles_collection.find(query).sort('level', 1))
            except Exception as e:
                logger.exception(f"Error getting roles: {e}")

        # Fallback to defaults if empty
        if not roles:
            try:
                from config.defaults import defaults
                roles = defaults.get_roles()
            except Exception as e:
                logger.warning(f"Could not load default roles: {e}")

        return roles

    def update_role(
        self,
        role_code: str,
        updates: Dict[str, Any],
        account_key: Optional[str] = None,
        updated_by: str = None
    ) -> bool:
        """Update a role."""
        if not self.roles_collection:
            return False

        try:
            query = {'role_code': role_code.lower(), 'active': True}
            if account_key:
                query['account_key'] = account_key
            else:
                query['scope'] = 'global'

            updates['updated_at'] = get_time_date_dt(include_time=True)
            if updated_by:
                updates['updated_by'] = updated_by

            result = self.roles_collection.update_one(query, {'$set': updates})
            return result.modified_count > 0
        except Exception as e:
            logger.exception(f"Error updating role: {e}")
            return False

    def delete_role(self, role_code: str, account_key: Optional[str] = None, deleted_by: str = None) -> bool:
        """Soft delete a role (set active=False)."""
        if not self.roles_collection:
            return False

        try:
            query = {'role_code': role_code.lower(), 'is_system': False}
            if account_key:
                query['account_key'] = account_key

            result = self.roles_collection.update_one(query, {
                '$set': {
                    'active': False,
                    'deleted_at': get_time_date_dt(include_time=True),
                    'deleted_by': deleted_by
                }
            })
            return result.modified_count > 0
        except Exception as e:
            logger.exception(f"Error deleting role: {e}")
            return False

    # =========================================================================
    # PERMISSION CATALOG OPERATIONS
    # =========================================================================

    def create_permission(
        self,
        permission_code: str,
        name: str,
        description: str,
        category: str,
        account_key: Optional[str] = None,
        created_by: str = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new permission in the catalog.

        Args:
            permission_code: Unique permission code (e.g., 'pond:create')
            name: Display name
            description: Permission description
            category: Category for grouping (e.g., 'pond', 'expense')
            account_key: If set, permission is account-specific
            created_by: User who created
            metadata: Additional metadata
        """
        if not self.permissions_collection:
            return None

        try:
            perm_id = generate_uuid_hex(24)
            now = get_time_date_dt(include_time=True)

            perm_doc = {
                '_id': perm_id,
                'permission_id': perm_id,
                'permission_code': permission_code.lower(),
                'name': name,
                'description': description,
                'category': category,
                'scope': 'account' if account_key else 'global',
                'account_key': account_key,
                'is_system': False,
                'active': True,
                'created_by': created_by,
                'created_at': now,
                'updated_at': now,
                'metadata': metadata or {}
            }

            self.permissions_collection.insert_one(perm_doc)
            logger.info(f"Created permission: {permission_code}")
            return perm_doc
        except Exception as e:
            logger.exception(f"Error creating permission: {e}")
            return None

    def get_permission(self, permission_code: str) -> Optional[Dict[str, Any]]:
        """Get permission by code."""
        if not self.permissions_collection:
            return None

        try:
            return self.permissions_collection.find_one({
                'permission_code': permission_code.lower(),
                'active': True
            })
        except Exception as e:
            logger.exception(f"Error getting permission: {e}")
            return None

    def get_all_permissions(self, account_key: Optional[str] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all permissions, optionally filtered by category. Falls back to defaults."""
        permissions = []

        if self.permissions_collection:
            try:
                query = {'active': True}
                if account_key:
                    query['$or'] = [
                        {'account_key': account_key},
                        {'scope': 'global'}
                    ]
                if category:
                    query['category'] = category

                permissions = list(self.permissions_collection.find(query).sort('category', 1))
            except Exception as e:
                logger.exception(f"Error getting permissions: {e}")

        # Fallback to defaults if empty
        if not permissions:
            try:
                from config.defaults import defaults
                permissions = defaults.get_permissions()
                if category:
                    permissions = [p for p in permissions if p.get('category') == category]
            except Exception as e:
                logger.warning(f"Could not load default permissions: {e}")

        return permissions

    def get_permissions_by_category(self, account_key: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get permissions grouped by category."""
        permissions = self.get_all_permissions(account_key)
        grouped = {}
        for perm in permissions:
            cat = perm.get('category', 'other')
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(perm)
        return grouped

    # =========================================================================
    # USER PERMISSION OPERATIONS
    # =========================================================================

    def get_user_permissions(self, user_key: str, account_key: str) -> Optional[Dict[str, Any]]:
        """Get user's permission overrides."""
        if not self.user_permissions_collection:
            return None

        try:
            return self.user_permissions_collection.find_one({
                'user_key': user_key,
                'account_key': account_key
            })
        except Exception as e:
            logger.exception(f"Error getting user permissions: {e}")
            return None

    def set_user_permissions(
        self,
        user_key: str,
        account_key: str,
        granted_permissions: List[str] = None,
        denied_permissions: List[str] = None,
        assigned_ponds: List[str] = None,
        supervisor_key: Optional[str] = None,
        set_by: str = None
    ) -> bool:
        """Set or update user's permission overrides.

        Args:
            user_key: User to update
            account_key: Account context
            granted_permissions: Additional permissions to grant
            denied_permissions: Permissions to explicitly deny
            assigned_ponds: Ponds user can access
            supervisor_key: User's supervisor
            set_by: User making the change
        """
        if not self.user_permissions_collection:
            return False

        try:
            now = get_time_date_dt(include_time=True)

            update_doc = {
                'user_key': user_key,
                'account_key': account_key,
                'updated_at': now,
                'updated_by': set_by
            }

            if granted_permissions is not None:
                update_doc['granted_permissions'] = granted_permissions
            if denied_permissions is not None:
                update_doc['denied_permissions'] = denied_permissions
            if assigned_ponds is not None:
                update_doc['assigned_ponds'] = assigned_ponds
            if supervisor_key is not None:
                update_doc['supervisor_key'] = supervisor_key

            result = self.user_permissions_collection.update_one(
                {'user_key': user_key, 'account_key': account_key},
                {
                    '$set': update_doc,
                    '$setOnInsert': {'created_at': now, 'created_by': set_by}
                },
                upsert=True
            )

            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            logger.exception(f"Error setting user permissions: {e}")
            return False

    def grant_permission_to_user(
        self,
        user_key: str,
        account_key: str,
        permission_code: str,
        granted_by: str
    ) -> bool:
        """Grant a specific permission to a user."""
        if not self.user_permissions_collection:
            return False

        try:
            now = get_time_date_dt(include_time=True)

            result = self.user_permissions_collection.update_one(
                {'user_key': user_key, 'account_key': account_key},
                {
                    '$addToSet': {'granted_permissions': permission_code.lower()},
                    '$pull': {'denied_permissions': permission_code.lower()},
                    '$set': {'updated_at': now, 'updated_by': granted_by},
                    '$setOnInsert': {'created_at': now, 'created_by': granted_by}
                },
                upsert=True
            )

            self._log_permission_change(
                user_key=user_key,
                account_key=account_key,
                action='grant',
                permission=permission_code,
                by_user=granted_by
            )

            return True
        except Exception as e:
            logger.exception(f"Error granting permission: {e}")
            return False

    def revoke_permission_from_user(
        self,
        user_key: str,
        account_key: str,
        permission_code: str,
        revoked_by: str
    ) -> bool:
        """Revoke a specific permission from a user."""
        if not self.user_permissions_collection:
            return False

        try:
            now = get_time_date_dt(include_time=True)

            result = self.user_permissions_collection.update_one(
                {'user_key': user_key, 'account_key': account_key},
                {
                    '$pull': {'granted_permissions': permission_code.lower()},
                    '$addToSet': {'denied_permissions': permission_code.lower()},
                    '$set': {'updated_at': now, 'updated_by': revoked_by},
                    '$setOnInsert': {'created_at': now, 'created_by': revoked_by}
                },
                upsert=True
            )

            self._log_permission_change(
                user_key=user_key,
                account_key=account_key,
                action='revoke',
                permission=permission_code,
                by_user=revoked_by
            )

            return True
        except Exception as e:
            logger.exception(f"Error revoking permission: {e}")
            return False

    def assign_ponds_to_user(
        self,
        user_key: str,
        account_key: str,
        pond_ids: List[str],
        assigned_by: str,
        replace: bool = False
    ) -> bool:
        """Assign ponds to a user."""
        if not self.user_permissions_collection:
            return False

        try:
            now = get_time_date_dt(include_time=True)

            if replace:
                update = {
                    '$set': {
                        'assigned_ponds': pond_ids,
                        'updated_at': now,
                        'updated_by': assigned_by
                    },
                    '$setOnInsert': {'created_at': now, 'created_by': assigned_by}
                }
            else:
                update = {
                    '$addToSet': {'assigned_ponds': {'$each': pond_ids}},
                    '$set': {'updated_at': now, 'updated_by': assigned_by},
                    '$setOnInsert': {'created_at': now, 'created_by': assigned_by}
                }

            result = self.user_permissions_collection.update_one(
                {'user_key': user_key, 'account_key': account_key},
                update,
                upsert=True
            )

            return True
        except Exception as e:
            logger.exception(f"Error assigning ponds: {e}")
            return False

    # =========================================================================
    # PERMISSION REQUEST OPERATIONS
    # =========================================================================

    def create_permission_request(
        self,
        user_key: str,
        account_key: str,
        permission_code: str,
        reason: str,
        requested_duration: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a permission access request.

        Args:
            user_key: User requesting access
            account_key: Account context
            permission_code: Permission being requested
            reason: Justification for the request
            requested_duration: Optional duration (e.g., '7d', '30d', 'permanent')
        """
        if not self.permission_requests_collection:
            return None

        try:
            request_id = generate_uuid_hex(24)
            now = get_time_date_dt(include_time=True)

            request_doc = {
                '_id': request_id,
                'request_id': request_id,
                'user_key': user_key,
                'account_key': account_key,
                'permission_code': permission_code.lower(),
                'reason': reason,
                'requested_duration': requested_duration or 'permanent',
                'status': 'pending',  # pending, approved, rejected, expired
                'created_at': now,
                'updated_at': now,
                'reviewed_by': None,
                'reviewed_at': None,
                'review_notes': None,
                'expires_at': None
            }

            self.permission_requests_collection.insert_one(request_doc)
            logger.info(f"Permission request created: {request_id}")
            return request_doc
        except Exception as e:
            logger.exception(f"Error creating permission request: {e}")
            return None

    def get_pending_requests(self, account_key: str, permission_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get pending permission requests for an account."""
        if not self.permission_requests_collection:
            return []

        try:
            query = {'account_key': account_key, 'status': 'pending'}
            if permission_code:
                query['permission_code'] = permission_code.lower()

            return list(self.permission_requests_collection.find(query).sort('created_at', -1))
        except Exception as e:
            logger.exception(f"Error getting pending requests: {e}")
            return []

    def get_user_requests(self, user_key: str, account_key: str) -> List[Dict[str, Any]]:
        """Get all requests made by a user."""
        if not self.permission_requests_collection:
            return []

        try:
            return list(self.permission_requests_collection.find({
                'user_key': user_key,
                'account_key': account_key
            }).sort('created_at', -1))
        except Exception as e:
            logger.exception(f"Error getting user requests: {e}")
            return []

    def approve_request(
        self,
        request_id: str,
        reviewed_by: str,
        notes: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> bool:
        """Approve a permission request."""
        if not self.permission_requests_collection:
            return False

        try:
            now = get_time_date_dt(include_time=True)

            # Get the request
            request = self.permission_requests_collection.find_one({'request_id': request_id})
            if not request or request.get('status') != 'pending':
                return False

            # Update request status
            result = self.permission_requests_collection.update_one(
                {'request_id': request_id},
                {'$set': {
                    'status': 'approved',
                    'reviewed_by': reviewed_by,
                    'reviewed_at': now,
                    'review_notes': notes,
                    'expires_at': expires_at,
                    'updated_at': now
                }}
            )

            if result.modified_count > 0:
                # Grant the permission
                self.grant_permission_to_user(
                    user_key=request['user_key'],
                    account_key=request['account_key'],
                    permission_code=request['permission_code'],
                    granted_by=reviewed_by
                )
                return True

            return False
        except Exception as e:
            logger.exception(f"Error approving request: {e}")
            return False

    def reject_request(
        self,
        request_id: str,
        reviewed_by: str,
        notes: Optional[str] = None
    ) -> bool:
        """Reject a permission request."""
        if not self.permission_requests_collection:
            return False

        try:
            now = get_time_date_dt(include_time=True)

            result = self.permission_requests_collection.update_one(
                {'request_id': request_id, 'status': 'pending'},
                {'$set': {
                    'status': 'rejected',
                    'reviewed_by': reviewed_by,
                    'reviewed_at': now,
                    'review_notes': notes,
                    'updated_at': now
                }}
            )

            return result.modified_count > 0
        except Exception as e:
            logger.exception(f"Error rejecting request: {e}")
            return False

    # =========================================================================
    # EFFECTIVE PERMISSIONS
    # =========================================================================

    def get_effective_permissions(self, user_key: str, account_key: str, role_code: str) -> Dict[str, Any]:
        """Get user's effective permissions combining role and user-specific overrides.

        Returns:
            Dict with:
                - role_permissions: Permissions from role
                - granted_permissions: Additional granted permissions
                - denied_permissions: Explicitly denied permissions
                - effective_permissions: Final computed permissions
                - assigned_ponds: Ponds user can access (None = all)
        """
        # Get role permissions
        role = self.get_role(role_code, account_key)
        role_permissions = set(role.get('permissions', [])) if role else set()

        # Get user-specific overrides
        user_perms = self.get_user_permissions(user_key, account_key)
        granted = set(user_perms.get('granted_permissions', [])) if user_perms else set()
        denied = set(user_perms.get('denied_permissions', [])) if user_perms else set()
        assigned_ponds = user_perms.get('assigned_ponds') if user_perms else None

        # Compute effective permissions
        effective = (role_permissions | granted) - denied

        return {
            'role': role_code,
            'role_permissions': list(role_permissions),
            'granted_permissions': list(granted),
            'denied_permissions': list(denied),
            'effective_permissions': list(effective),
            'assigned_ponds': assigned_ponds,
            'supervisor_key': user_perms.get('supervisor_key') if user_perms else None
        }

    def user_has_permission(self, user_key: str, account_key: str, role_code: str, permission_code: str) -> bool:
        """Check if user has a specific permission."""
        effective = self.get_effective_permissions(user_key, account_key, role_code)
        return permission_code.lower() in effective.get('effective_permissions', [])

    # =========================================================================
    # AUDIT LOGGING
    # =========================================================================

    def _log_permission_change(
        self,
        user_key: str,
        account_key: str,
        action: str,
        permission: str,
        by_user: str
    ):
        """Log permission change for audit trail."""
        try:
            if not self.audit_collection:
                return

            self.audit_collection.insert_one({
                'type': 'permission_change',
                'user_key': user_key,
                'account_key': account_key,
                'action': action,
                'permission': permission,
                'performed_by': by_user,
                'timestamp': get_time_date_dt(include_time=True)
            })
        except Exception as e:
            logger.exception(f"Error logging permission change: {e}")


# Singleton instance
_permission_repo_instance: Optional[PermissionRepository] = None


def get_permission_repository() -> PermissionRepository:
    """Get singleton PermissionRepository instance."""
    global _permission_repo_instance
    if _permission_repo_instance is None:
        _permission_repo_instance = PermissionRepository()
    return _permission_repo_instance

