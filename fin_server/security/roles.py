"""Role-based access control constants and enums."""
from enum import Enum
from typing import List, Set


class Role(str, Enum):
    """User roles in the fish farm system."""
    OWNER = "owner"
    MANAGER = "manager"
    SUPERVISOR = "supervisor"
    ANALYST = "analyst"
    ACCOUNTANT = "accountant"
    FEEDER = "feeder"
    WORKER = "worker"

    @classmethod
    def all_roles(cls) -> List[str]:
        """Get all role values."""
        return [r.value for r in cls]

    @classmethod
    def admin_roles(cls) -> Set[str]:
        """Roles that can manage users."""
        return {cls.OWNER.value, cls.MANAGER.value}

    @classmethod
    def field_roles(cls) -> Set[str]:
        """Field staff roles."""
        return {cls.SUPERVISOR.value, cls.FEEDER.value, cls.WORKER.value}

    @classmethod
    def office_roles(cls) -> Set[str]:
        """Office/desk roles."""
        return {cls.ANALYST.value, cls.ACCOUNTANT.value}


class Permission(str, Enum):
    """Granular permissions for fine-grained access control."""

    # User Management
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    USER_LIST = "user:list"

    # Pond Management
    POND_CREATE = "pond:create"
    POND_READ = "pond:read"
    POND_UPDATE = "pond:update"
    POND_DELETE = "pond:delete"
    POND_LIST = "pond:list"

    # Fish Management
    FISH_CREATE = "fish:create"
    FISH_READ = "fish:read"
    FISH_UPDATE = "fish:update"
    FISH_DELETE = "fish:delete"
    FISH_STOCK = "fish:stock"
    FISH_TRANSFER = "fish:transfer"
    FISH_HARVEST = "fish:harvest"
    FISH_MORTALITY = "fish:mortality"

    # Feeding
    FEEDING_CREATE = "feeding:create"
    FEEDING_READ = "feeding:read"
    FEEDING_UPDATE = "feeding:update"
    FEEDING_SCHEDULE = "feeding:schedule"
    FEEDING_INVENTORY = "feeding:inventory"

    # Sampling & Growth
    SAMPLING_CREATE = "sampling:create"
    SAMPLING_READ = "sampling:read"
    SAMPLING_APPROVE = "sampling:approve"
    GROWTH_READ = "growth:read"

    # Financial
    EXPENSE_CREATE = "expense:create"
    EXPENSE_READ = "expense:read"
    EXPENSE_UPDATE = "expense:update"
    EXPENSE_APPROVE = "expense:approve"
    EXPENSE_DELETE = "expense:delete"
    TRANSACTION_CREATE = "transaction:create"
    TRANSACTION_READ = "transaction:read"
    BANK_MANAGE = "bank:manage"
    BANK_READ = "bank:read"

    # Tasks
    TASK_CREATE = "task:create"
    TASK_READ = "task:read"
    TASK_ASSIGN = "task:assign"
    TASK_COMPLETE = "task:complete"
    TASK_DELETE = "task:delete"

    # Reports
    REPORT_OPERATIONAL = "report:operational"
    REPORT_FINANCIAL = "report:financial"
    REPORT_EXPORT = "report:export"
    REPORT_CREATE = "report:create"

    # Messaging
    MESSAGE_SEND = "message:send"
    MESSAGE_GROUP_CREATE = "message:group_create"
    MESSAGE_BROADCAST = "message:broadcast"

    # Settings & Admin
    SETTINGS_SYSTEM = "settings:system"
    SETTINGS_FARM = "settings:farm"
    AUDIT_READ = "audit:read"


# Role to permissions mapping
ROLE_PERMISSIONS: dict[str, Set[str]] = {
    Role.OWNER.value: {p.value for p in Permission},  # Owner has all permissions

    Role.MANAGER.value: {
        # User Management
        Permission.USER_CREATE.value,
        Permission.USER_READ.value,
        Permission.USER_UPDATE.value,
        Permission.USER_LIST.value,
        # Pond Management
        Permission.POND_CREATE.value,
        Permission.POND_READ.value,
        Permission.POND_UPDATE.value,
        Permission.POND_DELETE.value,
        Permission.POND_LIST.value,
        # Fish Management
        Permission.FISH_CREATE.value,
        Permission.FISH_READ.value,
        Permission.FISH_UPDATE.value,
        Permission.FISH_DELETE.value,
        Permission.FISH_STOCK.value,
        Permission.FISH_TRANSFER.value,
        Permission.FISH_HARVEST.value,
        Permission.FISH_MORTALITY.value,
        # Feeding
        Permission.FEEDING_CREATE.value,
        Permission.FEEDING_READ.value,
        Permission.FEEDING_UPDATE.value,
        Permission.FEEDING_SCHEDULE.value,
        Permission.FEEDING_INVENTORY.value,
        # Sampling & Growth
        Permission.SAMPLING_CREATE.value,
        Permission.SAMPLING_READ.value,
        Permission.SAMPLING_APPROVE.value,
        Permission.GROWTH_READ.value,
        # Financial
        Permission.EXPENSE_CREATE.value,
        Permission.EXPENSE_READ.value,
        Permission.EXPENSE_UPDATE.value,
        Permission.EXPENSE_APPROVE.value,
        Permission.TRANSACTION_CREATE.value,
        Permission.TRANSACTION_READ.value,
        Permission.BANK_READ.value,
        # Tasks
        Permission.TASK_CREATE.value,
        Permission.TASK_READ.value,
        Permission.TASK_ASSIGN.value,
        Permission.TASK_COMPLETE.value,
        Permission.TASK_DELETE.value,
        # Reports
        Permission.REPORT_OPERATIONAL.value,
        Permission.REPORT_FINANCIAL.value,
        Permission.REPORT_EXPORT.value,
        Permission.REPORT_CREATE.value,
        # Messaging
        Permission.MESSAGE_SEND.value,
        Permission.MESSAGE_GROUP_CREATE.value,
        Permission.MESSAGE_BROADCAST.value,
        # Settings
        Permission.SETTINGS_FARM.value,
        Permission.AUDIT_READ.value,
    },

    Role.SUPERVISOR.value: {
        # User (read only)
        Permission.USER_READ.value,
        Permission.USER_LIST.value,
        # Pond (assigned only - enforced at query level)
        Permission.POND_READ.value,
        Permission.POND_UPDATE.value,
        Permission.POND_LIST.value,
        # Fish
        Permission.FISH_READ.value,
        Permission.FISH_STOCK.value,
        Permission.FISH_TRANSFER.value,
        Permission.FISH_MORTALITY.value,
        Permission.FISH_HARVEST.value,
        # Feeding
        Permission.FEEDING_CREATE.value,
        Permission.FEEDING_READ.value,
        Permission.FEEDING_UPDATE.value,
        Permission.FEEDING_SCHEDULE.value,
        Permission.FEEDING_INVENTORY.value,
        # Sampling
        Permission.SAMPLING_CREATE.value,
        Permission.SAMPLING_READ.value,
        Permission.SAMPLING_APPROVE.value,
        Permission.GROWTH_READ.value,
        # Financial (limited)
        Permission.EXPENSE_CREATE.value,
        Permission.EXPENSE_READ.value,
        # Tasks
        Permission.TASK_CREATE.value,
        Permission.TASK_READ.value,
        Permission.TASK_ASSIGN.value,
        Permission.TASK_COMPLETE.value,
        # Reports
        Permission.REPORT_OPERATIONAL.value,
        # Messaging
        Permission.MESSAGE_SEND.value,
        Permission.MESSAGE_GROUP_CREATE.value,
    },

    Role.ANALYST.value: {
        # User (read only)
        Permission.USER_READ.value,
        Permission.USER_LIST.value,
        # Pond (read only)
        Permission.POND_READ.value,
        Permission.POND_LIST.value,
        # Fish (read only)
        Permission.FISH_READ.value,
        # Feeding (read only)
        Permission.FEEDING_READ.value,
        Permission.FEEDING_SCHEDULE.value,
        Permission.FEEDING_INVENTORY.value,
        # Sampling & Growth (read only)
        Permission.SAMPLING_READ.value,
        Permission.GROWTH_READ.value,
        # Financial (read only)
        Permission.EXPENSE_READ.value,
        Permission.TRANSACTION_READ.value,
        # Tasks (read only)
        Permission.TASK_READ.value,
        # Reports (full)
        Permission.REPORT_OPERATIONAL.value,
        Permission.REPORT_FINANCIAL.value,
        Permission.REPORT_EXPORT.value,
        Permission.REPORT_CREATE.value,
        # Messaging
        Permission.MESSAGE_SEND.value,
        # Audit
        Permission.AUDIT_READ.value,
    },

    Role.ACCOUNTANT.value: {
        # User (read only)
        Permission.USER_READ.value,
        Permission.USER_LIST.value,
        # Pond (read only)
        Permission.POND_READ.value,
        Permission.POND_LIST.value,
        # Fish (limited)
        Permission.FISH_READ.value,
        Permission.FISH_STOCK.value,
        Permission.FISH_HARVEST.value,
        # Feeding (read + inventory)
        Permission.FEEDING_READ.value,
        Permission.FEEDING_SCHEDULE.value,
        Permission.FEEDING_INVENTORY.value,
        # Sampling (read only)
        Permission.SAMPLING_READ.value,
        Permission.GROWTH_READ.value,
        # Financial (full)
        Permission.EXPENSE_CREATE.value,
        Permission.EXPENSE_READ.value,
        Permission.EXPENSE_UPDATE.value,
        Permission.EXPENSE_APPROVE.value,
        Permission.TRANSACTION_CREATE.value,
        Permission.TRANSACTION_READ.value,
        Permission.BANK_MANAGE.value,
        Permission.BANK_READ.value,
        # Reports
        Permission.REPORT_OPERATIONAL.value,
        Permission.REPORT_FINANCIAL.value,
        Permission.REPORT_EXPORT.value,
        Permission.REPORT_CREATE.value,
        # Messaging
        Permission.MESSAGE_SEND.value,
        # Audit
        Permission.AUDIT_READ.value,
    },

    Role.FEEDER.value: {
        # Pond (assigned only)
        Permission.POND_READ.value,
        Permission.POND_LIST.value,
        # Fish (read only)
        Permission.FISH_READ.value,
        # Feeding
        Permission.FEEDING_CREATE.value,
        Permission.FEEDING_READ.value,
        Permission.FEEDING_SCHEDULE.value,
        Permission.FEEDING_INVENTORY.value,
        # Tasks
        Permission.TASK_READ.value,
        Permission.TASK_COMPLETE.value,
        # Messaging
        Permission.MESSAGE_SEND.value,
    },

    Role.WORKER.value: {
        # Pond (assigned only)
        Permission.POND_READ.value,
        Permission.POND_LIST.value,
        # Fish (read only)
        Permission.FISH_READ.value,
        # Sampling (create with supervision)
        Permission.SAMPLING_CREATE.value,
        # Tasks
        Permission.TASK_READ.value,
        Permission.TASK_COMPLETE.value,
        # Messaging
        Permission.MESSAGE_SEND.value,
    },
}


def get_role_permissions(role: str) -> Set[str]:
    """Get all permissions for a role."""
    return ROLE_PERMISSIONS.get(role, set())


def has_permission(role: str, permission: str, custom_permissions: Set[str] = None) -> bool:
    """Check if a role has a specific permission.

    Args:
        role: User's role
        permission: Permission to check
        custom_permissions: Additional custom permissions granted to user

    Returns:
        True if user has the permission
    """
    role_perms = get_role_permissions(role)
    if permission in role_perms:
        return True
    if custom_permissions and permission in custom_permissions:
        return True
    return False


def get_allowed_roles_for_permission(permission: str) -> Set[str]:
    """Get all roles that have a specific permission."""
    allowed = set()
    for role, perms in ROLE_PERMISSIONS.items():
        if permission in perms:
            allowed.add(role)
    return allowed

