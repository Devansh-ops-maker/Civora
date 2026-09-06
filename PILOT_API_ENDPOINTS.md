# Pilot Management API Endpoints

## Base URL
```
http://localhost:8000/api/pilots/
```

---

## Endpoint: Get Pilot Details (Manage Pilot)

### Request
```
GET /api/pilots/manage/{pilot_id}/
```

### Parameters
- `pilot_id` (path parameter, required): UUID of the pilot
- **Authentication**: Bearer token required

### Headers
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Response (Status: 200 OK)
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "application": "660e8400-e29b-41d4-a716-446655440001",
  "challenge": "770e8400-e29b-41d4-a716-446655440002",
  "startup": "880e8400-e29b-41d4-a716-446655440003",
  "created_by": "990e8400-e29b-41d4-a716-446655440004",
  "title": "Urban Waste Management Pilot",
  "description": "A pilot program to test waste segregation and recycling in municipal areas",
  "objectives": [
    "Test waste segregation efficiency",
    "Measure adoption rates in target areas",
    "Evaluate cost-benefit ratio"
  ],
  "budget": "500000.00",
  "start_date": "2026-09-15",
  "end_date": "2026-12-15",
  "success_criteria": [
    "80% waste segregation accuracy",
    "50% community adoption",
    "30% cost reduction vs. traditional methods"
  ],
  "data_requirements": [
    "Daily waste collection logs",
    "Community feedback surveys",
    "Cost tracking spreadsheets"
  ],
  "status": "DRAFT",
  "created_at": "2026-09-06T12:34:56.789Z",
  "updated_at": "2026-09-06T12:34:56.789Z"
}
```

### Error Responses

#### 404 Not Found
```json
{
  "detail": "Not found."
}
```

#### 403 Forbidden
**Applies when:**
- User is a startup but doesn't own the pilot's startup
- User is government but didn't create the pilot

```json
{
  "detail": "You do not have permission to perform this action."
}
```

#### 401 Unauthorized
```json
{
  "detail": "Authentication credentials were not provided."
}
```

---

## Endpoint: List All Pilots

### Request
```
GET /api/pilots/
```

### Headers
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Response (Status: 200 OK)
```json
{
  "count": 15,
  "next": "http://localhost:8000/api/pilots/?page=2",
  "previous": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "application": "660e8400-e29b-41d4-a716-446655440001",
      "challenge": "770e8400-e29b-41d4-a716-446655440002",
      "startup": "880e8400-e29b-41d4-a716-446655440003",
      "created_by": "990e8400-e29b-41d4-a716-446655440004",
      "title": "Urban Waste Management Pilot",
      "description": "A pilot program to test waste segregation and recycling in municipal areas",
      "objectives": [],
      "budget": "500000.00",
      "start_date": "2026-09-15",
      "end_date": "2026-12-15",
      "success_criteria": [],
      "data_requirements": [],
      "status": "DRAFT",
      "created_at": "2026-09-06T12:34:56.789Z",
      "updated_at": "2026-09-06T12:34:56.789Z"
    }
  ]
}
```

**Note**: Results are filtered based on user type:
- **Startup users**: See only pilots for their startup
- **Government users**: See only pilots they created

---

## Endpoint: Change Pilot Status

### Request
```
POST /api/pilots/{pilot_id}/action/
```

### Body
```json
{
  "action": "activate"
}
```

### Allowed Actions & Transitions

| Action | Current Status | New Status | Description |
|--------|---|---|---|
| `activate` | DRAFT | ACTIVE | Start the pilot |
| `complete` | ACTIVE | COMPLETED | Mark pilot as successfully completed |
| `fail` | ACTIVE | FAILED | Mark pilot as failed |
| `cancel` | DRAFT or ACTIVE | CANCELLED | Cancel the pilot |

### Example Request
```bash
curl -X POST http://localhost:8000/api/pilots/550e8400-e29b-41d4-a716-446655440000/action/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"action": "activate"}'
```

### Response (Status: 200 OK)
Returns updated pilot object with new status.

### Error Responses

#### 400 Bad Request - Invalid Transition
```json
{
  "status": "Cannot transition application from DRAFT to REJECTED."
}
```

#### 403 Forbidden
```json
{
  "detail": "Only government users can manage pilot status."
}
```

---

## Endpoint: Get Pilot Milestones

### Request
```
GET /api/pilots/{pilot_id}/milestones/
```

### Response (Status: 200 OK)
```json
[
  {
    "id": "aa0e8400-e29b-41d4-a716-446655440000",
    "pilot": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Setup and Infrastructure",
    "description": "Deploy system and train government team",
    "amount": "100000.00",
    "due_date": "2026-10-15",
    "status": "PENDING",
    "created_at": "2026-09-06T12:34:56.789Z",
    "updated_at": "2026-09-06T12:34:56.789Z"
  }
]
```

---

## Endpoint: Create Pilot Milestone

### Request
```
POST /api/pilots/{pilot_id}/milestones/
```

### Body
```json
{
  "title": "Phase 1 Deployment",
  "description": "Initial deployment in pilot area",
  "amount": "150000.00",
  "due_date": "2026-10-15"
}
```

### Permissions
- Only **government users** can create milestones

### Response (Status: 201 Created)
Returns the newly created milestone object.

---

## Pilot Status Values

```
DRAFT       = "DRAFT"       # Initial state
ACTIVE      = "ACTIVE"      # Pilot is running
COMPLETED   = "COMPLETED"   # Pilot finished successfully
FAILED      = "FAILED"      # Pilot failed
CANCELLED   = "CANCELLED"   # Pilot was cancelled
```

---

## Authentication

All endpoints require authentication via JWT bearer token:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Obtain token by logging in:
```bash
POST /api/auth/token/
{
  "email": "user@example.com",
  "password": "password123"
}
```

---

## Common Use Cases

### 1. Load Pilot Management Page
```javascript
// Frontend code (React/Vue/etc.)
const pilotId = "550e8400-e29b-41d4-a716-446655440000";
const response = await fetch(
  `http://localhost:8000/api/pilots/manage/${pilotId}/`,
  {
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json"
    }
  }
);
const pilot = await response.json();
```

### 2. Activate Pilot
```javascript
const response = await fetch(
  `http://localhost:8000/api/pilots/${pilotId}/action/`,
  {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ action: "activate" })
  }
);
const updatedPilot = await response.json();
```

### 3. Get Milestones
```javascript
const response = await fetch(
  `http://localhost:8000/api/pilots/${pilotId}/milestones/`,
  {
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json"
    }
  }
);
const milestones = await response.json();
```

---

## Rate Limiting & Pagination

- Pagination: Results are paginated (default 20 per page)
- Add `?page=2` to navigate between pages
- No rate limiting currently implemented

---

## Support

For issues or questions, contact the backend team or check Django logs:
```bash
python3 manage.py runserver
```
