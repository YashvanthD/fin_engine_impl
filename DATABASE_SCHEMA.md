# 🗄️ Fish Farm Engine - Database Schema & Relations

**Version:** 1.0  
**Last Updated:** January 12, 2026

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Entity Relationship Diagram](#entity-relationship-diagram)
3. [Core Collections](#core-collections)
4. [Fish Management Collections](#fish-management-collections)
5. [Financial Collections](#financial-collections)
6. [Messaging Collections](#messaging-collections)
7. [Supporting Collections](#supporting-collections)
8. [Data Flow Diagrams](#data-flow-diagrams)
9. [Index Recommendations](#index-recommendations)

---

## Overview

The Fish Farm Engine uses **MongoDB** as its primary database. The schema is designed for:
- **Multi-tenancy**: All data is scoped by `account_key`
- **Audit Trail**: All records track `user_key`, `created_at`, `updated_at`
- **Soft Delete**: Records use `deleted_at` instead of hard delete
- **Referential Integrity**: Collections are linked via ID references

### Key Identifiers

| Field | Description | Example |
|-------|-------------|---------|
| `account_key` | Organization/Company ID | `"ACC-123456"` |
| `user_key` | User identifier | `"USR-ABC123"` |
| `pond_id` | Pond identifier | `"ACC-123456-001"` |
| `species_code` | Fish species code | `"TILAPIA_NILE"` |

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           FISH FARM ENGINE - ENTITY RELATIONS                            │
└─────────────────────────────────────────────────────────────────────────────────────────┘

                                    ┌───────────────┐
                                    │   companies   │
                                    │───────────────│
                                    │ account_key●──┼──────────────────────────────────────┐
                                    │ company_name  │                                      │
                                    │ admin_user_key│──┐                                   │
                                    └───────────────┘  │                                   │
                                           │           │                                   │
                    ┌──────────────────────┘           │                                   │
                    ▼                                  ▼                                   │
            ┌───────────────┐                  ┌───────────────┐                           │
            │     users     │◄─────────────────│ bank_accounts │                           │
            │───────────────│                  │───────────────│                           │
            │ user_key●     │                  │ account_id●   │                           │
            │ account_key○──┼──────────────────│ account_key○  │                           │
            │ username      │                  │ user_key○     │                           │
            │ roles[]       │                  │ balance       │                           │
            └───────────────┘                  │ type          │                           │
                    │                          └───────────────┘                           │
                    │                                  │                                   │
    ┌───────────────┼───────────────┬─────────────────┼────────────────────────────────────┤
    │               │               │                 │                                    │
    ▼               ▼               ▼                 ▼                                    │
┌─────────┐   ┌─────────┐   ┌───────────┐    ┌──────────────┐                              │
│  tasks  │   │ feeding │   │   ponds   │    │   expenses   │                              │
│─────────│   │─────────│   │───────────│    │──────────────│                              │
│ task_id●│   │feed_id● │   │ pond_id●  │    │ expense_id●  │                              │
│user_key○│   │pond_id○ │   │account_key○────│ account_key○─┼──────────────────────────────┘
│assignee │   │user_key○│   │ metadata  │    │ amount       │
└─────────┘   └─────────┘   │ fish_types│    │ category     │
                            └───────────┘    │ metadata     │
                                  │          │ event_id○    │
                    ┌─────────────┤          │ sampling_id○ │
                    │             │          └──────────────┘
                    ▼             ▼                  ▲
            ┌─────────────┐ ┌───────────────┐       │
            │ pond_event  │ │   sampling    │       │
            │─────────────│ │───────────────│       │
            │ event_id●   │ │ sampling_id●  │       │
            │ pond_id○    │ │ pond_id○      │       │
            │ fish_id○    │ │ species○      │       │
            │ event_type  │ │ event_id○     │───────┘
            │ sampling_id○│◄┼───────────────│
            │ expense_id○ │ │ expense_id○   │
            │ transfer_id │ │ stock_id      │
            └─────────────┘ └───────────────┘
                  │                 │
                  │    ┌───────────┘
                  ▼    ▼
            ┌─────────────────┐
            │ fish_analytics  │
            │─────────────────│
            │ batch_id●       │
            │ pond_id○        │
            │ species○        │
            │ account_key○    │
            │ count           │
            │ fish_age        │
            └─────────────────┘
                    │
                    ▼
            ┌───────────────┐      ┌───────────────┐
            │     fish      │◄─────│ fish_mapping  │
            │───────────────│      │───────────────│
            │ species_code● │      │ account_key●  │
            │ common_name   │      │ fish_ids[]○   │
            │ current_stock │      └───────────────┘
            └───────────────┘


═══════════════════════════════════════════════════════════════════════════════════════════
                              MESSAGING SUBSYSTEM
═══════════════════════════════════════════════════════════════════════════════════════════

┌───────────────┐         ┌───────────────┐         ┌─────────────────┐
│    users      │◄────────│ conversations │────────►│    messages     │
│───────────────│         │───────────────│         │─────────────────│
│ user_key●     │         │ conv_id●      │         │ message_id●     │
└───────────────┘         │ participants[]│         │ conversation_id○│
        │                 │ last_message  │         │ sender_key○     │
        │                 │ account_key○  │         │ content         │
        │                 └───────────────┘         │ reply_to○       │
        │                         │                 │ forwarded_from○ │
        │                         │                 └─────────────────┘
        │                         │                         │
        ▼                         ▼                         ▼
┌───────────────┐         ┌───────────────┐         ┌─────────────────┐
│ user_presence │         │  (room/topic) │         │message_receipts │
│───────────────│         │───────────────│         │─────────────────│
│ user_key●     │         │ conv:{id}     │         │ message_id○     │
│ status        │         │               │         │ user_key○       │
│ last_seen     │         │               │         │ status          │
│ socket_id     │         │               │         │ timestamp       │
└───────────────┘         └───────────────┘         └─────────────────┘


Legend:
  ● = Primary Key
  ○ = Foreign Key Reference
  ──► = References
  ◄── = Referenced By
```

---

## Core Collections

### 1. `users`

User accounts for authentication and authorization.

```javascript
{
  "_id": ObjectId,
  "user_key": "USR-ABC123",           // Unique user identifier
  "account_key": "ACC-123456",         // Organization reference
  "username": "john_doe",
  "email": "john@example.com",
  "phone": "+91-9876543210",
  "password_hash": "...",              // bcrypt hashed
  "roles": ["admin", "user"],
  "settings": {
    "timezone": "Asia/Kolkata",
    "notifications": true,
    "theme": "light"
  },
  "subscription": {
    "type": "premium",
    "expires_at": ISODate
  },
  "refresh_tokens": ["token1", "token2"],
  "last_login": ISODate,
  "joined_date": "2026-01-01",
  "created_at": ISODate,
  "updated_at": ISODate,
  "deleted_at": null                   // Soft delete
}
```

**Indexes:**
```javascript
db.users.createIndex({ "user_key": 1 }, { unique: true })
db.users.createIndex({ "account_key": 1, "username": 1 })
db.users.createIndex({ "email": 1 }, { sparse: true })
db.users.createIndex({ "phone": 1 }, { sparse: true })
```

**Relations:**
- Belongs to: `companies` (via `account_key`)
- Has many: `tasks`, `feeding`, `pond_event`, `expenses`
- Has one: `bank_accounts` (user type), `user_presence`

---

### 2. `companies`

Organization/Farm registration and metadata.

```javascript
{
  "_id": ObjectId,
  "account_key": "ACC-123456",         // Unique org identifier
  "company_name": "Green Valley Fish Farm",
  "admin_user_key": "USR-ABC123",      // Primary admin
  "users": [
    {
      "user_key": "USR-ABC123",
      "username": "admin",
      "roles": ["admin"],
      "joined_date": "2026-01-01",
      "active": true
    }
  ],
  "pincode": "560001",
  "address": "123 Farm Road",
  "description": "Premium fish farming",
  "employee_count": 5,
  "created_date": 1704067200,          // Epoch timestamp
  "settings": {
    "currency": "INR",
    "timezone": "Asia/Kolkata"
  },
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes:**
```javascript
db.companies.createIndex({ "account_key": 1 }, { unique: true })
db.companies.createIndex({ "admin_user_key": 1 })
```

**Relations:**
- Has many: `users`, `ponds`, `fish_mapping`, `expenses`, `transactions`
- Has one: `bank_accounts` (organization type)

---

### 3. `bank_accounts`

Financial accounts for users and organizations.

```javascript
{
  "_id": ObjectId,
  "account_id": "BANK-001",
  "account_key": "ACC-123456",         // Organization
  "user_key": "USR-ABC123",            // Optional: user account
  "type": "organization",              // "organization" | "user"
  "name": "Main Operating Account",
  "balance": 500000.00,
  "currency": "INR",
  "bank_name": "State Bank",
  "account_number": "XXXX1234",
  "ifsc_code": "SBIN0001234",
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes:**
```javascript
db.bank_accounts.createIndex({ "account_key": 1, "type": 1 })
db.bank_accounts.createIndex({ "user_key": 1 }, { sparse: true })
```

**Relations:**
- Belongs to: `companies`, `users`
- Has many: `statement_lines`

---

## Fish Management Collections

### 4. `ponds`

Pond infrastructure and metadata.

```javascript
{
  "_id": "ACC-123456-001",             // Same as pond_id
  "pond_id": "ACC-123456-001",
  "account_key": "ACC-123456",
  "name": "Pond A - Tilapia",
  "type": "earthen",                   // "earthen" | "concrete" | "tank"
  "area": 2000,                        // Square meters
  "depth": 1.5,                        // Meters
  "capacity": 3000,                    // Max fish capacity
  "location": {
    "lat": 12.9716,
    "lng": 77.5946
  },
  "metadata": {
    "total_fish": 2500,
    "fish_types": {
      "TILAPIA_NILE": 1500,
      "CATLA": 1000
    },
    "last_activity": {
      "event_type": "add",
      "fish_id": "TILAPIA_NILE",
      "count": 500,
      "timestamp": "2026-01-12T10:00:00Z"
    }
  },
  "current_stock": [
    {
      "species": "TILAPIA_NILE",
      "count": 1500,
      "avg_weight": 250,
      "added_date": ISODate
    }
  ],
  "water_quality": {
    "ph": 7.2,
    "temperature": 28,
    "dissolved_oxygen": 6.5,
    "last_checked": ISODate
  },
  "status": "active",                  // "active" | "inactive" | "maintenance"
  "created_at": ISODate,
  "updated_at": ISODate,
  "deleted_at": null
}
```

**Indexes:**
```javascript
db.ponds.createIndex({ "pond_id": 1 }, { unique: true })
db.ponds.createIndex({ "account_key": 1 })
db.ponds.createIndex({ "status": 1 })
```

**Relations:**
- Belongs to: `companies`
- Has many: `pond_event`, `sampling`, `feeding`, `fish_analytics`, `expenses`

---

### 5. `fish`

Fish species catalog and global stock.

```javascript
{
  "_id": "TILAPIA_NILE",               // Same as species_code
  "species_code": "TILAPIA_NILE",
  "common_name": "Nile Tilapia",
  "scientific_name": "Oreochromis niloticus",
  "category": "freshwater",
  "current_stock": 15000,              // Total across all ponds
  "growth_rate": {
    "optimal_temp": [25, 30],
    "target_weight_kg": 0.5,
    "growth_period_months": 6
  },
  "feed_info": {
    "feed_type": "pellet",
    "protein_requirement": 32,
    "fcr": 1.5                         // Feed conversion ratio
  },
  "price_range": {
    "min": 120,
    "max": 180,
    "currency": "INR",
    "unit": "kg"
  },
  "image_url": "/images/tilapia.jpg",
  "account_key": "ACC-123456",         // Optional: custom species
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes:**
```javascript
db.fish.createIndex({ "species_code": 1 }, { unique: true })
db.fish.createIndex({ "common_name": "text", "scientific_name": "text" })
```

**Relations:**
- Referenced by: `pond_event`, `sampling`, `fish_analytics`, `fish_mapping`

---

### 6. `fish_mapping`

Maps fish species to organizations.

```javascript
{
  "_id": ObjectId,
  "account_key": "ACC-123456",
  "fish_ids": [
    "TILAPIA_NILE",
    "CATLA",
    "ROHU",
    "PANGASIUS"
  ],
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes:**
```javascript
db.fish_mapping.createIndex({ "account_key": 1 }, { unique: true })
```

**Relations:**
- Belongs to: `companies`
- References: `fish` (via `fish_ids[]`)

---

### 7. `pond_event`

All events that happen in a pond (buy, sell, sample, transfer, etc.)

```javascript
{
  "_id": ObjectId,
  "event_id": "EVT-20260112-ABC",
  "pond_id": "ACC-123456-001",
  "account_key": "ACC-123456",
  "user_key": "USR-ABC123",            // Who performed
  "event_type": "add",                 // See event types below
  "fish_id": "TILAPIA_NILE",
  "count": 500,
  "fish_age_in_month": 2,
  "details": {
    "supplier": "Fish Hatchery Ltd",
    "price_per_fish": 5,
    "total_amount": 2500,
    "batch_number": "BTH-001"
  },
  "samples": [                         // For sample events
    { "weight": 250, "length": 15 },
    { "weight": 260, "length": 16 }
  ],
  "sampling_id": "SAM-001",            // Link to sampling
  "expense_id": "EXP-001",             // Link to expense
  "transfer_id": "TXF-001",            // Link shift_out ↔ shift_in
  "recorded_by": "USR-ABC123",
  "created_at": ISODate,
  "updated_at": ISODate,
  "deleted_at": null
}
```

**Event Types:**
| Type | Effect | Description |
|------|--------|-------------|
| `add` | +fish | Initial stocking or purchase |
| `buy` | +fish | Same as add (alias) |
| `sell` | -fish, +income | Fish sale |
| `sample` | -fish | Growth sampling |
| `remove` | -fish | Mortality/removal |
| `shift_out` | -fish | Transfer out |
| `shift_in` | +fish | Transfer in |

**Indexes:**
```javascript
db.pond_event.createIndex({ "pond_id": 1, "created_at": -1 })
db.pond_event.createIndex({ "account_key": 1, "event_type": 1 })
db.pond_event.createIndex({ "transfer_id": 1 }, { sparse: true })
db.pond_event.createIndex({ "sampling_id": 1 }, { sparse: true })
```

**Relations:**
- Belongs to: `ponds`, `companies`, `users`
- References: `fish`, `sampling`, `expenses`
- Self-references: `transfer_id` links paired events

---

### 8. `sampling`

Fish purchase and growth sampling records.

```javascript
{
  "_id": ObjectId,
  "sampling_id": "SAM-20260112-001",
  "pond_id": "ACC-123456-001",
  "account_key": "ACC-123456",
  "user_key": "USR-ABC123",
  "species": "TILAPIA_NILE",
  "type": "buy",                       // "buy" | "sampling" | "growth_check"
  "total_count": 500,
  "total_amount": 2500.00,
  "average_weight": 50,                // grams
  "average_length": 10,                // cm
  "sample_size": 20,
  "survival_rate": 98.5,
  "feed_conversion_ratio": 1.5,
  "cost_per_unit": 5.00,
  "stock_id": "STK-001",               // Link to fish_analytics batch
  "event_id": "EVT-001",               // Link to pond_event
  "expense_id": "EXP-001",             // Link to expense
  "notes": "Healthy batch from certified hatchery",
  "metadata": {
    "supplier": "Fish Hatchery Ltd",
    "batch_number": "BTH-001",
    "certificate": "CERT-2026-001"
  },
  "created_at": ISODate,
  "updated_at": ISODate,
  "deleted_at": null
}
```

**Indexes:**
```javascript
db.sampling.createIndex({ "pond_id": 1, "created_at": -1 })
db.sampling.createIndex({ "account_key": 1, "species": 1 })
db.sampling.createIndex({ "sampling_id": 1 }, { unique: true })
```

**Relations:**
- Belongs to: `ponds`, `companies`
- References: `fish`, `pond_event`, `expenses`, `fish_analytics`

---

### 9. `fish_analytics`

Fish population batches and growth tracking.

```javascript
{
  "_id": ObjectId,
  "batch_id": "BTH-20260112-001",
  "account_key": "ACC-123456",
  "pond_id": "ACC-123456-001",
  "species": "TILAPIA_NILE",
  "count": 500,                        // Can be negative for removals
  "fish_age_in_month": 2,
  "event_type": "add",
  "avg_weight": 50,
  "avg_length": 10,
  "stocking_date": ISODate,
  "expected_harvest_date": ISODate,
  "growth_data": [
    {
      "date": ISODate,
      "avg_weight": 100,
      "sample_size": 20
    }
  ],
  "metadata": {
    "batch_number": "BTH-001",
    "source": "sampling",
    "sampling_id": "SAM-001"
  },
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes:**
```javascript
db.fish_analytics.createIndex({ "account_key": 1, "species": 1, "pond_id": 1 })
db.fish_analytics.createIndex({ "pond_id": 1, "created_at": -1 })
db.fish_analytics.createIndex({ "batch_id": 1 })
```

**Relations:**
- Belongs to: `ponds`, `companies`
- References: `fish`, `sampling`

---

### 10. `fish_activity`

Detailed activity logs for fish operations.

```javascript
{
  "_id": ObjectId,
  "activity_id": "ACT-001",
  "account_key": "ACC-123456",
  "pond_id": "ACC-123456-001",
  "fish_id": "TILAPIA_NILE",
  "event_type": "sample",
  "event_id": "EVT-001",               // Link to pond_event
  "count": 20,
  "user_key": "USR-ABC123",
  "details": {
    "purpose": "growth_check",
    "method": "cast_net"
  },
  "samples": [
    { "weight": 250, "length": 15 },
    { "weight": 260, "length": 16 }
  ],
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes:**
```javascript
db.fish_activity.createIndex({ "pond_id": 1, "created_at": -1 })
db.fish_activity.createIndex({ "event_id": 1 })
```

---

### 11. `feeding`

Fish feeding records.

```javascript
{
  "_id": ObjectId,
  "feed_id": "FEED-20260112-001",
  "pond_id": "ACC-123456-001",
  "account_key": "ACC-123456",
  "user_key": "USR-ABC123",
  "feed_type": "pellet_32",
  "feed_brand": "Cargill Aqua",
  "quantity": 50,                      // kg
  "unit": "kg",
  "feeding_time": ISODate,
  "cost": 2500.00,                     // Optional
  "expense_id": "EXP-001",             // Link to expense if cost provided
  "notes": "Morning feed",
  "weather": "sunny",
  "water_temp": 28,
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes:**
```javascript
db.feeding.createIndex({ "pond_id": 1, "feeding_time": -1 })
db.feeding.createIndex({ "account_key": 1, "created_at": -1 })
```

**Relations:**
- Belongs to: `ponds`, `companies`, `users`
- References: `expenses` (optional)

---

## Financial Collections

### 12. `expenses`

All financial expenses and income.

```javascript
{
  "_id": ObjectId,
  "expense_id": "EXP-20260112-001",
  "account_key": "ACC-123456",
  "user_key": "USR-ABC123",
  "amount": 2500.00,
  "currency": "INR",
  "category": "Hatchery & Stock",      // From expense catalog
  "subcategory": "Fingerlings",
  "detail": "Tilapia fingerlings",
  "category_path": "Hatchery & Stock/Fingerlings/Tilapia fingerlings",
  "type": "fish",                      // "fish" | "feed" | "maintenance" | etc.
  "action": "buy",                     // "buy" | "sell" | "pay" | etc.
  "status": "SUCCESS",                 // "DRAFT" | "PENDING" | "SUCCESS" | "FAILED"
  "payment_method": "bank_transfer",
  "notes": "Fish purchase for Pond A",
  "metadata": {
    "pond_id": "ACC-123456-001",
    "species": "TILAPIA_NILE",
    "count": 500,
    "event_id": "EVT-001",
    "sampling_id": "SAM-001"
  },
  "transaction_ref": "TXN-001",        // Link to transaction
  "vendor": {
    "name": "Fish Hatchery Ltd",
    "contact": "+91-9876543210"
  },
  "invoice_no": "INV-2026-001",
  "gst": 450.00,
  "tax": 0,
  "approved_by": "USR-ADMIN",
  "approved_at": ISODate,
  "created_at": ISODate,
  "updated_at": ISODate,
  "deleted_at": null
}
```

**Indexes:**
```javascript
db.expenses.createIndex({ "account_key": 1, "created_at": -1 })
db.expenses.createIndex({ "account_key": 1, "category": 1 })
db.expenses.createIndex({ "metadata.pond_id": 1 })
db.expenses.createIndex({ "metadata.event_id": 1 })
db.expenses.createIndex({ "status": 1 })
```

**Relations:**
- Belongs to: `companies`, `users`
- References: `pond_event`, `sampling`, `transactions`
- Referenced by: `statement_lines`

---

### 13. `transactions`

Financial transaction ledger.

```javascript
{
  "_id": ObjectId,
  "tx_id": "TXN-20260112-001",
  "account_key": "ACC-123456",
  "user_key": "USR-ABC123",
  "amount": 2500.00,
  "currency": "INR",
  "type": "expense",                   // "expense" | "income" | "transfer"
  "subtype": "fish_purchase",
  "status": "completed",
  "direction": "out",                  // "in" | "out"
  "bank_account_id": "BANK-001",
  "related_id": "EXP-001",             // Link to expense/sampling
  "entries": [
    {
      "account": "assets:fish_stock",
      "debit": 2500.00,
      "credit": 0
    },
    {
      "account": "assets:bank",
      "debit": 0,
      "credit": 2500.00
    }
  ],
  "metadata": {
    "expense_id": "EXP-001",
    "pond_id": "ACC-123456-001"
  },
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes:**
```javascript
db.transactions.createIndex({ "account_key": 1, "created_at": -1 })
db.transactions.createIndex({ "tx_id": 1 }, { unique: true })
db.transactions.createIndex({ "related_id": 1 })
```

---

### 14. `statement_lines`

Bank statement line items (passbook entries).

```javascript
{
  "_id": ObjectId,
  "bank_account_id": "BANK-001",
  "account_key": "ACC-123456",
  "amount": 2500.00,
  "currency": "INR",
  "direction": "out",                  // "in" | "out"
  "running_balance": 497500.00,
  "reference": {
    "type": "expense",
    "id": "EXP-001"
  },
  "description": "Fish purchase",
  "transaction_id": "TXN-001",
  "created_at": ISODate
}
```

**Indexes:**
```javascript
db.statement_lines.createIndex({ "bank_account_id": 1, "created_at": -1 })
db.statement_lines.createIndex({ "reference.id": 1 })
```

---

## Messaging Collections

### 15. `conversations`

Chat conversations (direct, group, broadcast).

```javascript
{
  "_id": "CONV-ABC123",
  "conversation_id": "CONV-ABC123",
  "conversation_type": "direct",       // "direct" | "group" | "broadcast"
  "participants": ["USR-001", "USR-002"],
  "name": null,                        // For groups
  "description": null,
  "avatar_url": null,
  "created_by": "USR-001",
  "admins": [],                        // For groups
  "last_message": {
    "message_id": "MSG-XYZ",
    "sender_key": "USR-001",
    "content": "Hello!",
    "message_type": "text",
    "created_at": ISODate
  },
  "last_activity": ISODate,
  "muted_by": [],
  "pinned_by": ["USR-001"],
  "archived_by": [],
  "account_key": "ACC-123456",
  "metadata": {},
  "created_at": ISODate
}
```

**Indexes:**
```javascript
db.conversations.createIndex({ "participants": 1, "account_key": 1 })
db.conversations.createIndex({ "last_activity": -1 })
db.conversations.createIndex({ "conversation_id": 1 }, { unique: true })
```

---

### 16. `messages`

Chat messages.

```javascript
{
  "_id": "MSG-XYZ123",
  "message_id": "MSG-XYZ123",
  "conversation_id": "CONV-ABC123",
  "sender_key": "USR-001",
  "content": "Hello! How are you?",
  "message_type": "text",              // "text" | "image" | "file" | "audio" | "video"
  "reply_to": null,                    // Message ID if replying
  "forwarded_from": null,              // Message ID if forwarded
  "media_url": null,
  "media_thumbnail": null,
  "mentions": [],
  "metadata": {},
  "account_key": "ACC-123456",
  "created_at": ISODate,
  "edited_at": null,
  "deleted_at": null,                  // Soft delete for everyone
  "deleted_for": []                    // Soft delete for specific users
}
```

**Indexes:**
```javascript
db.messages.createIndex({ "conversation_id": 1, "created_at": -1 })
db.messages.createIndex({ "sender_key": 1 })
db.messages.createIndex({ "content": "text" })
db.messages.createIndex({ "message_id": 1 }, { unique: true })
```

---

### 17. `message_receipts`

Message delivery and read receipts.

```javascript
{
  "_id": ObjectId,
  "message_id": "MSG-XYZ123",
  "user_key": "USR-002",
  "status": "read",                    // "sent" | "delivered" | "read"
  "timestamp": ISODate
}
```

**Indexes:**
```javascript
db.message_receipts.createIndex({ "message_id": 1, "user_key": 1 }, { unique: true })
db.message_receipts.createIndex({ "user_key": 1, "status": 1 })
```

---

### 18. `user_presence`

User online/offline status.

```javascript
{
  "_id": "USR-001",
  "user_key": "USR-001",
  "status": "online",                  // "online" | "offline" | "away" | "typing"
  "last_seen": ISODate,
  "socket_id": "socket_abc123",
  "typing_in": null,                   // Conversation ID if typing
  "device_info": {
    "user_agent": "Mozilla/5.0...",
    "ip": "192.168.1.1"
  }
}
```

**Indexes:**
```javascript
db.user_presence.createIndex({ "user_key": 1 }, { unique: true })
db.user_presence.createIndex({ "status": 1 })
```

---

## Supporting Collections

### 19. `tasks`

Task and schedule management.

```javascript
{
  "_id": ObjectId,
  "task_id": "TSK-001",
  "account_key": "ACC-123456",
  "user_key": "USR-001",               // Creator
  "reporter": "USR-001",
  "assignee": "USR-002",
  "assigned_to": "USR-002",
  "title": "Check water quality Pond A",
  "description": "Daily pH and temperature check",
  "status": "pending",                 // "pending" | "inprogress" | "completed"
  "priority": "high",                  // "low" | "normal" | "high" | "critical"
  "task_date": "2026-01-12",
  "end_date": "2026-01-12 18:00",
  "recurring": "daily",                // "once" | "daily" | "weekly" | "monthly"
  "reminder": true,
  "reminder_time": "08:00",
  "remind_before": 30,                 // minutes
  "tags": ["water-quality", "pond-a"],
  "history": [
    {
      "action": "created",
      "by": "USR-001",
      "at": ISODate
    }
  ],
  "comments": [],
  "viewed": false,
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes:**
```javascript
db.tasks.createIndex({ "assignee": 1, "status": 1 })
db.tasks.createIndex({ "account_key": 1, "task_date": 1 })
db.tasks.createIndex({ "end_date": 1 })
```

---

### 20. `notification_queue`

Pending notifications for delivery.

```javascript
{
  "_id": ObjectId,
  "user_key": "USR-002",
  "from_user_key": "USR-001",
  "message": "You have a new task assigned",
  "type": "task",                      // "task" | "message" | "alert" | "system"
  "data": {
    "task_id": "TSK-001"
  },
  "status": "pending",                 // "pending" | "sent" | "failed"
  "sent_at": null,
  "created_at": ISODate
}
```

---

### 21. `audit_logs`

System audit trail.

```javascript
{
  "_id": ObjectId,
  "action": "create",                  // "create" | "update" | "delete" | "soft_delete"
  "collection": "pond_event",
  "document_id": "EVT-001",
  "user_key": "USR-001",
  "account_key": "ACC-123456",
  "timestamp": ISODate,
  "changes": {
    "added": {},
    "removed": {},
    "modified": {
      "count": { "old": 400, "new": 500 }
    }
  },
  "old_values": { "count": 400 },
  "new_values": { "count": 500 },
  "metadata": {
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0..."
  }
}
```

**Indexes:**
```javascript
db.audit_logs.createIndex({ "account_key": 1, "timestamp": -1 })
db.audit_logs.createIndex({ "collection": 1, "document_id": 1 })
db.audit_logs.createIndex({ "user_key": 1 })
```

---

## Data Flow Diagrams

### Flow 1: Fish Purchase (Buy)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FISH PURCHASE FLOW                                  │
│                                                                             │
│  API: POST /sampling                                                        │
│  Service: sampling_service.perform_buy_sampling()                           │
└─────────────────────────────────────────────────────────────────────────────┘

     ┌──────────┐
     │  Client  │
     └────┬─────┘
          │ POST /sampling
          │ { pondId, species, totalCount, totalAmount, ... }
          ▼
     ┌──────────────────────────────────────────────────────────────────┐
     │                     SAMPLING SERVICE                             │
     └──────────────────────────────────────────────────────────────────┘
          │
          ├──① CREATE SAMPLING RECORD
          │   └──► sampling { sampling_id, pond_id, species, total_count }
          │
          ├──② ENSURE FISH MAPPING
          │   └──► fish_mapping { $addToSet: fish_ids }
          │
          ├──③ UPDATE POND METADATA (atomic)
          │   └──► ponds { $inc: total_fish, fish_types.{species} }
          │
          ├──④ CREATE POND EVENT
          │   └──► pond_event { event_type: 'buy', sampling_id, ... }
          │        │
          │        └──► Update sampling with event_id
          │
          ├──⑤ UPDATE FISH STOCK
          │   └──► fish { $inc: current_stock }
          │
          ├──⑥ CREATE EXPENSE
          │   └──► expenses { category: 'Hatchery & Stock', action: 'buy' }
          │        │
          │        ├──► Update sampling with expense_id
          │        │
          │        └──► Update pond_event with expense_id
          │
          ├──⑦ UPDATE BANK BALANCE
          │   └──► bank_accounts { $inc: balance: -amount }
          │
          ├──⑧ CREATE STATEMENT LINE
          │   └──► statement_lines { direction: 'out', reference: expense }
          │
          └──⑨ CREATE FISH ANALYTICS BATCH
              └──► fish_analytics { batch_id, pond_id, species, count }
          
     ┌──────────────────────────────────────────────────────────────────┐
     │  RESULT: 9 collections updated with bidirectional links          │
     └──────────────────────────────────────────────────────────────────┘
```

---

### Flow 2: Fish Sale (Sell)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FISH SALE FLOW                                    │
│                                                                             │
│  API: POST /pond_event/{pond_id}/event/sell                                 │
└─────────────────────────────────────────────────────────────────────────────┘

     ┌──────────┐
     │  Client  │
     └────┬─────┘
          │ POST /pond_event/{pond_id}/event/sell
          │ { fish_id, count, details: { price_per_kg, total_weight_kg } }
          ▼
     ┌──────────────────────────────────────────────────────────────────┐
     │                     POND EVENT ROUTE                             │
     └──────────────────────────────────────────────────────────────────┘
          │
          ├──① CREATE POND EVENT
          │   └──► pond_event { event_type: 'sell', ... }
          │
          ├──② UPDATE POND METADATA
          │   └──► ponds { $inc: total_fish: -count, fish_types.{species}: -count }
          │
          ├──③ UPDATE FISH ANALYTICS
          │   └──► fish_analytics { count: -count } (negative batch)
          │
          ├──④ UPDATE FISH MAPPING
          │   └──► fish_mapping (check if species still exists)
          │
          ├──⑤ CREATE INCOME EXPENSE
          │   └──► expenses { category: 'Sales', action: 'sell', amount: revenue }
          │        │
          │        └──► Update pond_event with expense_id
          │
          ├──⑥ UPDATE BANK BALANCE (credit)
          │   └──► bank_accounts { $inc: balance: +revenue }
          │
          └──⑦ CREATE STATEMENT LINE
              └──► statement_lines { direction: 'in', reference: expense }
```

---

### Flow 3: Fish Transfer (Atomic)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ATOMIC FISH TRANSFER FLOW                              │
│                                                                             │
│  API: POST /pond_event/transfer                                             │
└─────────────────────────────────────────────────────────────────────────────┘

     ┌──────────┐
     │  Client  │
     └────┬─────┘
          │ POST /pond_event/transfer
          │ { source_pond_id, destination_pond_id, fish_id, count }
          ▼
     ┌──────────────────────────────────────────────────────────────────┐
     │                     TRANSFER HANDLER                             │
     │               (with rollback on failure)                         │
     └──────────────────────────────────────────────────────────────────┘
          │
          │  Generate: transfer_id = "TXF-{timestamp}-{random}"
          │
          ├──── STEP 1: SOURCE POND ────
          │
          ├──① CREATE SHIFT_OUT EVENT
          │   └──► pond_event { event_type: 'shift_out', transfer_id }
          │
          ├──② UPDATE SOURCE POND
          │   └──► ponds { $inc: total_fish: -count }
          │
          ├──③ ADD ANALYTICS BATCH (negative)
          │   └──► fish_analytics { count: -count }
          │
          │
          ├──── STEP 2: DESTINATION POND ────
          │
          ├──④ CREATE SHIFT_IN EVENT
          │   └──► pond_event { event_type: 'shift_in', transfer_id }
          │
          ├──⑤ UPDATE DESTINATION POND
          │   └──► ponds { $inc: total_fish: +count }
          │
          └──⑥ ADD ANALYTICS BATCH (positive)
              └──► fish_analytics { count: +count }
          
     ┌──────────────────────────────────────────────────────────────────┐
     │  ON FAILURE: Rollback by deleting shift_out event and           │
     │              reversing source pond updates                       │
     └──────────────────────────────────────────────────────────────────┘
```

---

### Flow 4: Delete Pond Event (with reversal)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DELETE POND EVENT FLOW                                   │
│                                                                             │
│  API: DELETE /pond_event/{pond_id}/events/{event_id}                        │
└─────────────────────────────────────────────────────────────────────────────┘

     ┌──────────┐
     │  Client  │
     └────┬─────┘
          │ DELETE /pond_event/{pond_id}/events/{event_id}
          ▼
     ┌──────────────────────────────────────────────────────────────────┐
     │                     DELETE HANDLER                               │
     └──────────────────────────────────────────────────────────────────┘
          │
          ├──① LOAD OLD EVENT
          │   └──► pond_event.find_one({ _id: event_id })
          │        { event_type: 'add', fish_id, count: 500 }
          │
          ├──② COMPUTE INVERSE TYPE
          │   └──► 'add' → inverse = 'remove'
          │        'sell' → inverse = 'add'
          │
          ├──③ REVERSE POND METADATA
          │   └──► ponds { $inc: total_fish: -500 } (opposite of original)
          │
          ├──④ REVERSE FISH ANALYTICS
          │   └──► fish_analytics { count: -500 } (opposite batch)
          │
          ├──⑤ REVERSE FISH STOCK
          │   └──► fish { $inc: current_stock: -500 }
          │
          ├──⑥ CANCEL LINKED EXPENSE (if exists)
          │   └──► expenses { $set: status: 'CANCELLED' }
          │
          ├──⑦ CREATE AUDIT LOG
          │   └──► audit_logs { action: 'delete', ... }
          │
          └──⑧ DELETE EVENT
              └──► pond_event.delete_one({ _id: event_id })
```

---

### Flow 5: Messaging (Send Message)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SEND MESSAGE FLOW                                      │
│                                                                             │
│  Socket Event: message:send                                                 │
└─────────────────────────────────────────────────────────────────────────────┘

     ┌──────────┐                              ┌──────────┐
     │ Sender   │                              │Recipient │
     └────┬─────┘                              └────▲─────┘
          │                                         │
          │ emit('message:send', {                  │
          │   conversationId, content               │
          │ })                                      │
          ▼                                         │
     ┌──────────────────────────────────────────────┼──────┐
     │                SOCKET SERVER                 │      │
     └──────────────────────────────────────────────┼──────┘
          │                                         │
          ├──① AUTHENTICATE                         │
          │   └──► Verify JWT token                 │
          │                                         │
          ├──② VERIFY ACCESS                        │
          │   └──► Check user in conversation       │
          │                                         │
          ├──③ CREATE MESSAGE                       │
          │   └──► messages.insert_one({            │
          │         message_id, conversation_id,    │
          │         sender_key, content             │
          │       })                                │
          │                                         │
          ├──④ UPDATE CONVERSATION                  │
          │   └──► conversations.update_one({       │
          │         last_message, last_activity     │
          │       })                                │
          │                                         │
          ├──⑤ EMIT TO SENDER                       │
          │   └──► emit('message:sent', { status }) │
          │                                         │
          ├──⑥ EMIT TO RECIPIENTS ─────────────────►│
          │   └──► emit('message:new', { ... })     │
          │                                         │
          ├──⑦ IF RECIPIENT ONLINE                  │
          │   └──► MARK DELIVERED                   │
          │        message_receipts.upsert({        │
          │          status: 'delivered'            │
          │        })                               │
          │                                         │
          └──⑧ EMIT DELIVERY RECEIPT ──────────────►│
              └──► emit('message:delivered')        │
```

---

## Index Recommendations

### Critical Indexes (Create First)

```javascript
// Authentication & Users
db.users.createIndex({ "user_key": 1 }, { unique: true })
db.users.createIndex({ "account_key": 1, "username": 1 })

// Core Operations
db.ponds.createIndex({ "pond_id": 1 }, { unique: true })
db.ponds.createIndex({ "account_key": 1 })

db.pond_event.createIndex({ "pond_id": 1, "created_at": -1 })
db.pond_event.createIndex({ "account_key": 1, "event_type": 1 })

db.sampling.createIndex({ "pond_id": 1, "created_at": -1 })
db.sampling.createIndex({ "account_key": 1 })

// Financial
db.expenses.createIndex({ "account_key": 1, "created_at": -1 })
db.expenses.createIndex({ "metadata.pond_id": 1 })

// Messaging
db.conversations.createIndex({ "participants": 1, "account_key": 1 })
db.messages.createIndex({ "conversation_id": 1, "created_at": -1 })
```

### Performance Indexes (Secondary)

```javascript
// Text Search
db.fish.createIndex({ "common_name": "text", "scientific_name": "text" })
db.messages.createIndex({ "content": "text" })

// Compound Indexes
db.fish_analytics.createIndex({ "account_key": 1, "species": 1, "pond_id": 1 })
db.feeding.createIndex({ "pond_id": 1, "feeding_time": -1 })

// Sparse Indexes
db.pond_event.createIndex({ "transfer_id": 1 }, { sparse: true })
db.pond_event.createIndex({ "sampling_id": 1 }, { sparse: true })
```

---

## Summary

### Collection Count: 21

| Category | Collections |
|----------|-------------|
| **Core** | users, companies, bank_accounts |
| **Fish Management** | ponds, fish, fish_mapping, pond_event, sampling, fish_analytics, fish_activity, feeding |
| **Financial** | expenses, transactions, statement_lines |
| **Messaging** | conversations, messages, message_receipts, user_presence |
| **Supporting** | tasks, notification_queue, audit_logs |

### Key Design Principles

1. **Multi-tenancy**: All data scoped by `account_key`
2. **Audit Trail**: `user_key`, `created_at`, `updated_at` on all records
3. **Soft Delete**: `deleted_at` field instead of hard delete
4. **Referential Links**: Bidirectional links between related collections
5. **Denormalization**: `last_message` in conversations for performance
6. **Event Sourcing**: `pond_event` as source of truth for fish operations

---

*Document generated: January 12, 2026*

