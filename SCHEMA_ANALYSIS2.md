# 📊 Database Schema Analysis & Improvement Recommendations

**Version:** 2.0  
**Analyzed:** January 12, 2026  
**Last Updated:** January 12, 2026

---

## Executive Summary

| Category | Current Score | Target Score | Status |
|----------|---------------|--------------|--------|
| **Data Consistency** | 9/10 | 9/10 | ✅ Achieved |
| **Normalization** | 7/10 | 8/10 | ⚡ In Progress |
| **Index Coverage** | 8/10 | 9/10 | ⚡ In Progress |
| **Referential Integrity** | 9/10 | 9/10 | ✅ Achieved |
| **Performance** | 8/10 | 9/10 | ⚡ In Progress |
| **Scalability** | 8/10 | 9/10 | ⚡ In Progress |

**Overall Score: 8.2/10** → Target: **8.7/10**

---

## ✅ Resolved Critical Issues

### 1. ~~Duplicate ID Fields in Key Identifiers Section~~ ✅ FIXED

**Status:** ✅ RESOLVED in DATABASE_SCHEMA.md

The Key Identifiers table has been updated with correct formats:

```markdown
| Field | Format | Length | Example |
|-------|--------|--------|---------|
| `account_key` | 6 numeric digits | 6 | `"123456"` |
| `user_key` | 9 numeric digits | 9 | `"123456789"` |
| `pond_id` | account_key-3 digits | 10 | `"123456-001"` |
```

**Verified:** DATABASE_SCHEMA.md lines 32-48 show correct format.

---

### 2. ~~Missing `account_key` on User Collection Examples~~ ✅ FIXED

**Status:** ✅ RESOLVED in DATABASE_SCHEMA.md

User collection examples now use correct ID formats (9-digit user_key, 6-digit account_key).

---

## 🔴 Remaining Critical Issues (High Priority)

### 1. Duplicate `_id` and Business ID Pattern

**Issue:** Collections use string `_id` that duplicates business keys:
```javascript
// ponds collection
"_id": "123456-001",           // Same as pond_id
"pond_id": "123456-001",
```

**Problems:**
- Storage overhead (duplicated data)
- Potential sync issues if one gets updated
- MongoDB's ObjectId provides better distribution for sharding

**Current State:** Still present in `ponds`, `fish` collections.

**Recommendation:**
```javascript
// Option A: Use ObjectId for _id (Recommended for new deployments)
{
  "_id": ObjectId,
  "pond_id": "123456-001",     // Business identifier
}

// Option B: Keep string _id (Current - acceptable for small/medium scale)
{
  "_id": "123456-001",         // OK if you remove duplicate pond_id field
}
```

**Priority:** Medium (acceptable for current scale, consider for v2.0)

---

### 2. `companies.users[]` Embedded Array - Scalability Risk

**Issue:** Companies collection embeds users array:
```javascript
"users": [
  {
    "user_key": "123456789",
    "username": "admin",
    "roles": ["admin"],
    ...
  }
]
```

**Problems:**
- Document size grows with users (16MB MongoDB limit)
- Updates require rewriting entire document
- No easy way to query individual user within company

**Recommendation:** Remove embedded `users[]` array - already have user_key reference in `users` collection.

**Priority:** High for farms with >50 employees

---

## 🟡 Medium Priority Issues

### 3. Redundant Fields in `tasks` Collection ⚠️ STILL PRESENT

**Issue:** Duplicate fields for same concept in code:
```javascript
// In fin_server/routes/task.py (lines 87-88) and task_service.py (lines 274-275)
"assignee": "987654321",
"assigned_to": "987654321",    // Same as assignee - REMOVE ONE
```

**Current State:** Both fields are being set with the same value in:
- `fin_server/routes/task.py` line 87-88
- `fin_server/services/task_service.py` lines 274-275

**Fix Required:** Keep only `assignee` and remove `assigned_to` (or vice versa).

**Priority:** Medium - causes storage overhead and potential confusion

---

### 4. Missing Version Field for Optimistic Locking ⚠️ NOT IMPLEMENTED

**Issue:** Collections that get concurrent updates lack version control:
- `ponds` (metadata.total_fish updated frequently)
- `bank_accounts` (balance updates)
- `fish` (current_stock)

**Current State:** `_v` field is NOT present in code. Checked:
- `fin_server/services/user_service.py` - bank_accounts created without `_v`
- No `_v` field found in any repository code

**Recommendation:** Add version field for optimistic locking:
```javascript
{
  "_v": 1,                     // Increment on each update
  "updated_at": ISODate
}
```

**Implementation:**
```python
# In create operations, add:
rec['_v'] = 1

# In update operations, use:
result = collection.update_one(
    {'_id': doc_id, '_v': current_version},
    {'$set': updates, '$inc': {'_v': 1}}
)
if result.modified_count == 0:
    raise OptimisticLockError("Document was modified by another process")
```

**Priority:** High for production systems with concurrent users

---

### 5. `ponds.metadata` vs `ponds.current_stock` Redundancy

**Issue:** Fish counts stored in two places:
```javascript
"metadata": {
  "total_fish": 2500,
  "fish_types": {
    "TILAP-00001": 1500,
    "CATLA-00001": 1000
  }
},
"current_stock": [
  {
    "species": "TILAP-00001",
    "count": 1500,
    ...
  }
]
```

**Problems:**
- Data duplication
- Sync issues between metadata.fish_types and current_stock
- Extra update operations needed

**Recommendation:** Keep only `current_stock[]` and compute totals on read, OR consolidate to `metadata.fish_types` only.

**Priority:** Medium - acceptable for now but should be addressed in refactor

---

### 6. Missing TTL Indexes for Ephemeral Data

**Issue:** Collections with temporary data lack auto-expiry:
- `user_presence` - stale records accumulate
- `notification_queue` - old notifications pile up
- `message_receipts` - could be archived after time

**Recommendation:**
```javascript
// Auto-delete presence records after 24 hours of inactivity
db.user_presence.createIndex(
  { "last_seen": 1 }, 
  { expireAfterSeconds: 86400 }
)

// Auto-delete sent notifications after 7 days
db.notification_queue.createIndex(
  { "sent_at": 1 }, 
  { expireAfterSeconds: 604800, partialFilterExpression: { status: "sent" } }
)
```

---

### 7. `fish` Collection - Global vs Account-Specific Species

**Issue:** Unclear ownership of fish species:
```javascript
"account_key": "123456",       // Optional: custom species
```

**Problems:**
- How to distinguish global species catalog from custom?
- What happens when account_key is null?
- Can two accounts have same species_code?

**Recommendation:** Add explicit scope:
```javascript
{
  "species_code": "TILAP-00001",
  "scope": "global",            // "global" | "account"
  "account_key": null,          // null for global, set for account-specific
}
```

Or use separate collections:
- `fish_species_catalog` - global species
- `account_fish_species` - custom species per account

---

### 8. `sampling` and `pond_event` Circular References

**Issue:** Bidirectional references can get out of sync:
```javascript
// sampling
"event_id": "PEV-aB3dE5fG7",

// pond_event
"sampling_id": "SMP-aB3dE5fG7",
```

**Recommendation:** Choose one direction as source of truth:
- **Option A:** Event creates Sampling → sampling has event_id (remove pond_event.sampling_id)
- **Option B:** Sampling creates Event → pond_event has sampling_id (remove sampling.event_id)

---

### 9. Missing Indexes for Common Queries

**Add these indexes:**
```javascript
// Tasks - for reminder queries (scheduler)
db.tasks.createIndex({ 
  "reminder_time": 1, 
  "status": 1, 
  "reminder": 1 
})

// Messages - for unread count per conversation
db.messages.createIndex({ 
  "conversation_id": 1, 
  "sender_key": 1, 
  "created_at": -1 
})

// Expenses - for date range reports
db.expenses.createIndex({ 
  "account_key": 1, 
  "created_at": 1, 
  "category": 1 
})

// Fish analytics - for harvest prediction
db.fish_analytics.createIndex({ 
  "expected_harvest_date": 1, 
  "account_key": 1 
})
```

---

## 🟢 Low Priority Improvements

### 10. Denormalize User Info in Messages

**Current:** Only `sender_key` stored (requires join for display name):
```javascript
"sender_key": "123456789"
```

**Improvement:** Cache sender info for faster reads:
```javascript
"sender": {
  "user_key": "123456789",
  "username": "john_doe",
  "avatar_url": "/avatars/john.jpg"
}
```

**Trade-off:** Extra storage vs faster message rendering

---

### 11. Add Conversation Unread Counts

**Current:** Need to query message_receipts to get unread count.

**Improvement:** Denormalize to conversations:
```javascript
"unread_counts": {
  "123456789": 0,
  "987654321": 5
}
```

---

### 12. `bank_accounts.account_id` Format Unclear

**Issue:** Uses `BANK-001` format but doesn't follow the new ID pattern.

**Recommendation:** Use consistent format:
```javascript
"account_id": "BNK-aB3dE5fG7"   // 12 alphanumeric like others
```

---

### 13. Missing `deleted_at` on Several Collections

**Collections without soft delete:**
- `fish` - species should be soft deletable
- `fish_analytics` - batches should be soft deletable
- `feeding` - records should be soft deletable
- `transactions` - should never delete, but add cancelled status
- `message_receipts` - could add soft delete

---

### 14. `expenses` Has Both `type` and `category`

**Issue:** Confusing naming:
```javascript
"category": "Hatchery & Stock",    // Human-readable
"type": "fish",                     // Machine category
```

**Recommendation:** Rename for clarity:
```javascript
"category": "Hatchery & Stock",     // Display category
"category_type": "fish",            // Machine category for filtering
```

---

### 15. Date Format Inconsistency

**Issue:** Mixed date formats across collections:
```javascript
"joined_date": "2026-01-01",        // String
"created_date": 1704067200,         // Epoch
"created_at": ISODate,              // MongoDB ISODate
"task_date": "2026-01-12",          // String
"end_date": "2026-01-12 18:00",     // String with time
```

**Recommendation:** Standardize on ISODate:
```javascript
"joined_date": ISODate("2026-01-01T00:00:00Z"),
"task_date": ISODate("2026-01-12T00:00:00Z"),
"end_date": ISODate("2026-01-12T18:00:00Z"),
```

---

## 📋 Schema Improvement Checklist

### Immediate (Before Production)

- [x] ~~Fix Key Identifiers table with correct ID formats~~ ✅ DONE
- [x] ~~Update users collection example with new ID format~~ ✅ DONE
- [ ] Remove duplicate `assigned_to` from tasks (Issue #3)
- [ ] Add `_v` version field to high-write collections (Issue #4)
- [ ] Add TTL index on `user_presence` (Issue #6)

### Short-term (Sprint 1-2)

- [ ] Consolidate `ponds.metadata.fish_types` and `ponds.current_stock` (Issue #5)
- [ ] Remove `companies.users[]` embedded array (Issue #2)
- [ ] Add missing indexes for common queries (Issue #9)
- [ ] Standardize date formats to ISODate (Issue #15)
- [ ] Add `scope` field to `fish` collection (Issue #7)

### Medium-term (Sprint 3-4)

- [ ] Choose single direction for sampling/pond_event reference (Issue #8)
- [ ] Add `deleted_at` to remaining collections (Issue #13)
- [ ] Denormalize sender info in messages (Issue #10)
- [ ] Add unread_counts to conversations (Issue #11)
- [ ] Standardize `bank_accounts.account_id` format (Issue #12)

### Long-term (Future Releases)

- [ ] Consider separating global vs account fish species
- [ ] Implement event sourcing for financial data
- [ ] Add data archival strategy for old messages
- [ ] Consider time-series collection for fish_analytics growth_data

---

## 📈 Index Optimization Summary

### Current Index Count: ~35
### Recommended Index Count: ~42

### Missing Critical Indexes

| Collection | Index | Purpose | Status |
|------------|-------|---------|--------|
| `tasks` | `{ reminder_time: 1, status: 1 }` | Scheduler queries | ❌ Missing |
| `messages` | `{ conversation_id: 1, sender_key: 1, created_at: -1 }` | Unread messages | ❌ Missing |
| `expenses` | `{ account_key: 1, created_at: 1, category: 1 }` | Reports | ❌ Missing |
| `fish_analytics` | `{ expected_harvest_date: 1 }` | Harvest planning | ❌ Missing |
| `pond_event` | `{ account_key: 1, fish_id: 1 }` | Species history | ❌ Missing |
| `user_presence` | `{ last_seen: 1 }` (TTL) | Auto-cleanup | ❌ Missing |

### Redundant Indexes to Review

| Collection | Index | Reason |
|------------|-------|--------|
| `sampling` | `{ account_key: 1, species: 1 }` | Covered by compound with pond_id |

---

## 🔧 Quick Fixes Script

```javascript
// Run these in MongoDB shell to fix immediate issues

// 1. Add version field to high-write collections
db.ponds.updateMany({ _v: { $exists: false } }, { $set: { "_v": 1 } })
db.bank_accounts.updateMany({ _v: { $exists: false } }, { $set: { "_v": 1 } })
db.fish.updateMany({ _v: { $exists: false } }, { $set: { "_v": 1 } })

// 2. Add TTL index on user_presence (24 hour expiry)
db.user_presence.createIndex(
  { "last_seen": 1 }, 
  { expireAfterSeconds: 86400, background: true }
)

// 3. Add missing indexes
db.tasks.createIndex({ "reminder_time": 1, "status": 1 }, { background: true })
db.fish_analytics.createIndex({ "expected_harvest_date": 1, "account_key": 1 }, { background: true })
db.messages.createIndex({ "conversation_id": 1, "sender_key": 1, "created_at": -1 }, { background: true })
db.expenses.createIndex({ "account_key": 1, "created_at": 1, "category": 1 }, { background: true })

// 4. Add deleted_at to collections missing it
db.fish.updateMany({ deleted_at: { $exists: false } }, { $set: { deleted_at: null } })
db.feeding.updateMany({ deleted_at: { $exists: false } }, { $set: { deleted_at: null } })
db.fish_analytics.updateMany({ deleted_at: { $exists: false } }, { $set: { deleted_at: null } })
```

---

## 📊 Issue Summary

| Priority | Total | Resolved | Remaining |
|----------|-------|----------|-----------|
| 🔴 Critical | 4 | 2 | 2 |
| 🟡 Medium | 9 | 0 | 9 |
| 🟢 Low | 6 | 0 | 6 |
| **Total** | **19** | **2** | **17** |

---

## Summary

The schema is **well-designed for a fish farm management system** with good multi-tenancy support. 

### ✅ What's Working Well
- Key identifier formats are correctly documented
- Multi-tenancy via `account_key` is properly implemented
- Audit trail fields (`created_at`, `updated_at`, `user_key`) are in place
- Soft delete pattern is documented

### ⚠️ Priority Fixes Needed
1. **Remove duplicate task fields** - `assignee`/`assigned_to` duplication in code
2. **Add optimistic locking** - `_v` version field for concurrent updates
3. **Add TTL indexes** - For ephemeral data cleanup
4. **Remove embedded arrays** - `companies.users[]` scalability risk

Implementing the high-priority fixes will significantly improve data integrity and system reliability.

---

*Analysis generated: January 12, 2026*  
*Version: 2.0*

