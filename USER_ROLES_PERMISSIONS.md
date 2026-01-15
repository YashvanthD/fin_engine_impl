# 👥 Fish Farm User Roles & Permissions

**Version:** 1.2  
**Last Updated:** January 13, 2026  
**Status:** ✅ Backend Implementation Complete

---

## 📋 Overview

This document defines user roles, their responsibilities, and permissions for the Fish Farm Management System. The role-based access control (RBAC) is now **database-backed** for flexibility:

- **Dynamic Roles**: Create custom roles per account
- **Dynamic Permissions**: Add custom permissions
- **User Overrides**: Grant/revoke individual permissions per user
- **Permission Requests**: Users can request access to specific permissions

---

## 🗄️ Database Collections (in user_db)

| Collection | Purpose |
|------------|---------|
| `roles` | Role definitions with default permissions |
| `permissions` | Permission catalog |
| `user_permissions` | User-specific permission overrides |
| `permission_requests` | Access requests from users |

### `roles` Collection Schema
```javascript
{
  "_id": "69653c8af4c2d41e5a1bcdbd",
  "role_id": "69653c8af4c2d41e5a1bcdbd",
  "role_code": "supervisor",          // Unique identifier
  "name": "Supervisor",               // Display name
  "description": "Team lead with field oversight",
  "permissions": ["pond:read", "task:assign", ...],
  "level": 3,                         // Hierarchy: 1=highest (owner)
  "scope": "global",                  // "global" or "account"
  "account_key": null,                // Set for account-specific roles
  "is_system": true,                  // Cannot be deleted
  "active": true,
  "created_by": "system",
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### `permissions` Collection Schema
```javascript
{
  "_id": "a1b2c3d4e5f6a7b8c9d0e1f2",
  "permission_id": "a1b2c3d4e5f6a7b8c9d0e1f2",
  "permission_code": "pond:create",   // Unique identifier
  "name": "Create Ponds",             // Display name
  "description": "Add new ponds",
  "category": "pond",                 // For grouping
  "scope": "global",
  "account_key": null,                // Set for account-specific
  "is_system": true,
  "active": true,
  "created_at": ISODate
}
```

### `user_permissions` Collection Schema
```javascript
{
  "_id": "b2c3d4e5f6a7b8c9d0e1f2a3",
  "user_key": "123456789012",
  "account_key": "987654321098",
  "granted_permissions": ["expense:approve"],   // Extra permissions
  "denied_permissions": ["user:delete"],        // Blocked permissions
  "assigned_ponds": ["pond_id_1", "pond_id_2"], // For field roles
  "supervisor_key": "111222333444",
  "created_at": ISODate,
  "updated_at": ISODate,
  "updated_by": "admin_user_key"
}
```

### `permission_requests` Collection Schema
```javascript
{
  "_id": "c3d4e5f6a7b8c9d0e1f2a3b4",
  "request_id": "c3d4e5f6a7b8c9d0e1f2a3b4",
  "user_key": "123456789012",
  "account_key": "987654321098",
  "permission_code": "expense:approve",
  "reason": "Need to approve expenses during manager leave",
  "requested_duration": "7d",         // "7d", "30d", "permanent"
  "status": "pending",                // "pending", "approved", "rejected"
  "created_at": ISODate,
  "reviewed_by": null,
  "reviewed_at": null,
  "review_notes": null,
  "expires_at": null
}
```

---

## 🔄 Permission Resolution Flow

```
User Permission Check:
  1. Get user's role from users.role
  2. Get role's default permissions from roles collection
  3. Get user overrides from user_permissions collection
  4. Compute effective = (role_permissions + granted) - denied
  5. Check if requested permission is in effective set
```

---

## 🎭 Role Hierarchy

```
                    ┌─────────────┐
                    │    OWNER    │
                    │  (Super Admin)│
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   MANAGER   │
                    │ (Farm Admin)│
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
 ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐
 │  SUPERVISOR │    │   ANALYST   │    │ ACCOUNTANT  │
 └──────┬──────┘    └─────────────┘    └─────────────┘
        │
 ┌──────┴──────────────────┐
 │                         │
 ┌▼─────────────┐   ┌──────▼──────┐
 │   WORKER     │   │   FEEDER    │
 │ (Field Staff)│   │             │
 └──────────────┘   └─────────────┘
```

---

## 📊 Role Definitions

### 1. 👑 OWNER (Super Admin)

**Description:** Farm owner with full system access. Creates the company account and has ultimate authority.

**Responsibilities:**
- Overall business management
- Financial oversight
- Strategic decisions
- Staff management

**Use Cases:**
| # | Use Case | Description |
|---|----------|-------------|
| O1 | Create Company | Register new fish farm company |
| O2 | Manage Managers | Add/remove/edit manager accounts |
| O3 | View All Reports | Access all financial and operational reports |
| O4 | Bank Account Setup | Create and manage bank accounts |
| O5 | Delete Company Data | Permanently delete records (with audit) |
| O6 | Export All Data | Full data export for compliance |
| O7 | Configure Settings | System-wide settings and preferences |
| O8 | View Audit Logs | Access complete audit trail |

---

### 2. 🏢 MANAGER (Farm Admin)

**Description:** Day-to-day farm operations manager. Handles staff, ponds, and operational decisions.

**Responsibilities:**
- Staff scheduling and assignment
- Pond management
- Inventory control
- Expense approval
- Production planning

**Use Cases:**
| # | Use Case | Description |
|---|----------|-------------|
| M1 | Manage Staff | Add/edit/deactivate workers, feeders, supervisors |
| M2 | Create Ponds | Add new ponds to the system |
| M3 | Assign Tasks | Create and assign tasks to staff |
| M4 | Approve Expenses | Review and approve expense claims |
| M5 | View Reports | Access operational and financial reports |
| M6 | Manage Fish Species | Add/edit fish species for the farm |
| M7 | Plan Harvests | Schedule and plan harvest operations |
| M8 | Transfer Fish | Approve fish transfers between ponds |
| M9 | Record Sales | Log fish sales and revenue |
| M10 | Manage Inventory | Track feed, medicine, equipment |
| M11 | Send Announcements | Broadcast messages to all staff |
| M12 | View All Ponds | Access all pond data and history |

---

### 3. 👷 SUPERVISOR (Team Lead)

**Description:** Oversees field operations and workers. Reports to manager.

**Responsibilities:**
- Supervise workers and feeders
- Quality control
- Daily reporting
- Issue escalation

**Use Cases:**
| # | Use Case | Description |
|---|----------|-------------|
| S1 | Assign Daily Tasks | Distribute tasks to workers/feeders |
| S2 | Record Events | Log pond events (mortality, disease, etc.) |
| S3 | Approve Sampling | Verify and approve growth sampling data |
| S4 | View Team Tasks | See all tasks for supervised team |
| S5 | Report Issues | Escalate problems to manager |
| S6 | Record Transfers | Log fish transfers between ponds |
| S7 | View Assigned Ponds | Access data for assigned ponds only |
| S8 | Update Task Status | Mark tasks as complete/in-progress |
| S9 | Record Water Quality | Log water quality measurements |
| S10 | Request Supplies | Submit feed/medicine requests |

---

### 4. 📊 ANALYST (Data Analyst)

**Description:** Analyzes farm data to provide insights and recommendations.

**Responsibilities:**
- Data analysis and reporting
- Growth predictions
- Cost optimization
- Trend identification

**Use Cases:**
| # | Use Case | Description |
|---|----------|-------------|
| A1 | View All Reports | Access all analytical reports |
| A2 | Generate Reports | Create custom reports |
| A3 | Export Data | Export data for external analysis |
| A4 | View Growth Data | Access fish growth and sampling data |
| A5 | View Financial Data | Access expense and revenue data (read-only) |
| A6 | Predict Harvests | Analyze and predict harvest dates |
| A7 | FCR Analysis | Calculate feed conversion ratios |
| A8 | Cost Analysis | Analyze production costs |
| A9 | View Historical Data | Access all historical records |
| A10 | Create Dashboards | Build custom dashboards |

---

### 5. 💰 ACCOUNTANT (Finance)

**Description:** Manages financial records, expenses, and transactions.

**Responsibilities:**
- Financial record keeping
- Expense management
- Transaction tracking
- Financial reporting

**Use Cases:**
| # | Use Case | Description |
|---|----------|-------------|
| AC1 | Record Expenses | Log all farm expenses |
| AC2 | Record Transactions | Log financial transactions |
| AC3 | Manage Bank Accounts | View and reconcile bank accounts |
| AC4 | Generate Invoices | Create sales invoices |
| AC5 | View Financial Reports | Access P&L, balance sheets |
| AC6 | Approve Payments | Approve expense payments |
| AC7 | Record Sales | Log fish sales revenue |
| AC8 | Tax Reporting | Generate tax-related reports |
| AC9 | Salary Management | Track staff salary payments |
| AC10 | Audit Expenses | Review expense claims |

---

### 6. 🐟 FEEDER (Feeding Staff)

**Description:** Responsible for daily fish feeding operations.

**Responsibilities:**
- Daily feeding
- Feed inventory tracking
- Feeding schedule adherence
- Basic fish observation

**Use Cases:**
| # | Use Case | Description |
|---|----------|-------------|
| F1 | Record Feeding | Log daily feeding activity |
| F2 | View Feeding Schedule | See assigned feeding tasks |
| F3 | Update Feed Stock | Log feed usage and remaining stock |
| F4 | Report Issues | Report fish behavior anomalies |
| F5 | View Assigned Ponds | See ponds assigned for feeding |
| F6 | Complete Tasks | Mark feeding tasks as done |
| F7 | Request Feed | Request feed restocking |
| F8 | View Feeding History | See past feeding records |

---

### 7. 👨‍🌾 WORKER (Field Staff)

**Description:** General field worker for various farm tasks.

**Responsibilities:**
- General maintenance
- Sampling assistance
- Harvesting support
- Equipment handling

**Use Cases:**
| # | Use Case | Description |
|---|----------|-------------|
| W1 | View Assigned Tasks | See tasks assigned to them |
| W2 | Complete Tasks | Mark tasks as complete |
| W3 | Record Sampling | Log fish sampling data (with supervision) |
| W4 | Report Issues | Report equipment/pond issues |
| W5 | View Work Schedule | See daily/weekly schedule |
| W6 | Request Leave | Submit leave requests |
| W7 | View Own Records | See personal work history |
| W8 | Chat with Team | Message supervisors/coworkers |

---

## 🔐 Permission Matrix

### Legend:
- ✅ Full Access (Create, Read, Update, Delete)
- 📖 Read Only
- ✏️ Create/Update Only
- ❌ No Access
- 🔒 Own Records Only

| Feature | Owner | Manager | Supervisor | Analyst | Accountant | Feeder | Worker |
|---------|-------|---------|------------|---------|------------|--------|--------|
| **User Management** |
| Create Users | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Edit Users | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Delete Users | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| View All Users | ✅ | ✅ | 📖 | 📖 | 📖 | ❌ | ❌ |
| **Pond Management** |
| Create Ponds | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Edit Ponds | ✅ | ✅ | ✏️ | ❌ | ❌ | ❌ | ❌ |
| Delete Ponds | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| View All Ponds | ✅ | ✅ | 🔒 | 📖 | 📖 | 🔒 | 🔒 |
| **Fish Management** |
| Add Fish Species | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Stock Fish (Buy) | ✅ | ✅ | ✏️ | ❌ | ✏️ | ❌ | ❌ |
| Transfer Fish | ✅ | ✅ | ✏️ | ❌ | ❌ | ❌ | ❌ |
| Record Mortality | ✅ | ✅ | ✏️ | ❌ | ❌ | ❌ | ❌ |
| Harvest Fish | ✅ | ✅ | ✏️ | ❌ | ✏️ | ❌ | ❌ |
| View Fish Data | ✅ | ✅ | 🔒 | 📖 | 📖 | 🔒 | 🔒 |
| **Feeding** |
| Record Feeding | ✅ | ✅ | ✅ | ❌ | ❌ | ✏️ | ❌ |
| View Feeding Schedule | ✅ | ✅ | ✅ | 📖 | 📖 | 📖 | ❌ |
| Manage Feed Inventory | ✅ | ✅ | ✏️ | 📖 | ✏️ | 📖 | ❌ |
| **Sampling & Growth** |
| Record Sampling | ✅ | ✅ | ✏️ | ❌ | ❌ | ❌ | ✏️ |
| Approve Sampling | ✅ | ✅ | ✏️ | ❌ | ❌ | ❌ | ❌ |
| View Growth Data | ✅ | ✅ | 🔒 | 📖 | 📖 | ❌ | ❌ |
| **Financial** |
| Create Expenses | ✅ | ✅ | ✏️ | ❌ | ✅ | ❌ | ❌ |
| Approve Expenses | ✅ | ✅ | ❌ | ❌ | ✏️ | ❌ | ❌ |
| View Expenses | ✅ | ✅ | 🔒 | 📖 | ✅ | ❌ | ❌ |
| Record Transactions | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| View Transactions | ✅ | ✅ | ❌ | 📖 | ✅ | ❌ | ❌ |
| Manage Bank Accounts | ✅ | 📖 | ❌ | ❌ | ✏️ | ❌ | ❌ |
| **Tasks** |
| Create Tasks | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Assign Tasks | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| View All Tasks | ✅ | ✅ | 🔒 | 📖 | ❌ | 🔒 | 🔒 |
| Complete Tasks | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| Delete Tasks | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Reports** |
| View Operational Reports | ✅ | ✅ | 📖 | ✅ | 📖 | ❌ | ❌ |
| View Financial Reports | ✅ | ✅ | ❌ | 📖 | ✅ | ❌ | ❌ |
| Export Reports | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| Create Custom Reports | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| **Messaging** |
| Send Messages | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Create Groups | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Broadcast Messages | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Settings** |
| System Settings | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Farm Settings | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| View Audit Logs | ✅ | ✅ | ❌ | 📖 | 📖 | ❌ | ❌ |

---

## 🔑 Role-Based API Access

### Authentication Endpoints
| Endpoint | Owner | Manager | Supervisor | Analyst | Accountant | Feeder | Worker |
|----------|-------|---------|------------|---------|------------|--------|--------|
| `POST /auth/login` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `POST /auth/refresh` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `POST /auth/logout` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `GET /auth/me` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### User Management Endpoints
| Endpoint | Owner | Manager | Supervisor | Analyst | Accountant | Feeder | Worker |
|----------|-------|---------|------------|---------|------------|--------|--------|
| `POST /user/create` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `GET /user/list` | ✅ | ✅ | 📖 | 📖 | 📖 | ❌ | ❌ |
| `PUT /user/{id}` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `DELETE /user/{id}` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### Pond Endpoints
| Endpoint | Owner | Manager | Supervisor | Analyst | Accountant | Feeder | Worker |
|----------|-------|---------|------------|---------|------------|--------|--------|
| `POST /pond/create` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `GET /pond/list` | ✅ | ✅ | 🔒 | 📖 | 📖 | 🔒 | 🔒 |
| `GET /pond/{id}` | ✅ | ✅ | 🔒 | 📖 | 📖 | 🔒 | 🔒 |
| `PUT /pond/{id}` | ✅ | ✅ | ✏️ | ❌ | ❌ | ❌ | ❌ |
| `DELETE /pond/{id}` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

### Event Endpoints
| Endpoint | Owner | Manager | Supervisor | Analyst | Accountant | Feeder | Worker |
|----------|-------|---------|------------|---------|------------|--------|--------|
| `POST /pond-event/buy` | ✅ | ✅ | ✏️ | ❌ | ✏️ | ❌ | ❌ |
| `POST /pond-event/sell` | ✅ | ✅ | ✏️ | ❌ | ✏️ | ❌ | ❌ |
| `POST /pond-event/transfer` | ✅ | ✅ | ✏️ | ❌ | ❌ | ❌ | ❌ |
| `POST /pond-event/mortality` | ✅ | ✅ | ✏️ | ❌ | ❌ | ❌ | ❌ |
| `GET /pond-event/list` | ✅ | ✅ | 🔒 | 📖 | 📖 | ❌ | ❌ |

### Feeding Endpoints
| Endpoint | Owner | Manager | Supervisor | Analyst | Accountant | Feeder | Worker |
|----------|-------|---------|------------|---------|------------|--------|--------|
| `POST /feeding/record` | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| `GET /feeding/list` | ✅ | ✅ | ✅ | 📖 | 📖 | 🔒 | ❌ |
| `GET /feeding/schedule` | ✅ | ✅ | ✅ | 📖 | ❌ | 📖 | ❌ |

### Expense Endpoints
| Endpoint | Owner | Manager | Supervisor | Analyst | Accountant | Feeder | Worker |
|----------|-------|---------|------------|---------|------------|--------|--------|
| `POST /expenses/create` | ✅ | ✅ | ✏️ | ❌ | ✅ | ❌ | ❌ |
| `GET /expenses/list` | ✅ | ✅ | 🔒 | 📖 | ✅ | ❌ | ❌ |
| `PUT /expenses/{id}/approve` | ✅ | ✅ | ❌ | ❌ | ✏️ | ❌ | ❌ |

### Task Endpoints
| Endpoint | Owner | Manager | Supervisor | Analyst | Accountant | Feeder | Worker |
|----------|-------|---------|------------|---------|------------|--------|--------|
| `POST /task/create` | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `GET /task/list` | ✅ | ✅ | 🔒 | 📖 | ❌ | 🔒 | 🔒 |
| `PUT /task/{id}/complete` | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| `DELETE /task/{id}` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

---

## 📱 Mobile App Features by Role

| Feature | Owner | Manager | Supervisor | Analyst | Accountant | Feeder | Worker |
|---------|-------|---------|------------|---------|------------|--------|--------|
| Dashboard | Full | Full | Team | Analytics | Finance | Simple | Simple |
| Pond Map | ✅ | ✅ | Assigned | 📖 | ❌ | Assigned | Assigned |
| Quick Actions | All | All | Events/Tasks | Reports | Expenses | Feeding | Tasks |
| Notifications | All | All | Team | Reports | Finance | Feeding | Tasks |
| Offline Mode | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |

---

## 🔄 Role Transition Scenarios

### Promotion Path
```
Worker → Feeder → Supervisor → Manager → Owner (invitation only)
```

### Cross-Training Scenarios
| From | To | Additional Permissions |
|------|----|-----------------------|
| Feeder | Supervisor | Task assignment, Event recording |
| Worker | Feeder | Feeding schedule access |
| Accountant | Manager | Operational permissions |

---

## 🛡️ Security Considerations

### Role Assignment Rules
1. Only **Owner** can create **Manager** accounts
2. Only **Owner/Manager** can create other roles
3. Users cannot elevate their own permissions
4. Role changes require audit logging
5. Inactive users retain role for reactivation

### Data Access Rules
1. All roles see only their `account_key` data
2. 🔒 (Own Records) means assigned ponds/tasks only
3. Financial data requires explicit permission
4. Audit logs are append-only
5. Deleted records use soft delete with `deleted_at`

### Session Rules
1. Tokens expire based on role sensitivity
2. Owner/Manager: 24 hours
3. Other roles: 7 days
4. Multiple device support for all roles
5. Force logout capability for admins

---

## 📋 Implementation Checklist

### Database Changes
- [x] Add `role` field to users collection
- [x] Add `permissions` array for custom overrides
- [x] Add `assigned_ponds` for restricted roles
- [x] Add `supervisor_key` for worker/feeder

### API Changes
- [x] Add role validation middleware (`fin_server/security/decorators.py`)
- [x] Add permission checking decorators (`require_role`, `require_permission`, etc.)
- [x] Update user creation to include role
- [x] Add role-based query filters (`fin_server/utils/permission_helpers.py`)

### New Files Created
| File | Purpose |
|------|---------|
| `fin_server/security/roles.py` | Role & Permission enums, ROLE_PERMISSIONS mapping |
| `fin_server/security/decorators.py` | `@require_role`, `@require_permission`, `@require_admin`, etc. |
| `fin_server/dto/role_dto.py` | RoleDTO, RoleAssignmentDTO |
| `fin_server/repository/user/role_repository.py` | Role database operations |
| `fin_server/services/role_service.py` | Role business logic |
| `fin_server/routes/role.py` | Role management API endpoints |
| `fin_server/utils/permission_helpers.py` | Permission utility functions |

### UI Changes
- [ ] Role-based menu visibility
- [ ] Permission-based button states
- [ ] Role indicator in profile
- [ ] Admin panel for role management

---

## 📝 Notes

1. **Default Role:** New users created without role default to `worker`
2. **Role Combination:** Users can have only ONE role at a time
3. **Custom Permissions:** Owners can grant specific permissions beyond role defaults
4. **Audit Trail:** All permission changes are logged

---

*Document created: January 13, 2026*  
*Backend implementation: January 13, 2026*  
*Status: ✅ Backend Complete - UI pending*

