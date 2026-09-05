# Government–Startup Innovation Procurement Platform

## Frontend Integration Guide / API Contract

This README is the handoff document for the frontend engineer building the React application against the completed Django REST backend.

The backend implements the full MVP workflow:

**Government problem → Challenge → Startup discovery → Application → Eligibility → AI + Human evaluation → Selection → Pilot → Milestones → Evidence → Payment → KPI measurement → Risk analysis → Outcome decision → Trust Graph**

The backend is intentionally simple:

- Django 5.x
- Django REST Framework
- PostgreSQL
- pgvector
- JWT authentication
- Ollama for local AI (`qwen3:8b` + `qwen3-embedding:0.6b`)

No frontend should call PostgreSQL or Ollama directly. All data and AI actions go through the Django REST API.

---

# 1. Development Setup

## Backend URL

Default Django development server:

```text
http://127.0.0.1:8000
```

Equivalent localhost URL:

```text
http://localhost:8000
```

The backend CORS configuration allows the default Vite origins:

```text
http://localhost:5173
http://127.0.0.1:5173
```

## Authentication

The API uses JWT Bearer authentication.

For protected requests send:

```http
Authorization: Bearer <access_token>
```

Access token lifetime: approximately 1 hour.

Refresh token lifetime: approximately 7 days.

When an access token expires, call the refresh endpoint with the refresh token.

---

# 2. Two User Types

There are only two application roles:

```text
GOVERNMENT
STARTUP
```

The same authentication system is used for both. The frontend should read `user_type` from the authenticated user object and route the user to the appropriate dashboard.

## Government UI

Main areas:

- Dashboard
- Challenges
- Applications / evaluation committee
- Startup Radar
- Selected startups
- Pilots
- Milestones / evidence verification
- KPI and risk dashboard
- Outcome decisions
- Trust Graph

## Startup UI

Main areas:

- Dashboard
- Startup Passport
- Passport evidence
- Open challenges
- My applications
- Selected pilots
- Milestone submissions
- Evidence submissions
- Payment status
- Own Trust Graph

Never rely only on hiding UI controls for authorization. The backend is the source of truth and returns `401`/`403` when an action is not permitted.

---

# 3. Standard Response / Error Handling

Successful responses generally use normal HTTP status codes:

```text
200 OK
201 Created
400 Bad Request
401 Unauthorized
403 Forbidden
404 Not Found
503 Service Unavailable
```

Validation errors generally look like:

```json
{
  "field_name": ["Human-readable validation message"]
}
```

or:

```json
{
  "detail": "Human-readable error message"
}
```

Frontend should show field-level validation beside the corresponding form field where possible.

---

# 4. Authentication API

Base path:

```text
/api/auth/
```

## 4.1 Register

```http
POST /api/auth/register/
```

Public endpoint.

### Government registration

```json
{
  "email": "officer@example.gov.in",
  "name": "Government Officer",
  "password": "strongpassword123",
  "user_type": "GOVERNMENT",
  "government_profile": {
    "department_name": "Water Department",
    "designation": "Municipal Engineer",
    "department_description": "Municipal water infrastructure department"
  }
}
```

### Startup registration

```json
{
  "email": "founder@example.com",
  "name": "Startup Founder",
  "password": "strongpassword123",
  "user_type": "STARTUP",
  "startup_account_profile": {
    "company_name": "AquaSense",
    "description": "IoT-based municipal water leak detection",
    "website": "https://example.com",
    "industry": "Water",
    "technologies": ["IoT", "Sensors", "Analytics"],
    "location": "Jaipur",
    "founded_year": 2024,
    "team_size": 12
  }
}
```

Response:

```json
{
  "user": {
    "id": "uuid",
    "email": "...",
    "name": "...",
    "user_type": "STARTUP",
    "created_at": "...",
    "government_profile": null,
    "startup_account_profile": { }
  },
  "tokens": {
    "refresh": "jwt-refresh-token",
    "access": "jwt-access-token"
  }
}
```

For a startup, the backend also auto-creates the Startup Passport from the registration profile.

## 4.2 Login

```http
POST /api/auth/login/
```

Body:

```json
{
  "email": "founder@example.com",
  "password": "strongpassword123"
}
```

Returns the same `user + tokens` structure as registration.

## 4.3 Refresh access token

```http
POST /api/auth/token/refresh/
```

Body:

```json
{
  "refresh": "jwt-refresh-token"
}
```

Response:

```json
{
  "access": "new-access-token"
}
```

## 4.4 Current user

```http
GET /api/auth/me/
```

Protected.

## 4.5 Update current user/profile

```http
PATCH /api/auth/me/
```

Body can contain:

```json
{
  "name": "Updated Name",
  "profile": {
    "department_name": "Water Department",
    "designation": "Senior Engineer"
  }
}
```

For startups the `profile` object uses startup profile fields instead.

---

# 5. Startup Passport API

Base path:

```text
/api/startups/
```

The backend has two startup concepts:

1. `accounts.StartupProfile` — registration/account profile.
2. `startups.Startup` — the richer **Startup Passport** used by Radar, evaluation, pilots and Trust Graph.

Frontend should treat the second one as the public startup identity.

## 5.1 Browse startup passports

```http
GET /api/startups/
```

Any authenticated user.

Useful for government browse/search views.

## 5.2 Startup passport detail

```http
GET /api/startups/{startup_id}/
```

Returns company information plus evidence and computed counts such as:

- `pilot_count`
- `deployment_count`
- `verified_evidence_count`

## 5.3 Current startup passport

```http
GET /api/startups/passport/
PATCH /api/startups/passport/
```

Startup user only.

PATCH example:

```json
{
  "description": "Updated company description",
  "technologies": ["IoT", "Sensors", "Edge AI"],
  "location": "Jaipur"
}
```

## 5.4 Own passport evidence

```http
GET  /api/startups/passport/evidence/
POST /api/startups/passport/evidence/
```

Startup only.

Example JSON when using an external URL:

```json
{
  "evidence_type": "GOVERNMENT_PILOT",
  "title": "Jaipur Municipal Leak Pilot",
  "description": "Pilot completion report",
  "external_url": "https://example.com/report"
}
```

For file uploads use `multipart/form-data` and send the `document` field as a file.

`verified` and `verified_at` are read-only here.

## 5.5 Own evidence detail

```http
GET    /api/startups/passport/evidence/{evidence_id}/
PATCH  /api/startups/passport/evidence/{evidence_id}/
DELETE /api/startups/passport/evidence/{evidence_id}/
```

A startup cannot edit or delete evidence after government verification.

## 5.6 Government verifies startup evidence

```http
POST /api/startups/evidence/{evidence_id}/verify/
```

Government only.

Body:

```json
{
  "verified": true
}
```

This is an important Trust Graph relationship:

```text
Startup claim → Evidence → Government verification
```

---

# 6. Challenge API

Base path:

```text
/api/challenges/
```

## 6.1 List challenges

```http
GET /api/challenges/
```

Government users can see challenges broadly.

Startup users see `OPEN` challenges only.

Optional filters supported by the backend include:

```text
?status=OPEN
?created_by=<government_user_uuid>
```

The API uses DRF page-number pagination for list endpoints. Default page size is 20.

Typical paginated response:

```json
{
  "count": 25,
  "next": "http://127.0.0.1:8000/api/challenges/?page=2",
  "previous": null,
  "results": [ ... ]
}
```

## 6.2 Create challenge

```http
POST /api/challenges/
```

Government only.

Body:

```json
{
  "title": "Municipal Pipe Leak Detection",
  "problem_statement": "Detect municipal water pipe leaks faster.",
  "desired_outcome": "Reduce leak detection time and water loss.",
  "requirements": {
    "required_technologies": ["IoT", "Sensors"],
    "required_industries": ["Water"],
    "minimum_team_size": 5,
    "government_experience_required": true
  },
  "constraints": [
    "Minimal excavation",
    "Must work with existing municipal infrastructure"
  ],
  "budget": "500000.00",
  "start_date": "2026-10-01",
  "application_deadline": "2026-09-25"
}
```

The backend starts a newly-created challenge in `DRAFT` status.

`created_by` and `status` are server-controlled.

## 6.3 Retrieve challenge

```http
GET /api/challenges/{challenge_id}/
```

## 6.4 Update challenge

```http
PATCH /api/challenges/{challenge_id}/
```

Only the government user who created the challenge can modify it.

## 6.5 Delete challenge

```http
DELETE /api/challenges/{challenge_id}/
```

Only the challenge owner.

## 6.6 Challenge lifecycle

Use:

```http
POST /api/challenges/{challenge_id}/transition/
```

Body:

```json
{
  "status": "OPEN"
}
```

Allowed lifecycle:

```text
DRAFT → OPEN → EVALUATION → PILOT → COMPLETED
                         ↘
                           CLOSED
```

More precisely, every transition is validated by the backend; the frontend should not allow arbitrary jumps.

Recommended UI: show a status stepper and only enable valid next transitions.

---

# 7. Application API

Base path:

```text
/api/applications/
```

This represents **Startup → Challenge** applications.

## 7.1 Startup applies to a challenge

```http
POST /api/applications/
```

Startup only.

Body:

```json
{
  "challenge": "challenge-uuid",
  "proposal": "Our proposed solution uses acoustic sensors and pressure monitoring..."
}
```

The backend infers the startup from the authenticated user.

Rules:

- Challenge must be `OPEN`.
- Startup cannot apply twice to the same challenge.
- `challenge`/`startup` are server-controlled in the stored application.

## 7.2 List applications

```http
GET /api/applications/
```

Startup users: their own applications.

Government users: applications for challenges they own.

## 7.3 Retrieve application

```http
GET /api/applications/{application_id}/
```

## 7.4 Application status lifecycle

```text
SUBMITTED
    ↓
ELIGIBILITY_CHECK
    ├──→ ELIGIBLE → UNDER_EVALUATION → SELECTED
    │                             └──→ REJECTED
    └──→ INELIGIBLE
```

## 7.5 Eligibility check

```http
POST /api/applications/{application_id}/check-eligibility/
```

Government only.

The response contains:

```json
{
  "eligible": true,
  "reason": "All configured eligibility requirements are satisfied.",
  "status": "ELIGIBLE"
}
```

Eligibility is deterministic; do not display it as an AI decision.

## 7.6 Start evaluation

```http
POST /api/applications/{application_id}/action/
```

Body:

```json
{
  "action": "start_evaluation"
}
```

Only valid from `ELIGIBLE`.

## 7.7 Select or reject

Same endpoint:

```http
POST /api/applications/{application_id}/action/
```

Select:

```json
{
  "action": "select"
}
```

Reject:

```json
{
  "action": "reject"
}
```

Final selection/rejection requires at least one human evaluation.

Only the government owner of the challenge can perform these application state changes.

---

# 8. Startup Radar API

Base path:

```text
/api/radar/
```

This is one of the main WOW screens.

Conceptual flow:

```text
Challenge
   ↓
Embedding
   ↓
pgvector semantic search
   ↓
Hard eligibility filtering
   ↓
Deterministic ranking
   ↓
AI explanation
```

## 8.1 Refresh challenge embedding

```http
POST /api/radar/challenges/{challenge_id}/refresh-embedding/
```

Government owner only.

No body required.

Response:

```json
{
  "detail": "Challenge embedding generated.",
  "challenge_id": "uuid"
}
```

The frontend can show this as a background/system action rather than a major workflow step.

## 8.2 Refresh my startup embedding

```http
POST /api/radar/startups/refresh-embedding/
```

Startup only.

No body required.

## 8.3 Get ranked startup matches

```http
GET /api/radar/challenges/{challenge_id}/matches/
```

Government owner only.

Optional query parameter:

```text
?limit=10
```

Allowed range: 1–50.

Response shape:

```json
{
  "challenge_id": "uuid",
  "count": 2,
  "results": [
    {
      "startup_id": "uuid",
      "company_name": "AquaSense",
      "industry": "Water",
      "technologies": ["IoT", "Sensors"],
      "semantic_similarity": 91.2,
      "technology_fit": 100.0,
      "domain_fit": 100.0,
      "pilot_readiness": 88.6,
      "evidence_score": 50.0,
      "match_score": 88.4,
      "match_reasons": [
        "Strong semantic match with the challenge.",
        "Matches required technologies: IoT, Sensors."
      ],
      "risks": []
    }
  ]
}
```

Recommended frontend presentation:

- Rank number
- Company name
- Match score
- Technology fit
- Domain fit
- Pilot readiness
- Verified evidence
- Match reasons
- Risks
- Link to Startup Passport

The backend ranking is deterministic. Do not label the numeric score as “AI confidence”.

## 8.4 AI explanation of matches

```http
POST /api/radar/challenges/{challenge_id}/explain/
```

Government owner only.

Body:

```json
{
  "limit": 5
}
```

Allowed range: 1–10.

Response:

```json
{
  "challenge_id": "uuid",
  "count": 1,
  "results": [
    {
      "startup_id": "uuid",
      "explanation": "The startup strongly matches the requested technology and domain...",
      "strengths": ["IoT fit", "Municipal water relevance"],
      "concerns": ["Limited evidence in this district"]
    }
  ]
}
```

This endpoint invokes the local Qwen model and may take noticeably longer than ordinary CRUD requests. Show a loading state.

---

# 9. Evaluation API

Evaluation happens against an application.

## 9.1 AI evaluation

```http
POST /api/applications/{application_id}/ai-evaluate/
```

Government evaluator only.

Application must be `UNDER_EVALUATION`.

Response fields include:

```text
technical_score
innovation_score
feasibility_score
scalability_score
evidence_score
overall_score
strengths
weaknesses
missing_evidence
recommendation
explanation
model_name
```

Important:

```text
AI recommendation = advisory
Human evaluation = authoritative
```

The frontend should visually distinguish these.

## 9.2 Human evaluations list

```http
GET /api/applications/{application_id}/human-evaluations/
```

Any government evaluator can view evaluations for committee review.

## 9.3 Submit human evaluation

```http
POST /api/applications/{application_id}/human-evaluations/
```

Government evaluator only.

Body:

```json
{
  "technical_score": 9,
  "innovation_score": 8,
  "feasibility_score": 9,
  "scalability_score": 8,
  "evidence_score": 8,
  "comments": "Strong technical proposal with good pilot readiness.",
  "recommendation": "SELECT"
}
```

Scores are 0–10.

Recommendation values:

```text
SELECT
REJECT
REVIEW
```

Each government evaluator may submit only one evaluation for the same application.

## 9.4 Evaluation summary

```http
GET /api/applications/{application_id}/evaluation-summary/
```

Response includes:

```text
application_id
status
ai_score
human_evaluation_count
human_average_score
combined_score
human_recommendations
selection_ready
```

Use this for a committee summary card.

---

# 10. Pilot API

Base path:

```text
/api/pilots/
```

Only selected applications can become pilots.

## 10.1 Create pilot manually

```http
POST /api/pilots/
```

Government challenge owner only.

Body:

```json
{
  "application": "application-uuid",
  "title": "Municipal Leak Detection Pilot",
  "description": "Pilot the selected startup solution in two zones.",
  "objectives": [
    "Reduce leak detection time",
    "Reduce water loss"
  ],
  "budget": "100000.00",
  "start_date": "2026-09-10",
  "end_date": "2026-12-10",
  "success_criteria": [
    "Detection time reduced by 30%"
  ],
  "data_requirements": [
    "Pressure readings",
    "Flow readings"
  ]
}
```

`application`, `challenge`, `startup`, `created_by`, and `status` are server-controlled in the resulting pilot.

## 10.2 Pilot status action

```http
POST /api/pilots/{pilot_id}/action/
```

Body values:

```json
{"action": "activate"}
```

```json
{"action": "complete"}
```

```json
{"action": "fail"}
```

```json
{"action": "cancel"}
```

Lifecycle:

```text
DRAFT → ACTIVE → COMPLETED
              ├→ FAILED
              └→ CANCELLED
```

Activating the pilot also moves an `EVALUATION` challenge to `PILOT`.

## 10.3 AI-generated pilot plan

Two endpoints exist.

### Generate a plan for an existing pilot

```http
POST /api/pilots/{pilot_id}/generate-plan/
```

Returns the generated plan but does not itself modify the pilot.

### Generate pilot directly from a selected application

```http
POST /api/pilots/generate-from-application/
```

Body:

```json
{
  "application": "selected-application-uuid"
}
```

This invokes local Qwen and creates the pilot plus generated milestones.

Plan shape:

```json
{
  "title": "...",
  "description": "...",
  "objectives": ["..."],
  "budget": 100000,
  "duration_days": 90,
  "success_criteria": ["..."],
  "data_requirements": ["..."],
  "milestones": [
    {
      "title": "Deployment",
      "description": "Deploy sensors",
      "amount": 20000,
      "due_day": 30
    }
  ]
}
```

Show this as an AI-generated draft that the government user can review rather than as an unquestionable decision.

---

# 11. Milestone API

Base routes are under:

```text
/api/pilots/milestones/
```

## 11.1 List all accessible milestones

```http
GET /api/pilots/milestones/
```

Startup sees its own pilot milestones.

Government sees milestones for pilots it owns.

## 11.2 Create milestone

```http
POST /api/pilots/{pilot_id}/milestones/
```

Government only.

Body:

```json
{
  "title": "Deploy sensors",
  "description": "Install and activate sensors in the selected zone.",
  "amount": "200000.00",
  "due_date": "2026-10-10"
}
```

The pilot relationship is server-controlled.

## 11.3 Submit milestone

```http
POST /api/pilots/milestones/{milestone_id}/submit/
```

Startup participating in the pilot only.

Moves:

```text
PENDING → SUBMITTED
```

## 11.4 Review milestone

```http
POST /api/pilots/milestones/{milestone_id}/review/
```

Government only.

Moves:

```text
SUBMITTED → UNDER_REVIEW
```

## 11.5 Verify milestone

```http
POST /api/pilots/milestones/{milestone_id}/verify/
```

Government only.

Before milestone verification, at least one evidence item attached to the milestone must already be government-verified.

Moves:

```text
UNDER_REVIEW → VERIFIED
```

A payment record is created automatically if needed.

## 11.6 Approve payment

```http
POST /api/pilots/milestones/{milestone_id}/approve-payment/
```

Government only.

Moves:

```text
VERIFIED → PAYMENT_APPROVED
```

## 11.7 Mark payment paid

```http
POST /api/pilots/milestones/{milestone_id}/pay/
```

Government only.

Moves:

```text
PAYMENT_APPROVED → PAID
```

The payment is simulated. The backend generates a reference such as:

```text
SIM-XXXXXXXXXX
```

Do not present this as a real banking transaction.

---

# 12. Pilot Evidence API

Evidence routes are both nested under a pilot and available as a read/verify collection.

## 12.1 List evidence for a pilot

```http
GET /api/pilots/{pilot_id}/evidence/
```

## 12.2 Submit evidence

```http
POST /api/pilots/{pilot_id}/evidence/
```

Startup participating in the pilot only.

Body when using JSON/external URL:

```json
{
  "milestone": "milestone-uuid",
  "evidence_type": "TEST_RESULT",
  "title": "Leak detection test results",
  "description": "Results from the first test batch.",
  "external_url": "https://example.com/test-results"
}
```

For a file upload, use `multipart/form-data` and send:

```text
milestone
 evidence_type
title
description
file
external_url (optional)
```

Valid pilot evidence types:

```text
DEPLOYMENT_REPORT
TEST_RESULT
KPI_REPORT
GOVERNMENT_REPORT
SYSTEM_LOG
PHOTO
OTHER
```

Evidence can only be submitted after the milestone has reached `SUBMITTED` or `UNDER_REVIEW`.

## 12.3 Verify evidence

```http
POST /api/pilots/evidence-records/{evidence_id}/verify/
```

Government only.

Body:

```json
{
  "verified": true
}
```

Verified evidence cannot be unverified in the MVP.

Recommended UI:

```text
Evidence
  ├── Pending verification
  └── ✓ Government verified
```

---

# 13. KPI API

KPIs are nested under a pilot.

## 13.1 List KPIs

```http
GET /api/pilots/{pilot_id}/kpis/
```

## 13.2 Create KPI

```http
POST /api/pilots/{pilot_id}/kpis/
```

Government only.

Body:

```json
{
  "name": "Leak detection rate",
  "description": "Percentage of known leaks correctly detected.",
  "unit": "%",
  "baseline": 40,
  "target": 75,
  "actual": null,
  "direction": "HIGHER_IS_BETTER"
}
```

Directions:

```text
HIGHER_IS_BETTER
LOWER_IS_BETTER
```

Example lower-is-better KPI:

```json
{
  "name": "Average response time",
  "unit": "hours",
  "baseline": 72,
  "target": 24,
  "actual": 18,
  "direction": "LOWER_IS_BETTER"
}
```

The backend calculates KPI status automatically.

Statuses:

```text
NOT_MEASURED
ACHIEVED
PARTIALLY_ACHIEVED
FAILED
```

Frontend should display the status and compare baseline → target → actual visually.

---

# 14. Pre-Pilot Simulation API

Endpoint:

```http
POST /api/pilots/{pilot_id}/simulate/
```

Government only.

Body:

```json
{
  "assumptions": {
    "expected_progress": 0.9
  }
}
```

If omitted, the backend uses its default assumption.

The result contains:

```text
pilot
assumptions
predicted_results
created_at
updated_at
```

Example `predicted_results` entry:

```json
{
  "<kpi-uuid>": {
    "kpi": "Leak detection rate",
    "baseline": 40.0,
    "target": 75.0,
    "predicted": 71.5,
    "unit": "%"
  }
}
```

Important frontend wording:

> **Illustrative pre-pilot simulation — not a guarantee of pilot performance.**

Do not label these numbers as AI predictions or guaranteed outcomes.

---

# 15. Risk / Red Flag API

Endpoint:

```http
POST /api/pilots/{pilot_id}/risk-check/
```

Government only.

The backend checks the pilot deterministically for currently implemented risk rules such as:

- Potential PII / sensitive data requirements
- Milestone amounts exceeding pilot budget
- Missing measurable KPIs

Response:

```json
{
  "count": 2,
  "risks": [
    {
      "id": "uuid",
      "pilot": "uuid",
      "category": "DATA",
      "severity": "HIGH",
      "title": "Potential PII exposure",
      "reason": "Pilot data requirements may involve personal or sensitive information.",
      "mitigation": "Use anonymization and restrict processing to approved government infrastructure.",
      "status": "OPEN"
    }
  ]
}
```

Severity values:

```text
LOW
MEDIUM
HIGH
CRITICAL
```

Risk status:

```text
OPEN
MITIGATED
ACCEPTED
```

Frontend should prioritize severity visually, with clear mitigation text.

---

# 16. Outcome / Scale Decision API

## 16.1 Generate outcome decision

```http
POST /api/pilots/{pilot_id}/outcome/
```

Government only.

By default, the pilot must be `COMPLETED` or `FAILED`.

To explicitly override this requirement in the MVP:

```json
{
  "force": true
}
```

## 16.2 Retrieve outcome decision

```http
GET /api/pilots/{pilot_id}/outcome/
```

Possible recommendations:

```text
SCALE
EXTEND_PILOT
STOP
```

Response includes:

```text
recommendation
rationale
kpi_summary
risk_summary
generated_by
created_at
updated_at
```

Current deterministic logic:

```text
All KPIs achieved
+ no high/critical open risks
        ↓
      SCALE

Incomplete / not measurable / promising but insufficient
        ↓
   EXTEND_PILOT

Multiple KPI failures
or unresolved high/critical risk
        ↓
       STOP
```

This is the key procurement-decision screen.

Recommended UI:

```text
              PILOT OUTCOME

        ┌─────────────────────┐
        │       SCALE         │
        │  Evidence supports  │
        │   broader rollout   │
        └─────────────────────┘

KPIs                5 / 5 achieved
High risks          0 open
Milestones          4 / 4 paid
Verified evidence   12 records
```

---

# 17. Trust Graph API

Base path:

```text
/api/trust-graph/
```

No graph database is used. The backend builds graph nodes and edges from existing PostgreSQL/Django relationships.

The frontend is responsible for visualizing the returned graph.

## 17.1 Startup Trust Graph

```http
GET /api/trust-graph/startups/{startup_id}/
```

Government users can inspect startup graphs.

Startup users can inspect only their own graph.

Response:

```json
{
  "root": {
    "id": "startup-uuid",
    "type": "startup",
    "label": "AquaSense"
  },
  "nodes": [
    {
      "id": "startup-uuid",
      "type": "startup",
      "label": "AquaSense"
    },
    {
      "id": "pilot-uuid",
      "type": "pilot",
      "label": "Water Pilot",
      "status": "COMPLETED"
    }
  ],
  "edges": [
    {
      "source": "startup-uuid",
      "target": "pilot-uuid",
      "relationship": "PARTICIPATED_IN"
    }
  ]
}
```

Possible node types include:

```text
startup
startup_evidence
pilot
challenge
government
kpi
milestone
pilot_evidence
```

Common relationship values include:

```text
SUPPORTED_BY
HAS_EVIDENCE
PARTICIPATED_IN
FOR_CHALLENGE
CONDUCTED_BY
MEASURED_BY
HAS_MILESTONE
SELECTED_STARTUP
```

## 17.2 Pilot Trust Graph

```http
GET /api/trust-graph/pilots/{pilot_id}/
```

Returns the graph around the pilot and its participating startup.

## 17.3 Challenge Trust Graph

```http
GET /api/trust-graph/challenges/{challenge_id}/
```

Returns the challenge plus selected startups and relationships relevant to the challenge.

The current challenge graph is intentionally simpler than the startup graph.

---

# 18. Recommended Frontend Page Structure

A practical React route structure:

```text
/login
/register

/government
/government/challenges
/government/challenges/new
/government/challenges/:id
/government/challenges/:id/radar
/government/challenges/:id/applications
/government/applications/:id
/government/pilots/:id
/government/pilots/:id/outcome
/government/startups/:id
/government/trust-graph/startups/:id

/startup
/startup/passport
/startup/passport/evidence
/startup/challenges
/startup/applications
/startup/applications/:id
/startup/pilots/:id
/startup/trust-graph
```

These are frontend suggestions, not backend routes.

---

# 19. Recommended Government Workflow

## Step 1 — Create challenge

Government fills a normal challenge form:

```text
Title
Problem
Desired outcome
Requirements
Constraints
Budget
Dates
```

Save as `DRAFT`.

## Step 2 — Publish challenge

Transition:

```text
DRAFT → OPEN
```

## Step 3 — Discover startups

Open Radar:

```text
Refresh embedding
↓
Get matches
↓
View ranked startups
↓
Request AI explanations
↓
Open Startup Passport
```

## Step 4 — Review applications

Government sees incoming applications.

Run eligibility.

Move eligible applications into evaluation.

## Step 5 — Evaluation committee

For each application:

```text
AI Evaluation
↓
Human evaluator 1
Human evaluator 2
Human evaluator 3
↓
Evaluation summary
```

The UI should clearly separate AI advisory analysis from human scores.

## Step 6 — Select startup

Once at least one human evaluation exists:

```text
UNDER_EVALUATION → SELECTED
```

## Step 7 — Create pilot

Either manually create the pilot or use:

```text
Generate Pilot From Application
```

Review the AI-generated draft before using it operationally.

## Step 8 — Activate pilot

```text
DRAFT → ACTIVE
```

## Step 9 — Manage milestones

Government creates milestones.

Startup submits milestone.

Government reviews.

## Step 10 — Evidence

Startup submits evidence against the milestone.

Government verifies evidence.

## Step 11 — Verify milestone and pay

```text
Evidence verified
↓
Milestone verified
↓
Payment approved
↓
Payment marked paid
```

## Step 12 — Measure outcomes

Government creates KPIs and records actuals.

Run pre-pilot simulation before the pilot or as an illustrative comparison view.

Run risk check.

## Step 13 — Make outcome decision

Complete/fail the pilot.

Generate outcome:

```text
SCALE
EXTEND_PILOT
STOP
```

## Step 14 — Show trust graph

Use the Trust Graph to visually explain:

```text
Startup
  ↓
Pilot
  ↓
KPIs
  ↓
Milestones
  ↓
Evidence
  ↓
Government verification
```

---

# 20. Recommended Startup Workflow

## Step 1 — Register

Startup registers and receives JWT tokens.

The backend auto-creates the Startup Passport.

## Step 2 — Complete Passport

Startup updates:

```text
Company information
Description
Industry
Technology
Location
Team size
```

## Step 3 — Add evidence

Startup adds:

```text
Certifications
Government pilots
Deployments
Case studies
Awards
Patents
```

Evidence remains unverified until a government user verifies it.

## Step 4 — Browse challenges

Startup sees only `OPEN` challenges.

## Step 5 — Apply

Startup submits:

```text
Challenge
Proposal
```

## Step 6 — Wait for evaluation

Startup can view application status but cannot alter government decisions.

## Step 7 — If selected, participate in pilot

Startup views its pilot and milestones.

## Step 8 — Submit milestone

```text
PENDING → SUBMITTED
```

## Step 9 — Submit evidence

Attach evidence to the submitted milestone.

## Step 10 — Track payment

Startup sees:

```text
VERIFIED
PAYMENT_APPROVED
PAID
```

and the simulated payment reference when paid.

## Step 11 — View resulting Trust Graph

Startup can view its own graph showing the evidence-backed history of its participation.

---

# 21. Frontend State Machines

Do not implement status fields as arbitrary free-form strings in the UI. Treat them as explicit enums.

## Challenge

```text
DRAFT
OPEN
EVALUATION
PILOT
COMPLETED
CLOSED
```

## Application

```text
SUBMITTED
ELIGIBILITY_CHECK
ELIGIBLE
INELIGIBLE
UNDER_EVALUATION
SELECTED
REJECTED
```

## Pilot

```text
DRAFT
ACTIVE
COMPLETED
FAILED
CANCELLED
```

## Milestone

```text
PENDING
SUBMITTED
UNDER_REVIEW
VERIFIED
PAYMENT_APPROVED
PAID
```

## KPI

```text
NOT_MEASURED
ACHIEVED
PARTIALLY_ACHIEVED
FAILED
```

## Outcome

```text
SCALE
EXTEND_PILOT
STOP
```

## Risk

Severity:

```text
LOW
MEDIUM
HIGH
CRITICAL
```

Status:

```text
OPEN
MITIGATED
ACCEPTED
```

---

# 22. AI Loading / UX Expectations

AI endpoints can be significantly slower than CRUD endpoints because they call the local Ollama model.

These endpoints should always have visible loading states:

```text
POST /api/radar/challenges/{id}/explain/
POST /api/applications/{id}/ai-evaluate/
POST /api/pilots/{id}/generate-plan/
POST /api/pilots/generate-from-application/
```

Also handle:

```text
503 Service Unavailable
```

with a user-friendly message such as:

> AI service is temporarily unavailable. You can continue with manual evaluation.

Do not block the entire application because an AI endpoint is unavailable.

---

# 23. Important Frontend Rules

## Never trust IDs supplied by the user for ownership

The backend determines the authenticated startup/government identity.

## Never treat AI output as authoritative

AI output is advisory, especially:

- startup explanations
- AI evaluation
- pilot generation

## Never bypass lifecycle rules

The backend rejects invalid state transitions.

## Keep evidence verification visually distinct

Use a clear verified badge for government-verified evidence.

## Do not expose raw embeddings

Embeddings are backend implementation details. There is no frontend feature that needs the 1024-dimensional vector itself.

## Treat simulated payments as simulated

Show “Simulated payment” or equivalent terminology in the UI.

---

# 24. Example End-to-End Demo Data

A strong demo can use a municipal water-leak challenge.

### Challenge

```text
Title:
Municipal Pipe Leak Detection

Problem:
The municipality cannot detect underground leaks quickly.

Desired outcome:
Reduce leak detection time and water loss.
```

### Radar

```text
AquaSense       91%
HydroWatch      84%
PipeVision      76%
```

### Selected startup

```text
AquaSense
```

### Pilot

```text
90 days
3 zones
4 milestones
```

### KPI

```text
Leak detection rate
Baseline: 40%
Target: 75%
Actual: 80%
Status: ACHIEVED
```

### Risk

```text
Potential PII exposure
Severity: HIGH
```

### Outcome

```text
SCALE
```

### Trust Graph

```text
AquaSense
   ↓
Water Pilot
   ↓
Leak Detection KPI
   ↓
Deployment Milestone
   ↓
Verified Test Result
   ↓
Government Verification
```

This sequence should be the primary hackathon demo path.

---

# 25. Backend Source of Truth

The current backend is the authoritative implementation of this document.

When a UI requirement conflicts with backend behavior, the frontend should adapt to the API contract rather than inventing a new workflow.

The guiding product principle is:

```text
AI proposes.
Rules enforce.
Humans decide.
Evidence proves.
```

The frontend's job is to make that process understandable, transparent, and visually compelling.
