# AtomQuest Goal Portal

## Overview

AtomQuest is a full-stack performance goal portal for organizations. Employees set weighted annual goals, managers approve them, and both sides track quarterly check-ins with automated progress scoring. Admins manage users, cycles, audit trails, and organization-wide analytics.

## Tech Stack

- **Frontend:** React 19, Vite, Tailwind CSS 4, shadcn/ui, Recharts, Axios
- **Backend:** FastAPI, SQLAlchemy, Pydantic
- **Database:** PostgreSQL (Supabase-compatible)
- **Auth:** JWT + Google OAuth (SSO)
- **Email:** SendGrid transactional notifications

## Running with Docker

```bash
docker-compose up --build
```

Then open http://localhost

API docs at http://localhost/api/docs

Seed demo users (once the stack is up):

```bash
curl -X POST http://localhost/api/auth/seed
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL or Supabase project

### Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # set DATABASE_URL and SECRET_KEY
uvicorn main:app --reload --port 8000
```

Seed demo users (once):

```bash
curl -X POST http://localhost:8000/api/auth/seed
```

API docs: http://localhost:8000/docs

### Frontend Setup

```bash
cd frontend
npm install
cp .env.example .env        # VITE_API_URL=http://localhost:8000/api
npm run dev
```

App: http://localhost:5173

### Demo Credentials

| Role     | Email                 | Password    |
|----------|-----------------------|-------------|
| Admin    | admin@atomquest.com   | admin123    |
| Manager  | manager@atomquest.com | manager123  |
| Employee | priya@atomquest.com   | emp123      |

Use the **floating role switcher** (bottom-right) to jump between demo accounts without retyping credentials.

## Architecture

- **Role-based routing:** Employee, manager, and admin UIs share `AppLayout` with role-specific navigation.
- **Goal lifecycle:** Draft → submitted → approved/returned; approved goals lock until admin unlock.
- **Scoring engine:** Shared logic for numeric min/max, timeline, and zero-based UoM types in `backend/utils.py` and `frontend/src/utils/scoreCalculator.js`.
- **Audit trail:** All admin and workflow actions logged for compliance.
- **Analytics layer:** Aggregated quarter trends, thrust-area performance, manager effectiveness, and heatmaps via `/api/admin/analytics/*`.

## Features Implemented

- [x] Goal Creation & Validation (multi-step form, weightage bar)
- [x] Manager Approval Workflow
- [x] Quarterly Check-ins
- [x] Admin Panel (users, cycles, audit logs)
- [x] Analytics Dashboard
- [x] Audit Trail
- [x] Achievement Reports (CSV Export)
- [x] Role Switcher (Demo Mode)
- [x] Employee & Manager Progress Reports
- [x] Toast notifications & global layout polish

## Key Routes

| Role     | Path                      |
|----------|---------------------------|
| Employee | `/employee/dashboard`     |
| Employee | `/employee/goals/new`     |
| Employee | `/employee/checkins`    |
| Employee | `/employee/progress`      |
| Manager  | `/manager/dashboard`      |
| Manager  | `/manager/team-progress`  |
| Admin    | `/admin/analytics`        |
| Admin    | `/admin/reports`          |

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing secret |
| `CORS_ORIGINS` | Comma-separated frontend origins |
| `ENV` | `development` or `production` (controls error detail) |
| `SENDGRID_API_KEY` | SendGrid API key for email notifications |
| `SENDGRID_FROM_EMAIL` | Verified sender email in SendGrid |
| `SENDGRID_FROM_NAME` | Display name for outgoing emails |
| `FRONTEND_URL` | Portal URL for links in emails (e.g. `http://localhost:5173`) |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID (SSO) |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | OAuth callback URL (`http://localhost:5173/auth/callback`) |
| `HR_EMAIL` | HR contact for critical escalations |

### Frontend (`frontend/.env`)

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Backend API base (e.g. `http://localhost:8000/api`) |

### Google OAuth Setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project: **AtomQuest**
3. Go to **APIs & Services** → **Credentials**
4. Create **OAuth 2.0 Client ID**
5. Application type: **Web application**
6. Authorized redirect URIs:
   - `http://localhost:5173/auth/callback`
   - `http://localhost/auth/callback` (when using Docker on port 80)
7. Copy **Client ID** and **Client Secret** to `backend/.env`

### SendGrid Setup

1. Create a [SendGrid](https://sendgrid.com) account
2. Verify a sender email under **Settings** → **Sender Authentication**
3. Create an API key with **Mail Send** permission
4. Add `SENDGRID_API_KEY` and `SENDGRID_FROM_EMAIL` to `backend/.env`

Emails are sent automatically when goals are submitted, approved, returned, and when escalations are created.
