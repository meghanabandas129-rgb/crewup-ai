# CrewUp AI — Phases 2–5 upgrade

## What this update adds

**Phase 2: Model-backed AI + tools**
- `/api/ai/crew-builder` uses structured skill ranking and, when configured, a real locally hosted **Ollama** model to explain matched teammates.
- `/api/ai/crews/{crew}/copilot` selects allowlisted, **read-only** backend tools based on the user's question, checks membership before querying data, and sends retrieved results to Ollama for grounded responses. When the model is unavailable it returns transparent deterministic summaries.
- `/api/ai/crews/{crew}/plan` generates a suggested project task plan (never silently writes tasks).
- `/api/ai/status` reports whether AI is configured. **AI_ENABLED=false is the safe default.**
- No AI tool can approve task transfers, add users to crews, or reveal travel plans. Existing approval routes remain authoritative.

**Phase 3: UI**
- New **AI Copilot** screen in the existing responsive sidebar, with a project copilot, Crew Builder, and project planner.
- Readable results, engine labels, tool provenance, responsive layout, keyboard focus styling, and reduced-motion support.
- The original Events, Radar, Crews, Workspace, handover and Travel Radar screens remain in place.

**Phase 4: Testing and security foundation**
- Added `backend/test_ai.py`, alongside existing `test_api.py` and `test_travel.py`.
- Production mode (`ENVIRONMENT=production`) blocks launching with the repository's development JWT secret.
- The AI endpoint restricts crew context to authenticated crew members and excludes email/contact fields from matching responses.
- **Still required before public launch:** address npm audit findings, use a dedicated secret manager, improve token storage and session controls, rate-limit authentication, configure TLS and monitoring, add end-to-end browser tests, and turn off demo data/credentials.

**Phase 5: PostgreSQL readiness (migration materials, NOT a live DB switch)**
- `deployment/postgres_schema.sql` creates equivalent tables and several indexes on managed PostgreSQL.
- `deployment/export_sqlite.py` exports the existing SQLite data into a *private* JSON snapshot.
- `deployment/import_postgres.py` imports an export into an **empty** schema, using optional `psycopg`.
- Important: the running API **still uses SQLite**. The runtime DB adapter must be converted to PostgreSQL and tested before deploying against a PostgreSQL instance. These migration files are preparation, not a production cutover.

## Local Windows setup

Extract ZIP into a NEW folder, for example `Downloads\crewup-ai-v2\crewup-ai`.

### Backend, clean virtual environment (Windows PowerShell 5.1)

```powershell
cd "$HOME\Downloads\crewup-ai-v2\crewup-ai\backend"
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

### Frontend (second terminal)

```powershell
cd "$HOME\Downloads\crewup-ai-v2\crewup-ai\frontend"
npm install
npm run build
npm run dev
```

Open `http://localhost:5173`, log in to your newly registered account, select a crew, then click **AI Copilot**.

### Enable an actual local LLM (optional, recommended for Phase 2 demo)

Install Ollama from its official website, then in a **third** terminal:

```powershell
ollama pull qwen2.5:3b
ollama serve
```

If `ollama serve` says the port is already in use, Ollama is likely already running; do not start a second instance.

In the **backend** terminal, stop the server with Ctrl+C and restart it with:

```powershell
$env:AI_ENABLED="true"
$env:OLLAMA_MODEL="qwen2.5:3b"
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

Results show `engine: ollama` if inference succeeds. If the model is unavailable or times out, `engine: rules_fallback` is intentional and clearly disclosed. Tool data is transmitted to the configured Ollama server; keep that server local if your crew data must remain on your computer.

### Run backend tests (with server stopped, same backend folder)

```powershell
.\.venv\Scripts\python.exe test_api.py
.\.venv\Scripts\python.exe test_travel.py
.\.venv\Scripts\python.exe test_ai.py
```

### After those tests: Phase 6

1. Run `npm audit`, resolve actual findings without `--force` until compatibility is checked.
2. Run full frontend build and cross-account browser regression tests.
3. Move runtime data and permissions to managed PostgreSQL; test a copy of your data first. Do **not** commit migration snapshots or your old SQLite database.
4. Configure production secrets, CORS origins, authentication protections, and remove or disable demo accounts.
5. Push a clean repository to GitHub, deploy frontend to Vercel, and deploy FastAPI to a persistent backend host.
6. Test all endpoints from the public domain and verify user privacy before inviting real users.

## Verification in authoring environment

- Backend regression scripts: `test_api.py`, `test_travel.py`, `test_ai.py` passed.
- Python syntax compilation passed.
- Frontend `npm install` timed out because dependencies could not be retrieved in this environment. **Frontend production build and browser UI were not independently verified here.**
- Real Ollama inference and live PostgreSQL connectivity were not tested here.
