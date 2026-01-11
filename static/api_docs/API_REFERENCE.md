# Fin Engine API Documentation

Complete API reference for the Fin Engine fish farming management platform.

**Base URL:** `http://localhost:5000`  
**Version:** 1.0.0  
**Last Updated:** January 11, 2026

---

## Table of Contents

1. [Authentication](#authentication)
2. [User Management](#user-management)
3. [Company Management](#company-management)
4. [Fish Management](#fish-management)
5. [Pond Management](#pond-management)
6. [Feeding & Sampling](#feeding--sampling)
7. [Expenses & Transactions](#expenses--transactions)
8. [AI Services (OpenAI)](#ai-services-openai)
9. [MCP (Model Context Protocol)](#mcp-model-context-protocol)
10. [Error Handling](#error-handling)

---

## Authentication

All protected endpoints require a JWT token in the Authorization header:
```
Authorization: Bearer <token>
```

### POST /auth/register
Register a new user account.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "name": "John Doe",
  "phone": "+1234567890",
  "master_password": "server_master_password"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "user_key": "usr_abc123",
    "account_key": "acc_xyz789",
    "email": "user@example.com",
    "access_token": "eyJ...",
    "refresh_token": "eyJ..."
  }
}
```

### POST /auth/login
Authenticate user and get tokens.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "user_key": "usr_abc123",
    "account_key": "acc_xyz789",
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "expires_in": 604800
  }
}
```

### POST /auth/refresh
Refresh access token using refresh token.

**Request Body:**
```json
{
  "refresh_token": "eyJ..."
}
```

### POST /auth/logout
Logout and invalidate tokens.

**Headers:** `Authorization: Bearer <token>`

### GET /auth/me
Get current authenticated user info.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "success": true,
  "data": {
    "user_key": "usr_abc123",
    "account_key": "acc_xyz789",
    "email": "user@example.com",
    "name": "John Doe",
    "role": "admin"
  }
}
```

---

## User Management

### GET /user/profile
Get user profile.

### PUT /user/profile
Update user profile.

**Request Body:**
```json
{
  "name": "John Doe",
  "phone": "+1234567890",
  "avatar_url": "https://..."
}
```

### PUT /user/password
Change password.

**Request Body:**
```json
{
  "current_password": "oldpassword",
  "new_password": "newpassword"
}
```

---

## Company Management

### POST /company/register
Register a new company.

**Request Body:**
```json
{
  "company_name": "Fish Farm Co.",
  "address": "123 Farm Road",
  "phone": "+1234567890",
  "email": "contact@fishfarm.com",
  "admin_email": "admin@fishfarm.com",
  "admin_password": "securepassword",
  "admin_name": "Admin User",
  "master_password": "server_master_password"
}
```

### GET /company
Get company details.

### PUT /company
Update company details.

### GET /company/employees
List company employees.

### POST /company/employees
Add employee to company.

**Request Body:**
```json
{
  "email": "employee@fishfarm.com",
  "password": "temppassword",
  "name": "Employee Name",
  "role": "staff"
}
```

### DELETE /company/employees/{user_key}
Remove employee from company.

---

## Fish Management

### GET /fish
List all fish species for the account.

**Query Parameters:**
- `include_analytics` (boolean): Include growth analytics

**Response:**
```json
{
  "success": true,
  "data": {
    "fish": [
      {
        "species_code": "TILAPIA_NILE",
        "common_name": "Nile Tilapia",
        "scientific_name": "Oreochromis niloticus",
        "analytics": {...}
      }
    ]
  }
}
```

### POST /fish
Add a new fish species.

**Request Body:**
```json
{
  "species_code": "TILAPIA_NILE",
  "common_name": "Nile Tilapia",
  "scientific_name": "Oreochromis niloticus",
  "description": "Common freshwater fish"
}
```

### GET /fish/{species_code}
Get fish species details.

### PUT /fish/{species_code}
Update fish species.

### DELETE /fish/{species_code}
Remove fish species.

### GET /fish/{species_code}/analytics
Get growth analytics for species.

---

## Pond Management

### GET /pond
List all ponds.

**Response:**
```json
{
  "success": true,
  "data": {
    "ponds": [
      {
        "pond_id": "pond_001",
        "name": "Pond A",
        "size": 1000,
        "size_unit": "sqm",
        "location": "North Section",
        "status": "active"
      }
    ]
  }
}
```

### POST /pond
Create a new pond.

**Request Body:**
```json
{
  "name": "Pond A",
  "size": 1000,
  "size_unit": "sqm",
  "location": "North Section",
  "depth": 2.5,
  "water_source": "well"
}
```

### GET /pond/{pond_id}
Get pond details.

### PUT /pond/{pond_id}
Update pond.

### DELETE /pond/{pond_id}
Delete pond.

### POST /pond/{pond_id}/stock
Add fish stock to pond.

**Request Body:**
```json
{
  "species_code": "TILAPIA_NILE",
  "count": 5000,
  "avg_weight": 10,
  "source": "Hatchery A",
  "stock_date": "2026-01-10"
}
```

### POST /pond/{pond_id}/harvest
Record harvest from pond.

---

## Feeding & Sampling

### GET /feeding
List feeding records.

**Query Parameters:**
- `pond_id`: Filter by pond
- `start_date`: Start date (ISO format)
- `end_date`: End date (ISO format)
- `limit`: Max records (default: 50)

### POST /feeding
Record feeding.

**Request Body:**
```json
{
  "pond_id": "pond_001",
  "feed_type": "pellet",
  "quantity": 50,
  "unit": "kg",
  "feeding_time": "2026-01-10T08:00:00Z",
  "notes": "Morning feeding"
}
```

### GET /sampling
List water quality samples.

### POST /sampling
Record water quality sample.

**Request Body:**
```json
{
  "pond_id": "pond_001",
  "temperature": 28.5,
  "ph": 7.2,
  "dissolved_oxygen": 6.5,
  "ammonia": 0.02,
  "nitrite": 0.01,
  "sample_date": "2026-01-10T10:00:00Z"
}
```

---

## Expenses & Transactions

### GET /expenses
List expenses.

**Query Parameters:**
- `category`: Filter by category
- `start_date`: Start date
- `end_date`: End date
- `limit`: Max records

### POST /expenses
Create expense record.

**Request Body:**
```json
{
  "category": "feed",
  "amount": 5000,
  "description": "Fish feed purchase",
  "date": "2026-01-10",
  "pond_id": "pond_001",
  "vendor": "Feed Supplier Inc."
}
```

### GET /expenses/{expense_id}
Get expense details.

### PUT /expenses/{expense_id}
Update expense.

### DELETE /expenses/{expense_id}
Delete expense.

### GET /expenses/summary
Get expense summary by category.

### GET /transactions
List all transactions.

### POST /transactions
Create transaction.

---

## AI Services (OpenAI)

### GET /ai/openai/health
Check if OpenAI service is configured.

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "ok",
    "configured": true,
    "model": "gpt-4o-mini"
  }
}
```

### GET /ai/openai/models
List available OpenAI models.

### POST /ai/openai/query
Send a query to OpenAI. **Supports optional image input for vision.**

**Request Body (JSON):**
```json
{
  "prompt": "What is the best feeding schedule for tilapia?",
  "model": "gpt-4o-mini",
  "max_tokens": 1000,
  "temperature": 0.7,
  "system_prompt": "You are a fish farming expert.",
  "image_url": "https://example.com/fish.jpg",
  "image_base64": "base64_encoded_data",
  "detail": "auto"
}
```

**OR Multipart Form Data (for file upload):**
- `prompt` (required): Your question
- `image` (optional): Image file
- `model` (optional): Model name
- `system_prompt` (optional): System context
- `max_tokens` (optional): Max response tokens
- `temperature` (optional): Creativity (0-2)
- `detail` (optional): Image detail level ("low", "high", "auto")

**Response:**
```json
{
  "success": true,
  "data": {
    "response": "For tilapia, I recommend...",
    "model": "gpt-4o-mini",
    "usage": {
      "prompt_tokens": 150,
      "completion_tokens": 200,
      "total_tokens": 350
    },
    "finish_reason": "stop"
  }
}
```

### POST /ai/openai/chat
Multi-turn chat conversation.

**Request Body:**
```json
{
  "messages": [
    {"role": "system", "content": "You are a fish farming expert."},
    {"role": "user", "content": "What causes ammonia spikes?"},
    {"role": "assistant", "content": "Ammonia spikes are typically caused by..."},
    {"role": "user", "content": "How do I fix it?"}
  ],
  "model": "gpt-4o-mini",
  "max_tokens": 1000,
  "temperature": 0.7
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "message": "To reduce ammonia levels...",
    "role": "assistant",
    "model": "gpt-4o-mini",
    "usage": {...}
  }
}
```

### POST /ai/openai/analyze
Analyze data using AI.

**Request Body:**
```json
{
  "data": {
    "ponds": [...],
    "expenses": [...],
    "growth_data": [...]
  },
  "question": "What trends do you see in the growth data?",
  "context": "This is data from a tilapia farm in Southeast Asia."
}
```

### POST /ai/openai/summarize
Summarize text.

**Request Body:**
```json
{
  "text": "Long text to summarize...",
  "max_length": "medium"
}
```

**max_length options:** "short", "medium", "long"

### POST /ai/openai/analyze-image
Analyze a single image (dedicated endpoint).

**Request Body (JSON):**
```json
{
  "image_url": "https://example.com/image.jpg",
  "prompt": "What's in this image?",
  "model": "gpt-4o-mini",
  "max_tokens": 1000,
  "detail": "auto"
}
```

**OR Base64:**
```json
{
  "image_base64": "base64_encoded_data",
  "prompt": "Describe this image"
}
```

**OR Multipart Form Data:**
- `image` (required): Image file
- `prompt` (optional): Question about image
- `model` (optional): Model name
- `detail` (optional): "low", "high", "auto"

### POST /ai/openai/analyze-images
Analyze multiple images together.

**Request Body:**
```json
{
  "images": [
    {"url": "https://example.com/image1.jpg"},
    {"url": "https://example.com/image2.jpg"},
    {"base64": "base64_data", "mime_type": "image/png"}
  ],
  "prompt": "Compare these images and describe differences",
  "model": "gpt-4o-mini",
  "max_tokens": 2000,
  "detail": "auto"
}
```

**Note:** Maximum 10 images allowed.

### POST /ai/openai/analyze-fish
Specialized fish image analysis.

**Request Body (JSON):**
```json
{
  "image_url": "https://example.com/fish.jpg",
  "analysis_type": "health"
}
```

**OR Multipart Form Data:**
- `image` (required): Fish image file
- `analysis_type` (optional): Type of analysis

**Analysis Types:**
| Type | Description |
|------|-------------|
| `general` | Overall farm/fish assessment, count, water clarity |
| `health` | Health indicators: fins, scales, lesions, disease signs, health score (1-10) |
| `species` | Species identification with confidence level |
| `size` | Size/weight estimation, growth stage assessment |

**Response:**
```json
{
  "success": true,
  "data": {
    "analysis_type": "health",
    "analysis": "Based on the image, I can observe...",
    "model": "gpt-4o-mini",
    "usage": {...}
  }
}
```

### GET /ai/openai/usage
Get AI usage statistics for the account.

**Query Parameters:**
- `days`: Number of days to look back (default: 30)

**Response:**
```json
{
  "success": true,
  "data": {
    "summary": {
      "total_requests": 150,
      "total_prompt_tokens": 45000,
      "total_completion_tokens": 12000,
      "total_tokens": 57000,
      "models_used": ["gpt-4o-mini", "gpt-4o"]
    },
    "by_model": [
      {"model": "gpt-4o-mini", "request_count": 120, "total_tokens": 45000}
    ],
    "daily_usage": [
      {"date": "2026-01-10", "request_count": 25, "total_tokens": 8500}
    ]
  }
}
```

### GET /ai/openai/usage/history
Get detailed AI usage history.

**Query Parameters:**
- `limit`: Max records (default: 50)
- `skip`: Records to skip (default: 0)

---

## MCP (Model Context Protocol)

MCP server for AI assistant integration.

### GET /mcp/info
Get MCP server information.

**Response:**
```json
{
  "success": true,
  "data": {
    "name": "fin-engine-mcp",
    "version": "1.0.0",
    "protocolVersion": "2024-11-05",
    "capabilities": {"tools": {"listChanged": true}}
  }
}
```

### GET /mcp/tools
List available MCP tools.

### POST /mcp/tools/call
Execute an MCP tool.

**Request Body:**
```json
{
  "name": "get_dashboard_summary",
  "arguments": {
    "account_key": "acc_xyz789"
  }
}
```

### POST /mcp/tools/{tool_name}
Execute a specific tool by name.

**Available Tools:**
| Tool | Description |
|------|-------------|
| `get_user_info` | Get user information |
| `get_company_info` | Get company details |
| `list_fish_species` | List fish species with analytics |
| `get_fish_analytics` | Get detailed fish analytics |
| `list_ponds` | List all ponds |
| `get_pond_details` | Get specific pond details |
| `get_expenses` | Get expense records |
| `get_financial_summary` | Get financial summary |
| `get_feeding_records` | Get feeding history |
| `get_sampling_data` | Get water quality data |
| `search_data` | Search across collections |
| `get_dashboard_summary` | Get complete dashboard |

### POST /mcp/session
Create an MCP session.

### DELETE /mcp/session/{session_id}
End an MCP session.

### POST /mcp/protocol
Handle MCP protocol requests (JSON-RPC style).

### GET /mcp/dashboard
Get dashboard summary (convenience endpoint).

---

## Error Handling

All API errors follow this format:

```json
{
  "success": false,
  "error": {
    "message": "Error description",
    "code": "ERROR_CODE"
  }
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing or invalid token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found |
| 409 | Conflict - Resource already exists |
| 422 | Unprocessable Entity - Validation error |
| 500 | Internal Server Error |
| 503 | Service Unavailable - External service down |

### Common Error Codes

| Code | Description |
|------|-------------|
| `AUTH_REQUIRED` | Authentication required |
| `INVALID_TOKEN` | Token is invalid or expired |
| `INVALID_CREDENTIALS` | Wrong email or password |
| `USER_EXISTS` | User already registered |
| `NOT_FOUND` | Resource not found |
| `VALIDATION_ERROR` | Input validation failed |
| `PERMISSION_DENIED` | Insufficient permissions |
| `OPENAI_NOT_CONFIGURED` | OpenAI API key not set |

---

## Rate Limiting

Rate limiting may be applied:
- 60 requests per minute per user
- 1000 requests per hour per account

Rate limit headers:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1704931200
```

---

## Webhooks (Coming Soon)

Configure webhooks for events:
- `pond.stocked` - Fish stocked in pond
- `pond.harvested` - Harvest recorded
- `alert.triggered` - Water quality alert
- `expense.created` - New expense recorded

---

## SDK Examples

### Python
```python
import requests

BASE_URL = "http://localhost:5000"
TOKEN = "your_access_token"

headers = {"Authorization": f"Bearer {TOKEN}"}

# Query AI
response = requests.post(
    f"{BASE_URL}/ai/openai/query",
    headers=headers,
    json={
        "prompt": "What's the optimal pH for tilapia?",
        "system_prompt": "You are a fish farming expert."
    }
)
print(response.json())

# Query with image
with open("fish.jpg", "rb") as f:
    response = requests.post(
        f"{BASE_URL}/ai/openai/query",
        headers=headers,
        files={"image": f},
        data={"prompt": "What type of fish is this?"}
    )
print(response.json())
```

### JavaScript
```javascript
const BASE_URL = "http://localhost:5000";
const TOKEN = "your_access_token";

// Query AI
const response = await fetch(`${BASE_URL}/ai/openai/query`, {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${TOKEN}`,
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    prompt: "What's the optimal pH for tilapia?",
    system_prompt: "You are a fish farming expert."
  })
});
const data = await response.json();
console.log(data);

// Query with image (FormData)
const formData = new FormData();
formData.append("prompt", "What type of fish is this?");
formData.append("image", fileInput.files[0]);

const response = await fetch(`${BASE_URL}/ai/openai/query`, {
  method: "POST",
  headers: { "Authorization": `Bearer ${TOKEN}` },
  body: formData
});
```

### cURL
```bash
# Login
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}'

# Query AI
curl -X POST http://localhost:5000/ai/openai/query \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"What is tilapia?"}'

# Query with image file
curl -X POST http://localhost:5000/ai/openai/query \
  -H "Authorization: Bearer TOKEN" \
  -F "prompt=What type of fish is this?" \
  -F "image=@fish.jpg"

# Analyze fish image
curl -X POST http://localhost:5000/ai/openai/analyze-fish \
  -H "Authorization: Bearer TOKEN" \
  -F "image=@fish.jpg" \
  -F "analysis_type=health"
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_ENV` | Environment (development/staging/production) | development |
| `JWT_SECRET` | JWT signing secret | Required in production |
| `MONGO_URI` | MongoDB connection string | mongodb://localhost:27017 |
| `OPENAI_API_KEY` | OpenAI API key | None |
| `OPENAI_MODEL` | Default OpenAI model | gpt-4o-mini |
| `MASTER_ADMIN_PASSWORD` | Master password for registration | password (dev only) |

---

## Changelog

### v1.0.0 (January 2026)
- Initial release
- Authentication & user management
- Company management
- Fish & pond management
- Feeding & sampling records
- Expenses & transactions
- AI services (OpenAI integration)
- MCP server for AI assistants
- Image analysis for fish health

