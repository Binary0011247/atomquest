# AtomQuest Goal Portal

**🌐 Live Demo**	atomquest-rho.vercel.app
**📚 API Documentation**	https://atomquest-production-56d3.up.railway.app/api/docs
**📄 Full Submission Document** https://atomquest-production-56d3.up.railway.app/

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







