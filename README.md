# Government–Startup Innovation Procurement Platform — Backend

## Phase 1 — Foundation (done)
- Django project (`config`) + 6 apps scaffolded: accounts, challenges, startups, evaluations, pilots, intelligence
- PostgreSQL configured as sole datastore (see `.env`)
- pgvector extension enabled in the target DB (`CREATE EXTENSION vector;`)
- Custom `User` model (email-based, single auth system, `user_type` = GOVERNMENT | STARTUP)
- `GovernmentProfile` / `StartupProfile` (1:1 with User)
- JWT auth via simplejwt: register, login, refresh, me
- Role-based permission classes: `IsGovernmentUser`, `IsStartupUser`, `IsOwner`, `IsOwnerOrReadOnly`
- Verified end-to-end against a real local Postgres 16 + pgvector instance: migrations, registration (both roles), login, protected `/me/`, validation errors, superuser creation.

## Setup
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit DB credentials
createdb govstartup
psql govstartup -c "CREATE EXTENSION IF NOT EXISTS vector;"
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Endpoints so far
```
POST /api/auth/register/      { email, name, password, user_type, government_profile | startup_account_profile }
POST /api/auth/login/         { email, password } -> { user, tokens }
POST /api/auth/token/refresh/ { refresh } -> { access }
GET  /api/auth/me/            (auth required)
PATCH /api/auth/me/           { name?, profile? }
```

## Phase 2 — Startups / Startup Passport (done)
- `Startup` model (the Passport): company info, technologies, evidence counts, and a
  pgvector `embedding` field (HNSW index, cosine ops) reserved for Startup Radar in Phase 5.
  The extension (`CREATE EXTENSION vector`) is now provisioned automatically by the
  migration — no manual `psql` step needed on a fresh DB.
- `StartupEvidence`: claims tied to concrete evidence (certifications, pilots,
  deployments, case studies, awards, patents), each independently verifiable.
- A Startup Passport is **auto-created** the moment a STARTUP user registers
  (signal off `accounts.StartupProfile`), seeded from the registration data,
  then evolves independently. `python manage.py backfill_passports` retroactively
  creates passports for any pre-existing StartupProfile rows.
- Self-service endpoints for the owning startup; read-only browsing for any
  authenticated user; verification is government-only and stamps
  `verified_by` / `verified_at` (Claim -> Evidence -> Verification, spec §26).
  Verified evidence becomes immutable to the startup (edit/delete blocked).
- Verified end-to-end: passport auto-seed, self-edit, evidence submission,
  government-only verify (403 for a startup trying to self-verify), immutability
  after verification, and cross-role write boundaries (government can't edit
  a passport; a startup can't verify).

## Endpoints — startups
```
GET   /api/startups/                              browse passports (any authenticated user)
GET   /api/startups/{id}/                         passport detail + evidence (any authenticated user)
GET   /api/startups/{id}/evidence/                 a startup's evidence, read-only (e.g. gov review)
GET/PATCH /api/startups/passport/                  own passport (startup only)
GET/POST  /api/startups/passport/evidence/         own evidence list/create (startup only)
GET/PATCH/DELETE /api/startups/passport/evidence/{evidence_id}/   own evidence (blocked once verified)
POST  /api/startups/evidence/{evidence_id}/verify/  { "verified": true|false } (government only)
```

## Next
Phase 3 — `challenges` app: Challenge CRUD, status lifecycle, government permissions.
# SIH_2026_backend
