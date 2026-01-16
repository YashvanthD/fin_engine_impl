# Centralized WebSocket Architecture Plan

**Status: ✅ IMPLEMENTED**  
**Date: 2026-01-16**

## Implementation Summary

### Files Created
```
fin_server/websocket/
├── __init__.py                        # Module exports
├── event_emitter.py                   # Centralized event emitter
├── hub.py                             # WebSocket hub with event handlers
└── handlers/
    ├── __init__.py
    ├── notification_handler.py        # Create/emit notifications
    └── alert_handler.py               # Create/emit alerts
```

### Files Modified
- `server.py` - Initialize WebSocket hub
- `fin_server/routes/notification.py` - Integrated with WebSocket handlers
- `fin_server/routes/dashboard.py` - Deprecated alert endpoints
- `static/api_docs/api-constants.js` - Added WS_EVENTS constants

### How to Use

#### Backend: Emit notification/alert from any route
```python
from fin_server.websocket.handlers.notification_handler import NotificationHandler
from fin_server.websocket.handlers.alert_handler import AlertHandler

# Create notification (saves to DB + emits via WebSocket)
NotificationHandler.create_and_emit(
    account_key='acc_xxx',
    target_user_key='usr_xxx',
    title='New Task',
    message='You have a new task assigned'
)

# Create alert (saves to DB + emits to all account users)
AlertHandler.create_and_emit(
    account_key='acc_xxx',
    title='Low Oxygen',
    message='Oxygen in Pond A is below threshold',
    severity='critical'
)
```

#### Frontend: Connect to WebSocket
```javascript
import io from 'socket.io-client';

const socket = io('http://localhost:5000', {
  auth: { token: accessToken }
});

// Listen for notifications
socket.on('notification:new', (data) => {
  console.log('New notification:', data);
});

// Listen for alerts
socket.on('alert:new', (data) => {
  console.log('New alert:', data);
});
```

---

## Current State Analysis

### Existing Infrastructure
1. **Socket.IO Server** (`socket_server.py`) - Real-time messaging with:
   - User authentication via JWT
   - Multi-device support
   - Presence (online/offline)
   - Typing indicators
   - Read receipts
   - Group chats

2. **Notification Worker** (`worker.py`) - Background queue processing

3. **Messaging Repository** - MongoDB storage for conversations/messages

### Current Limitations
- Notifications use polling (HTTP GET every 30s)
- Alerts are not pushed in real-time
- No unified event system
- Chat and notifications are separate systems

---

## Proposed Architecture: Unified WebSocket Hub

```
┌─────────────────────────────────────────────────────────────────────┐
│                         UI CLIENT                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ Notification │  │    Chat      │  │   Alerts     │               │
│  │   Component  │  │  Component   │  │  Component   │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                 │                 │                        │
│         └─────────────────┼─────────────────┘                        │
│                           │                                          │
│                    ┌──────▼───────┐                                  │
│                    │  WebSocket   │                                  │
│                    │   Client     │                                  │
│                    └──────┬───────┘                                  │
└───────────────────────────┼──────────────────────────────────────────┘
                            │
                   WebSocket Connection
                            │
┌───────────────────────────▼──────────────────────────────────────────┐
│                     BACKEND SERVER                                    │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │              Centralized WebSocket Hub                       │     │
│  │                   (socket_hub.py)                            │     │
│  │                                                              │     │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │     │
│  │  │ Notification │ │    Chat      │ │    Alert     │         │     │
│  │  │   Handler    │ │   Handler    │ │   Handler    │         │     │
│  │  └──────────────┘ └──────────────┘ └──────────────┘         │     │
│  │                                                              │     │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │     │
│  │  │   Presence   │ │   Typing     │ │    Stream    │         │     │
│  │  │   Handler    │ │  Indicator   │ │   Handler    │         │     │
│  │  └──────────────┘ └──────────────┘ └──────────────┘         │     │
│  └─────────────────────────────────────────────────────────────┘     │
│                           │                                           │
│                           ▼                                           │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │                    Event Bus / Queue                         │     │
│  │                  (Redis PubSub / Memory)                     │     │
│  └─────────────────────────────────────────────────────────────┘     │
│                           │                                           │
│         ┌─────────────────┼─────────────────┐                        │
│         ▼                 ▼                 ▼                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ Notification │  │   Message    │  │    Alert     │               │
│  │  Repository  │  │  Repository  │  │  Repository  │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Event Types & Namespaces

### 1. Connection Events
```
connect                    - Client connected
disconnect                 - Client disconnected
error                      - Connection error
reconnect                  - Client reconnected
```

### 2. Notification Events (namespace: /notification)
```
notification:new           - New notification received
notification:read          - Notification marked as read
notification:read_all      - All notifications marked as read
notification:deleted       - Notification deleted
notification:count         - Unread count update
```

### 3. Alert Events (namespace: /alert)
```
alert:new                  - New alert created
alert:acknowledged         - Alert acknowledged
alert:deleted              - Alert deleted
alert:count                - Unacknowledged count update
```

### 4. Chat Events (Real-time Messaging)

**Important**: REST API is ONLY for initial data loading. All real-time communication uses WebSocket.

**REST API (Initial Load Only):**
- GET /api/chat/conversations - List conversations
- GET /api/chat/conversations/{id}/messages - Get message history (with pagination)
- GET /api/chat/search - Search messages
- GET /api/chat/unread - Get unread counts

**WebSocket Events (Real-time):**

#### Client -> Server Events:
```
chat:send                  - Send a new message
  Data: {
    conversationId: string,     // Required
    content: string,            // Message text
    type: string,               // 'text', 'image', 'file', etc.
    replyTo?: string,           // Message ID being replied to
    tempId?: string,            // Client-side temp ID for optimistic updates
    mediaUrl?: string,          // For media messages
    mentions?: string[]         // User keys mentioned
  }

chat:read                  - Mark messages as read
  Data: {
    conversationId?: string,    // Mark all in conversation
    messageId?: string          // Or mark specific message
  }

chat:delivered             - Mark message as delivered
  Data: {
    messageId: string
  }

chat:typing                - Typing indicator
  Data: {
    conversationId: string,
    isTyping: boolean
  }

chat:edit                  - Edit a message
  Data: {
    messageId: string,
    content: string
  }

chat:delete                - Delete a message
  Data: {
    messageId: string,
    forEveryone: boolean        // Delete for all or just self
  }

chat:conversation:create   - Create new conversation
  Data: {
    type: 'direct' | 'group',
    participants: string[],     // User keys
    name?: string               // For groups
  }

chat:conversation:join     - Join conversation room
  Data: {
    conversationId: string
  }
```

#### Server -> Client Events:
```
chat:message:sent          - Confirmation message was stored
  Data: {
    messageId: string,          // Server-generated ID
    conversationId: string,
    senderKey: string,
    content: string,
    type: string,
    status: 'sent',
    createdAt: string,          // ISO timestamp
    tempId: string              // Client's temp ID for matching
  }

chat:message               - New message received
  Data: { same as chat:message:sent }

chat:message:delivered     - Message was delivered to recipient
  Data: {
    messageId: string,
    deliveredTo: string,        // User key
    timestamp: string
  }

chat:message:read          - Message was read
  Data: {
    conversationId?: string,    // If bulk read
    messageId?: string,         // If single message
    readBy: string,
    timestamp: string
  }

chat:message:edited        - Message was edited
  Data: {
    messageId: string,
    content: string,
    editedAt: string
  }

chat:message:deleted       - Message was deleted
  Data: {
    messageId: string,
    deletedAt: string,
    forEveryone: boolean
  }

chat:typing:start          - User started typing
chat:typing:stop           - User stopped typing
  Data: {
    conversationId: string,
    userKey: string,
    timestamp: string
  }

chat:conversation:created  - New conversation created
  Data: {
    conversationId: string,
    type: string,
    participants: string[],
    name?: string,
    createdBy: string,
    createdAt: string
  }

chat:presence              - User presence changed
  Data: {
    userKey: string,
    status: 'online' | 'offline' | 'typing',
    timestamp: string
  }

chat:error                 - Error occurred
  Data: {
    code: string,               // Error code
    message: string,
    tempId?: string             // If related to a send attempt
  }
```

### 5. Presence Events (namespace: /presence)
```
presence:online            - User came online
presence:offline           - User went offline
presence:away              - User is away
presence:busy              - User is busy
```

### 6. Stream Events (namespace: /stream)
```
stream:data                - Generic data stream
stream:task_update         - Task status changed
stream:pond_update         - Pond data updated
stream:expense_update      - Expense status changed
```

---

## Implementation Plan

### Phase 1: Refactor Socket Hub (Week 1)

#### 1.1 Create Centralized Event Emitter
```python
# fin_server/websocket/event_emitter.py

class EventEmitter:
    """Centralized event emitter for all real-time events."""
    
    @staticmethod
    def emit_to_user(user_key: str, event: str, data: dict)
    
    @staticmethod
    def emit_to_account(account_key: str, event: str, data: dict)
    
    @staticmethod  
    def emit_to_room(room_id: str, event: str, data: dict)
    
    @staticmethod
    def broadcast(event: str, data: dict)
```

#### 1.2 Create Event Handlers
```
fin_server/websocket/
├── __init__.py
├── hub.py                 # Main WebSocket hub
├── event_emitter.py       # Centralized emitter
├── handlers/
│   ├── __init__.py
│   ├── notification_handler.py
│   ├── alert_handler.py
│   ├── chat_handler.py
│   ├── presence_handler.py
│   └── stream_handler.py
└── middleware/
    ├── __init__.py
    └── auth_middleware.py
```

### Phase 2: Integrate Notifications (Week 1-2)

#### 2.1 Push Notifications via WebSocket
When a notification is created via REST API, also emit via WebSocket:

```python
# In notification route - after creating notification
from fin_server.websocket.event_emitter import EventEmitter

# After saving to DB
EventEmitter.emit_to_user(target_user_key, 'notification:new', {
    'notification_id': notification_id,
    'title': title,
    'message': message,
    'type': notification_type,
    'created_at': created_at
})

# Also emit count update
EventEmitter.emit_to_user(target_user_key, 'notification:count', {
    'unread': get_unread_count(target_user_key)
})
```

### Phase 3: Integrate Alerts (Week 2)

#### 3.1 Push Alerts via WebSocket
```python
# After creating alert
EventEmitter.emit_to_account(account_key, 'alert:new', {
    'alert_id': alert_id,
    'title': title,
    'message': message,
    'severity': severity,
    'type': alert_type
})
```

### Phase 4: Real-time Data Streams (Week 3)

#### 4.1 Task Updates
```python
# When task status changes
EventEmitter.emit_to_account(account_key, 'stream:task_update', {
    'task_id': task_id,
    'status': new_status,
    'updated_by': user_key
})
```

#### 4.2 Pond Updates
```python
# When pond data changes
EventEmitter.emit_to_account(account_key, 'stream:pond_update', {
    'pond_id': pond_id,
    'field': 'oxygen_level',
    'value': 6.5,
    'timestamp': timestamp
})
```

---

## UI Client Implementation

### WebSocket Client Service

```javascript
// services/websocketService.js

class WebSocketService {
  constructor() {
    this.socket = null;
    this.listeners = new Map();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
  }

  connect(token) {
    this.socket = io(WS_URL, {
      auth: { token },
      transports: ['websocket'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    });

    this.setupEventHandlers();
  }

  setupEventHandlers() {
    // Connection events
    this.socket.on('connect', () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
    });

    this.socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
    });

    this.socket.on('error', (error) => {
      console.error('WebSocket error:', error);
    });

    // Forward all events to registered listeners
    this.socket.onAny((event, data) => {
      const callbacks = this.listeners.get(event) || [];
      callbacks.forEach(cb => cb(data));
    });
  }

  // Subscribe to an event
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
    
    return () => this.off(event, callback); // Return unsubscribe function
  }

  // Unsubscribe from an event
  off(event, callback) {
    const callbacks = this.listeners.get(event) || [];
    this.listeners.set(event, callbacks.filter(cb => cb !== callback));
  }

  // Emit an event
  emit(event, data) {
    if (this.socket?.connected) {
      this.socket.emit(event, data);
    }
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }
}

export const wsService = new WebSocketService();
export default wsService;
```

### React Hook for Notifications

```javascript
// hooks/useRealtimeNotifications.js

import { useState, useEffect } from 'react';
import wsService from '../services/websocketService';

export function useRealtimeNotifications() {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    // Subscribe to notification events
    const unsubNew = wsService.on('notification:new', (notification) => {
      setNotifications(prev => [notification, ...prev]);
      setUnreadCount(prev => prev + 1);
    });

    const unsubRead = wsService.on('notification:read', ({ notification_id }) => {
      setNotifications(prev => 
        prev.map(n => n.id === notification_id ? { ...n, read: true } : n)
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
    });

    const unsubCount = wsService.on('notification:count', ({ unread }) => {
      setUnreadCount(unread);
    });

    // Cleanup
    return () => {
      unsubNew();
      unsubRead();
      unsubCount();
    };
  }, []);

  return { notifications, unreadCount };
}
```

### React Hook for Alerts

```javascript
// hooks/useRealtimeAlerts.js

import { useState, useEffect } from 'react';
import wsService from '../services/websocketService';

export function useRealtimeAlerts() {
  const [alerts, setAlerts] = useState([]);
  const [unacknowledgedCount, setUnacknowledgedCount] = useState(0);

  useEffect(() => {
    const unsubNew = wsService.on('alert:new', (alert) => {
      setAlerts(prev => [alert, ...prev]);
      setUnacknowledgedCount(prev => prev + 1);
      
      // Show toast/notification
      showToast({
        type: alert.severity,
        title: alert.title,
        message: alert.message
      });
    });

    const unsubAck = wsService.on('alert:acknowledged', ({ alert_id }) => {
      setAlerts(prev => 
        prev.map(a => a.id === alert_id ? { ...a, acknowledged: true } : a)
      );
      setUnacknowledgedCount(prev => Math.max(0, prev - 1));
    });

    return () => {
      unsubNew();
      unsubAck();
    };
  }, []);

  return { alerts, unacknowledgedCount };
}
```

---

## File Changes Summary

### New Files to Create
```
fin_server/websocket/
├── __init__.py
├── hub.py
├── event_emitter.py
├── handlers/
│   ├── __init__.py
│   ├── notification_handler.py
│   ├── alert_handler.py
│   ├── chat_handler.py
│   ├── presence_handler.py
│   └── stream_handler.py
```

### Files to Modify
```
fin_server/routes/notification.py    - Add WebSocket emit after DB operations
fin_server/routes/task.py            - Add stream events
fin_server/routes/pond.py            - Add stream events
fin_server/messaging/socket_server.py - Integrate with new hub
server.py                            - Initialize WebSocket hub
```

---

## Migration Strategy

### Step 1: Create New WebSocket Hub (Non-breaking)
- Create new `websocket/` module
- Keep existing `messaging/socket_server.py` working
- New hub wraps existing functionality

### Step 2: Add Event Emitting to Routes (Non-breaking)
- Add `EventEmitter.emit_*()` calls to routes
- UI can optionally use WebSocket or continue polling
- Both methods work simultaneously

### Step 3: UI Migration
- Add WebSocket client service
- Replace polling with WebSocket subscriptions
- Keep polling as fallback

### Step 4: Deprecate Polling (Breaking)
- Mark polling endpoints as deprecated
- Remove polling from UI
- Optimize WebSocket-only flow

---

## Benefits

1. **Real-time Updates** - Instant notifications/alerts without polling
2. **Reduced Server Load** - No more constant HTTP polling
3. **Better UX** - Immediate feedback for all actions
4. **Unified System** - One connection for all real-time features
5. **Scalable** - Can add Redis PubSub for multi-server deployment
6. **Battery Friendly** - Less network requests on mobile

---

## Questions for Review

1. **Redis?** - Do we want Redis PubSub for horizontal scaling?
2. **Namespaces?** - Use Socket.IO namespaces or single namespace with event prefixes?
3. **Offline Queue?** - Queue events when user is offline and deliver on reconnect?
4. **Rate Limiting?** - Limit events per second to prevent flooding?
5. **Compression?** - Enable Socket.IO compression for large payloads?

---

## Timeline Estimate

| Phase | Task | Duration |
|-------|------|----------|
| 1 | Create WebSocket Hub & Event Emitter | 2-3 days |
| 2 | Integrate Notifications | 1-2 days |
| 3 | Integrate Alerts | 1 day |
| 4 | Integrate Chat (refactor existing) | 2-3 days |
| 5 | Add Stream Events (tasks, ponds) | 2-3 days |
| 6 | UI Client Implementation | 3-4 days |
| 7 | Testing & Bug Fixes | 2-3 days |
| **Total** | | **~2-3 weeks** |

