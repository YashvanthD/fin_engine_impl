# 🐟 Fin Engine - Fish Farm Management System

## Complete Use Cases & API Guide

This document covers all use cases for managing a modern fish farm - from initial setup to harvest and sales.

---

## Table of Contents

1. [Overview](#overview)
2. [Data Flow & Repository Mapping](#data-flow--repository-mapping)
3. [Phase 1: Farm Setup & Registration](#phase-1-farm-setup--registration)
3. [Phase 2: Infrastructure Setup (Ponds)](#phase-2-infrastructure-setup-ponds)
4. [Phase 3: Fish Species Setup](#phase-3-fish-species-setup)
5. [Phase 4: Fish Purchase & Stocking](#phase-4-fish-purchase--stocking)
6. [Phase 5: Daily Operations](#phase-5-daily-operations)
7. [Phase 6: Growth Monitoring & Sampling](#phase-6-growth-monitoring--sampling)
8. [Phase 7: Fish Mortality & Health Management](#phase-7-fish-mortality--health-management)
9. [Phase 8: Fish Transfer Between Ponds](#phase-8-fish-transfer-between-ponds)
10. [Phase 9: Harvest & Sales](#phase-9-harvest--sales)
11. [Phase 10: Financial Management](#phase-10-financial-management)
12. [Phase 11: Reporting & Analytics](#phase-11-reporting--analytics)
13. [Phase 12: End of Cycle & Pond Reset](#phase-12-end-of-cycle--pond-reset)
14. [Quick Reference](#quick-reference)
15. [Pond Event Types Summary](#pond-event-types-summary)

---

## Data Flow & Repository Mapping

This section documents which MongoDB collections (repositories) are created/updated for each major operation. Understanding these flows is essential for maintaining data consistency.

### Collections Overview

| Collection | Purpose |
|------------|---------|
| `users` | User accounts (employees, admins) |
| `companies` | Company/Farm registration |
| `bank_accounts` | Bank accounts for users and organization |
| `ponds` | Pond entities with metadata |
| `fish` | Fish species catalog |
| `fish_mapping` | Maps fish species to accounts |
| `fish_analytics` | Fish population batches and growth data |
| `fish_activity` | Fish activity logs (samples, events) |
| `pond_event` | Pond events (add, sell, sample, remove, shift) |
| `sampling` | Growth sampling and purchase records |
| `feeding` | Feeding records |
| `expenses` | Financial expenses |
| `transactions` | Financial transactions |
| `payments` | Payment records |
| `bank_statements` | Imported bank statements |
| `statement_lines` | Bank statement line items |
| `tasks` | Task/schedule management |

---

### Flow 1: Company/Admin Registration

**Trigger:** `POST /auth/signup` or `POST /company/register`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        COMPANY REGISTRATION FLOW                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. CREATE USER (admin)                                                     │
│     └── Collection: `users`                                                 │
│         • user_key (generated)                                              │
│         • account_key (generated)                                           │
│         • username, email, phone, password (hashed)                         │
│         • roles: ['admin']                                                  │
│         • refresh_tokens                                                    │
│         • subscription                                                      │
│                                                                             │
│  2. CREATE COMPANY                                                          │
│     └── Collection: `companies`                                             │
│         • account_key (same as user)                                        │
│         • company_name                                                      │
│         • admin_user_key                                                    │
│         • users: [{ user_key, username, roles, active }]                    │
│         • employee_count: 1                                                 │
│                                                                             │
│  3. CREATE USER BANK ACCOUNT                                                │
│     └── Collection: `bank_accounts`                                         │
│         • account_number (generated)                                        │
│         • user_key                                                          │
│         • account_key                                                       │
│         • type: 'user'                                                      │
│         • balance: 0                                                        │
│                                                                             │
│  4. CREATE ORGANIZATION BANK ACCOUNT                                        │
│     └── Collection: `bank_accounts`                                         │
│         • account_number (generated)                                        │
│         • account_key                                                       │
│         • type: 'organization'                                              │
│         • balance: 0                                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Service:** `user_service.create_user_and_accounts()`

---

### Flow 2: Add Employee/Worker

**Trigger:** `POST /auth/account/{account_key}/signup`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ADD EMPLOYEE FLOW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. CREATE USER                                                             │
│     └── Collection: `users`                                                 │
│         • user_key (generated)                                              │
│         • account_key (existing company's)                                  │
│         • roles: ['worker'] or ['supervisor']                               │
│                                                                             │
│  2. UPDATE COMPANY USERS LIST                                               │
│     └── Collection: `companies`                                             │
│         • Push to users[]                                                   │
│         • Increment employee_count                                          │
│                                                                             │
│  3. CREATE USER BANK ACCOUNT (optional)                                     │
│     └── Collection: `bank_accounts`                                         │
│         • type: 'user'                                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Flow 3: Create Pond

**Trigger:** `POST /pond/create`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CREATE POND FLOW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. CREATE POND                                                             │
│     └── Collection: `ponds`                                                 │
│         • _id: pond_id (auto: {account_key}-{number})                       │
│         • pond_id                                                           │
│         • account_key                                                       │
│         • name, type, area, depth, capacity                                 │
│         • metadata: {                                                       │
│             total_fish: 0,                                                  │
│             fish_types: {},                                                 │
│             last_activity: null                                             │
│           }                                                                 │
│         • current_stock: []                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Flow 4: Register Fish Species

**Trigger:** `POST /fish/create`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        REGISTER FISH SPECIES FLOW                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. CREATE FISH SPECIES                                                     │
│     └── Collection: `fish`                                                  │
│         • _id: species_code                                                 │
│         • species_code                                                      │
│         • common_name, scientific_name                                      │
│         • account_key                                                       │
│                                                                             │
│  2. ADD TO FISH MAPPING                                                     │
│     └── Collection: `fish_mapping`                                          │
│         • Upsert: { account_key }                                           │
│         • $addToSet: { fish_ids: species_code }                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Flow 5: Buy Fish / Fish Purchase (via Sampling API)

**Trigger:** `POST /sampling` (with totalCount and totalAmount)

This is the **most complex flow** - it updates 9 collections!

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      FISH PURCHASE (BUY) FLOW                               │
│                   Service: sampling_service.perform_buy_sampling()          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. CREATE SAMPLING RECORD                                                  │
│     └── Collection: `sampling`                                              │
│         • sampling_id (generated)                                           │
│         • pond_id, species                                                  │
│         • total_count, total_amount                                         │
│         • average_weight, average_length                                    │
│         • stock_id (derived)                                                │
│                                                                             │
│  2. ENSURE FISH MAPPING                                                     │
│     └── Collection: `fish_mapping`                                          │
│         • $addToSet: { fish_ids: species }                                  │
│                                                                             │
│  3. UPDATE POND METADATA (atomic)                                           │
│     └── Collection: `ponds`                                                 │
│         • $inc: {                                                           │
│             fish_count: +count,                                             │
│             'metadata.total_fish': +count,                                  │
│             'metadata.fish_types.{species}': +count                         │
│           }                                                                 │
│         • $set: { 'metadata.last_activity': {...} }                         │
│                                                                             │
│  4. CREATE POND EVENT                                                       │
│     └── Collection: `pond_event`                                            │
│         • pond_id, event_type: 'buy'                                        │
│         • details: { species, count, total_amount, stock_id }               │
│                                                                             │
│  5. UPDATE FISH CURRENT STOCK                                               │
│     └── Collection: `fish`                                                  │
│         • $inc: { current_stock: +count }                                   │
│                                                                             │
│  6. CREATE EXPENSE                                                          │
│     └── Collection: `expenses`                                              │
│         • amount: total_amount                                              │
│         • category: 'asset', type: 'fish', action: 'buy'                    │
│         • metadata: { pond_id, stock_id, species }                          │
│                                                                             │
│  7. UPDATE ORGANIZATION BANK BALANCE                                        │
│     └── Collection: `bank_accounts`                                         │
│         • $inc: { balance: -total_amount } (debit)                          │
│                                                                             │
│  8. CREATE STATEMENT LINE                                                   │
│     └── Collection: `statement_lines`                                       │
│         • bank_account_id, amount, direction: 'out'                         │
│         • reference: { type: 'expense', id: expense_id }                    │
│                                                                             │
│  9. ADD FISH ANALYTICS BATCH                                                │
│     └── Collection: `fish_analytics`                                        │
│         • species_code, count: +count                                       │
│         • fish_age_in_month                                                 │
│         • account_key, pond_id                                              │
│         • event_id                                                          │
│                                                                             │
│  10. CREATE FISH ACTIVITY                                                   │
│      └── Collection: `fish_activity`                                        │
│          • pond_id, fish_id: species                                        │
│          • event_type: 'buy', count                                         │
│                                                                             │
│  11. UPDATE POND CURRENT STOCK (via StockRepository)                        │
│      └── Collection: `ponds`                                                │
│          • Push/update current_stock[]: { species, quantity, avg_weight }   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Services Used:**
- `sampling_service.perform_buy_sampling()`
- `expense_service.create_expense_with_repo()`
- `StockRepository.add_stock_transactional()`

---

### Flow 6: Stock Fish via Pond Event (Add)

**Trigger:** `POST /pond_event/{pond_id}/event/add`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         POND EVENT: ADD FISH FLOW                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. CREATE POND EVENT                                                       │
│     └── Collection: `pond_event`                                            │
│         • pond_id, event_type: 'add'                                        │
│         • fish_id (species), count                                          │
│         • fish_age_in_month, details                                        │
│                                                                             │
│  2. UPDATE POND METADATA (atomic)                                           │
│     └── Collection: `ponds`                                                 │
│         • $inc: {                                                           │
│             'metadata.total_fish': +count,                                  │
│             'metadata.fish_types.{fish_id}': +count                         │
│           }                                                                 │
│         • $set: { 'metadata.last_activity': {...} }                         │
│                                                                             │
│  3. ENSURE FISH MAPPING                                                     │
│     └── Collection: `fish_mapping`                                          │
│         • $addToSet: { fish_ids: fish_id }                                  │
│                                                                             │
│  4. ADD FISH ANALYTICS BATCH (+count)                                       │
│     └── Collection: `fish_analytics`                                        │
│         • species_code, count: +count                                       │
│         • fish_age_in_month                                                 │
│                                                                             │
│  5. CREATE FISH ACTIVITY (for add events)                                   │
│     └── Collection: `fish_activity`                                         │
│         • event_type: 'add'                                                 │
│         • samples[] (if provided)                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Flow 7: Sell Fish / Harvest

**Trigger:** `POST /pond_event/{pond_id}/event/sell`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         POND EVENT: SELL FISH FLOW                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. CREATE POND EVENT                                                       │
│     └── Collection: `pond_event`                                            │
│         • pond_id, event_type: 'sell'                                       │
│         • fish_id, count                                                    │
│         • details: { buyer, price_per_kg, total_amount, etc. }              │
│                                                                             │
│  2. UPDATE POND METADATA (atomic)                                           │
│     └── Collection: `ponds`                                                 │
│         • $inc: {                                                           │
│             'metadata.total_fish': -count,    ◄── DECREASE                  │
│             'metadata.fish_types.{fish_id}': -count                         │
│           }                                                                 │
│         • Cleanup zero/negative counts                                      │
│                                                                             │
│  3. ADD FISH ANALYTICS BATCH (-count)                                       │
│     └── Collection: `fish_analytics`                                        │
│         • count: -count (negative batch for removal)                        │
│                                                                             │
│  (Optional - done separately via /transactions or /expenses)                │
│                                                                             │
│  4. CREATE TRANSACTION (for sales)                                          │
│     └── Collection: `transactions`                                          │
│         • type: 'sale', amount                                              │
│         • pond_id, species                                                  │
│                                                                             │
│  5. CREATE INCOME EXPENSE                                                   │
│     └── Collection: `expenses`                                              │
│         • category: 'income', action: 'sell'                                │
│                                                                             │
│  6. UPDATE BANK BALANCE                                                     │
│     └── Collection: `bank_accounts`                                         │
│         • $inc: { balance: +amount } (credit)                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Flow 8: Fish Mortality (Remove)

**Trigger:** `POST /pond_event/{pond_id}/event/remove`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       POND EVENT: REMOVE FISH FLOW                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. CREATE POND EVENT                                                       │
│     └── Collection: `pond_event`                                            │
│         • event_type: 'remove'                                              │
│         • details: { reason, disease_type, etc. }                           │
│                                                                             │
│  2. UPDATE POND METADATA                                                    │
│     └── Collection: `ponds`                                                 │
│         • $inc: { 'metadata.total_fish': -count }  ◄── DECREASE             │
│                                                                             │
│  3. ADD FISH ANALYTICS BATCH (-count)                                       │
│     └── Collection: `fish_analytics`                                        │
│         • count: -count (negative)                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Flow 9: Sample Fish for Growth

**Trigger:** `POST /pond_event/{pond_id}/event/sample`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       POND EVENT: SAMPLE FISH FLOW                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. CREATE POND EVENT                                                       │
│     └── Collection: `pond_event`                                            │
│         • event_type: 'sample'                                              │
│         • samples: [{ weight, length }, ...]                                │
│                                                                             │
│  2. UPDATE POND METADATA                                                    │
│     └── Collection: `ponds`                                                 │
│         • $inc: { 'metadata.total_fish': -count }  ◄── DECREASE             │
│                                                                             │
│  3. ADD FISH ANALYTICS BATCH (-count)                                       │
│     └── Collection: `fish_analytics`                                        │
│                                                                             │
│  4. CREATE FISH ACTIVITY                                                    │
│     └── Collection: `fish_activity`                                         │
│         • event_type: 'sample'                                              │
│         • samples: [...]                                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Flow 10: Transfer Fish Between Ponds

**Trigger:** `POST /pond_event/{source}/event/shift_out` + `POST /pond_event/{dest}/event/shift_in`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      FISH TRANSFER BETWEEN PONDS                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STEP 1: SHIFT OUT (Source Pond)                                            │
│  ─────────────────────────────────                                          │
│  1a. CREATE POND EVENT (shift_out)                                          │
│      └── Collection: `pond_event`                                           │
│          • event_type: 'shift_out'                                          │
│          • details: { destination_pond }                                    │
│                                                                             │
│  1b. UPDATE SOURCE POND METADATA                                            │
│      └── Collection: `ponds`                                                │
│          • $inc: { 'metadata.total_fish': -count }  ◄── DECREASE            │
│                                                                             │
│  1c. ADD ANALYTICS BATCH (-count)                                           │
│      └── Collection: `fish_analytics`                                       │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  STEP 2: SHIFT IN (Destination Pond)                                        │
│  ────────────────────────────────────                                       │
│  2a. CREATE POND EVENT (shift_in)                                           │
│      └── Collection: `pond_event`                                           │
│          • event_type: 'shift_in'                                           │
│          • details: { source_pond }                                         │
│                                                                             │
│  2b. UPDATE DESTINATION POND METADATA                                       │
│      └── Collection: `ponds`                                                │
│          • $inc: { 'metadata.total_fish': +count }  ◄── INCREASE            │
│                                                                             │
│  2c. ADD ANALYTICS BATCH (+count)                                           │
│      └── Collection: `fish_analytics`                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Flow 11: Record Feeding

**Trigger:** `POST /feeding/`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FEEDING RECORD FLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. CREATE FEEDING RECORD                                                   │
│     └── Collection: `feeding`                                               │
│         • pondId                                                            │
│         • feedType, feedBrand                                               │
│         • quantity, unit                                                    │
│         • feedingTime                                                       │
│         • recordedBy                                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Flow 12: Create Expense

**Trigger:** `POST /expenses`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CREATE EXPENSE FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. CREATE EXPENSE                                                          │
│     └── Collection: `expenses`                                              │
│         • amount, currency                                                  │
│         • category, type, action                                            │
│         • status (normalized)                                               │
│         • metadata: { pond_id, species, etc. }                              │
│                                                                             │
│  2. UPDATE ORG BANK BALANCE (if debit)                                      │
│     └── Collection: `bank_accounts`                                         │
│         • $inc: { balance: -amount }                                        │
│                                                                             │
│  3. CREATE STATEMENT LINE                                                   │
│     └── Collection: `statement_lines`                                       │
│         • bank_account_id, amount                                           │
│         • direction: 'out' (debit) or 'in' (credit)                         │
│         • reference: { type: 'expense', id: expense_id }                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Flow 13: Create Task

**Trigger:** `POST /task/`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CREATE TASK FLOW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. RESOLVE ASSIGNEE                                                        │
│     └── Collection: `users` (read)                                          │
│         • Validate assigned_to exists                                       │
│                                                                             │
│  2. CREATE TASK                                                             │
│     └── Collection: `tasks`                                                 │
│         • task_id (generated)                                               │
│         • user_key (creator), reporter                                      │
│         • assignee, assigned_to                                             │
│         • title, description, status, priority                              │
│         • task_date, end_date                                               │
│         • recurring, reminder                                               │
│         • history: [], comments: [], tags: []                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Flow 14: Delete Pond (Cascade)

**Trigger:** `DELETE /pond/{pond_id}`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DELETE POND (CASCADE) FLOW                             │
│                   Service: pond_service.delete_pond_and_related()           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  (Optional) PREPARE FINANCIALS                                              │
│  └── Create final sale/expense records if amounts provided                  │
│                                                                             │
│  1. DELETE SAMPLING RECORDS                                                 │
│     └── Collection: `sampling`                                              │
│         • deleteMany({ pond_id })                                           │
│                                                                             │
│  2. DELETE POND EVENTS                                                      │
│     └── Collection: `pond_event`                                            │
│         • deleteMany({ pond_id })                                           │
│                                                                             │
│  3. DELETE FISH ACTIVITY                                                    │
│     └── Collection: `fish_activity`                                         │
│         • deleteMany({ pond_id })                                           │
│                                                                             │
│  4. DELETE FISH ANALYTICS                                                   │
│     └── Collection: `fish_analytics`                                        │
│         • deleteMany({ pond_id })                                           │
│                                                                             │
│  5. DELETE RELATED EXPENSES                                                 │
│     └── Collection: `expenses`                                              │
│         • deleteMany({ pond_id }) via metadata                              │
│                                                                             │
│  6. DELETE POND                                                             │
│     └── Collection: `ponds`                                                 │
│         • deleteOne({ pond_id })                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Flow 15: Update Pond Event

**Trigger:** `PUT /pond_event/{pond_id}/events/{event_id}`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      UPDATE POND EVENT FLOW                                 │
│                   (Reverses old effects, applies new)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. LOAD OLD EVENT                                                          │
│     └── Collection: `pond_event` (read)                                     │
│                                                                             │
│  2. REVERSE OLD EVENT EFFECTS                                               │
│     └── Collection: `ponds`                                                 │
│         • If old was add/shift_in: $inc -count (reverse)                    │
│         • If old was remove/sell/sample/shift_out: $inc +count (reverse)    │
│     └── Collection: `fish_analytics`                                        │
│         • Add inverse batch                                                 │
│                                                                             │
│  3. UPDATE EVENT DOCUMENT                                                   │
│     └── Collection: `pond_event`                                            │
│         • Update allowed fields                                             │
│                                                                             │
│  4. APPLY NEW EVENT EFFECTS                                                 │
│     └── Collection: `ponds`                                                 │
│         • Apply new counts                                                  │
│     └── Collection: `fish_analytics`                                        │
│         • Add new batch                                                     │
│                                                                             │
│  5. CREATE ACTIVITY (if sample/add)                                         │
│     └── Collection: `fish_activity`                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Flow 16: Delete Sampling Record

**Trigger:** `DELETE /sampling/{sampling_id}`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DELETE SAMPLING FLOW                                   │
│                   Service: expense_service.handle_sampling_deletion()       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. CANCEL RELATED EXPENSES                                                 │
│     └── Collection: `expenses`                                              │
│         • Update status to 'CANCELLED'                                      │
│         • Or delete related expenses                                        │
│                                                                             │
│  2. REVERSE STOCK CHANGES                                                   │
│     └── Collection: `ponds`                                                 │
│         • Decrement stock if was a buy                                      │
│                                                                             │
│  3. DELETE ANALYTICS ENTRIES                                                │
│     └── Collection: `fish_analytics`                                        │
│         • Remove related batches                                            │
│                                                                             │
│  4. DELETE ACTIVITY RECORDS                                                 │
│     └── Collection: `fish_activity`                                         │
│                                                                             │
│  5. DELETE SAMPLING DOCUMENT                                                │
│     └── Collection: `sampling`                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Summary: Collection Update Matrix

| Operation | users | companies | bank_accounts | ponds | fish | fish_mapping | fish_analytics | fish_activity | pond_event | sampling | expenses | transactions | feeding | tasks |
|-----------|:-----:|:---------:|:-------------:|:-----:|:----:|:------------:|:--------------:|:-------------:|:----------:|:--------:|:--------:|:------------:|:-------:|:-----:|
| **Company Register** | ✅ | ✅ | ✅✅ | | | | | | | | | | | |
| **Add Employee** | ✅ | ✅ | ✅ | | | | | | | | | | | |
| **Create Pond** | | | | ✅ | | | | | | | | | | |
| **Register Fish** | | | | | ✅ | ✅ | | | | | | | | |
| **Buy Fish (Sampling)** | | | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | | | |
| **Pond Event: Add** | | | | ✅ | | ✅ | ✅ | ✅ | ✅ | | | | | |
| **Pond Event: Sell** | | | | ✅ | | | ✅ | | ✅ | | | | | |
| **Pond Event: Remove** | | | | ✅ | | | ✅ | | ✅ | | | | | |
| **Pond Event: Sample** | | | | ✅ | | | ✅ | ✅ | ✅ | | | | | |
| **Pond Event: Shift** | | | | ✅✅ | | | ✅✅ | | ✅✅ | | | | | |
| **Record Feeding** | | | | | | | | | | | | | ✅ | |
| **Create Expense** | | | ✅ | | | | | | | | ✅ | | | |
| **Create Transaction** | | | | | | | | | | | | ✅ | | |
| **Create Task** | | | | | | | | | | | | | | ✅ |
| **Delete Pond** | | | | ✅ | | | ✅ | ✅ | ✅ | ✅ | ✅ | | | |

Legend: ✅ = Created/Updated, ✅✅ = Multiple records affected

---

The Fin Engine API provides complete management for fish farming operations including:

- **Farm & User Management** - Company registration, employee management
- **Pond Management** - Create, update, monitor ponds
- **Fish Management** - Species catalog, stock tracking, analytics
- **Pond Events** - Track all fish movements (add, sell, sample, transfer, mortality)
- **Feeding & Sampling** - Daily feeding logs, growth monitoring
- **Financial Tracking** - Expenses, transactions, revenue
- **Task Management** - Assign and track farm tasks

### Base URL
```
http://localhost:5000
```

### Authentication
Most endpoints require JWT token:
```
Authorization: Bearer <your_token>
```

---

## Phase 1: Farm Setup & Registration

### UC-1.1: Register Farm/Company (Admin Signup)

Register your fish farm as a company. This creates the admin account and organization.

**When to use:** First time setup - before any other operations

```http
POST /auth/signup
Content-Type: application/json

{
  "username": "farmadmin",
  "email": "admin@myfishfarm.com",
  "password": "SecurePass123!",
  "phone": "+91-9876543210",
  "company_name": "Green Valley Fish Farm",
  "company_address": "123 Lake Road, Karnataka",
  "master_password": "your-master-password"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "message": "Admin signup validated and saved.",
    "user_id": "usr_abc123",
    "account_key": "ACC001",
    "user_key": "USR001"
  }
}
```

---

### UC-1.2: Add Farm Employees/Workers

Add additional users (workers, supervisors, managers) to your farm account.

**When to use:** After company registration, when you need to add team members

```http
POST /auth/account/{account_key}/signup
Authorization: Bearer {admin_token}
Content-Type: application/json

{
  "username": "supervisor_ravi",
  "email": "ravi@myfishfarm.com",
  "password": "WorkerPass123!",
  "phone": "+91-9876543211",
  "roles": ["supervisor"]
}
```

**Available Roles:** `admin`, `supervisor`, `worker`, `viewer`

---

### UC-1.3: Login to Farm System

Authenticate and get access token for API operations.

**When to use:** Every time you start working with the system

```http
POST /auth/login
Content-Type: application/json

{
  "email": "admin@myfishfarm.com",
  "password": "SecurePass123!"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGc...",
    "refresh_token": "eyJhbGc...",
    "user_key": "USR001",
    "account_key": "ACC001"
  }
}
```

---

## Phase 2: Infrastructure Setup (Ponds)

### UC-2.1: Create a Nursery Pond

Register a new pond for fish fingerlings/fry.

**When to use:** When constructing or adding a new pond to your farm

```http
POST /pond/create
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Pond A - Nursery",
  "type": "nursery",
  "area": 500,
  "area_unit": "sqm",
  "depth": 1.5,
  "depth_unit": "m",
  "capacity": 5000,
  "water_source": "borewell",
  "location": {
    "latitude": 12.9716,
    "longitude": 77.5946
  },
  "metadata": {
    "construction_date": "2025-06-15",
    "liner_type": "HDPE",
    "aeration": true
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "pond_id": "ACC001-001",
    "name": "Pond A - Nursery",
    "type": "nursery",
    "capacity": 5000
  }
}
```

---

### UC-2.2: Create a Grow-out Pond

Create a larger pond for growing fish to harvest size.

**When to use:** Setting up production ponds for mature fish

```http
POST /pond/create
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Pond B - Grow Out 1",
  "type": "grow-out",
  "area": 2000,
  "area_unit": "sqm",
  "depth": 2.0,
  "depth_unit": "m",
  "capacity": 15000,
  "water_source": "canal",
  "metadata": {
    "aeration": true,
    "aerator_count": 4
  }
}
```

---

### UC-2.3: Update Pond Details

Modify pond information like capacity, equipment, or metadata.

**When to use:** When pond specifications change or need correction

```http
PUT /pond/update/{pond_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "capacity": 6000,
  "metadata": {
    "aeration": true,
    "aerator_count": 2,
    "last_maintenance": "2026-01-10"
  }
}
```

---

### UC-2.4: List All Ponds

Get overview of all ponds in your farm.

**When to use:** Dashboard view, reporting, or selecting a pond for operations

```http
GET /pond/
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "ponds": [
      {
        "pond_id": "ACC001-001",
        "name": "Pond A - Nursery",
        "type": "nursery",
        "capacity": 5000,
        "metadata": {
          "total_fish": 4500,
          "fish_types": {
            "TILAPIA_NILE": 4500
          }
        }
      }
    ]
  }
}
```

---

### UC-2.5: Get Pond Details

View complete details of a specific pond.

**When to use:** Detailed pond monitoring or before performing operations

```http
GET /pond/{pond_id}
Authorization: Bearer {token}
```

---

## Phase 3: Fish Species Setup

### UC-3.1: Register Fish Species - Tilapia

Add a new fish species to your farm's catalog.

**When to use:** When starting to farm a new type of fish (done once per species)

```http
POST /fish/create
Authorization: Bearer {token}
Content-Type: application/json

{
  "common_name": "Nile Tilapia",
  "scientific_name": "Oreochromis niloticus",
  "species_code": "TILAPIA_NILE",
  "description": "Fast-growing freshwater fish, ideal for warm climates",
  "growth_rate": "fast",
  "optimal_temp_min": 25,
  "optimal_temp_max": 30,
  "market_size_kg": 0.5
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "species_id": "TILAPIA_NILE",
    "species_code": "TILAPIA_NILE"
  }
}
```

---

### UC-3.2: Register Fish Species - Catfish

Add catfish species to diversify your farm.

```http
POST /fish/create
Authorization: Bearer {token}
Content-Type: application/json

{
  "common_name": "Pangasius Catfish",
  "scientific_name": "Pangasianodon hypophthalmus",
  "species_code": "CATFISH_PANGA",
  "description": "Hardy bottom-feeder, good for mixed farming",
  "growth_rate": "medium",
  "optimal_temp_min": 22,
  "optimal_temp_max": 28,
  "market_size_kg": 1.0
}
```

---

### UC-3.3: List All Fish Species

View all fish species registered in your farm with analytics.

```http
GET /fish/
Authorization: Bearer {token}
```

---

## Phase 4: Fish Purchase & Stocking

### UC-4.1: Purchase Fish Fingerlings (via Sampling API)

Record purchase of fish fingerlings from a hatchery. This creates stock records AND expense entries automatically.

**When to use:** Buying new fish stock from suppliers

```http
POST /sampling
Authorization: Bearer {token}
Content-Type: application/json

{
  "pondId": "ACC001-001",
  "species": "TILAPIA_NILE",
  "samplingDate": "2026-01-12T10:00:00+05:30",
  "totalCount": 5000,
  "sampleSize": 50,
  "averageWeight": 10,
  "averageLength": 5,
  "totalAmount": 25000,
  "notes": "Purchased from ABC Hatchery, Batch #TN-2026-001"
}
```

**Result:** 
- Purchase recorded with expense entry
- Stock added to pond
- Fish analytics updated

---

### UC-4.2: Stock Fish in Pond (Add Event)

Record stocking of fish into a pond using pond events.

**When to use:** Adding fish to a pond (initial stocking or when not tracking purchase cost separately)

```http
POST /pond_event/{pond_id}/event/add
Authorization: Bearer {token}
Content-Type: application/json

{
  "fish_id": "TILAPIA_NILE",
  "count": 5000,
  "fish_age_in_month": 1,
  "details": {
    "source": "ABC Hatchery",
    "batch_number": "TN-2026-001",
    "notes": "Initial stocking - nursery pond"
  }
}
```

**Result:**
- Fish added to pond (+5000)
- Pond metadata updated with fish count
- Analytics tracking started

---

### UC-4.3: Record Fish Purchase Expense (Separate)

Record the financial expense for fish purchase separately.

**When to use:** When purchase wasn't recorded via sampling API

```http
POST /expenses
Authorization: Bearer {token}
Content-Type: application/json

{
  "category": "asset",
  "type": "fish",
  "action": "buy",
  "amount": 25000,
  "currency": "INR",
  "pond_id": "ACC001-001",
  "description": "Tilapia fingerlings - 5000 nos",
  "vendor": "ABC Hatchery",
  "metadata": {
    "species": "TILAPIA_NILE",
    "quantity": 5000,
    "price_per_unit": 5
  }
}
```

---

## Phase 5: Daily Operations

### UC-5.1: Record Morning Feeding

Log feeding activity for a pond.

**When to use:** After each feeding session (typically 2-3 times daily)

```http
POST /feeding/
Authorization: Bearer {token}
Content-Type: application/json

{
  "pondId": "ACC001-001",
  "feedType": "floating pellet",
  "feedBrand": "Growel Aqua",
  "quantity": 25,
  "unit": "kg",
  "feedingTime": "2026-01-12T08:00:00+05:30",
  "notes": "Morning feeding - fish active"
}
```

---

### UC-5.2: Record Evening Feeding

```http
POST /feeding/
Authorization: Bearer {token}
Content-Type: application/json

{
  "pondId": "ACC001-001",
  "feedType": "floating pellet",
  "feedBrand": "Growel Aqua",
  "quantity": 20,
  "unit": "kg",
  "feedingTime": "2026-01-12T17:00:00+05:30",
  "notes": "Evening feeding - reduced quantity due to cloudy weather"
}
```

---

### UC-5.3: Record Feed Purchase Expense

Track feed purchase costs.

**When to use:** Buying fish feed stock

```http
POST /expenses
Authorization: Bearer {token}
Content-Type: application/json

{
  "category": "operational",
  "type": "feed",
  "action": "buy",
  "amount": 45000,
  "currency": "INR",
  "description": "Fish feed - 50 bags (25kg each)",
  "vendor": "Growel Feeds Pvt Ltd",
  "metadata": {
    "feed_type": "floating pellet",
    "quantity_bags": 50,
    "weight_per_bag_kg": 25,
    "price_per_bag": 900
  }
}
```

---

### UC-5.4: Create Task for Worker

Create and assign tasks to farm workers.

**When to use:** Assigning work to team members

```http
POST /task/
Authorization: Bearer {token}
Content-Type: application/json

{
  "title": "Check aerators in Pond B",
  "description": "Inspect all 4 aerators, clean filters, check oil levels",
  "assigned_to": "worker_ravi_key",
  "priority": "high",
  "task_date": "2026-01-12",
  "end_date": "2026-01-12 17:00",
  "tags": ["maintenance", "pond-b"]
}
```

---

### UC-5.5: Record Water Quality Check

Log water quality parameters for a pond.

**When to use:** During routine water quality monitoring (daily/weekly)

```http
POST /water-quality/samples
Authorization: Bearer {token}
Content-Type: application/json

{
  "pond_id": "ACC001-001",
  "temperature": 28.5,
  "ph": 7.2,
  "dissolved_oxygen": 6.5,
  "ammonia": 0.02,
  "nitrite": 0.01,
  "turbidity": 25,
  "sample_date": "2026-01-12T09:00:00+05:30"
}
```

---

## Phase 6: Growth Monitoring & Sampling

### UC-6.1: Monthly Growth Sampling (Pond Event)

Sample fish to measure growth progress.

**When to use:** Monthly or bi-weekly growth checks

```http
POST /pond_event/{pond_id}/event/sample
Authorization: Bearer {token}
Content-Type: application/json

{
  "fish_id": "TILAPIA_NILE",
  "count": 30,
  "fish_age_in_month": 3,
  "details": {
    "notes": "Monthly growth sampling",
    "weather": "Sunny",
    "water_temp": 28
  },
  "samples": [
    {"weight": 150, "length": 15},
    {"weight": 165, "length": 16},
    {"weight": 145, "length": 14.5},
    {"weight": 170, "length": 16.5},
    {"weight": 155, "length": 15.2}
  ]
}
```

**Result:**
- Growth data recorded
- Average weight/length calculated
- Pond count decreased by sample size (-30)
- Analytics updated

---

### UC-6.2: Growth Sampling via Sampling API

Alternative method with detailed metrics.

**When to use:** Detailed growth tracking with survival rate and FCR

```http
POST /sampling
Authorization: Bearer {token}
Content-Type: application/json

{
  "pondId": "ACC001-001",
  "species": "TILAPIA_NILE",
  "samplingDate": "2026-01-12T10:00:00+05:30",
  "sampleSize": 30,
  "averageWeight": 157,
  "averageLength": 15.4,
  "survivalRate": 92,
  "feedConversionRatio": 1.6,
  "notes": "Month 3 sampling - good growth rate"
}
```

---

### UC-6.3: Get Fish Analytics

View growth analytics and population data.

**When to use:** Reviewing growth progress, planning harvest

```http
GET /fish/{species_id}/analytics?min_age=2&max_age=6
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "species_code": "TILAPIA_NILE",
    "analytics": {
      "total_count": 5000,
      "age_analytics": {
        "3": {"count": 2000, "avg_weight": 150},
        "6": {"count": 3000, "avg_weight": 450}
      }
    }
  }
}
```

---

### UC-6.4: Get Sampling History

View historical sampling data for trend analysis.

```http
GET /sampling/history?pondId=ACC001-001&species=TILAPIA_NILE&startDate=2025-10-01&limit=20
Authorization: Bearer {token}
```

---

## Phase 7: Fish Mortality & Health Management

### UC-7.1: Record Fish Mortality (Remove Event)

Log fish deaths due to disease, water quality issues, or other causes.

**When to use:** When dead fish are found in the pond

```http
POST /pond_event/{pond_id}/event/remove
Authorization: Bearer {token}
Content-Type: application/json

{
  "fish_id": "TILAPIA_NILE",
  "count": 25,
  "details": {
    "reason": "Disease outbreak",
    "disease_type": "Bacterial infection - Aeromonas",
    "symptoms": "Red spots, fin rot, lethargy",
    "notes": "Found during morning check. Isolated pond, started treatment.",
    "action_taken": "Applied antibiotics, increased aeration"
  }
}
```

**Result:**
- Mortality recorded
- Pond count decreased (-25)
- Useful for mortality rate calculation

---

### UC-7.2: Record Medicine/Treatment Expense

Track costs for fish treatment.

```http
POST /expenses
Authorization: Bearer {token}
Content-Type: application/json

{
  "category": "operational",
  "type": "medicine",
  "action": "buy",
  "amount": 5500,
  "currency": "INR",
  "pond_id": "ACC001-001",
  "description": "Oxytetracycline treatment for bacterial infection",
  "vendor": "Aqua Vet Supplies",
  "metadata": {
    "medicine_name": "Oxytetracycline 20%",
    "quantity": 5,
    "unit": "kg",
    "treatment_duration_days": 7
  }
}
```

---

### UC-7.3: Create Health Monitoring Task

Schedule recurring health checks after disease outbreak.

```http
POST /task/
Authorization: Bearer {token}
Content-Type: application/json

{
  "title": "Daily health check - Pond A (Post-treatment)",
  "description": "Monitor fish behavior, check for new deaths, measure water quality",
  "priority": "high",
  "recurring": "daily",
  "task_date": "2026-01-13",
  "end_date": "2026-01-20 09:00",
  "tags": ["health", "pond-a", "treatment"]
}
```

---

## Phase 8: Fish Transfer Between Ponds

### UC-8.1: Transfer Fish OUT of Nursery (shift_out)

Move fish from nursery pond to grow-out pond - Step 1: Record outgoing.

**When to use:** Fish are ready to move from nursery to grow-out (typically after 2-3 months)

```http
POST /pond_event/ACC001-001/event/shift_out
Authorization: Bearer {token}
Content-Type: application/json

{
  "fish_id": "TILAPIA_NILE",
  "count": 3000,
  "fish_age_in_month": 3,
  "details": {
    "destination_pond": "ACC001-002",
    "reason": "Size grading - moving to grow-out",
    "notes": "Fish reached 150g average, ready for grow-out phase",
    "average_weight_at_transfer": 150
  }
}
```

**Result:** Fish count decreased in nursery pond (-3000)

---

### UC-8.2: Transfer Fish INTO Grow-out Pond (shift_in)

Complete the transfer - Step 2: Record incoming.

**When to use:** Immediately after shift_out to maintain accurate counts

```http
POST /pond_event/ACC001-002/event/shift_in
Authorization: Bearer {token}
Content-Type: application/json

{
  "fish_id": "TILAPIA_NILE",
  "count": 3000,
  "fish_age_in_month": 3,
  "details": {
    "source_pond": "ACC001-001",
    "reason": "Received from nursery for grow-out",
    "notes": "3000 fingerlings from nursery batch TN-2026-001",
    "average_weight_at_transfer": 150
  }
}
```

**Result:** Fish count increased in grow-out pond (+3000)

---

### UC-8.3: Size Grading - Separate Large Fish

Move larger fish to separate pond for faster harvest.

```http
POST /pond_event/ACC001-002/event/shift_out
Authorization: Bearer {token}
Content-Type: application/json

{
  "fish_id": "TILAPIA_NILE",
  "count": 500,
  "fish_age_in_month": 5,
  "details": {
    "destination_pond": "ACC001-003",
    "reason": "Size grading - jumbo fish",
    "notes": "Large fish (400g+) moved for early harvest",
    "average_weight_at_transfer": 420
  }
}
```

---

## Phase 9: Harvest & Sales

### UC-9.1: Partial Harvest for Local Market (Sell Event)

Harvest a portion of fish for immediate sale.

**When to use:** When fish reach market size and there's buyer demand

```http
POST /pond_event/{pond_id}/event/sell
Authorization: Bearer {token}
Content-Type: application/json

{
  "fish_id": "TILAPIA_NILE",
  "count": 500,
  "details": {
    "notes": "Partial harvest for Bangalore market",
    "buyer": "Fresh Fish Traders",
    "buyer_contact": "+91-9876543000",
    "price_per_kg": 180,
    "total_weight_kg": 250,
    "total_amount": 45000,
    "average_fish_weight_g": 500,
    "harvest_method": "seine net"
  }
}
```

**Result:**
- Sale recorded
- Pond fish count decreased (-500)
- Ready for revenue tracking

---

### UC-9.2: Record Sales Transaction

Create transaction record for the sale.

**When to use:** After harvest, for financial tracking

```http
POST /transactions
Authorization: Bearer {token}
Content-Type: application/json

{
  "type": "sale",
  "pond_id": "ACC001-002",
  "species": "TILAPIA_NILE",
  "quantity": 500,
  "weight_kg": 250,
  "amount": 45000,
  "currency": "INR",
  "payment_method": "bank_transfer",
  "payment_status": "pending",
  "buyer": {
    "name": "Fresh Fish Traders",
    "contact": "+91-9876543000"
  },
  "notes": "Invoice #INV-2026-0045"
}
```

---

### UC-9.3: Full Pond Harvest

Complete harvest of all fish from a pond.

**When to use:** End of culture cycle, pond draining

```http
POST /pond_event/{pond_id}/event/sell
Authorization: Bearer {token}
Content-Type: application/json

{
  "fish_id": "TILAPIA_NILE",
  "count": 2500,
  "details": {
    "notes": "Full harvest - end of cycle",
    "buyer": "Metro Wholesale Market",
    "price_per_kg": 170,
    "total_weight_kg": 1375,
    "total_amount": 233750,
    "average_fish_weight_g": 550,
    "harvest_date": "2026-01-12",
    "harvest_method": "complete drain"
  }
}
```

---

### UC-9.4: Record Revenue/Income

Record income from fish sales for accounting.

**When to use:** When payment is received

```http
POST /expenses
Authorization: Bearer {token}
Content-Type: application/json

{
  "category": "income",
  "type": "fish_sale",
  "action": "sell",
  "amount": 233750,
  "currency": "INR",
  "pond_id": "ACC001-002",
  "description": "Tilapia harvest - full pond sale",
  "metadata": {
    "species": "TILAPIA_NILE",
    "quantity": 2500,
    "weight_kg": 1375,
    "buyer": "Metro Wholesale Market",
    "invoice": "INV-2026-0046"
  }
}
```

---

## Phase 10: Financial Management

### UC-10.1: Record Electricity Expense

Track monthly utility costs.

```http
POST /expenses
Authorization: Bearer {token}
Content-Type: application/json

{
  "category": "operational",
  "type": "utilities",
  "action": "pay",
  "amount": 18500,
  "currency": "INR",
  "description": "Electricity bill - January 2026",
  "vendor": "BESCOM",
  "metadata": {
    "bill_number": "EB-2026-01-12345",
    "billing_period": "December 2025",
    "units_consumed": 2850
  }
}
```

---

### UC-10.2: Record Labor/Salary Expense

Track worker salaries.

```http
POST /expenses
Authorization: Bearer {token}
Content-Type: application/json

{
  "category": "operational",
  "type": "labor",
  "action": "pay",
  "amount": 75000,
  "currency": "INR",
  "description": "Monthly salaries - January 2026",
  "metadata": {
    "workers_count": 5,
    "period": "January 2026",
    "breakdown": {
      "supervisor": 25000,
      "workers": 50000
    }
  }
}
```

---

### UC-10.3: Record Equipment Purchase

Track capital expenses.

```http
POST /expenses
Authorization: Bearer {token}
Content-Type: application/json

{
  "category": "asset",
  "type": "equipment",
  "action": "buy",
  "amount": 85000,
  "currency": "INR",
  "description": "New aerator system - Pond B",
  "vendor": "Aqua Tech Solutions",
  "metadata": {
    "equipment_type": "paddle wheel aerator",
    "power": "2HP",
    "quantity": 2,
    "warranty_years": 2
  }
}
```

---

### UC-10.4: View All Expenses

Get filtered list of expenses.

```http
GET /expenses?start_date=2026-01-01&end_date=2026-01-31&category=operational
Authorization: Bearer {token}
```

---

### UC-10.5: View Transactions

Get all financial transactions.

```http
GET /transactions?type=sale&startDate=2026-01-01&endDate=2026-01-31
Authorization: Bearer {token}
```

---

## Phase 11: Reporting & Analytics

### UC-11.1: Get Pond Events History

View complete history of all events for a pond.

```http
GET /pond_event/{pond_id}/events
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "events": [
      {
        "id": "evt001",
        "eventType": "add",
        "species": "TILAPIA_NILE",
        "count": 5000,
        "timestamp": "2026-01-01T10:00:00+05:30"
      },
      {
        "id": "evt002",
        "eventType": "sample",
        "species": "TILAPIA_NILE",
        "count": 30,
        "timestamp": "2026-01-10T09:00:00+05:30"
      },
      {
        "id": "evt003",
        "eventType": "sell",
        "species": "TILAPIA_NILE",
        "count": 500,
        "timestamp": "2026-01-12T14:00:00+05:30"
      }
    ]
  }
}
```

---

### UC-11.2: Get All Fish Analytics

Farm-wide analytics for all species.

```http
GET /fish/analytics
Authorization: Bearer {token}
```

---

### UC-11.3: Get Feeding Records by Pond

View feeding history for FCR calculation.

```http
GET /feeding/pond/{pond_id}
Authorization: Bearer {token}
```

---

### UC-11.4: Get Fish Field Statistics

Get statistical data for analysis.

```http
GET /fish/stats/weight
Authorization: Bearer {token}
```

---

### UC-11.5: List Tasks by Status

Review pending or completed tasks.

```http
GET /task/?status=pending&priority=high
Authorization: Bearer {token}
```

---

## Phase 12: End of Cycle & Pond Reset

### UC-12.1: Record Pond Maintenance Expense

Track costs for pond cleaning after harvest.

```http
POST /expenses
Authorization: Bearer {token}
Content-Type: application/json

{
  "category": "operational",
  "type": "maintenance",
  "action": "pay",
  "amount": 15000,
  "currency": "INR",
  "pond_id": "ACC001-002",
  "description": "Pond cleaning and lime treatment after harvest",
  "metadata": {
    "activities": ["draining", "drying", "lime application", "refilling"],
    "lime_quantity_kg": 500,
    "drying_days": 7
  }
}
```

---

### UC-12.2: Update Pond Status - Maintenance

Mark pond as under maintenance.

```http
PUT /pond/update/{pond_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "status": "maintenance",
  "metadata": {
    "last_harvest_date": "2026-01-12",
    "next_stocking_date": "2026-01-25",
    "maintenance_activities": ["lime treatment", "predator removal", "water filling"]
  }
}
```

---

### UC-12.3: Mark Pond Ready for Stocking

Update pond status when ready for new fish.

```http
PUT /pond/update/{pond_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "status": "ready",
  "metadata": {
    "preparation_complete": "2026-01-24",
    "water_quality_checked": true,
    "ready_for_stocking": true
  }
}
```

---

### UC-12.4: Delete Pond (If Needed)

Remove a pond from the system.

**When to use:** Pond decommissioned or no longer in use

```http
DELETE /pond/{pond_id}
Authorization: Bearer {token}
```

---

## Quick Reference

### Daily Tasks Checklist
- [ ] Record feeding (2-3 times)
- [ ] Check water quality
- [ ] Monitor fish behavior
- [ ] Record any mortality
- [ ] Complete assigned tasks

### Weekly Tasks Checklist
- [ ] Detailed water quality test
- [ ] Equipment inspection
- [ ] Feed inventory check
- [ ] Review pending tasks

### Monthly Tasks Checklist
- [ ] Growth sampling
- [ ] Pay bills and record expenses
- [ ] Review fish analytics
- [ ] Plan harvests
- [ ] Salary payments

---

## Pond Event Types Summary

| Event Type | API Path | Effect on Count | When to Use |
|------------|----------|-----------------|-------------|
| **add** | `/pond_event/{pond_id}/event/add` | **+count** | Stocking new fish, receiving purchased fish |
| **remove** | `/pond_event/{pond_id}/event/remove` | **-count** | Fish mortality, disease culling, losses |
| **sell** | `/pond_event/{pond_id}/event/sell` | **-count** | Harvesting fish for sale |
| **sample** | `/pond_event/{pond_id}/event/sample` | **-count** | Growth measurement, quality testing |
| **shift_out** | `/pond_event/{pond_id}/event/shift_out` | **-count** | Transferring fish OUT to another pond |
| **shift_in** | `/pond_event/{pond_id}/event/shift_in` | **+count** | Receiving fish from another pond |

### Event Flow Examples

**New Fish Purchase:**
```
Hatchery → [add] → Nursery Pond
```

**Nursery to Grow-out Transfer:**
```
Nursery Pond → [shift_out] → [shift_in] → Grow-out Pond
```

**Harvest and Sale:**
```
Grow-out Pond → [sell] → Market
```

**Mortality:**
```
Any Pond → [remove] → (recorded for analytics)
```

---

## API Endpoints Summary

| Category | Endpoint | Methods |
|----------|----------|---------|
| **Auth** | `/auth/signup` | POST |
| **Auth** | `/auth/login` | POST |
| **Auth** | `/auth/account/{account_key}/signup` | POST |
| **Pond** | `/pond/create` | POST |
| **Pond** | `/pond/` | GET |
| **Pond** | `/pond/{pond_id}` | GET, DELETE |
| **Pond** | `/pond/update/{pond_id}` | PUT |
| **Fish** | `/fish/create` | POST |
| **Fish** | `/fish/` | GET, POST, PUT |
| **Fish** | `/fish/{species_id}` | GET, PUT |
| **Fish** | `/fish/analytics` | GET |
| **Fish** | `/fish/{species_id}/analytics` | GET |
| **Pond Events** | `/pond_event/{pond_id}/event/add` | POST |
| **Pond Events** | `/pond_event/{pond_id}/event/sell` | POST |
| **Pond Events** | `/pond_event/{pond_id}/event/sample` | POST |
| **Pond Events** | `/pond_event/{pond_id}/event/remove` | POST |
| **Pond Events** | `/pond_event/{pond_id}/event/shift_in` | POST |
| **Pond Events** | `/pond_event/{pond_id}/event/shift_out` | POST |
| **Pond Events** | `/pond_event/{pond_id}/events` | GET |
| **Pond Events** | `/pond_event/{pond_id}/events/{event_id}` | PUT, DELETE |
| **Sampling** | `/sampling` | POST |
| **Sampling** | `/sampling/{pond_id}` | GET |
| **Sampling** | `/sampling/history` | GET |
| **Sampling** | `/sampling/{sampling_id}` | PUT, DELETE |
| **Feeding** | `/feeding/` | GET, POST |
| **Feeding** | `/feeding/pond/{pond_id}` | GET |
| **Expenses** | `/expenses` | GET, POST |
| **Transactions** | `/transactions` | GET, POST |
| **Transactions** | `/transactions/{tx_id}` | GET, PUT, DELETE |
| **Tasks** | `/task/` | GET, POST |
| **Tasks** | `/task/{task_id}` | GET, PUT, DELETE |

---

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing or invalid token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found |
| 409 | Conflict - Resource already exists |
| 500 | Internal Server Error |

---

---

## Additional Use Cases

### User Profile & Settings Management

#### UC-A.1: Get User Profile

View current user's profile information.

```http
GET /user/profile
Authorization: Bearer {token}
```

---

#### UC-A.2: Update User Profile

Update profile fields like name, address, timezone.

```http
PUT /user/profile
Authorization: Bearer {token}
Content-Type: application/json

{
  "first_name": "Rajesh",
  "last_name": "Kumar",
  "address1": "123 Farm Lane",
  "pincode": "560001",
  "timezone": "Asia/Kolkata"
}
```

---

#### UC-A.3: Change Password

Update user password.

```http
PUT /user/password
Authorization: Bearer {token}
Content-Type: application/json

{
  "old_password": "OldPassword123!",
  "new_password": "NewSecurePass456!"
}
```

---

#### UC-A.4: Logout

Logout user and clear refresh tokens.

```http
POST /user/logout
Authorization: Bearer {token}
```

---

#### UC-A.5: Get User Settings

View user settings and subscription.

```http
GET /user/settings
Authorization: Bearer {token}
```

---

#### UC-A.6: Update User Settings

Update user preferences.

```http
PUT /user/settings
Authorization: Bearer {token}
Content-Type: application/json

{
  "settings": {
    "timezone": "Asia/Kolkata",
    "language": "en",
    "notifications": {
      "email": true,
      "push": true,
      "sms": false
    }
  }
}
```

---

#### UC-A.7: Update Notification Settings

Configure notification preferences.

```http
PUT /user/settings/notifications
Authorization: Bearer {token}
Content-Type: application/json

{
  "notifications": {
    "email": true,
    "push": true,
    "task_reminders": true,
    "daily_digest": false
  }
}
```

---

#### UC-A.8: List Users in Account

Get all users in your farm account (admin view).

```http
GET /user/list
Authorization: Bearer {token}
```

---

#### UC-A.9: Delete User (Admin Only)

Remove a user from the account.

```http
DELETE /user/account/{account_key}/user/{user_key}
Authorization: Bearer {admin_token}
```

---

### Company Management

#### UC-B.1: Register Company (Alternative)

Alternative company registration endpoint.

```http
POST /company/register
Content-Type: application/json

{
  "company_name": "Blue Lake Fish Farm",
  "username": "admin_user",
  "password": "SecurePass123!",
  "email": "admin@bluelake.com",
  "phone": "+91-9876543210",
  "pincode": "560001",
  "description": "Premium fish farming operation",
  "master_password": "your-master-password"
}
```

---

#### UC-B.2: Get Company Details

View complete company information.

```http
GET /company/{account_key}
Authorization: Bearer {token}
```

---

#### UC-B.3: Update Company Details

Update company information (admin only).

```http
PUT /company/{account_key}
Authorization: Bearer {admin_token}
Content-Type: application/json

{
  "company_name": "Blue Lake Premium Fish Farm",
  "pincode": "560002",
  "description": "Updated description"
}
```

---

#### UC-B.4: Get Company Users

List all users in a company.

```http
GET /company/{account_key}/users
Authorization: Bearer {token}
```

---

#### UC-B.5: Remove User from Company (Admin)

Remove a user from company.

```http
DELETE /company/{account_key}/users/{user_key}
Authorization: Bearer {admin_token}
```

---

### Advanced Pond Features

#### UC-C.1: Get Fish Options for Pond

Get dropdown options for fish species available in your account.

```http
GET /pond/{pond_id}/fish_options
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "pondId": "ACC001-001",
    "options": [
      {"id": "TILAPIA_NILE", "species_code": "TILAPIA_NILE", "common_name": "Nile Tilapia"},
      {"id": "CATFISH_PANGA", "species_code": "CATFISH_PANGA", "common_name": "Pangasius Catfish"}
    ]
  }
}
```

---

#### UC-C.2: Get Pond Activity

Get paginated fish activity (samples) for a pond.

```http
GET /pond/{pond_id}/activity?fish_id=TILAPIA_NILE&limit=50&skip=0&start_date=2026-01-01&end_date=2026-01-31
Authorization: Bearer {token}
```

---

#### UC-C.3: Get Pond History (Combined)

Get combined history of events, activities, and analytics for a pond.

```http
GET /pond/{pond_id}/history?start_date=2025-10-01&end_date=2026-01-31&include_events=true&include_activities=true&include_analytics=true&limit=100
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "history": {
      "pond_id": "ACC001-001",
      "events": [...],
      "activities": [...],
      "analytics": [...]
    }
  }
}
```

---

### Payments & Bank Reconciliation

#### UC-D.1: Mark Expense as Paid

Mark an expense as paid with payment details.

```http
POST /expenses/{expense_id}/pay
Authorization: Bearer {token}
Content-Type: application/json

{
  "payment": {
    "amount": 45000,
    "method": "bank_transfer",
    "reference": "TXN123456",
    "paid_date": "2026-01-12"
  },
  "transaction": {
    "type": "payment",
    "amount": 45000
  }
}
```

---

#### UC-D.2: Create Payment

Create a standalone payment record.

```http
POST /expenses/payments
Authorization: Bearer {token}
Content-Type: application/json

{
  "amount": 25000,
  "method": "cash",
  "description": "Feed supplier payment",
  "vendor": "Growel Feeds",
  "transaction": {
    "type": "payment",
    "amount": 25000
  }
}
```

---

#### UC-D.3: Get Payment Details

Retrieve a specific payment.

```http
GET /expenses/payments/{payment_id}
Authorization: Bearer {token}
```

---

#### UC-D.4: Import Bank Statement

Import bank statement for reconciliation.

```http
POST /expenses/bank_statements/import
Authorization: Bearer {token}
Content-Type: application/json

{
  "statement": {
    "bank_name": "HDFC Bank",
    "account_number": "XXXX1234",
    "statement_date": "2026-01-31",
    "opening_balance": 100000,
    "closing_balance": 85000
  },
  "lines": [
    {
      "date": "2026-01-10",
      "description": "NEFT-ABC Hatchery",
      "debit": 25000,
      "credit": 0,
      "balance": 75000,
      "externalRef": "NEFT123456"
    }
  ]
}
```

---

#### UC-D.5: Reconcile by External Reference

Match bank statement lines with payments.

```http
POST /expenses/reconcile/by-external
Authorization: Bearer {token}
Content-Type: application/json

{
  "bankAccountId": "bank_acc_123",
  "externalRef": "NEFT123456"
}
```

---

### Task Advanced Features

#### UC-E.1: Move/Reassign Task

Reassign a task to another user.

```http
POST /task/{task_id}/move
Authorization: Bearer {token}
Content-Type: application/json

{
  "new_assignee": "worker_ravi_key"
}
```

---

#### UC-E.2: Get Task by ID

Retrieve a specific task.

```http
GET /task/{task_id}
Authorization: Bearer {token}
```

---

#### UC-E.3: Update Task Status

Update task status and details.

```http
PUT /task/{task_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "status": "completed",
  "notes": "Task completed successfully",
  "actual_end_date": "2026-01-12 16:30"
}
```

---

#### UC-E.4: Delete Task

Remove a task.

```http
DELETE /task/{task_id}
Authorization: Bearer {token}
```

---

### AI/OpenAI Services

#### UC-F.1: Check AI Service Health

Check if OpenAI is configured.

```http
GET /ai/openai/health
```

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "ok",
    "configured": true,
    "model": "gpt-4"
  }
}
```

---

#### UC-F.2: List Available Models

Get available OpenAI models.

```http
GET /ai/openai/models
Authorization: Bearer {token}
```

---

#### UC-F.3: AI Query (Chat)

Send a query to AI for fish farming advice.

```http
POST /ai/openai/query
Authorization: Bearer {token}
Content-Type: application/json

{
  "prompt": "What is the optimal water temperature for Tilapia farming?",
  "context": {
    "pond_id": "ACC001-001",
    "species": "TILAPIA_NILE"
  }
}
```

---

#### UC-F.4: Get AI Usage Statistics

View AI usage for billing/monitoring.

```http
GET /ai/openai/usage?days=30
Authorization: Bearer {token}
```

---

#### UC-F.5: Get AI Usage History

View detailed AI usage history.

```http
GET /ai/openai/usage/history?limit=50
Authorization: Bearer {token}
```

---

### Public APIs (No Auth Required)

#### UC-G.1: Health Check

Check if the API server is running.

```http
GET /public/health
```

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "ok",
    "db": "reachable"
  }
}
```

---

#### UC-G.2: Get Public Company Info

Get minimal company info without authentication.

```http
GET /public/company/{account_key}
```

---

#### UC-G.3: Get Public Fish List

Get fish species (optionally filtered by account).

```http
GET /public/fish?account_key=ACC001
```

---

#### UC-G.4: Get Company by User Identifier

Find company by user details.

```http
GET /public/user/company?email=admin@myfishfarm.com
```

---

#### UC-G.5: Get Public Company Info (via Company endpoint)

```http
GET /company/public/{account_key}
```

---

### Token Management

#### UC-H.1: Refresh Access Token

Get new access token using refresh token.

```http
POST /auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGc..."
}
```

---

## Complete API Endpoints Summary (Extended)

| Category | Endpoint | Methods | Auth Required |
|----------|----------|---------|---------------|
| **Public** | `/public/health` | GET | No |
| **Public** | `/public/company/{account_key}` | GET | No |
| **Public** | `/public/fish` | GET | No |
| **Public** | `/public/user/company` | GET | No |
| **Auth** | `/auth/signup` | POST | No |
| **Auth** | `/auth/login` | POST | No |
| **Auth** | `/auth/refresh` | POST | No |
| **Auth** | `/auth/account/{account_key}/signup` | POST | Yes (Admin) |
| **User** | `/user/profile` | GET, PUT | Yes |
| **User** | `/user/password` | PUT | Yes |
| **User** | `/user/logout` | POST | Yes |
| **User** | `/user/me` | GET | Yes |
| **User** | `/user/settings` | GET, PUT | Yes |
| **User** | `/user/settings/notifications` | PUT | Yes |
| **User** | `/user/list` | GET | Yes |
| **User** | `/user/account/{account_key}/user/{user_key}` | DELETE | Yes (Admin) |
| **Company** | `/company/register` | POST | No |
| **Company** | `/company/{account_key}` | GET, PUT | Yes |
| **Company** | `/company/{account_key}/users` | GET | Yes |
| **Company** | `/company/{account_key}/users/{user_key}` | DELETE | Yes (Admin) |
| **Company** | `/company/public/{account_key}` | GET | No |
| **Pond** | `/pond/create` | POST | Yes |
| **Pond** | `/pond/` | GET | Yes |
| **Pond** | `/pond/{pond_id}` | GET, PUT, DELETE | Yes |
| **Pond** | `/pond/update/{pond_id}` | PUT | Yes |
| **Pond** | `/pond/{pond_id}/fish_options` | GET | Yes |
| **Pond** | `/pond/{pond_id}/activity` | GET | Yes |
| **Pond** | `/pond/{pond_id}/history` | GET | Yes |
| **Fish** | `/fish/create` | POST | Yes |
| **Fish** | `/fish/` | GET, POST, PUT | Yes |
| **Fish** | `/fish/{species_id}` | GET, PUT | Yes |
| **Fish** | `/fish/analytics` | GET | Yes |
| **Fish** | `/fish/{species_id}/analytics` | GET | Yes |
| **Fish** | `/fish/fields` | GET | Yes |
| **Fish** | `/fish/distinct/{field}` | GET | Yes |
| **Fish** | `/fish/stats/{field}` | GET | Yes |
| **Pond Events** | `/pond_event/{pond_id}/event/add` | POST | Yes |
| **Pond Events** | `/pond_event/{pond_id}/event/sell` | POST | Yes |
| **Pond Events** | `/pond_event/{pond_id}/event/sample` | POST | Yes |
| **Pond Events** | `/pond_event/{pond_id}/event/remove` | POST | Yes |
| **Pond Events** | `/pond_event/{pond_id}/event/shift_in` | POST | Yes |
| **Pond Events** | `/pond_event/{pond_id}/event/shift_out` | POST | Yes |
| **Pond Events** | `/pond_event/{pond_id}/events` | GET | Yes |
| **Pond Events** | `/pond_event/{pond_id}/events/{event_id}` | PUT, DELETE | Yes |
| **Sampling** | `/sampling` | POST | Yes |
| **Sampling** | `/sampling/{pond_id}` | GET | Yes |
| **Sampling** | `/sampling/history` | GET | Yes |
| **Sampling** | `/sampling/{sampling_id}` | PUT, DELETE | Yes |
| **Feeding** | `/feeding/` | GET, POST | Yes |
| **Feeding** | `/feeding/pond/{pond_id}` | GET | Yes |
| **Expenses** | `/expenses` | GET, POST | Yes |
| **Expenses** | `/expenses/{expense_id}/pay` | POST | Yes |
| **Expenses** | `/expenses/payments` | POST | Yes |
| **Expenses** | `/expenses/payments/{payment_id}` | GET | Yes |
| **Expenses** | `/expenses/transactions` | POST | Yes |
| **Expenses** | `/expenses/bank_statements/import` | POST | Yes |
| **Expenses** | `/expenses/reconcile/by-external` | POST | Yes |
| **Transactions** | `/transactions` | GET, POST | Yes |
| **Transactions** | `/transactions/{tx_id}` | GET, PUT, DELETE | Yes |
| **Tasks** | `/task/` | GET, POST | Yes |
| **Tasks** | `/task/{task_id}` | GET, PUT, DELETE | Yes |
| **Tasks** | `/task/{task_id}/move` | POST | Yes |
| **AI** | `/ai/openai/health` | GET | No |
| **AI** | `/ai/openai/models` | GET | Yes |
| **AI** | `/ai/openai/query` | POST | Yes |
| **AI** | `/ai/openai/usage` | GET | Yes |
| **AI** | `/ai/openai/usage/history` | GET | Yes |

---

## Total Use Cases Count

| Phase | Use Cases |
|-------|-----------|
| Phase 1: Farm Setup & Registration | 3 |
| Phase 2: Infrastructure Setup (Ponds) | 5 |
| Phase 3: Fish Species Setup | 3 |
| Phase 4: Fish Purchase & Stocking | 3 |
| Phase 5: Daily Operations | 5 |
| Phase 6: Growth Monitoring & Sampling | 4 |
| Phase 7: Fish Mortality & Health | 3 |
| Phase 8: Fish Transfer Between Ponds | 3 |
| Phase 9: Harvest & Sales | 4 |
| Phase 10: Financial Management | 5 |
| Phase 11: Reporting & Analytics | 5 |
| Phase 12: End of Cycle & Pond Reset | 4 |
| **Additional: User Profile & Settings** | 9 |
| **Additional: Company Management** | 5 |
| **Additional: Advanced Pond Features** | 3 |
| **Additional: Payments & Reconciliation** | 5 |
| **Additional: Task Advanced Features** | 4 |
| **Additional: AI/OpenAI Services** | 5 |
| **Additional: Public APIs** | 5 |
| **Additional: Token Management** | 1 |
| **TOTAL** | **79 Use Cases** |

---

## Support

For questions or issues, please contact the development team or refer to the full API documentation.

