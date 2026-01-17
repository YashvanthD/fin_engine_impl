# Chat System Schema

## Overview

The chat system uses **5 MongoDB collections** stored in the `media_db` database:

| Collection | Purpose |
|------------|---------|
| `conversations` | Chat rooms (direct, group, broadcast) |
| `chat_messages` | Individual messages |
| `message_receipts` | Delivery/read receipts |
| `user_presence` | Online/offline status |
| `user_conversations` | Fast lookup: user → their conversations |

---

## 1. Conversations Collection

**Collection Name:** `conversations`

Stores chat conversations (1-on-1, groups, broadcasts).

### Schema

```javascript
{
  "_id": "conv_123456789",           // Same as conversation_id
  "conversation_id": "conv_123456789", // Unique conversation identifier
  "conversation_type": "direct",      // "direct" | "group" | "broadcast"
  
  // Participants
  "participants": [                   // Array of user_keys
    "184517846618",                   // User A's user_key
    "293847561234"                    // User B's user_key
  ],
  
  // Group-specific fields
  "name": null,                       // Group name (null for direct)
  "description": null,                // Group description
  "avatar_url": null,                 // Group avatar
  "admins": [],                       // Array of admin user_keys (for groups)
  "created_by": "184517846618",       // Who created the conversation
  
  // Last message preview (denormalized for performance)
  "last_message": {
    "message_id": "msg_xyz789",
    "sender_key": "184517846618",
    "content": "Hello!",              // First 100 chars
    "message_type": "text",
    "created_at": ISODate("2026-01-17T10:00:00Z")
  },
  
  // Timestamps
  "last_activity": ISODate("2026-01-17T10:00:00Z"),
  "created_at": ISODate("2026-01-17T09:00:00Z"),
  
  // User-specific settings (stored as arrays)
  "muted_by": [],                     // Users who muted this conversation
  "pinned_by": [],                    // Users who pinned this conversation
  "archived_by": [],                  // Users who archived this conversation
  
  // Unread counts per user
  "unread_counts": {
    "184517846618": 0,
    "293847561234": 5
  },
  
  // Multi-tenant
  "account_key": "241862723908",      // Account this conversation belongs to
  
  // Extra data
  "metadata": {}
}
```

### Indexes

```javascript
db.conversations.createIndex({ "conversation_id": 1 }, { unique: true })
db.conversations.createIndex({ "participants": 1 })
db.conversations.createIndex({ "account_key": 1 })
db.conversations.createIndex({ "last_activity": -1 })
db.conversations.createIndex({ "participants": 1, "conversation_type": 1, "account_key": 1 })
```

---

## 2. Chat Messages Collection

**Collection Name:** `chat_messages`

Stores individual chat messages.

### Schema

```javascript
{
  "_id": "msg_abc123",                // Same as message_id
  "message_id": "msg_abc123",         // Unique message identifier
  "conversation_id": "conv_123456789", // Parent conversation
  
  // Sender info
  "sender_key": "184517846618",       // Who sent the message
  "sender_info": {                    // Denormalized sender info (optional)
    "name": "John Doe",
    "avatar_url": "/avatars/john.jpg"
  },
  
  // Content
  "content": "Hello, how are you?",   // Message text
  "message_type": "text",             // "text" | "image" | "file" | "audio" | "video" | "system"
  
  // Media (for non-text messages)
  "media_url": null,                  // URL to media file
  "media_thumbnail": null,            // Thumbnail URL
  
  // Reply/Forward
  "reply_to": null,                   // message_id being replied to
  "forwarded_from": null,             // Original message_id if forwarded
  
  // Mentions
  "mentions": [],                     // Array of mentioned user_keys
  
  // Timestamps
  "created_at": ISODate("2026-01-17T10:00:00Z"),
  "edited_at": null,                  // Set when message is edited
  "deleted_at": null,                 // Set when message is deleted
  
  // Per-user deletion (for "delete for me")
  "deleted_for": [],                  // Users who deleted this message locally
  
  // Multi-tenant
  "account_key": "241862723908",
  
  // Extra data
  "metadata": {}
}
```

### Indexes

```javascript
db.chat_messages.createIndex({ "message_id": 1 }, { unique: true })
db.chat_messages.createIndex({ "conversation_id": 1, "created_at": -1 })
db.chat_messages.createIndex({ "sender_key": 1 })
db.chat_messages.createIndex({ "account_key": 1 })
db.chat_messages.createIndex({ "content": "text" })  // Text search
```

---

## 3. Message Receipts Collection

**Collection Name:** `message_receipts`

Tracks delivery and read status per user per message.

### Schema

```javascript
{
  "_id": ObjectId("..."),
  "message_id": "msg_abc123",         // Which message
  "conversation_id": "conv_123456789", // For efficient querying
  "user_key": "293847561234",         // Which user
  "status": "read",                   // "delivered" | "read"
  "delivered_at": ISODate("2026-01-17T10:00:01Z"),
  "read_at": ISODate("2026-01-17T10:00:05Z")
}
```

### Indexes

```javascript
db.message_receipts.createIndex({ "message_id": 1, "user_key": 1 }, { unique: true })
db.message_receipts.createIndex({ "conversation_id": 1, "user_key": 1 })
```

---

## 4. User Presence Collection

**Collection Name:** `user_presence`

Tracks online/offline/typing status.

### Schema

```javascript
{
  "_id": ObjectId("..."),
  "user_key": "184517846618",         // User identifier
  "status": "online",                 // "online" | "offline" | "away" | "busy" | "typing"
  "socket_id": "abc123xyz",           // Current WebSocket socket ID
  "typing_in": null,                  // conversation_id if currently typing
  "last_seen": ISODate("2026-01-17T10:00:00Z"),
  "device_info": {
    "user_agent": "Mozilla/5.0...",
    "ip": "192.168.1.1"
  }
}
```

### Indexes

```javascript
db.user_presence.createIndex({ "user_key": 1 }, { unique: true })
db.user_presence.createIndex({ "status": 1 })
```

---

## 5. User Conversations Collection (Fast Lookup)

**Collection Name:** `user_conversations`

Maps user_key to their conversation IDs for fast lookup. This is a denormalized collection that speeds up:
- Getting all conversations for a user
- Checking if a user is part of a conversation
- Storing per-user settings (muted, pinned, archived, unread count)

### Schema

```javascript
{
  "_id": "184517846618",              // Same as user_key
  "user_key": "184517846618",         // User identifier
  "conversations": [                   // Array of conversation entries
    {
      "conversation_id": "conv_123456789",
      "joined_at": ISODate("2026-01-17T09:00:00Z"),
      "is_muted": false,
      "is_pinned": true,              // Pinned conversations appear at top
      "is_archived": false,
      "last_read_at": ISODate("2026-01-17T10:00:00Z"),
      "unread_count": 5               // Messages since last_read_at
    },
    {
      "conversation_id": "conv_789012345",
      "joined_at": ISODate("2026-01-16T14:00:00Z"),
      "is_muted": true,
      "is_pinned": false,
      "is_archived": false,
      "last_read_at": null,
      "unread_count": 12
    }
  ],
  "created_at": ISODate("2026-01-15T08:00:00Z"),
  "updated_at": ISODate("2026-01-17T10:00:00Z")
}
```

### Indexes

```javascript
db.user_conversations.createIndex({ "user_key": 1 }, { unique: true })
db.user_conversations.createIndex({ "conversations.conversation_id": 1 })
```

### Usage

```javascript
// Get all conversation IDs for a user (fast)
db.user_conversations.findOne({ user_key: "184517846618" })

// Get total unread count
db.user_conversations.aggregate([
  { $match: { user_key: "184517846618" } },
  { $unwind: "$conversations" },
  { $group: { _id: null, total: { $sum: "$conversations.unread_count" } } }
])

// Update unread count when new message arrives
db.user_conversations.updateOne(
  { user_key: "184517846618", "conversations.conversation_id": "conv_123" },
  { $inc: { "conversations.$.unread_count": 1 } }
)

// Mark conversation as read
db.user_conversations.updateOne(
  { user_key: "184517846618", "conversations.conversation_id": "conv_123" },
  { $set: { 
      "conversations.$.unread_count": 0,
      "conversations.$.last_read_at": new Date()
    } 
  }
)
```

---

## WebSocket Event Flow

### Creating a Conversation

```
┌─────────┐                    ┌─────────┐                    ┌─────────┐
│ User A  │                    │ Server  │                    │ User B  │
└────┬────┘                    └────┬────┘                    └────┬────┘
     │                              │                              │
     │  chat:conversation:create    │                              │
     │  {type:"direct",             │                              │
     │   participants:["userB_key"]}│                              │
     │ ─────────────────────────────>                              │
     │                              │                              │
     │                              │  Creates conversation        │
     │                              │  in MongoDB                  │
     │                              │                              │
     │  chat:conversation:created   │                              │
     │  {conversationId:"conv_123"} │                              │
     │ <─────────────────────────────                              │
     │                              │                              │
     │                              │  chat:conversation:created   │
     │                              │  {conversationId:"conv_123"} │
     │                              │ ─────────────────────────────>
     │                              │                              │
```

### Sending a Message

```
┌─────────┐                    ┌─────────┐                    ┌─────────┐
│ User A  │                    │ Server  │                    │ User B  │
└────┬────┘                    └────┬────┘                    └────┬────┘
     │                              │                              │
     │  chat:send                   │                              │
     │  {conversationId:"conv_123", │                              │
     │   content:"Hello!",          │                              │
     │   tempId:"temp_001"}         │                              │
     │ ─────────────────────────────>                              │
     │                              │                              │
     │                              │  1. Validate conversation    │
     │                              │  2. Store in chat_messages   │
     │                              │  3. Update conversation      │
     │                              │     last_message             │
     │                              │                              │
     │  chat:message:sent           │                              │
     │  {messageId:"msg_xyz",       │                              │
     │   tempId:"temp_001"}         │                              │
     │ <─────────────────────────────                              │
     │                              │                              │
     │                              │  chat:message                │
     │                              │  {messageId:"msg_xyz",       │
     │                              │   content:"Hello!",          │
     │                              │   senderKey:"userA_key"}     │
     │                              │ ─────────────────────────────>
     │                              │                              │
     │                              │  (User B is online)          │
     │                              │  Mark as delivered           │
     │                              │                              │
     │  chat:message:delivered      │                              │
     │  {messageId:"msg_xyz",       │                              │
     │   deliveredTo:"userB_key"}   │                              │
     │ <─────────────────────────────                              │
     │                              │                              │
```

### Reading Messages

```
┌─────────┐                    ┌─────────┐                    ┌─────────┐
│ User A  │                    │ Server  │                    │ User B  │
└────┬────┘                    └────┬────┘                    └────┬────┘
     │                              │                              │
     │                              │  chat:read                   │
     │                              │  {conversationId:"conv_123"} │
     │                              │ <─────────────────────────────
     │                              │                              │
     │                              │  Update message_receipts     │
     │                              │                              │
     │  chat:message:read           │                              │
     │  {conversationId:"conv_123", │                              │
     │   readBy:"userB_key"}        │                              │
     │ <─────────────────────────────                              │
     │                              │                              │
```

---

## ID Generation

IDs are generated using the `generate_conversation_id()` and `generate_message_id()` functions:

```python
# From fin_server/utils/generator.py
def generate_conversation_id() -> str:
    return f"conv_{generate_unique_id()}"

def generate_message_id() -> str:
    return f"msg_{generate_unique_id()}"

def generate_unique_id() -> str:
    # Returns a unique numeric string like "575343248518"
    import time
    import random
    return str(int(time.time() * 1000) + random.randint(0, 999))
```

---

## Example Data

### Direct Conversation between User A and User B

**Conversation Document:**
```json
{
  "_id": "conv_575343248518",
  "conversation_id": "conv_575343248518",
  "conversation_type": "direct",
  "participants": ["184517846618", "293847561234"],
  "name": null,
  "created_by": "184517846618",
  "admins": [],
  "last_message": {
    "message_id": "msg_575343300123",
    "sender_key": "184517846618",
    "content": "Hello! How are you?",
    "message_type": "text",
    "created_at": "2026-01-17T10:00:00.000Z"
  },
  "last_activity": "2026-01-17T10:00:00.000Z",
  "created_at": "2026-01-17T09:55:00.000Z",
  "muted_by": [],
  "pinned_by": [],
  "archived_by": [],
  "account_key": "241862723908"
}
```

**Message Document:**
```json
{
  "_id": "msg_575343300123",
  "message_id": "msg_575343300123",
  "conversation_id": "conv_575343248518",
  "sender_key": "184517846618",
  "content": "Hello! How are you?",
  "message_type": "text",
  "reply_to": null,
  "media_url": null,
  "mentions": [],
  "created_at": "2026-01-17T10:00:00.000Z",
  "edited_at": null,
  "deleted_at": null,
  "account_key": "241862723908"
}
```

---

## Common Issues & Solutions

### Issue: "Conversation not found"

**Cause:** The conversation ID doesn't exist in the database.

**Debug Steps:**
1. Check if `chat:conversation:create` was called first
2. Check if the conversation was actually stored (check MongoDB)
3. Verify the `conversation_id` matches exactly

**MongoDB Debug Query:**
```javascript
// List all conversations
db.conversations.find({}).pretty()

// Find specific conversation
db.conversations.findOne({ conversation_id: "conv_575343248518" })

// Find conversations for a user
db.conversations.find({ participants: "184517846618" }).pretty()
```

### Issue: "User not a participant"

**Cause:** The user trying to send/read is not in the `participants` array.

**Solution:** Ensure both users are added to participants when creating the conversation.

### Issue: Collections are None

**Cause:** MongoDB connection not established or collections not initialized.

**Solution:** 
1. Ensure MongoDB is running
2. Check `get_collection()` is returning valid repositories
3. Check the database name in config

---

## REST API Endpoints (for initial load only)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/chat/conversations` | List user's conversations |
| GET | `/api/chat/conversations/{id}` | Get conversation details |
| GET | `/api/chat/conversations/{id}/messages` | Get message history |
| GET | `/api/chat/search?q=text` | Search messages |
| GET | `/api/chat/unread` | Get unread counts |
| GET | `/api/chat/presence?user_keys=a,b` | Get user presence |

**Note:** Do NOT use REST API to send messages. Always use WebSocket.

---

## WebSocket Events Summary

### Client → Server

| Event | Purpose | Required Data |
|-------|---------|---------------|
| `chat:conversation:create` | Create conversation | `{type, participants, name?}` |
| `chat:send` | Send message | `{conversationId, content, type?, tempId?}` |
| `chat:read` | Mark as read | `{conversationId}` or `{messageId}` |
| `chat:typing` | Typing indicator | `{conversationId, isTyping}` |
| `chat:edit` | Edit message | `{messageId, content}` |
| `chat:delete` | Delete message | `{messageId, forEveryone?}` |

### Server → Client

| Event | Purpose |
|-------|---------|
| `chat:conversation:created` | Conversation created |
| `chat:message:sent` | Your message was stored |
| `chat:message` | New message received |
| `chat:message:delivered` | Message delivered |
| `chat:message:read` | Message read |
| `chat:message:edited` | Message was edited |
| `chat:message:deleted` | Message was deleted |
| `chat:typing:start` | User started typing |
| `chat:typing:stop` | User stopped typing |
| `chat:error` | Error occurred |

