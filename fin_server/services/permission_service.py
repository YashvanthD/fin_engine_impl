"""Simple permission service with sparse storage.

Design:
- Template file defines all features with default False
- Database stores ONLY True values (sparse)
- On read: merge template with stored values
- Simple structure: feature -> {enabled, entitled, edit, view}
"""
import logging
from typing import Optional, Dict, Any, List
import copy

from fin_server.repository.mongo_helper import get_collection
from fin_server.security.permission_template import (
    PERMISSION_TEMPLATE,
    ROLE_PERMISSION_TEMPLATES,
    get_default_permissions,
    get_role_permissions,
    get_all_features,
)
from fin_server.utils.time_utils import get_time_date_dt

logger = logging.getLogger(__name__)


class PermissionService:
    """Service for managing user permissions with sparse storage."""

    def __init__(self):
        self._user_permissions_collection = None

    @property
    def user_permissions_collection(self):
        """Collection: user_permissions - stores only True values."""
        if self._user_permissions_collection is None:
            self._user_permissions_collection = get_collection('user_permissions')
        return self._user_permissions_collection

    # =========================================================================
    # GET PERMISSIONS
    # =========================================================================

    def get_user_permissions(self, user_key: str, account_key: str, role: str) -> Dict[str, Any]:
        """Get user's effective permissions.

        Flow:
        1. Start with default template (all False)
        2. Apply role permissions (True values)
        3. Apply user-specific overrides (True values from DB)

        Args:
            user_key: User's key
            account_key: Account context
            role: User's role

        Returns:
            Full permissions dict with all features
        """
        # Step 1: Start with template
        permissions = get_default_permissions()

        # Step 2: Apply role defaults
        role_perms = ROLE_PERMISSION_TEMPLATES.get(role, {})
        for feature, flags in role_perms.items():
            if feature in permissions:
                permissions[feature].update(flags)

        # Step 3: Apply user-specific overrides from DB
        if self.user_permissions_collection:
            try:
                user_doc = self.user_permissions_collection.find_one({
                    'user_key': user_key,
                    'account_key': account_key
                })

                if user_doc and 'permissions' in user_doc:
                    # DB stores only True values, merge them
                    for feature, flags in user_doc['permissions'].items():
                        if feature in permissions:
                            permissions[feature].update(flags)
            except Exception as e:
                logger.exception(f"Error getting user permissions: {e}")

        return permissions

    def get_user_permission_overrides(self, user_key: str, account_key: str) -> Dict[str, Any]:
        """Get only the user's overrides (what's stored in DB).

        Returns:
            Sparse dict with only True values
        """
        if not self.user_permissions_collection:
            return {}

        try:
            user_doc = self.user_permissions_collection.find_one({
                'user_key': user_key,
                'account_key': account_key
            })

            if user_doc:
                return {
                    'permissions': user_doc.get('permissions', {}),
                    'assigned_ponds': user_doc.get('assigned_ponds'),
                    'supervisor_key': user_doc.get('supervisor_key'),
                    'updated_at': user_doc.get('updated_at'),
                }
            return {}
        except Exception as e:
            logger.exception(f"Error getting user overrides: {e}")
            return {}

    # =========================================================================
    # CHECK PERMISSIONS
    # =========================================================================

    def has_permission(
        self,
        user_key: str,
        account_key: str,
        role: str,
        feature: str,
        flag: str = 'view'
    ) -> bool:
        """Check if user has a specific permission flag.

        Args:
            user_key: User's key
            account_key: Account context
            role: User's role
            feature: Feature name (e.g., 'pond_manage')
            flag: Flag to check ('enabled', 'entitled', 'edit', 'view')

        Returns:
            True if permission is granted
        """
        permissions = self.get_user_permissions(user_key, account_key, role)

        if feature not in permissions:
            return False

        return permissions[feature].get(flag, False)

    def can_view(self, user_key: str, account_key: str, role: str, feature: str) -> bool:
        """Check if user can view a feature."""
        return self.has_permission(user_key, account_key, role, feature, 'view')

    def can_edit(self, user_key: str, account_key: str, role: str, feature: str) -> bool:
        """Check if user can edit a feature."""
        return self.has_permission(user_key, account_key, role, feature, 'edit')

    def is_entitled(self, user_key: str, account_key: str, role: str, feature: str) -> bool:
        """Check if user is entitled to a feature."""
        return self.has_permission(user_key, account_key, role, feature, 'entitled')

    def is_enabled(self, user_key: str, account_key: str, role: str, feature: str) -> bool:
        """Check if feature is enabled for user."""
        return self.has_permission(user_key, account_key, role, feature, 'enabled')

    # =========================================================================
    # SET PERMISSIONS (Sparse Storage)
    # =========================================================================

    def set_user_permission(
        self,
        user_key: str,
        account_key: str,
        feature: str,
        flags: Dict[str, bool],
        set_by: str
    ) -> bool:
        """Set permission flags for a user.

        Only stores True values in DB. False values are removed.

        Args:
            user_key: User to update
            account_key: Account context
            feature: Feature name
            flags: Dict with flags to set (e.g., {'edit': True, 'view': True})
            set_by: User making the change

        Returns:
            True if successful
        """
        if not self.user_permissions_collection:
            return False

        if feature not in PERMISSION_TEMPLATE:
            logger.warning(f"Unknown feature: {feature}")
            return False

        try:
            now = get_time_date_dt(include_time=True)

            # Build update - only include True values
            true_flags = {k: v for k, v in flags.items() if v is True}
            false_flags = [k for k, v in flags.items() if v is False]

            update_ops = {
                '$set': {
                    'user_key': user_key,
                    'account_key': account_key,
                    'updated_at': now,
                    'updated_by': set_by,
                },
                '$setOnInsert': {
                    'created_at': now,
                    'created_by': set_by,
                }
            }

            # Set True values
            for flag, value in true_flags.items():
                # Convert boolean values to strings to match expected types
                update_ops['$set'][f'permissions.{feature}.{flag}'] = str(value)

            # Unset False values (remove from DB)
            if false_flags:
                update_ops['$unset'] = {}
                for flag in false_flags:
                    update_ops['$unset'][f'permissions.{feature}.{flag}'] = ""

            self.user_permissions_collection.update_one(
                {'user_key': user_key, 'account_key': account_key},
                update_ops,
                upsert=True
            )

            return True
        except Exception as e:
            logger.exception(f"Error setting permission: {e}")
            return False

    def grant_feature(
        self,
        user_key: str,
        account_key: str,
        feature: str,
        set_by: str,
        edit: bool = False,
        view: bool = True
    ) -> bool:
        """Grant a feature to a user.

        Args:
            user_key: User to grant to
            account_key: Account context
            feature: Feature name
            set_by: User making the change
            edit: Grant edit access
            view: Grant view access

        Returns:
            True if successful
        """
        return self.set_user_permission(
            user_key=user_key,
            account_key=account_key,
            feature=feature,
            flags={
                'enabled': True,
                'entitled': True,
                'edit': edit,
                'view': view,
            },
            set_by=set_by
        )

    def revoke_feature(
        self,
        user_key: str,
        account_key: str,
        feature: str,
        set_by: str
    ) -> bool:
        """Revoke a feature from a user.

        Removes all flags for the feature from DB.

        Args:
            user_key: User to revoke from
            account_key: Account context
            feature: Feature name
            set_by: User making the change
        """
        if not self.user_permissions_collection:
            return False

        try:
            now = get_time_date_dt(include_time=True)

            self.user_permissions_collection.update_one(
                {'user_key': user_key, 'account_key': account_key},
                {
                    '$unset': {f'permissions.{feature}': ""},
                    '$set': {'updated_at': now, 'updated_by': set_by}
                }
            )

            return True
        except Exception as e:
            logger.exception(f"Error revoking feature: {e}")
            return False

    def set_bulk_permissions(
        self,
        user_key: str,
        account_key: str,
        permissions: Dict[str, Dict[str, bool]],
        set_by: str
    ) -> bool:
        """Set multiple permissions at once.

        Args:
            user_key: User to update
            account_key: Account context
            permissions: Dict of feature -> flags (e.g., {'pond_manage': {'edit': True}})
            set_by: User making the change

        Returns:
            True if successful
        """
        if not self.user_permissions_collection:
            return False

        try:
            now = get_time_date_dt(include_time=True)

            set_ops = {
                'user_key': user_key,
                'account_key': account_key,
                'updated_at': now,
                'updated_by': set_by,
            }
            unset_ops = {}

            for feature, flags in permissions.items():
                if feature not in PERMISSION_TEMPLATE:
                    continue

                for flag, value in flags.items():
                    if value is True:
                        # Convert boolean values to strings to match expected types
                        set_ops[f'permissions.{feature}.{flag}'] = str(True)
                    elif value is False:
                        unset_ops[f'permissions.{feature}.{flag}'] = ""

            update_ops = {'$set': set_ops, '$setOnInsert': {'created_at': now, 'created_by': set_by}}
            if unset_ops:
                update_ops['$unset'] = unset_ops

            self.user_permissions_collection.update_one(
                {'user_key': user_key, 'account_key': account_key},
                update_ops,
                upsert=True
            )

            return True
        except Exception as e:
            logger.exception(f"Error setting bulk permissions: {e}")
            return False

    # =========================================================================
    # ASSIGNED PONDS
    # =========================================================================

    def set_assigned_ponds(
        self,
        user_key: str,
        account_key: str,
        pond_ids: List[str],
        set_by: str
    ) -> bool:
        """Set user's assigned ponds."""
        if not self.user_permissions_collection:
            return False

        try:
            now = get_time_date_dt(include_time=True)

            self.user_permissions_collection.update_one(
                {'user_key': user_key, 'account_key': account_key},
                {
                    '$set': {
                        'assigned_ponds': pond_ids,
                        'updated_at': now,
                        'updated_by': set_by,
                    },
                    '$setOnInsert': {'created_at': now, 'created_by': set_by}
                },
                upsert=True
            )

            return True
        except Exception as e:
            logger.exception(f"Error setting assigned ponds: {e}")
            return False

    def get_assigned_ponds(self, user_key: str, account_key: str, role: str) -> Optional[List[str]]:
        """Get user's assigned ponds.

        Returns None if user can access all ponds (admin roles).
        """
        # Admin roles can access all ponds
        if role in ['owner', 'manager', 'analyst', 'accountant']:
            return None

        if not self.user_permissions_collection:
            return []

        try:
            user_doc = self.user_permissions_collection.find_one({
                'user_key': user_key,
                'account_key': account_key
            })

            if user_doc:
                return user_doc.get('assigned_ponds', [])
            return []
        except Exception as e:
            logger.exception(f"Error getting assigned ponds: {e}")
            return []

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_available_roles(self) -> List[str]:
        """Get list of available roles."""
        return list(ROLE_PERMISSION_TEMPLATES.keys())

    def get_role_default_permissions(self, role: str) -> Dict[str, Any]:
        """Get default permissions for a role (for display/reference)."""
        return get_role_permissions(role)

    def get_all_features(self) -> List[str]:
        """Get list of all feature names."""
        return get_all_features()

    def get_permission_template(self) -> Dict[str, Any]:
        """Get the permission template (for reference)."""
        return copy.deepcopy(PERMISSION_TEMPLATE)

    def get_permission_by_user_key_and_account_key(self, user_key: str, account_key: str, permission: str, role: str = None) -> bool:
        """Check if a specific permission exists for a user in an account."""
        permissions = self.get_user_permissions(user_key, account_key, role="user")
        return permissions.get(permission, {}).get('enabled', False)

    def is_dynamic_valid_permission(self, user_key: str, account_key: str, permission: str, role: str = None) -> bool:
        """Dynamically validate if a user has a specific permission."""
        try:
            return self.is_admin(role)
            return self.get_permission_by_user_key_and_account_key(user_key, account_key, permission)
        except Exception as e:
            logger.exception(f"Error validating dynamic permission: {e}")
            return False

    def is_admin(self, role):
        """Check if the service is running with admin privileges."""
        # Placeholder for actual admin check logic
        if role != 'admin' and role != 'owner':
            return False
        return True


# Singleton
_permission_service: Optional[PermissionService] = None


def get_permission_service() -> PermissionService:
    """Get singleton PermissionService instance."""
    global _permission_service
    if _permission_service is None:
        _permission_service = PermissionService()
    return _permission_service

