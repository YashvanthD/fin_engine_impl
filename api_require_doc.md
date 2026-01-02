# API Requirements for AquaFarm Pro (Frontend Integration)

This document lists all backend endpoints the frontend calls, the expected request/response shapes, headers/auth rules, validation notes, and concrete example requests/responses you can hand to backend engineers.

Base URL (development)
- http://localhost:5000/api

Auth / Tokens
- Access token header: `Authorization: Bearer <accessToken>`
- Frontend stores tokens in AsyncStorage keys:
  - `auth_token` => access token
  - `refresh_token` => refresh token
  - `user_data` => serialized user object
- Typical response envelope used by frontend (ApiResponse):
  {
    "success": boolean,
    "data": any,
    "error": string (optional),
    "timestamp": string (optional)
  }

General rules
- All POST/PATCH requests with body use `Content-Type: application/json`.
- All endpoints except `/auth/login`, `/auth/signup`, `/auth/refresh` require Authorization header.
- When a request fails, return HTTP status code != 200 and a JSON body like `{ "message": "error description" }` (apiService reads `errorData.message`). Also returning ApiResponse with success=false and error field is OK.
- IDs: frontend accepts `id` or `_id`. Please return `_id` (MongoDB) and also include `id` (string) if convenient.

Index of endpoints
- Authentication
  - POST /auth/login
  - POST /auth/signup
  - POST /auth/logout
  - POST /auth/me
  - POST /auth/refresh

- Ponds
  - GET /ponds
  - POST /ponds
  - GET /ponds/:id
  - PATCH /ponds/:id
  - DELETE /ponds/:id

- Schedules / Tasks
  - GET /schedules
  - POST /schedules
  - PATCH /schedules/:id
  - DELETE /schedules/:id

- Feeding
  - POST /feeding
  - GET /feeding
  - GET /feeding/pond/:id

- Sampling
  - POST /sampling
  - GET /sampling/:pondId

- Dashboard & Alerts
  - GET /dashboard
  - (optional) GET /alerts
  - (optional) PUT /alerts/:id/acknowledge

- Users
  - GET /users
  - GET /users/:id
  - POST /users
  - PATCH /users/:id
  - DELETE /users/:id

- Water quality and growth records (recommended)
  - GET /water-quality?pondId=:pondId
  - POST /water-quality
  - GET /growth-records?pondId=:pondId

Detailed endpoint specifications

---

## Authentication

### POST /auth/login
- Purpose: Authenticate user and return tokens and user object
- Headers: Content-Type: application/json
- Body (JSON):
  - email: string (required)
  - password: string (required)

- Success response (200):
{
  "success": true,
  "data": {
    "accessToken": "<jwt-access-token>",
    "refreshToken": "<jwt-refresh-token>",
    "user": {
      "id": "user-123",
      "email": "admin@...",
      "name": "Admin",
      "role": "admin",
      "phone": "...",
      "avatar": "...",
      "permissions": ["..."],
      "createdAt": "<iso>",
      "lastLogin": "<iso>",
      "managerId": "..."
    }
  }
}

- Failure (401/400):
  - HTTP 401 with body `{ "message": "Invalid credentials" }`
  - Or `{"success": false, "error": "Invalid credentials"}`

- Example request body:
```json
{ "email": "admin@fishfarm.com", "password": "admin123" }
```

- Example success response (condensed):
```json
{
  "success": true,
  "data": {
    "accessToken": "eyJhbGci...",
    "refreshToken": "rftoken...",
    "user": { "id": "u1", "email": "admin@fishfarm.com", "name": "Admin", "role": "admin" }
  }
}
```

---

### POST /auth/signup
- Purpose: create new user
- Headers: Content-Type: application/json
- Body:
  - name: string (required)
  - email: string (required)
  - password: string (required)
  - role?: string (optional)

- Success response: `ApiResponse.data` contains created `User` object.

- Example body:
```json
{
  "name": "New Staff",
  "email": "staff@fishfarm.com",
  "password": "staff123",
  "role": "staff"
}
```

---

### POST /auth/logout
- Purpose: invalidate refresh token server-side and clear client tokens
- Headers: Authorization: Bearer <accessToken>, Content-Type: application/json
- Body:
  - refreshToken: string (optional but frontend sends it)

- Success response: `{ "success": true }`
- After this, frontend removes auth_token, refresh_token, user_data from storage.

---

### POST /auth/me
- Purpose: return user info (refresh or validate current user)
- Headers: Authorization: Bearer <accessToken>, Content-Type: application/json
- Body: optional; frontend sends stored user object `{ user: {...} }`
- Response: `ApiResponse.data` should be the user object or wrapper containing user.

---

### POST /auth/refresh
- Purpose: exchange refresh token for new access token (and optionally new refresh token)
- Headers: Content-Type: application/json
- Body:
  - refreshToken: string (required)
- Response:
  - `data: { accessToken: string, refreshToken?: string }`
- Error: 401 if refreshToken invalid

---

## Ponds

### GET /ponds
- Purpose: return list of ponds
- Headers: Authorization
- Query params: none
- Response: `ApiResponse.data` = array of `Pond` objects

Pond object (recommended canonical shape):
```json
{
  "id": "pond-123",
  "_id": "...optional...",
  "name": "Tilapia Pond A1",
  "dimensions": { "length": 50, "width": 25, "depth": 2.5 },
  "volume": 3125,
  "type": "concrete",
  "location": { "latitude": 6.5244, "longitude": 3.3792 },
  "currentStock": [],
  "waterQuality": [],
  "photos": [],
  "createdAt": "<iso>",
  "lastMaintenance": "<iso>",
  "status": "active"
}
```

---

### POST /ponds
- Purpose: create a pond
- Headers: Authorization
- Body (JSON):
  - name: string (required)
  - dimensions: { length: number, width: number, depth: number } (required)
  - location: { latitude: number, longitude: number } (required)
  - type?: 'concrete'|'earthen'|'Plastic'
  - volume?: number
  - currentStock?: array
  - photos?: string[]
  - lastMaintenance?: string (ISO)
  - status?: string
- Response: ApiResponse.data = created Pond (with id)

- Example body (frontend CreatePondModal sends):
```json
{
  "name": "Tilapia Pond A1",
  "dimensions": { "length": 50, "width": 25, "depth": 2.5 },
  "volume": 3125,
  "type": "concrete",
  "location": { "latitude": 6.5244, "longitude": 3.3792 },
  "currentStock": [],
  "waterQuality": [],
  "photos": [],
  "lastMaintenance": "2025-12-21T12:00:00.000Z",
  "status": "active"
}
```

---

### GET /ponds/:id
- Purpose: get pond by ID
- Headers: Authorization
- Response: ApiResponse.data = Pond

---

### PATCH /ponds/:id
- Purpose: update pond fields
- Headers: Authorization
- Body: partial Pond object (only fields to update)
- Response: ApiResponse.data = updated Pond

---

### DELETE /ponds/:id
- Purpose: delete pond
- Headers: Authorization
- Response: ApiResponse.success = true

---

## Schedules / Tasks
Frontend uses `/schedules` path. The Task type is in `app/types/index.ts`.

Task (frontend) highlights:
- id/_id?: string
- title: string
- description?: string
- type?: 'feeding'|'maintenance'|'sampling'|'cleaning'|'monitoring'
- taskType?: 'Feeding'|'Sampling'|'Preparation'|'Cleaning' (backend friendly)
- pondId?: string
- assignedTo?: string
- status?: 'pending'|'in-progress'|'done'|'completed'|'overdue'
- priority?: 'low'|'medium'|'high'|'critical'
- scheduledDate?: string
- startTime?: string
- endTime?: string
- estimatedDuration?: number
- recurring?: { frequency: 'daily'|'weekly'|'monthly' }


### GET /schedules
- Purpose: list schedules
- Headers: Authorization
- Query params (optional): pondId, assignedTo, status
- Response: ApiResponse.data = Task[]

---

### POST /schedules
- Purpose: create schedule/task
- Headers: Authorization
- Body (apiService constructs `scheduleData`):
  - pondId?: string
  - taskType: string (mapped from frontend `type`, e.g. 'Feeding')
  - title: string
  - description?: string
  - assignedTo?: string
  - startTime?: string (ISO)
  - endTime?: string (ISO)
  - status?: string
  - priority?: string
  - estimatedDuration?: number
  - recurring?: object
- Response: ApiResponse.data = created Task

- Example body (from CreateTaskModal mapping):
```json
{
  "pondId": "pond-123",
  "taskType": "Feeding",
  "title": "Morning Feeding - Tilapia Pond A1",
  "description": "Feed with pellets",
  "assignedTo": "staff-001",
  "startTime": "2025-12-22T08:00:00.000Z",
  "endTime": "2025-12-22T08:30:00.000Z",
  "status": "pending",
  "priority": "medium",
  "estimatedDuration": 30,
  "recurring": { "frequency": "daily" }
}
```

---

### PATCH /schedules/:id
- Purpose: update task/schedule
- Headers: Authorization
- Body: partial fields to update
- Response: ApiResponse.data = updated Task

---

### DELETE /schedules/:id
- Purpose: delete schedule
- Headers: Authorization
- Response: ApiResponse.success = true

---

## Feeding
Frontend expects `/feeding` endpoints (apiService). mockApiService used `/feeding-records` in some places — prefer `/feeding` for real backend.

### POST /feeding
- Purpose: record feeding event
- Headers: Authorization, Content-Type: application/json
- Body:
  - pondId: string (required)
  - date?: string (ISO)
  - feedType: string (required)
  - feedQuantity: number (required) — units: kg (frontend input labeled kg)
  - dfr?: number
  - scheduleId?: string
  - remarks?: string
- Response: ApiResponse.data = created feeding record (shape flexible, but recommended `FeedingRecord`):

FeedingRecord recommended shape:
```json
{
  "id": "feed-123",
  "pondId": "pond-123",
  "feedType": "Pellets",
  "quantity": 12.5,
  "feedingTime": "2025-12-21T10:00:00.000Z",
  "waterTemperature": 27.5,
  "fishBehavior": "active",
  "recordedBy": "staff-001",
  "notes": "..."
}
```

- Example request body used by app/feed.tsx:
```json
{
  "pondId": "pond-123",
  "feedType": "Pellets",
  "feedQuantity": 5.25,
  "remarks": "Evening feeding",
  "date": "2025-12-21T18:00:00.000Z"
}
```

---

### GET /feeding
- Purpose: list feeding records
- Headers: Authorization
- Response: ApiResponse.data = FeedingRecord[]

---

### GET /feeding/pond/:id
- Purpose: feeding records filtered by pond
- Headers: Authorization
- Response: ApiResponse.data = FeedingRecord[]

---

## Sampling

### POST /sampling
- Purpose: record sampling / growth data
- Headers: Authorization, Content-Type: application/json
- Body (apiService.recordSampling):
  - pondId: string (required)
  - createdBy?: string
  - date?: string (ISO)
  - sampleCount: number (required)
  - avgWeight: number (required) — grams
  - mortality?: number
  - dfr?: number
  - scheduleId?: string
  - remarks?: string
- Response: ApiResponse.data = created sampling record

- Example body (frontend expected):
```json
{
  "pondId": "pond-123",
  "createdBy": "staff-001",
  "date": "2025-12-21T09:00:00.000Z",
  "sampleCount": 5,
  "avgWeight": 80.5,
  "mortality": 0,
  "dfr": 1.1,
  "remarks": "Samples near inlet"
}
```

---

### GET /sampling/:pondId
- Purpose: list sampling records for pond
- Headers: Authorization
- Response: ApiResponse.data = array of sampling records

---

## Dashboard & Alerts

### GET /dashboard
- Purpose: top-level dashboard data (cards, alerts, charts)
- Headers: Authorization
- Response: ApiResponse.data = object with dashboard contents.
- apiService expects either `data.cards` or `data` to contain:
  - totalPonds: number
  - activeTasks: number
  - criticalAlerts: number
  - averageGrowthRate: number
  - totalStock: number
  - feedEfficiency: number
  - alerts: Alert[] (optional)

- Example response (condensed):
```json
{
  "success": true,
  "data": {
    "cards": {
      "totalPonds": 12,
      "activeTasks": 5,
      "criticalAlerts": 1,
      "averageGrowthRate": 2.3,
      "totalStock": 5400,
      "feedEfficiency": 1.8
    },
    "alerts": [ /* array of Alert objects */ ]
  }
}
```

---

### GET /alerts (optional) or alerts inside dashboard data
- Purpose: return alert list
- Response: ApiResponse.data = Alert[]

### PUT /alerts/:id/acknowledge (recommended)
- Purpose: mark alert acknowledged
- Headers: Authorization, Content-Type: application/json
- Body: { "userId": "staff-001" }
- Response: ApiResponse.data = updated Alert

Alert type (from frontend types):
```json
{
  "id": "alert-1",
  "type": "water_quality",
  "severity": "warning",
  "title": "Low DO",
  "message": "Dissolved oxygen below threshold",
  "pondId": "pond-123",
  "timestamp": "2025-12-21T11:00:00.000Z",
  "acknowledged": false
}
```

---

## Users

### GET /users
- Purpose: list users
- Headers: Authorization
- Response: ApiResponse.data = User[]

### GET /users/:id
- Purpose: get specific user
- Headers: Authorization
- Response: ApiResponse.data = User

### POST /users
- Purpose: create a new user (admin only in many deployments)
- Headers: Authorization
- Body: { name, email, password, role, managerId?, phone? }
- Response: ApiResponse.data = created User

### PATCH /users/:id
- Purpose: update user
- Headers: Authorization
- Body: partial user fields
- Response: ApiResponse.data = updated User

### DELETE /users/:id
- Purpose: delete user
- Headers: Authorization
- Response: ApiResponse.success = true

---

## Water quality & Growth records (recommended)
- GET /water-quality?pondId=:pondId
- POST /water-quality
- GET /growth-records?pondId=:pondId

WaterQualityRecord and GrowthRecord shapes are defined in frontend `app/types/index.ts`. Ensure backend returns compatible fields.

---

## Error handling guidance
- On validation or auth error return appropriate HTTP status code (400, 401, 403, 404, 500) and JSON body.
- Two acceptable formats consumed by frontend:
  1. Short error object used in handleResponse: `{ "message": "User not found" }` (handleResponse looks for `errorData.message`)
  2. ApiResponse wrapper: `{ "success": false, "error": "User not found" }`
- Prefer returning both HTTP status plus a meaningful JSON message.

---

## Example curl snippets
(Replace `{{API}}` with `http://localhost:5000/api` and `{{TOKEN}}` with a valid access token.)

Login:
```bash
curl -X POST "{{API}}/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@fishfarm.com","password":"admin123"}'
```

Create pond (requires token):
```bash
curl -X POST "{{API}}/ponds" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {{TOKEN}}" \
  -d '{"name":"Tilapia Pond A1","dimensions":{"length":50,"width":25,"depth":2.5},"location":{"latitude":6.5244,"longitude":3.3792},"type":"concrete"}'
```

Create task / schedule:
```bash
curl -X POST "{{API}}/schedules" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {{TOKEN}}" \
  -d '{"pondId":"pond-123","taskType":"Feeding","title":"Morning Feeding","description":"Pellets","assignedTo":"staff-001","startTime":"2025-12-22T08:00:00.000Z","endTime":"2025-12-22T08:30:00.000Z","status":"pending","priority":"medium"}'
```

Record feeding:
```bash
curl -X POST "{{API}}/feeding" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {{TOKEN}}" \
  -d '{"pondId":"pond-123","date":"2025-12-21T18:00:00.000Z","feedType":"Pellets","feedQuantity":5.25,"remarks":"Evening feeding"}'
```

Record sampling:
```bash
curl -X POST "{{API}}/sampling" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {{TOKEN}}" \
  -d '{"pondId":"pond-123","createdBy":"staff-001","date":"2025-12-21T09:00:00.000Z","sampleCount":5,"avgWeight":80.5,"mortality":0}'
```

---

## Implementation notes & recommendations for backend devs
1. Return consistent `ApiResponse` envelope where possible. The frontend is tolerant of either nested `.data.cards` or plain `.data` for dashboard and will attempt to parse both.
2. Support query params on `/schedules` (pondId, assignedTo, status) to allow filtered lists.
3. Make sure CORS is enabled for the Expo app origin and that the mobile device/emulator can reach `localhost:5000` (use `10.0.2.2` for Android emulator).
4. When using MongoDB, include both `_id` and `id` string in responses, or map `_id` -> `id` for frontend convenience.
5. Implement token refresh endpoint `/auth/refresh` to support refresh flow; return new access token and optionally new refresh token.
6. For critical write endpoints (create feeding/sampling), validate numeric types (feedQuantity numeric, avgWeight numeric) and required fields.

---

## Example responses (full-like)

Successful pond list response:
```json
{
  "success": true,
  "data": [
    {
      "id": "pond-123",
      "name": "Tilapia Pond A1",
      "dimensions": { "length": 50, "width": 25, "depth": 2.5 },
      "volume": 3125,
      "type": "concrete",
      "location": { "latitude": 6.5244, "longitude": 3.3792 },
      "currentStock": [],
      "createdAt": "2025-10-01T10:00:00.000Z",
      "status": "active"
    }
  ]
}
```

Auth failure example:
```json
HTTP/1.1 401 Unauthorized
{ "message": "Invalid email or password" }
```

---

If you want, I can also:
- produce an OpenAPI 3.0 (YAML or JSON) file from this spec,
- create a Postman collection / sample tests,
- or scaffold a small Express server with route stubs that satisfy the frontend (useful for backend devs to implement logic).

Tell me which next artifact you'd like and I'll generate it.

