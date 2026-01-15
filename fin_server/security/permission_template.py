"""Permission template with all features and their default flags.

Each feature has 4 flags:
- enabled: Feature is active for the account
- entitled: User is entitled to access this feature (based on subscription/plan)
- edit: User can create/update/delete
- view: User can read/view

Default: All flags are False
Database stores only True values (sparse storage)
"""

# Permission template - all default to False
# Format: "feature_name": {"enabled": False, "entitled": False, "edit": False, "view": False}

PERMISSION_TEMPLATE = {
    # =========================================================================
    # USER MANAGEMENT
    # =========================================================================
    "user_create": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "user_list": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "user_delete": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "user_role_assign": {"enabled": False, "entitled": False, "edit": False, "view": False},

    # =========================================================================
    # POND MANAGEMENT
    # =========================================================================
    "pond_manage": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "pond_delete": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "pond_stock": {"enabled": False, "entitled": False, "edit": False, "view": False},

    # =========================================================================
    # FISH MANAGEMENT
    # =========================================================================
    "fish_species": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "fish_stock": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "fish_transfer": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "fish_harvest": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "fish_mortality": {"enabled": False, "entitled": False, "edit": False, "view": False},

    # =========================================================================
    # FEEDING
    # =========================================================================
    "feeding_record": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "feeding_schedule": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "feeding_inventory": {"enabled": False, "entitled": False, "edit": False, "view": False},

    # =========================================================================
    # SAMPLING & GROWTH
    # =========================================================================
    "sampling_record": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "sampling_approve": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "growth_analytics": {"enabled": False, "entitled": False, "edit": False, "view": False},

    # =========================================================================
    # FINANCIAL
    # =========================================================================
    "expense_manage": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "expense_approve": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "transaction_manage": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "bank_manage": {"enabled": False, "entitled": False, "edit": False, "view": False},

    # =========================================================================
    # TASKS
    # =========================================================================
    "task_create": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "task_assign": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "task_complete": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "task_delete": {"enabled": False, "entitled": False, "edit": False, "view": False},

    # =========================================================================
    # REPORTS
    # =========================================================================
    "report_operational": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "report_financial": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "report_export": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "report_custom": {"enabled": False, "entitled": False, "edit": False, "view": False},

    # =========================================================================
    # MESSAGING
    # =========================================================================
    "message_send": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "message_group": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "message_broadcast": {"enabled": False, "entitled": False, "edit": False, "view": False},

    # =========================================================================
    # SETTINGS & ADMIN
    # =========================================================================
    "settings_system": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "settings_farm": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "audit_logs": {"enabled": False, "entitled": False, "edit": False, "view": False},

    # =========================================================================
    # ROLE & PERMISSION MANAGEMENT
    # =========================================================================
    "role_manage": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "permission_grant": {"enabled": False, "entitled": False, "edit": False, "view": False},
    "permission_request": {"enabled": False, "entitled": False, "edit": False, "view": False},
}


# Role templates - define which permissions are True for each role
# Only True values are listed (sparse definition)

ROLE_PERMISSION_TEMPLATES = {
    "owner": {
        # Full access to everything
        "user_create": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "user_list": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "user_delete": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "user_role_assign": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "pond_manage": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "pond_delete": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "pond_stock": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "fish_species": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "fish_stock": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "fish_transfer": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "fish_harvest": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "fish_mortality": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "feeding_record": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "feeding_schedule": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "feeding_inventory": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "sampling_record": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "sampling_approve": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "growth_analytics": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "expense_manage": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "expense_approve": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "transaction_manage": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "bank_manage": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "task_create": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "task_assign": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "task_complete": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "task_delete": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "report_operational": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "report_financial": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "report_export": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "report_custom": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "message_send": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "message_group": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "message_broadcast": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "settings_system": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "settings_farm": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "audit_logs": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "role_manage": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "permission_grant": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "permission_request": {"enabled": True, "entitled": True, "edit": True, "view": True},
    },

    "manager": {
        "user_create": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "user_list": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "user_role_assign": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "pond_manage": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "pond_delete": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "pond_stock": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "fish_species": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "fish_stock": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "fish_transfer": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "fish_harvest": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "fish_mortality": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "feeding_record": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "feeding_schedule": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "feeding_inventory": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "sampling_record": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "sampling_approve": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "growth_analytics": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "expense_manage": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "expense_approve": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "transaction_manage": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "bank_manage": {"enabled": True, "entitled": True, "view": True},  # No edit for bank
        "task_create": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "task_assign": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "task_complete": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "task_delete": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "report_operational": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "report_financial": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "report_export": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "report_custom": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "message_send": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "message_group": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "message_broadcast": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "settings_farm": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "audit_logs": {"enabled": True, "entitled": True, "view": True},
        "role_manage": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "permission_grant": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "permission_request": {"enabled": True, "entitled": True, "edit": True, "view": True},
    },

    "supervisor": {
        "user_list": {"enabled": True, "entitled": True, "view": True},
        "pond_manage": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "pond_stock": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "fish_stock": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "fish_transfer": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "fish_harvest": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "fish_mortality": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "feeding_record": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "feeding_schedule": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "feeding_inventory": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "sampling_record": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "sampling_approve": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "growth_analytics": {"enabled": True, "entitled": True, "view": True},
        "expense_manage": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "task_create": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "task_assign": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "task_complete": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "report_operational": {"enabled": True, "entitled": True, "view": True},
        "message_send": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "message_group": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "permission_request": {"enabled": True, "entitled": True, "edit": True, "view": True},
    },

    "analyst": {
        "user_list": {"enabled": True, "entitled": True, "view": True},
        "pond_manage": {"enabled": True, "entitled": True, "view": True},
        "fish_species": {"enabled": True, "entitled": True, "view": True},
        "feeding_schedule": {"enabled": True, "entitled": True, "view": True},
        "feeding_inventory": {"enabled": True, "entitled": True, "view": True},
        "sampling_record": {"enabled": True, "entitled": True, "view": True},
        "growth_analytics": {"enabled": True, "entitled": True, "view": True},
        "expense_manage": {"enabled": True, "entitled": True, "view": True},
        "transaction_manage": {"enabled": True, "entitled": True, "view": True},
        "task_create": {"enabled": True, "entitled": True, "view": True},
        "report_operational": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "report_financial": {"enabled": True, "entitled": True, "view": True},
        "report_export": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "report_custom": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "message_send": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "audit_logs": {"enabled": True, "entitled": True, "view": True},
        "permission_request": {"enabled": True, "entitled": True, "edit": True, "view": True},
    },

    "accountant": {
        "user_list": {"enabled": True, "entitled": True, "view": True},
        "pond_manage": {"enabled": True, "entitled": True, "view": True},
        "fish_stock": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "fish_harvest": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "feeding_schedule": {"enabled": True, "entitled": True, "view": True},
        "feeding_inventory": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "sampling_record": {"enabled": True, "entitled": True, "view": True},
        "growth_analytics": {"enabled": True, "entitled": True, "view": True},
        "expense_manage": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "expense_approve": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "transaction_manage": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "bank_manage": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "report_operational": {"enabled": True, "entitled": True, "view": True},
        "report_financial": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "report_export": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "report_custom": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "message_send": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "audit_logs": {"enabled": True, "entitled": True, "view": True},
        "permission_request": {"enabled": True, "entitled": True, "edit": True, "view": True},
    },

    "feeder": {
        "pond_manage": {"enabled": True, "entitled": True, "view": True},
        "fish_species": {"enabled": True, "entitled": True, "view": True},
        "feeding_record": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "feeding_schedule": {"enabled": True, "entitled": True, "view": True},
        "feeding_inventory": {"enabled": True, "entitled": True, "view": True},
        "task_complete": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "message_send": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "permission_request": {"enabled": True, "entitled": True, "edit": True, "view": True},
    },

    "worker": {
        "pond_manage": {"enabled": True, "entitled": True, "view": True},
        "fish_species": {"enabled": True, "entitled": True, "view": True},
        "sampling_record": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "task_complete": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "message_send": {"enabled": True, "entitled": True, "edit": True, "view": True},
        "permission_request": {"enabled": True, "entitled": True, "edit": True, "view": True},
    },
}


def get_default_permissions() -> dict:
    """Get a copy of the permission template with all False values."""
    import copy
    return copy.deepcopy(PERMISSION_TEMPLATE)


def get_role_permissions(role: str) -> dict:
    """Get permissions for a role (merged with template).

    Args:
        role: Role name (owner, manager, supervisor, etc.)

    Returns:
        Full permission dict with role's True values merged
    """
    import copy
    permissions = copy.deepcopy(PERMISSION_TEMPLATE)

    role_perms = ROLE_PERMISSION_TEMPLATES.get(role, {})
    for feature, flags in role_perms.items():
        if feature in permissions:
            permissions[feature].update(flags)

    return permissions


def get_all_features() -> list:
    """Get list of all feature names."""
    return list(PERMISSION_TEMPLATE.keys())


def get_feature_categories() -> dict:
    """Get features grouped by category."""
    categories = {
        "user": ["user_create", "user_list", "user_delete", "user_role_assign"],
        "pond": ["pond_manage", "pond_delete", "pond_stock"],
        "fish": ["fish_species", "fish_stock", "fish_transfer", "fish_harvest", "fish_mortality"],
        "feeding": ["feeding_record", "feeding_schedule", "feeding_inventory"],
        "sampling": ["sampling_record", "sampling_approve", "growth_analytics"],
        "financial": ["expense_manage", "expense_approve", "transaction_manage", "bank_manage"],
        "task": ["task_create", "task_assign", "task_complete", "task_delete"],
        "report": ["report_operational", "report_financial", "report_export", "report_custom"],
        "message": ["message_send", "message_group", "message_broadcast"],
        "settings": ["settings_system", "settings_farm", "audit_logs"],
        "role": ["role_manage", "permission_grant", "permission_request"],
    }
    return categories

