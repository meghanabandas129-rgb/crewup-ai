# CrewUp AI — Social Radar + TeamFlow Collaboration

A full-stack **hackathon MVP** unifying people and event discovery with team workspaces, project boards, explainable matching and a two-stage task-handover approval process.

## Included features

- **Accounts**: sign-up/sign-in, editable profiles, password hashing, JWT sessions.
- **Discover events**: browsable demo events with categories and filters. Demo events are **illustrative**, not scraped or verified live listings.
- **Social Radar**: explainable, rules-based people recommendations using complementary skills, shared skills, and city. Scores are illustrative, not real predictive AI probabilities.
- **Travel Radar**: event-specific opt-in departure city / date matching, route-fit indicators, mutual connection requests with acceptance or rejection, and easy opt-out. No precise location or phone-number exposure.
- **Crews**: create crews, request to join, owner approval, member roles.
- **TeamFlow workspace**: projects represented by crew workspaces, Kanban task board, status changes, priorities, task skills, member views, activity logs, crew chat.
- **Intelligent handover**: rank possible replacements by skill overlap and current workload; assignee requests transfer, candidate accepts, owner approves, reassignment is committed with a preserved audit trail.
- **AI Insights**: data-derived progress summaries, pending transfers, overdue tasks, and workload indicators. Does not use an LLM by default.
- **Responsive dark UI**: desktop and mobile layouts.

## Requirements

- Node.js >= 20.19 and npm (frontend; installation requires access to npm registry)
- Python >= 3.10 (backend)

## Local setup

**Terminal 1 — backend**

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# For a real deployment, set JWT_SECRET to a random 32+ character value.
uvicorn main:app --reload --port 8000
```

Backend docs: http://localhost:8000/docs

**Terminal 2 — frontend**

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 . Development proxy forwards `/api` requests to backend at `127.0.0.1:8000`.

Demo accounts (for local testing only):

| Account | Email | Password | Role in seeded crew |
|---|---|---|---|
| Aarav | aarav@demo.crewup | demo1234 | Crew owner |
| Ishita | ishita@demo.crewup | demo1234 | Member |
| Rohan | rohan@demo.crewup | demo1234 | Member |

**Test approval flow:** Log in as Ishita, open Pixel Pioneers and task "Build matching API", request transfer to Rohan. Sign out and log in as Rohan to accept. Sign out and log in as Aarav to approve. Re-open the task and verify ownership. Login switch is deliberate to test role checks.

## Environment configuration

- Frontend: copy `frontend/.env.example` to `frontend/.env` and configure `VITE_API_URL` when the API is deployed. Leave blank for local Vite proxy.
- Backend: use environment variables `JWT_SECRET`, `CORS_ORIGINS`, and `DATABASE_PATH`. Copying `.env.example` is illustrative: **the backend does not automatically load `.env`**; export these variables in your shell or configure them in your host dashboard.
- Backend persistence defaults to a local SQLite file. For production, move to a persistent managed database. SQLite files on ephemeral free hosting may be deleted on restart.

## Deployment

### Frontend on Vercel

1. Push this repository to GitHub.
2. In Vercel import the repo, set root directory to `frontend`.
3. Framework preset: Vite. Build command: `npm run build`; output directory: `dist`.
4. Set `VITE_API_URL=https://your-public-fastapi-host.example` in Vercel environment variables.
5. Redeploy and ensure browser requests reach the backend URL.

### Backend

Deploy the `backend` folder to a Python-capable host with:

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Set `JWT_SECRET` to a strong random value and `CORS_ORIGINS` to the **exact** frontend HTTPS origin. Configure **persistent storage** or migrate the SQLite models to Postgres before real use.

**Vercel alone does not host this stateful SQLite API reliably as-is.** Deploy the frontend to Vercel and the API to a compatible persistent backend host.

## Architecture

```text
React / TypeScript / Vite  (frontend)
          | HTTPS REST + JWT
          v
FastAPI (backend)
  |-- Auth and crew permissions
  |-- Event and profile queries
  |-- Deterministic match/ranking engine
  |-- Tasks, chat and insight calculations
  |-- Two-stage handover approval
          |
          v
SQLite database (local MVP)
```

## Security / production limitations

- This is a **demo-quality MVP**, not production security-certified software. The seeded accounts and simple email/password login are for demonstration, not real participants.
- No live event feed, private travel itinerary matching, payment processing, push notifications, GPS tracking, real-time sockets, email verification, OAuth, attachments, or LLM provider is included.
- Matching and insight recommendations are **deterministic, explainable heuristics**, not model-trained predictions or autonomous Agentic AI.
- Chat refreshes after messages; there is no live socket subscription.
- Add rate limiting, password reset, email verification, HTTPS enforcement, stronger input validation and migrations before public launch.
- Prevent demo seed users on any public deployment and replace the default JWT secret. Review the `init()` seed logic and auth settings before exposing the API.
- CodeVerse submission must match the competition's official problem statement and actual development rules; the sample events and this README do not establish event eligibility.

## Tests

With backend dependencies installed:

```bash
cd backend
pip install httpx  # FastAPI TestClient dependency, if absent
python test_api.py
```

Front-end build:

```bash
cd frontend
npm install
npm run build
```

## Travel matching privacy

Travel Radar is **off by default**. Members need to share a plan for a specific event to see matches who opted into the same event. Only departure city, travel date, mode, and display name appear, not exact route, live GPS, address, email, or phone. Connection requests require recipient approval. This is social discovery, not verified transport booking or identity verification.

## Phases 2–5 upgrade

See **[PHASES_2_TO_5.md](PHASES_2_TO_5.md)** for updated Windows commands, model-backed AI features, security and testing checks, PostgreSQL migration tools, and remaining production deployment work. The AI service is opt-in and defaults to a rules-based fallback until `AI_ENABLED=true` and a local Ollama model are available. PostgreSQL files are migration materials: the active API remains on SQLite until a database adapter is implemented and tested.
