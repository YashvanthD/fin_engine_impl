# 📊 Database Schema Analysis & Improvement Recommendations

**Version:** 1.0  
**Analyzed:** January 12, 2026

---

## Executive Summary

| Category | Current Score | Target Score |
|----------|---------------|--------------|
| **Data Consistency** | 7/10 | 9/10 |
| **Normalization** | 6/10 | 8/10 |
| **Index Coverage** | 7/10 | 9/10 |
| **Referential Integrity** | 6/10 | 9/10 |
| **Performance** | 7/10 | 9/10 |
| **Scalability** | 7/10 | 9/10 |

**Overall Score: 6.7/10** → Target: **8.7/10**

---

## 🔴 Critical Issues (High Priority)

### 1. Duplicate ID Fields in Key Identifiers Section

**Issue:** The Key Identifiers table still shows old format examples that conflict with the new ID system.

```markdown
# Current (Line 32-37):
| `account_key` | Organization/Company ID | `"ACC-123456"` |
| `user_key` | User identifier | `"USR-ABC123"` |

# Should be:
| `account_key` | 6 numeric digits | `"123456"` |
| `user_key` | 9 numeric digits | `"123456789"` |
```

**Impact:** Documentation inconsistency, developer confusion  
**Fix:** Update Key Identifiers table to match new format

---

### 2. Duplicate `_id` and Business ID Pattern

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

**Recommendation:**
```javascript
// Option A: Use ObjectId for _id (Recommended)
{
  "_id": ObjectId,
  "pond_id": "123456-001",     // Business identifier
}

// Option B: Use string _id (Current - acceptable for small scale)
{
  "_id": "123456-001",         // Remove duplicate pond_id field
}
```

---

### 3. Missing `account_key` on User Collection Examples

**Issue:** Users collection example still shows old format:
```javascript
"user_key": "USR-ABC123",      // Should be: "123456789"
"account_key": "ACC-123456",   // Should be: "123456"
```

---

### 4. `companies.users[]` Embedded Array - Scalability Risk

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

---

## 🟡 Medium Priority Issues

### 5. Redundant Fields in `tasks` Collection

**Issue:** Duplicate fields for same concept:
```javascript
"assignee": "987654321",
"assigned_to": "987654321",    // Same as assignee - REMOVE ONE
```

**Fix:** Keep only `assignee` or `assigned_to`, not both.

---

### 6. Missing Version Field for Optimistic Locking

**Issue:** Collections that get concurrent updates lack version control:
- `ponds` (metadata.total_fish updated frequently)
- `bank_accounts` (balance updates)
- `fish` (current_stock)

**Recommendation:** Add version field:
```javascript
{
  "_v": 1,                     // Increment on each update
  "updated_at": ISODate
}
```

---

### 7. `ponds.metadata` vs `ponds.current_stock` Redundancy

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

**Recommendation:** Keep only `current_stock[]` and compute totals on read:
```javascript
"current_stock": [
  {
    "species": "TILAP-00001",
    "count": 1500,
    "avg_weight": 250,
    "added_date": ISODate,
    "batch_id": "BAT-xxx"        // Add batch reference
  }
],
"total_fish": 2500               // Computed field or use aggregation
```

---

### 8. Missing TTL Indexes for Ephemeral Data

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

### 9. `fish` Collection - Global vs Account-Specific Species

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

### 10. `sampling` and `pond_event` Circular References

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

### 11. Missing Indexes for Common Queries

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

### 12. Denormalize User Info in Messages

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

### 13. Add Conversation Unread Counts

**Current:** Need to query message_receipts to get unread count.

**Improvement:** Denormalize to conversations:
```javascript
"unread_counts": {
  "123456789": 0,
  "987654321": 5
}
```

---

### 14. `bank_accounts.account_id` Format Unclear

**Issue:** Uses `BANK-001` format but doesn't follow the new ID pattern.

**Recommendation:** Use consistent format:
```javascript
"account_id": "BNK-aB3dE5fG7"   // 12 alphanumeric like others
```

---

### 15. Missing `deleted_at` on Several Collections

**Collections without soft delete:**
- `fish` - species should be soft deletable
- `fish_analytics` - batches should be soft deletable
- `feeding` - records should be soft deletable
- `transactions` - should never delete, but add cancelled status
- `message_receipts` - could add soft delete

---

### 16. `expenses` Has Both `type` and `category`

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

### 17. Date Format Inconsistency

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

- [ ] Fix Key Identifiers table with correct ID formats
- [ ] Update users collection example with new ID format
- [ ] Remove duplicate `assigned_to` from tasks
- [ ] Add `_v` version field to high-write collections
- [ ] Add TTL index on `user_presence`

### Short-term (Sprint 1-2)

- [ ] Consolidate `ponds.metadata.fish_types` and `ponds.current_stock`
- [ ] Remove `companies.users[]` embedded array
- [ ] Add missing indexes for common queries
- [ ] Standardize date formats to ISODate
- [ ] Add `scope` field to `fish` collection

### Medium-term (Sprint 3-4)

- [ ] Choose single direction for sampling/pond_event reference
- [ ] Add `deleted_at` to remaining collections
- [ ] Denormalize sender info in messages
- [ ] Add unread_counts to conversations
- [ ] Standardize `bank_accounts.account_id` format

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

| Collection | Index | Purpose |
|------------|-------|---------|
| `tasks` | `{ reminder_time: 1, status: 1 }` | Scheduler queries |
| `messages` | `{ conversation_id: 1, sender_key: 1, created_at: -1 }` | Unread messages |
| `expenses` | `{ account_key: 1, created_at: 1, category: 1 }` | Reports |
| `fish_analytics` | `{ expected_harvest_date: 1 }` | Harvest planning |
| `pond_event` | `{ account_key: 1, fish_id: 1 }` | Species history |

### Redundant Indexes to Review

| Collection | Index | Reason |
|------------|-------|--------|
| `sampling` | `{ account_key: 1, species: 1 }` | Covered by compound with pond_id |

---

## 🔧 Quick Fixes Script

```javascript
// Run these in MongoDB shell to fix immediate issues

// 1. Add version field to high-write collections
db.ponds.updateMany({}, { $set: { "_v": 1 } })
db.bank_accounts.updateMany({}, { $set: { "_v": 1 } })
db.fish.updateMany({}, { $set: { "_v": 1 } })

// 2. Add TTL index on user_presence
db.user_presence.createIndex(
  { "last_seen": 1 }, 
  { expireAfterSeconds: 86400, background: true }
)

// 3. Add missing indexes
db.tasks.createIndex({ "reminder_time": 1, "status": 1 }, { background: true })
db.fish_analytics.createIndex({ "expected_harvest_date": 1, "account_key": 1 }, { background: true })

// 4. Add deleted_at to collections missing it
db.fish.updateMany({ deleted_at: { $exists: false } }, { $set: { deleted_at: null } })
db.feeding.updateMany({ deleted_at: { $exists: false } }, { $set: { deleted_at: null } })
```

---

## Summary

The schema is **well-designed for a fish farm management system** with good multi-tenancy support. The main areas for improvement are:

1. **Data Consistency** - Fix duplicate fields and standardize formats
2. **Performance** - Add missing indexes and TTL for ephemeral data  
3. **Scalability** - Remove embedded arrays, add version control
4. **Maintainability** - Reduce circular references, standardize dates

Implementing the high-priority fixes will significantly improve data integrity and system reliability.

---

*Analysis generated: January 12, 2026*

