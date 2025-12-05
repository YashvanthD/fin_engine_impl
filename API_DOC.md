# TaskCircuit API Documentation (2025-12-05)

## Authentication
### POST /auth/signup
- Register a new admin/company (requires master password)
- **Fields:**
  - master_password (str, required)
  - company_name (str, required)
  - username (str, required)
  - password (str, required)
  - email (str, required)
- cURL:
```
curl -X POST http://localhost:5000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "master_password": "YOUR_MASTER_ADMIN_PASSWORD",
    "company_name": "TaskCircuit",
    "username": "adminuser",
    "password": "adminpassword",
    "email": "admin@example.com"
  }'
```

### POST /auth/login
- Login with username/password
- **Fields:**
  - username (str, required)
  - password (str, required)
- cURL:
```
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "adminuser",
    "password": "adminpassword"
  }'
```

### POST /auth/token
- Get new access token from refresh token
- **Fields:**
  - type (str, required, must be "refresh_token")
  - token (str, required, refresh_token)
- cURL:
```
curl -X POST http://localhost:5000/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "type": "refresh_token",
    "token": "REFRESH_TOKEN"
  }'
```

## Company
### POST /company/register
- Register a new company (admin only)
- **Fields:**
  - company_name (str, required)
  - description (str, optional)
  - pincode (str, optional)
  - number_of_employees (int, optional)
  - owner_user_key (str, required)
  - account_key (str, required)
- cURL:
```
curl -X POST http://localhost:5000/company/register \
  -H "Content-Type: application/json" \
  -d '{ ...company fields... }'
```

### PUT /company/update
- Update company info (admin only)
- **Fields:**
  - Any updatable company field (see above)
- cURL:
```
curl -X PUT http://localhost:5000/company/update \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ ...fields to update... }'
```

### GET /company/<account_key>
- Get public company info
- **Fields Returned:**
  - company_name
  - created_date
  - owner_user_key
  - worker_count
  - account_key
- cURL:
```
curl -X GET http://localhost:5000/company/<account_key>
```

## User
### POST /auth/account/<account_key>/signup
- Register a user under a company (admin only)
- **Fields:**
  - username (str, required)
  - password (str, required)
  - email (str, required)
  - role (str, required)
  - account_key (str, required)
- cURL:
```
curl -X POST http://localhost:5000/auth/account/<account_key>/signup \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ ...user fields... }'
```

## Fish
### POST /fish/
- Add a fish record
- **Fields:**
  - common_name (str, required)
  - scientific_name (str, required)
  - species_code (str, required)
  - count (int, required)
  - length (float, required)
  - weight (float, required)
  - account_key (str, required)
  - [Any additional dynamic fields]
- cURL:
```
curl -X POST http://localhost:5000/fish/ \
  -H "Content-Type: application/json" \
  -d '{
    "common_name": "Catfish",
    "scientific_name": "Siluriformes",
    "species_code": "CF001",
    "count": 10,
    "length": 25.5,
    "weight": 2.3,
    "account_key": "ACC123"
  }'
```

### GET /fish/?account_key=xxx
- List all fish for an account
- **Fields Required:**
  - account_key (str, required, as query param)
- cURL:
```
curl -X GET "http://localhost:5000/fish/?account_key=ACC123"
```

### GET /fish/<fish_id>
- Get fish details
- **Fields Returned:**
  - All fish fields
- cURL:
```
curl -X GET http://localhost:5000/fish/<fish_id>
```

### PUT /fish/<fish_id>
- Update fish
- **Fields:**
  - Any updatable fish field
- cURL:
```
curl -X PUT http://localhost:5000/fish/<fish_id> \
  -H "Content-Type: application/json" \
  -d '{ ...fields... }'
```

### DELETE /fish/<fish_id>
- Delete fish
- cURL:
```
curl -X DELETE http://localhost:5000/fish/<fish_id>
```

## Pond
### POST /pond/
- Create a pond (requires auth)
- **Fields:**
  - pond_name (str, required)
  - location (str, required)
  - size (str, required)
  - water_type (str, required)
  - account_key (str, required)
  - [Any additional dynamic fields]
- cURL:
```
curl -X POST http://localhost:5000/pond/ \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "pond_name": "Main Pond",
    "location": "Farm 1",
    "size": "Large",
    "water_type": "Freshwater",
    "account_key": "ACC123"
  }'
```

### GET /pond/?account_key=xxx
- List ponds for an account
- **Fields Required:**
  - account_key (str, required, as query param)
- cURL:
```
curl -X GET "http://localhost:5000/pond/?account_key=ACC123" \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

### GET /pond/<pond_id>
- Get pond details, events, analytics
- **Fields Returned:**
  - pond (all fields)
  - events (list)
  - analytics (object)
- cURL:
```
curl -X GET http://localhost:5000/pond/<pond_id> \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

### PUT /pond/<pond_id>
- Update pond
- **Fields:**
  - Any updatable pond field
- cURL:
```
curl -X PUT http://localhost:5000/pond/<pond_id> \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ ...fields... }'
```

### DELETE /pond/<pond_id>
- Delete pond
- cURL:
```
curl -X DELETE http://localhost:5000/pond/<pond_id> \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

### POST /pond/<pond_id>/event
- Add fish event to pond
- **Fields:**
  - fish_id (str, required)
  - action (str, required, "add" or "remove")
  - count (int, required)
  - date (str, required)
- cURL:
```
curl -X POST http://localhost:5000/pond/<pond_id>/event \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "fish_id": "FISH123",
    "action": "add",
    "count": 10,
    "date": "2025-12-05"
  }'
```

### GET /pond/<pond_id>/events
- List all events for pond
- cURL:
```
curl -X GET http://localhost:5000/pond/<pond_id>/events \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

## Messaging & Notification (Socket.io)
- Connect with JWT token (access_token or refresh_token)
- **Fields:**
  - Authorization header: Bearer ACCESS_TOKEN or Bearer REFRESH_TOKEN
- JS Example:
```js
const socket = io("http://localhost:5000", {
  extraHeaders: {
    Authorization: "Bearer ACCESS_TOKEN_OR_REFRESH_TOKEN"
  }
});
```
- Events:
  - `send_message`: `{ to_user_key, message, from_user_key }`
  - `broadcast_notification`: `{ account_key, notification, from_user_key, user_keys? }`
  - `receive_message`, `receive_notification`: delivered to client
- All notifications/messages are persisted and delivered to online/offline users.

## Error Handling
- All APIs return `{ success: false, error: "..." }` for errors.
- Auth required for protected endpoints (401 Unauthorized if missing/invalid).

---
For more details, see each endpoint's request/response format above. All endpoints use JSON. Authentication is via Bearer token in `Authorization` header where required.