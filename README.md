# Civora

This repository contains both the backend and frontend for the SIH 2026 government-startup innovation platform. The backend is built with Django and Django REST Framework, and the frontend is a client app that consumes the API for authentication, challenge management, evaluations, and pilot workflows.

## Project Overview

The platform supports the full workflow from challenge publication to startup selection and pilot management:

- Government users create and manage challenges
- Startups register and apply to relevant challenges
- Applications are checked for eligibility
- AI-assisted and human evaluations assess submissions
- Selected applications move into pilot execution
- Milestones, evidence, KPIs, and outcome decisions are tracked

## Tech Stack

### Backend
- Python
- Django
- Django REST Framework
- PostgreSQL
- JWT authentication
- Ollama for local AI workflows

### Frontend
- React / Vite-based frontend app
- API-based integration with the Django backend
- Role-based UI flows for government and startup users

## Project Structure

```text
SIH_2026_backend/
├── accounts/                # authentication, users, profiles
├── challenges/              # challenge models and APIs
├── config/                  # project settings and URL routing
├── evaluations/             # eligibility and evaluation flow
├── intelligence/            # AI, trust graph, analysis logic
├── pilots/                  # pilot lifecycle, milestones, evidence
├── startups/                # startup data and related APIs
├── manage.py                # Django project entrypoint
├── requirements.txt         # Python dependencies
├── PILOT_API_ENDPOINTS.md   # pilot API reference notes
├── sih_2026_backend/        # local virtual environment
├── .env                     # environment variables
├── .gitignore
├── README.md
└── ...
```

## Setup

### 1. Create or activate a virtual environment

```bash
cd /Users/manishisingh/Downloads/SIH_2026_backend
python3 -m venv .venv
source .venv/bin/activate
```

Or use the existing project environment:

```bash
cd /Users/manishisingh/Downloads/SIH_2026_backend
source sih_2026_backend/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Set up your database and application settings in a local `.env` file or environment variables as required by the project.

### 4. Apply database migrations

```bash
python manage.py migrate
```

### 5. Run the backend

```bash
python manage.py runserver
```

### 6. Run the frontend

Run the frontend app separately from its own project directory using the framework's normal dev command (for example, Vite-based app):

```bash
npm install
npm run dev
```

## Main Modules

### `accounts`
Handles user login, signup, role-based access, and profile management.

### `challenges`
Contains challenge models, serializers, views, and business rules for government challenge management.

### `evaluations`
Handles application eligibility checks and evaluation scoring workflows.

### `pilots`
Covers pilot setup, pilot actions, milestones, evidence, KPI tracking, risk checks, and outcome decisions.

### `startups`
Contains startup and startup-passport-related data and APIs.

### `intelligence`
Includes AI-powered services, trust graph logic, scrapers, and analysis features.

### `config`
Project-level Django configuration, settings, and URL routing.

## Notes

- This project includes both backend and frontend work.
- The frontend communicates with the backend through API endpoints.
- JWT is used for authentication.
- Some features depend on local AI services and environment configuration.

## Purpose

The platform is meant to streamline the journey from problem statement to startup selection, pilot delivery, and outcome tracking in a structured, auditable way.
