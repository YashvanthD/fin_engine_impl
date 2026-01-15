"""Role repository for managing user roles in MongoDB."""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from fin_server.repository.mongo_helper import get_collection
from fin_server.utils.time_utils import get_time_date_dt

logger = logging.getLogger(__name__)


class RoleRepository:
    """Repository for role-related database operations."""

    def __init__(self):
        self.users_repo = get_collection('users')
        self.audit_repo = get_collection('audit_log')

    def get_user_role(self, user_key: str) -> Optional[Dict[str, Any]]:
        """Get user's role information.

        Args:
            user_key: User's unique key

        Returns:
            Dict with role, permissions, assigned_ponds, etc.
        """
        if not self.users_repo:
            logger.warning('Users repository not available')
            return None

        try:
            user = self.users_repo.find_one({'user_key': user_key})
            if not user:
                return None

            return {
                'role': user.get('role', 'worker'),
                'permissions': user.get('permissions', []),
                'assigned_ponds': user.get('assigned_ponds', []),
                'supervisor_key': user.get('supervisor_key'),
                'department': user.get('department'),
                'shift': user.get('shift'),
                'hire_date': user.get('hire_date')
            }
        except Exception as e:
            logger.exception(f'Error getting user role: {e}')
            return None

    def update_user_role(
        self,
        user_key: str,
        role: str,
        assigned_by: str,
        permissions: Optional[List[str]] = None,
        assigned_ponds: Optional[List[str]] = None,
        supervisor_key: Optional[str] = None,
        reason: Optional[str] = None
    ) -> bool:
        """Update user's role.

        Args:
            user_key: User to update
            role: New role
            assigned_by: User making the change
            permissions: Custom permissions (optional)
            assigned_ponds: Ponds assigned to user (optional)
            supervisor_key: User's supervisor (optional)
            reason: Reason for change (optional)

        Returns:
            True if successful
        """
        if not self.users_repo:
            logger.warning('Users repository not available')
            return False

        try:
            # Get current role for audit
            current = self.get_user_role(user_key)
            old_role = current.get('role') if current else 'none'

            # Build update document
            update_doc = {
                'role': role,
                'updated_at': get_time_date_dt(include_time=True),
                'role_updated_by': assigned_by,
                'role_updated_at': get_time_date_dt(include_time=True)
            }

            if permissions is not None:
                update_doc['permissions'] = permissions

            if assigned_ponds is not None:
                update_doc['assigned_ponds'] = assigned_ponds

            if supervisor_key is not None:
                update_doc['supervisor_key'] = supervisor_key

            # Update user
            result = self.users_repo.update_one(
                {'user_key': user_key},
                {'$set': update_doc}
            )

            if result.modified_count > 0:
                # Log audit entry
                self._log_role_change(
                    user_key=user_key,
                    old_role=old_role,
                    new_role=role,
                    assigned_by=assigned_by,
                    reason=reason,
                    permissions=permissions,
                    assigned_ponds=assigned_ponds
                )
                return True

            return False
        except Exception as e:
            logger.exception(f'Error updating user role: {e}')
            return False

    def assign_ponds_to_user(
        self,
        user_key: str,
        pond_ids: List[str],
        assigned_by: str,
        replace: bool = False
    ) -> bool:
        """Assign ponds to a user.

        Args:
            user_key: User to assign ponds to
            pond_ids: List of pond IDs
            assigned_by: User making the assignment
            replace: If True, replace existing ponds. If False, add to existing.

        Returns:
            True if successful
        """
        if not self.users_repo:
            return False

        try:
            if replace:
                update = {'$set': {'assigned_ponds': pond_ids, 'updated_at': get_time_date_dt(include_time=True)}}
            else:
                update = {
                    '$addToSet': {'assigned_ponds': {'$each': pond_ids}},
                    '$set': {'updated_at': get_time_date_dt(include_time=True)}
                }

            result = self.users_repo.update_one(
                {'user_key': user_key},
                update
            )

            if result.modified_count > 0:
                self._log_audit(
                    action='ponds_assigned',
                    user_key=user_key,
                    details={'pond_ids': pond_ids, 'replace': replace},
                    performed_by=assigned_by
                )
                return True

            return False
        except Exception as e:
            logger.exception(f'Error assigning ponds: {e}')
            return False

    def remove_pond_from_user(
        self,
        user_key: str,
        pond_id: str,
        removed_by: str
    ) -> bool:
        """Remove a pond from user's assigned ponds.

        Args:
            user_key: User to update
            pond_id: Pond to remove
            removed_by: User making the change

        Returns:
            True if successful
        """
        if not self.users_repo:
            return False

        try:
            result = self.users_repo.update_one(
                {'user_key': user_key},
                {
                    '$pull': {'assigned_ponds': pond_id},
                    '$set': {'updated_at': get_time_date_dt(include_time=True)}
                }
            )

            if result.modified_count > 0:
                self._log_audit(
                    action='pond_removed',
                    user_key=user_key,
                    details={'pond_id': pond_id},
                    performed_by=removed_by
                )
                return True

            return False
        except Exception as e:
            logger.exception(f'Error removing pond: {e}')
            return False

    def set_supervisor(
        self,
        user_key: str,
        supervisor_key: str,
        set_by: str
    ) -> bool:
        """Set user's supervisor.

        Args:
            user_key: User to update
            supervisor_key: New supervisor's user_key
            set_by: User making the change

        Returns:
            True if successful
        """
        if not self.users_repo:
            return False

        try:
            result = self.users_repo.update_one(
                {'user_key': user_key},
                {'$set': {
                    'supervisor_key': supervisor_key,
                    'updated_at': get_time_date_dt(include_time=True)
                }}
            )

            if result.modified_count > 0:
                self._log_audit(
                    action='supervisor_set',
                    user_key=user_key,
                    details={'supervisor_key': supervisor_key},
                    performed_by=set_by
                )
                return True

            return False
        except Exception as e:
            logger.exception(f'Error setting supervisor: {e}')
            return False

    def add_custom_permission(
        self,
        user_key: str,
        permission: str,
        granted_by: str
    ) -> bool:
        """Add a custom permission to user.

        Args:
            user_key: User to update
            permission: Permission to add
            granted_by: User granting the permission

        Returns:
            True if successful
        """
        if not self.users_repo:
            return False

        try:
            result = self.users_repo.update_one(
                {'user_key': user_key},
                {
                    '$addToSet': {'permissions': permission},
                    '$set': {'updated_at': get_time_date_dt(include_time=True)}
                }
            )

            if result.modified_count > 0:
                self._log_audit(
                    action='permission_granted',
                    user_key=user_key,
                    details={'permission': permission},
                    performed_by=granted_by
                )
                return True

            return False
        except Exception as e:
            logger.exception(f'Error adding permission: {e}')
            return False

    def remove_custom_permission(
        self,
        user_key: str,
        permission: str,
        removed_by: str
    ) -> bool:
        """Remove a custom permission from user.

        Args:
            user_key: User to update
            permission: Permission to remove
            removed_by: User removing the permission

        Returns:
            True if successful
        """
        if not self.users_repo:
            return False

        try:
            result = self.users_repo.update_one(
                {'user_key': user_key},
                {
                    '$pull': {'permissions': permission},
                    '$set': {'updated_at': get_time_date_dt(include_time=True)}
                }
            )

            if result.modified_count > 0:
                self._log_audit(
                    action='permission_revoked',
                    user_key=user_key,
                    details={'permission': permission},
                    performed_by=removed_by
                )
                return True

            return False
        except Exception as e:
            logger.exception(f'Error removing permission: {e}')
            return False

    def get_users_by_role(
        self,
        role: str,
        account_key: str,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all users with a specific role.

        Args:
            role: Role to filter by
            account_key: Account to filter by
            include_inactive: Include inactive users

        Returns:
            List of user documents
        """
        if not self.users_repo:
            return []

        try:
            query = {'role': role, 'account_key': account_key}
            if not include_inactive:
                query['active'] = True

            users = list(self.users_repo.find(query))
            return users
        except Exception as e:
            logger.exception(f'Error getting users by role: {e}')
            return []

    def get_supervised_users(
        self,
        supervisor_key: str,
        account_key: str
    ) -> List[Dict[str, Any]]:
        """Get all users supervised by a specific user.

        Args:
            supervisor_key: Supervisor's user_key
            account_key: Account to filter by

        Returns:
            List of user documents
        """
        if not self.users_repo:
            return []

        try:
            users = list(self.users_repo.find({
                'supervisor_key': supervisor_key,
                'account_key': account_key,
                'active': True
            }))
            return users
        except Exception as e:
            logger.exception(f'Error getting supervised users: {e}')
            return []

    def get_users_assigned_to_pond(
        self,
        pond_id: str,
        account_key: str
    ) -> List[Dict[str, Any]]:
        """Get all users assigned to a specific pond.

        Args:
            pond_id: Pond ID to filter by
            account_key: Account to filter by

        Returns:
            List of user documents
        """
        if not self.users_repo:
            return []

        try:
            users = list(self.users_repo.find({
                'assigned_ponds': pond_id,
                'account_key': account_key,
                'active': True
            }))
            return users
        except Exception as e:
            logger.exception(f'Error getting users for pond: {e}')
            return []

    def _log_role_change(
        self,
        user_key: str,
        old_role: str,
        new_role: str,
        assigned_by: str,
        reason: Optional[str] = None,
        permissions: Optional[List[str]] = None,
        assigned_ponds: Optional[List[str]] = None
    ):
        """Log role change to audit log."""
        self._log_audit(
            action='role_change',
            user_key=user_key,
            details={
                'old_role': old_role,
                'new_role': new_role,
                'permissions': permissions,
                'assigned_ponds': assigned_ponds,
                'reason': reason
            },
            performed_by=assigned_by
        )

    def _log_audit(
        self,
        action: str,
        user_key: str,
        details: Dict[str, Any],
        performed_by: str
    ):
        """Log action to audit log collection."""
        if not self.audit_repo:
            logger.warning('Audit repository not available')
            return

        try:
            audit_entry = {
                'action': action,
                'target_user_key': user_key,
                'performed_by': performed_by,
                'details': details,
                'timestamp': get_time_date_dt(include_time=True),
                'created_at': get_time_date_dt(include_time=True)
            }
            self.audit_repo.insert_one(audit_entry)
        except Exception as e:
            logger.exception(f'Error logging audit entry: {e}')


# Singleton instance
_role_repo_instance: Optional[RoleRepository] = None


def get_role_repository() -> RoleRepository:
    """Get singleton RoleRepository instance."""
    global _role_repo_instance
    if _role_repo_instance is None:
        _role_repo_instance = RoleRepository()
    return _role_repo_instance

