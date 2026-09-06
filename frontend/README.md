# Civora — Frontend (Phase 6 checkpoint)

React + Vite + Tailwind frontend for the Government–Startup Innovation Procurement Platform.

## Current checkpoint

Phases 1–5 are implemented:

1. Scaffold — Vite, React, Tailwind, Router, JWT auth, design system, API client.
2. Government core — dashboard, challenge CRUD, challenge lifecycle.
3. Radar + Passport — Startup Radar, passport views, applications and eligibility.
4. Evaluation + Pilots — AI/human evaluation, pilot generation, milestones and evidence.
5. Outcomes + Trust Graph — KPI tracker, simulation, risk checks, outcome decision, trust graph visualization.
6. Startup-side screens — startup dashboard, passport editor/evidence, applications, pilot tracking, own trust graph, and final UI polish.

## Run locally

```bash
npm install
npm run dev
```

Frontend: `http://localhost:5173`
Backend: `http://127.0.0.1:8000`

The backend CORS configuration allows both `localhost:5173` and `127.0.0.1:5173`.

## Architecture

```text
React SPA
  ├── AuthContext + role guards
  ├── Axios API client + JWT refresh
  ├── Government screens
  └── Startup screens
          |
          v
     Django REST API
          |
     PostgreSQL + pgvector
          |
        Ollama
```

The browser never talks directly to PostgreSQL or Ollama.

## Startup routes

```text
/startup
/startup/passport
/startup/challenges
/startup/applications
/startup/applications/:id
/startup/pilots
/startup/pilots/:id
/startup/trust-graph
```

### Startup journey

```text
Dashboard
  ↓
Complete Passport
  ↓
Add / verify evidence
  ↓
Browse open government challenges
  ↓
Submit application
  ↓
Track eligibility + evaluation
  ↓
Selected
  ↓
Track pilot + milestones
  ↓
Submit evidence
  ↓
Track payment status
  ↓
View KPI / outcome
  ↓
View own Trust Graph
```

## Design language

The frontend uses a dark civic/gov-tech visual language:

- Ink/slate background
- Paper typography
- Brass for primary actions
- Teal for active/system states
- Sage for verified/success states
- Amber for attention/review
- Terracotta for failure/risk
- Fraunces for display typography
- Public Sans for UI/body copy
- IBM Plex Mono for metadata, status, and technical values

Framer Motion is used selectively for page entrance, score reveals, cards, and trust-graph motion. Respect `prefers-reduced-motion`.

## API integration

Use the existing API modules in `src/api/` rather than calling Axios directly from pages.

```text
src/api/auth.js
src/api/startups.js
src/api/challenges.js
src/api/applications.js
src/api/pilots.js
src/api/trustGraph.js
```

The API client automatically attaches the JWT access token and attempts a refresh when an access token expires.

## Important backend semantics

- There are exactly two user types: `GOVERNMENT` and `STARTUP`.
- Backend permissions are authoritative; UI hiding is not security.
- AI output is advisory.
- Deterministic rules control eligibility, KPI status, risks, and outcome recommendation.
- Government verification is authoritative for evidence.
- Simulated payments must be labelled as simulated.
- Do not expose embeddings or call Ollama from the browser.

## Startup-specific implementation notes

### Passport

The current startup Passport page supports:

- Passport editing
- Technology tags
- Evidence creation
- Evidence editing/deletion while unverified
- Evidence verification state display
- Startup embedding refresh

### Applications

Startup users can only see their own applications and can apply to `OPEN` challenges.

### Pilots

Startup users can:

- View selected pilots
- Track milestones
- Submit milestones
- Submit milestone evidence
- View KPI results
- View the outcome decision
- See simulated payment state

They cannot verify evidence, approve payments, or change government-controlled states.

### Trust Graph

The startup graph is rendered from the backend `nodes` / `edges` response. No graph database is required.

## Final frontend goal

The UI should make the backend principle visible:

> AI proposes. Rules enforce. Humans decide. Evidence proves.

The most important startup-side experience is the progression from:

**Passport → Application → Pilot → Evidence → Verified track record → Trust Graph.**
