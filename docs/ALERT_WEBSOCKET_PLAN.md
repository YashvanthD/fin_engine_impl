# Alert System via WebSocket - Implementation Plan

## Overview

This plan outlines how to implement a comprehensive alert system that works through both REST API and WebSocket for real-time delivery. Alerts are account-wide notifications for critical events like water temperature changes, task deadlines, system events, etc.

## Current State Analysis

### ✅ Already Implemented

1. **REST API Endpoints** (`/api/notification/alert/*`)
   - `POST /api/notification/alert/` - Create alert
   - `GET /api/notification/alert/` - List alerts
   - `GET /api/notification/alert/<id>` - Get single alert
   - `PUT /api/notification/alert/<id>/acknowledge` - Acknowledge alert
   - `DELETE /api/notification/alert/<id>` - Delete alert (admin)

2. **AlertHandler Class** (`fin_server/websocket/handlers/alert_handler.py`)
   - `create_and_emit()` - Creates alert in DB and emits via WebSocket
   - `acknowledge_and_emit()` - Acknowledges and emits
   - `delete_and_emit()` - Deletes and emits
   - Convenience methods: `create_pond_alert()`, `create_task_alert()`, `create_system_alert()`, `create_critical_alert()`

3. **EventEmitter** (`fin_server/websocket/event_emitter.py`)
   - `notify_account_alert()` - Emits alert:new to all account users
   - `update_alert_count()` - Updates unacknowledged count
   - Event constants: `ALERT_NEW`, `ALERT_ACKNOWLEDGED`, `ALERT_DELETED`, `ALERT_COUNT`

4. **WebSocket Hub** - Basic connection handling

### ❌ Missing / Needs Enhancement

1. **WebSocket Event Handlers** - No client->server alert events registered in hub
2. **Alert Rules Engine** - No automatic alert triggering based on thresholds
3. **Alert Categories/Types** - Need more structured alert types
4. **Test HTML** - No test file for alerts like chat tests
5. **UI Integration** - WebSocket service needs alert event handling

---

## Implementation Plan

### Phase 1: WebSocket Alert Handler Registration

Register WebSocket event handlers for client-initiated alert actions in `hub.py`:

```
Events to Register:
- alert:acknowledge     (client -> server) - Acknowledge an alert
- alert:acknowledge_all (client -> server) - Acknowledge all alerts
- alert:dismiss         (client -> server) - Dismiss/delete alert
- alert:subscribe       (client -> server) - Subscribe to specific alert types
```

**File:** `fin_server/websocket/hub.py`

### Phase 2: Alert Types & Severity Schema

Define structured alert categories for fish farming:

```
Alert Sources:
- pond       - Water quality, temperature, oxygen levels
- task       - Task deadlines, overdue tasks
- feeding    - Feeding schedules, low feed stock
- fish       - Mortality, disease detection
- weather    - Weather warnings
- system     - System errors, maintenance
- user       - User actions, permission changes

Alert Types:
- info       - Informational
- warning    - Warning, needs attention
- critical   - Critical, immediate action required
- success    - Success/resolved notification

Severity Levels:
- low        - Can be addressed later
- medium     - Should be addressed soon
- high       - Needs prompt attention
- critical   - Immediate action required
```

### Phase 3: Alert Rules Engine

Create a rules engine that automatically triggers alerts based on thresholds:

**File:** `fin_server/services/alert_rules_service.py`

```python
# Example Rules:
rules = [
    {
        "name": "high_water_temperature",
        "source": "pond",
        "metric": "water_temperature",
        "condition": "gt",  # greater than
        "threshold": 32,    # degrees celsius
        "severity": "high",
        "message_template": "Water temperature in {pond_name} is {value}°C (above {threshold}°C)"
    },
    {
        "name": "low_oxygen_level",
        "source": "pond",
        "metric": "oxygen_level",
        "condition": "lt",  # less than
        "threshold": 4,     # mg/L
        "severity": "critical",
        "message_template": "Oxygen level in {pond_name} is critically low: {value} mg/L"
    },
    {
        "name": "task_overdue",
        "source": "task",
        "condition": "overdue",
        "severity": "medium",
        "message_template": "Task '{task_name}' is overdue by {days} days"
    },
    {
        "name": "high_mortality_rate",
        "source": "fish",
        "metric": "mortality_rate",
        "condition": "gt",
        "threshold": 5,  # percent
        "severity": "critical",
        "message_template": "High mortality rate detected in {pond_name}: {value}%"
    }
]
```

### Phase 4: Alert Triggering Integration Points

Integrate alert triggers into existing services:

1. **Water Quality Service** - Trigger alerts on parameter updates
2. **Task Service** - Trigger alerts on deadline approach/overdue
3. **Pond Service** - Trigger alerts on critical changes
4. **Sampling Service** - Trigger alerts on abnormal readings

**Example Integration in `pond_service.py`:**
```python
def update_water_quality(pond_id, data):
    # ... existing update logic ...
    
    # Check alert rules
    if data.get('temperature') > 32:
        AlertHandler.create_pond_alert(
            account_key=account_key,
            pond_id=pond_id,
            title="High Water Temperature Alert",
            message=f"Temperature in {pond_name} is {data['temperature']}°C",
            severity='high'
        )
```

### Phase 5: WebSocket Events Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    ALERT FLOW DIAGRAM                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐                                              │
│  │ TRIGGER      │                                              │
│  │ SOURCES      │                                              │
│  ├──────────────┤                                              │
│  │ • REST API   │────┐                                         │
│  │ • Scheduler  │    │                                         │
│  │ • Sensor Data│    │    ┌─────────────────┐                  │
│  │ • Rule Engine│────┼───▶│ AlertHandler    │                  │
│  │ • Manual     │    │    │ create_and_emit │                  │
│  └──────────────┘    │    └────────┬────────┘                  │
│                      │             │                            │
│                      │             ▼                            │
│                      │    ┌─────────────────┐                  │
│                      │    │ MongoDB         │                  │
│                      │    │ alerts collection│                  │
│                      │    └────────┬────────┘                  │
│                      │             │                            │
│                      │             ▼                            │
│                      │    ┌─────────────────┐                  │
│                      └───▶│ EventEmitter    │                  │
│                           │ emit_to_account │                  │
│                           └────────┬────────┘                  │
│                                    │                            │
│                                    ▼                            │
│                           ┌─────────────────┐                  │
│                           │ WebSocket Hub   │                  │
│                           │ (Socket.IO)     │                  │
│                           └────────┬────────┘                  │
│                                    │                            │
│              ┌─────────────────────┼─────────────────────┐     │
│              ▼                     ▼                     ▼     │
│     ┌─────────────┐       ┌─────────────┐       ┌─────────────┐│
│     │ User A      │       │ User B      │       │ User C      ││
│     │ (Browser)   │       │ (Browser)   │       │ (Mobile)    ││
│     └─────────────┘       └─────────────┘       └─────────────┘│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 6: WebSocket Event Definitions

**Server → Client Events:**
```javascript
// New alert created
socket.on('alert:new', (data) => {
    // data: { alert_id, title, message, type, severity, source, source_id, created_at }
});

// Alert acknowledged
socket.on('alert:acknowledged', (data) => {
    // data: { alert_id, acknowledged_by, acknowledged_at }
});

// Alert deleted
socket.on('alert:deleted', (data) => {
    // data: { alert_id }
});

// Alert count updated
socket.on('alert:count', (data) => {
    // data: { unacknowledged_count }
});
```

**Client → Server Events:**
```javascript
// Acknowledge alert
socket.emit('alert:acknowledge', { alert_id: 'xxx' }, (response) => {
    // response: { success: true, alert_id: 'xxx' }
});

// Acknowledge all alerts
socket.emit('alert:acknowledge_all', {}, (response) => {
    // response: { success: true, count: 5 }
});

// Subscribe to specific alert types (optional)
socket.emit('alert:subscribe', { types: ['critical', 'high'] });
```

---

## Implementation Tasks

### Task 1: Register WebSocket Alert Handlers in Hub ✅
**File:** `fin_server/websocket/hub.py`
- Add `alert:acknowledge` handler
- Add `alert:acknowledge_all` handler
- Add error handling

### Task 2: Create Alert Rules Service
**File:** `fin_server/services/alert_rules_service.py`
- Define alert rules schema
- Create rule evaluation engine
- Support threshold-based triggers
- Support time-based triggers (overdue tasks)

### Task 3: Create Alert Rules Data
**File:** `data/default_alert_rules.json`
- Define default fish farm alert rules
- Temperature thresholds
- Oxygen level thresholds
- pH level thresholds
- Task deadline rules

### Task 4: Integrate Alert Triggers
**Files:** Various service files
- `fin_server/services/pond_service.py` - Water quality alerts
- `fin_server/services/task_service.py` - Task deadline alerts
- `fin_server/services/sampling_service.py` - Abnormal reading alerts

### Task 5: Create Test HTML File
**File:** `test_websocket_alerts.html`
- Connect to WebSocket
- Create alerts via REST API
- Receive alerts via WebSocket
- Acknowledge alerts via WebSocket
- Display alert history

### Task 6: Update UI WebSocket Service
**File:** (UI project) `socketService.js`
- Ensure alert events are handled
- Provide convenience methods for alerts

---

## Alert Data Schema

```javascript
{
    "_id": "alert_abc123",
    "alert_id": "alert_abc123",
    "account_key": "acc_xxx",
    
    // Content
    "title": "High Water Temperature",
    "message": "Pond 1 temperature is 34°C (threshold: 32°C)",
    
    // Classification
    "type": "warning",           // info, warning, critical, success
    "severity": "high",          // low, medium, high, critical
    "source": "pond",            // pond, task, fish, feeding, weather, system
    "source_id": "pond_xxx",     // Related entity ID
    
    // Status
    "acknowledged": false,
    "acknowledged_by": null,
    "acknowledged_at": null,
    
    // Auto-dismiss
    "auto_dismiss": false,
    "dismiss_after_minutes": null,
    
    // Metadata
    "rule_id": "high_water_temp", // If triggered by rule
    "data": {                     // Additional context
        "current_value": 34,
        "threshold": 32,
        "pond_name": "Pond 1"
    },
    
    // Audit
    "created_by": "system",      // or user_key if manual
    "created_at": "2026-01-17T10:30:00Z",
    "updated_at": "2026-01-17T10:30:00Z"
}
```

---

## Usage Examples

### Example 1: Manual Alert Creation via REST API

```bash
curl -X POST http://localhost:5000/api/notification/alert/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Scheduled Maintenance",
    "message": "System maintenance scheduled for tonight 10 PM",
    "type": "info",
    "severity": "low",
    "source": "system"
  }'
```

### Example 2: Programmatic Alert from Service

```python
from fin_server.websocket.handlers.alert_handler import AlertHandler

# When water temperature is updated
def on_water_quality_update(pond_id, account_key, data):
    temperature = data.get('temperature')
    if temperature and temperature > 32:
        AlertHandler.create_pond_alert(
            account_key=account_key,
            pond_id=pond_id,
            title="High Water Temperature Alert",
            message=f"Water temperature is {temperature}°C",
            severity='high'
        )
```

### Example 3: WebSocket Client Handling

```javascript
// Connect to WebSocket
const socket = io('http://localhost:5000', {
    auth: { token: 'your_jwt_token' }
});

// Listen for new alerts
socket.on('alert:new', (alert) => {
    console.log('New alert:', alert);
    showAlertPopup(alert);
    updateAlertBadge();
});

// Listen for alert count updates
socket.on('alert:count', (data) => {
    document.getElementById('alertBadge').textContent = data.unacknowledged_count;
});

// Acknowledge an alert
function acknowledgeAlert(alertId) {
    socket.emit('alert:acknowledge', { alert_id: alertId }, (response) => {
        if (response.success) {
            console.log('Alert acknowledged');
        }
    });
}
```

---

## Testing Plan

1. **Unit Tests**
   - AlertHandler methods
   - Alert rules evaluation
   - EventEmitter alert functions

2. **Integration Tests**
   - REST API endpoints
   - WebSocket event delivery
   - Multi-user alert broadcast

3. **Manual Testing**
   - Use `test_websocket_alerts.html`
   - Test across multiple browser tabs
   - Test alert acknowledgment sync

---

## Next Steps

1. ✅ Plan created (this document)
2. ⏳ Register WebSocket alert handlers in hub.py
3. ⏳ Create alert rules service
4. ⏳ Create test HTML file for alerts
5. ⏳ Integrate triggers into pond/task services
6. ⏳ Update API documentation

Would you like me to proceed with the implementation?

