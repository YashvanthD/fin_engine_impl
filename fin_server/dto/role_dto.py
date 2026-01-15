"""Role DTO for user role management."""
from typing import Optional, Dict, Any, List, Set
from datetime import datetime


class RoleDTO:
    """Data Transfer Object for user roles."""

    def __init__(
        self,
        role: str,
        permissions: Optional[List[str]] = None,
        assigned_ponds: Optional[List[str]] = None,
        supervisor_key: Optional[str] = None,
        department: Optional[str] = None,
        shift: Optional[str] = None,
        hire_date: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ):
        self.role = role
        self.permissions = permissions or []
        self.assigned_ponds = assigned_ponds or []
        self.supervisor_key = supervisor_key
        self.department = department
        self.shift = shift
        self.hire_date = hire_date
        self.extra = extra or {}

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> 'RoleDTO':
        """Create RoleDTO from database document."""
        if not doc:
            return cls(role='worker')

        return cls(
            role=doc.get('role') or 'worker',
            permissions=doc.get('permissions') or doc.get('custom_permissions') or [],
            assigned_ponds=doc.get('assigned_ponds') or [],
            supervisor_key=doc.get('supervisor_key'),
            department=doc.get('department'),
            shift=doc.get('shift'),
            hire_date=doc.get('hire_date'),
            extra={k: v for k, v in doc.items() if k not in [
                'role', 'permissions', 'custom_permissions', 'assigned_ponds',
                'supervisor_key', 'department', 'shift', 'hire_date'
            ]}
        )

    @classmethod
    def from_request(cls, payload: Dict[str, Any]) -> 'RoleDTO':
        """Create RoleDTO from API request."""
        return cls(
            role=payload.get('role') or 'worker',
            permissions=payload.get('permissions') or payload.get('customPermissions') or [],
            assigned_ponds=payload.get('assigned_ponds') or payload.get('assignedPonds') or [],
            supervisor_key=payload.get('supervisor_key') or payload.get('supervisorKey'),
            department=payload.get('department'),
            shift=payload.get('shift'),
            hire_date=payload.get('hire_date') or payload.get('hireDate'),
            extra={k: v for k, v in payload.items() if k not in [
                'role', 'permissions', 'customPermissions', 'assigned_ponds', 'assignedPonds',
                'supervisor_key', 'supervisorKey', 'department', 'shift', 'hire_date', 'hireDate'
            ]}
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'role': self.role,
            'permissions': self.permissions,
            'assigned_ponds': self.assigned_ponds,
            'supervisor_key': self.supervisor_key,
            'department': self.department,
            'shift': self.shift,
            'hire_date': self.hire_date,
            **self.extra
        }

    def to_ui(self) -> Dict[str, Any]:
        """Convert to UI-friendly format."""
        return {
            'role': self.role,
            'permissions': self.permissions,
            'assignedPonds': self.assigned_ponds,
            'supervisorKey': self.supervisor_key,
            'department': self.department,
            'shift': self.shift,
            'hireDate': self.hire_date,
            **self.extra
        }


class RoleAssignmentDTO:
    """DTO for role assignment requests."""

    def __init__(
        self,
        user_key: str,
        role: str,
        assigned_by: str,
        permissions: Optional[List[str]] = None,
        assigned_ponds: Optional[List[str]] = None,
        supervisor_key: Optional[str] = None,
        effective_date: Optional[str] = None,
        reason: Optional[str] = None
    ):
        self.user_key = user_key
        self.role = role
        self.assigned_by = assigned_by
        self.permissions = permissions or []
        self.assigned_ponds = assigned_ponds or []
        self.supervisor_key = supervisor_key
        self.effective_date = effective_date or datetime.utcnow().isoformat()
        self.reason = reason

    @classmethod
    def from_request(cls, payload: Dict[str, Any], assigned_by: str) -> 'RoleAssignmentDTO':
        """Create from API request."""
        return cls(
            user_key=payload.get('user_key') or payload.get('userKey'),
            role=payload.get('role'),
            assigned_by=assigned_by,
            permissions=payload.get('permissions') or [],
            assigned_ponds=payload.get('assigned_ponds') or payload.get('assignedPonds') or [],
            supervisor_key=payload.get('supervisor_key') or payload.get('supervisorKey'),
            effective_date=payload.get('effective_date') or payload.get('effectiveDate'),
            reason=payload.get('reason')
        )

    def to_audit_log(self) -> Dict[str, Any]:
        """Convert to audit log format."""
        return {
            'action': 'role_assignment',
            'user_key': self.user_key,
            'new_role': self.role,
            'assigned_by': self.assigned_by,
            'permissions': self.permissions,
            'assigned_ponds': self.assigned_ponds,
            'supervisor_key': self.supervisor_key,
            'effective_date': self.effective_date,
            'reason': self.reason,
            'timestamp': datetime.utcnow().isoformat()
        }

