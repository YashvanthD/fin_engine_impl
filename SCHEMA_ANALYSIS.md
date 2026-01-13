# 📊 Database Schema Analysis & Improvement Recommendations

**Version:** 2.0  
**Last Updated:** January 13, 2026  
**Status:** In Progress

---

## Executive Summary

| Category | Current Score | Target Score | Status |
|----------|---------------|--------------|--------|
| **Data Consistency** | 9/10 | 9/10 | ✅ Achieved |
| **Normalization** | 7/10 | 8/10 | ⚡ In Progress |
| **Index Coverage** | 7/10 | 9/10 | ⚠️ Needs Work |
| **Referential Integrity** | 8/10 | 9/10 | ⚡ In Progress |
| **Performance** | 7/10 | 9/10 | ⚠️ Needs Work |
| **Scalability** | 8/10 | 9/10 | ⚡ In Progress |

**Overall Score: 7.7/10** → Target: **8.8/10**

---

## ✅ Resolved Issues

### 1. ~~Duplicate ID Fields in Key Identifiers~~ ✅ FIXED (Jan 13, 2026)

**Resolution:** Updated all ID generators to use new UUID hex format.

| ID Type | Old Format | New Format |
|---------|------------|------------|
| `account_key` | 6 digits (`"123456"`) | 12 digits (`"123456789012"`) |
| `user_key` | 9 digits (`"123456789"`) | 12 digits (`"987654321098"`) |
| `pond_id` | `"123456-001"` | 24 hex (`"69653c8af4c2d41e5a1bcdbd"`) |
| `message_id` | `"MSG-aB3dE5fG7"` | 24 hex (`"69653c8af4c2d41e5a1bcdbd"`) |
| `transaction_id` | `"TXN-aB3dE5fG7"` | 24 hex (`"69653c8af4c2d41e5a1bcdbd"`) |
| All other IDs | Prefixed format | Pure 24-char UUID hex |

**Files Updated:**
- `fin_server/utils/generator.py` - All ID generators now use UUID hex
- `fin_server/routes/fish.py` - Updated to use `generate_fish_event_id()`
- `fin_server/messaging/service.py` - Updated to use new generators
- `fin_server/messaging/socket_server.py` - Updated to use new generators
- `DATABASE_SCHEMA.md` - Documentation updated

---

### 2. ~~Missing `account_key` Format in Documentation~~ ✅ FIXED (Jan 13, 2026)

**Resolution:** DATABASE_SCHEMA.md now shows correct 12-digit numeric format.

---

### 3. ~~Predictable ID Prefixes~~ ✅ FIXED (Jan 13, 2026)

**Resolution:** Removed all prefixes (MSG-, TXN-, EXP-, etc.) - all IDs are now pure 24-character UUID hex strings for security.

---

### 4. ~~Duplicate `assignee`/`assigned_to` Fields in Tasks~~ ✅ FIXED (Jan 13, 2026)

**Resolution:** Removed duplicate `assigned_to` field - now using only `assignee` as the canonical field.

**Files Updated:**
- `fin_server/routes/task.py` - Removed `assigned_to`, using `assignee` only
- `fin_server/services/task_service.py` - Updated field mapping
- `fin_server/dto/task_dto.py` - Prioritizes `assignee` field
- `fin_server/utils/helpers.py` - Updated UI mapping

**Backward Compatibility:** API still accepts `assigned_to` and `assignedTo` in requests for backward compatibility but stores as `assignee`.

---

## 🔴 Critical Issues (High Priority)

### 1. `companies.users[]` Embedded Array - Scalability Risk

**Status:** ⚠️ NOT FIXED - Still present in code

**Issue:** Companies collection embeds users array:
```javascript
"users": [
  {
    "user_key": "123456789012",
    "username": "admin",
    "roles": ["admin"],
    ...
  }
]
```

**Location:** `fin_server/routes/company.py` (lines 157-165)

**Problems:**
- Document size grows with users (16MB MongoDB limit)
- Updates require rewriting entire document
- No easy way to query individual user within company

**Recommendation:** Remove embedded `users[]` array - already tracked via `account_key` in `users` collection.

**Priority:** HIGH for farms with >50 employees

---

### 2. Missing Version Field for Optimistic Locking

**Status:** ⚠️ SCRIPT EXISTS but not enforced in code

**Issue:** Collections that get concurrent updates lack version control:
- `ponds` (metadata.total_fish updated frequently)
- `bank_accounts` (balance updates)
- `fish` (current_stock)

**Existing Script:** `scripts/add_version_field.py` (migration script exists)

**Recommendation:** 
1. Run migration script to add `_v` field to existing documents
2. Update repository methods to use versioned updates

```python
# In fin_server/utils/versioning.py - Already implemented!
from fin_server.utils.versioning import versioned_update
```

---

## 🟡 Medium Priority Issues

### 4. `ponds.metadata` vs `ponds.current_stock` Redundancy

**Status:** ⚠️ NOT FIXED

**Issue:** Fish counts stored in two places:
```javascript
"metadata": {
  "total_fish": 2500,
  "fish_types": {
    "69653c8af4c2d41e5a1bcdbd": 1500,  // species_code
    "a1b2c3d4e5f6a7b8c9d0e1f2": 1000
  }
},
"current_stock": [
  {
    "species": "69653c8af4c2d41e5a1bcdbd",
    "count": 1500,
    ...
  }
]
```

**Recommendation:** Consolidate to single source of truth.

---

### 5. Missing TTL Indexes for Ephemeral Data

**Status:** ⚠️ NOT IMPLEMENTED

**Collections needing TTL:**
- `user_presence` - stale records accumulate
- `notification_queue` - old notifications pile up

**Required Indexes:**
```javascript
db.user_presence.createIndex({ "last_seen": 1 }, { expireAfterSeconds: 86400 })
db.notification_queue.createIndex({ "sent_at": 1 }, { expireAfterSeconds: 604800 })
```

---

### 6. `fish` Collection - Global vs Account-Specific Species

**Status:** ⚠️ NOT FIXED

**Issue:** Unclear ownership of fish species - no `scope` field.

**Recommendation:** Add explicit scope:
```javascript
{
  "species_code": "69653c8af4c2d41e5a1bcdbd",
  "scope": "global",            // "global" | "account"
  "account_key": null,          // null for global, set for account-specific
}
```

---

### 7. `sampling` and `pond_event` Circular References

**Status:** ⚠️ NOT FIXED

**Issue:** Bidirectional references can get out of sync:
```javascript
// sampling
"event_id": "69653c8af4c2d41e5a1bcdbd",

// pond_event  
"sampling_id": "a1b2c3d4e5f6a7b8c9d0e1f2",
```

**Recommendation:** Choose single direction as source of truth.

---

### 8. Missing Indexes for Common Queries

**Status:** ⚠️ NOT IMPLEMENTED

**Required Indexes:**
```javascript
// Tasks - for reminder queries (scheduler)
db.tasks.createIndex({ "reminder_time": 1, "status": 1, "reminder": 1 })

// Messages - for unread count per conversation
db.messages.createIndex({ "conversation_id": 1, "sender_key": 1, "created_at": -1 })

// Expenses - for date range reports
db.expenses.createIndex({ "account_key": 1, "created_at": 1, "category": 1 })

// Fish analytics - for harvest prediction
db.fish_analytics.createIndex({ "expected_harvest_date": 1, "account_key": 1 })
```

---

## 🟢 Low Priority Improvements

### 9. Denormalize User Info in Messages

**Status:** 📋 PLANNED

**Current:** Only `sender_key` stored (requires join for display name)

**Improvement:** Cache sender info for faster reads:
```javascript
"sender": {
  "user_key": "123456789012",
  "username": "john_doe",
  "avatar_url": "/avatars/john.jpg"
}
```

---

### 10. Add Conversation Unread Counts

**Status:** 📋 PLANNED

**Improvement:** Denormalize to conversations:
```javascript
"unread_counts": {
  "123456789012": 0,
  "987654321098": 5
}
```

---

### 11. Missing `deleted_at` on Several Collections

**Status:** ⚠️ PARTIAL - Some collections have it

**Collections needing soft delete:**
- `fish` - species should be soft deletable
- `fish_analytics` - batches should be soft deletable  
- `feeding` - records should be soft deletable

**Note:** `fin_server/utils/audit.py` has `soft_delete()` function ready to use.

---

### 12. Date Format Inconsistency

**Status:** ⚠️ NOT FIXED

**Issue:** Mixed date formats across collections:
```javascript
"joined_date": "2026-01-01",        // String
"created_date": 1704067200,         // Epoch
"created_at": ISODate,              // MongoDB ISODate
```

**Recommendation:** Standardize using `fin_server/utils/time_utils.py`:
```python
from fin_server.utils.time_utils import get_time_date_dt
# Returns proper datetime object
```

---

## 📋 Action Items Checklist

### Immediate (This Sprint)

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 1 | ~~Remove duplicate `assigned_to` from tasks~~ | `task.py`, `task_service.py` | ✅ DONE |
| 2 | Run `_v` migration script | `scripts/add_version_field.py` | ⬜ TODO |
| 3 | Add TTL index on `user_presence` | MongoDB shell | ⬜ TODO |
| 4 | Add TTL index on `notification_queue` | MongoDB shell | ⬜ TODO |

### Short-term (Sprint 1-2)

| # | Task | Priority |
|---|------|----------|
| 5 | Remove `companies.users[]` embedded array | HIGH |
| 6 | Consolidate `ponds.metadata` and `current_stock` | MEDIUM |
| 7 | Add missing database indexes | MEDIUM |
| 8 | Add `scope` field to `fish` collection | MEDIUM |

### Medium-term (Sprint 3-4)

| # | Task | Priority |
|---|------|----------|
| 9 | Fix sampling/pond_event circular reference | LOW |
| 10 | Add `deleted_at` to remaining collections | LOW |
| 11 | Denormalize sender info in messages | LOW |
| 12 | Standardize date formats | LOW |

---

## 📈 Index Optimization Summary

### Current Index Count: ~35
### Recommended Index Count: ~42

### Missing Critical Indexes

| Collection | Index | Purpose | Priority |
|------------|-------|---------|----------|
| `tasks` | `{ reminder_time: 1, status: 1 }` | Scheduler queries | HIGH |
| `messages` | `{ conversation_id: 1, created_at: -1 }` | Message listing | HIGH |
| `expenses` | `{ account_key: 1, created_at: 1 }` | Reports | MEDIUM |
| `fish_analytics` | `{ expected_harvest_date: 1 }` | Harvest planning | MEDIUM |
| `user_presence` | `{ last_seen: 1 }` (TTL) | Auto-cleanup | HIGH |

---

## 🔧 Quick Fixes Script

```javascript
// Run these in MongoDB shell to fix immediate issues

// 1. Add version field to high-write collections (if not already done)
db.ponds.updateMany({ _v: { $exists: false } }, { $set: { "_v": 1 } })
db.bank_accounts.updateMany({ _v: { $exists: false } }, { $set: { "_v": 1 } })
db.fish.updateMany({ _v: { $exists: false } }, { $set: { "_v": 1 } })

// 2. Add TTL index on user_presence (24 hour expiry)
db.user_presence.createIndex(
  { "last_seen": 1 }, 
  { expireAfterSeconds: 86400, background: true }
)

// 3. Add TTL index on notification_queue (7 day expiry for sent)
db.notification_queue.createIndex(
  { "sent_at": 1 }, 
  { expireAfterSeconds: 604800, 
    partialFilterExpression: { status: "sent" },
    background: true 
  }
)

// 4. Add missing indexes
db.tasks.createIndex({ "reminder_time": 1, "status": 1 }, { background: true })
db.messages.createIndex({ "conversation_id": 1, "created_at": -1 }, { background: true })
db.expenses.createIndex({ "account_key": 1, "created_at": 1, "category": 1 }, { background: true })
db.fish_analytics.createIndex({ "expected_harvest_date": 1, "account_key": 1 }, { background: true })

// 5. Add deleted_at to collections missing it
db.fish.updateMany({ deleted_at: { $exists: false } }, { $set: { deleted_at: null } })
db.feeding.updateMany({ deleted_at: { $exists: false } }, { $set: { deleted_at: null } })
db.fish_analytics.updateMany({ deleted_at: { $exists: false } }, { $set: { deleted_at: null } })
```

---

## 📊 Issue Summary

| Priority | Total | Resolved | Remaining |
|----------|-------|----------|-----------|
| 🔴 Critical | 6 | 4 | 2 |
| 🟡 Medium | 8 | 0 | 8 |
| 🟢 Low | 4 | 0 | 4 |
| **Total** | **18** | **4** | **14** |

### Progress: 22% Complete

---

## Summary

The schema has been **significantly improved** with the new UUID-based ID system:

### ✅ What's Fixed
- All IDs now use 24-character UUID hex format (non-predictable)
- `account_key` and `user_key` are now 12-digit numeric
- No more prefixes (MSG-, TXN-, etc.) for better security
- Removed duplicate `assigned_to` field from tasks (now using only `assignee`)
- Documentation updated in DATABASE_SCHEMA.md

### ⚠️ Still Needs Work
1. **Run version field migration** (script exists)
2. **Add TTL indexes** for ephemeral data
3. **Remove embedded arrays** (`companies.users[]`)
4. **Add missing database indexes**

### Next Steps
1. Run the Quick Fixes Script above
2. Add TTL indexes for auto-cleanup

---

*Document updated: January 13, 2026*  
*Next review: January 20, 2026*
