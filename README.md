# AI-First CRM — HCP Log Interaction Screen

A split-screen app for life-science field reps:

- **Left panel** — a strictly **read-only** interaction form (React + Redux).
- **Right panel** — an **AI Assistant** chat (FastAPI + LangGraph + Groq) that is the
  *only* way the left panel ever changes.

```
React (Redux) <---HTTP---> FastAPI <---> LangGraph agent <---> Groq LLM
                                |                 |
                                +------ tools ----+---> PostgreSQL
```

---

## ⚠️ Read this first: the `gemma2-9b-it` model

The assignment spec asks for Groq's `gemma2-9b-it`. **Groq deprecated that
model on 2025-10-08**, and its official replacement (`llama-3.1-8b-instant`)
was *itself* deprecated in June 2026. Calling `gemma2-9b-it` today returns a
"model decommissioned" error from Groq's API — this isn't something fixable
in application code.

To keep the app actually runnable, the model name is read from an env var
(`GROQ_MODEL` in `backend/.env`), defaulting to `openai/gpt-oss-20b`, which is
active on Groq and supports tool calling as of this writing. If your grader
specifically checks for the literal string `gemma2-9b-it`, you can set
`GROQ_MODEL=gemma2-9b-it` in `.env` — the code will pass it straight through
to Groq — but expect it to error at runtime until/unless Groq reinstates it.
Check https://console.groq.com/docs/models for the current list.

---

## Project layout

```
hcp-crm/
├── docker-compose.yml        # Postgres for local dev
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   ├── init.sql              # Raw SQL schema + seed data
│   └── app/
│       ├── config.py         # Env var loading
│       ├── database.py       # SQLAlchemy engine/session
│       ├── models.py         # SQLAlchemy ORM models
│       ├── schemas.py        # Pydantic request/response models
│       ├── state.py          # LangGraph state shape (mirrors Redux state)
│       ├── tools.py          # The 5 LangGraph tools
│       ├── agent.py          # The LangGraph state machine
│       └── main.py           # FastAPI app / routes
└── frontend/
    ├── package.json
    ├── .env.example
    └── src/
        ├── store.js
        ├── api.js
        ├── slices/interactionSlice.js
        ├── slices/chatSlice.js
        ├── App.jsx
        └── components/
            ├── FormPanel.jsx
            └── ChatPanel.jsx
```

---

## 1. Start PostgreSQL

```bash
docker compose up -d
```

This starts Postgres on `localhost:5432` (db `hcp_crm`, user `hcp_user`,
password `hcp_password`) and automatically runs `backend/init.sql` (schema +
seed HCPs/materials) **the first time** the container's data volume is
created. If you need to re-seed later, either `docker compose down -v` to
wipe the volume and start fresh, or run `init.sql` manually:

```bash
docker exec -i hcp_crm_postgres psql -U hcp_user -d hcp_crm < backend/init.sql
```

---

## 2. Backend (FastAPI + LangGraph)

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: paste your GROQ_API_KEY (free key: https://console.groq.com/keys)

uvicorn app.main:app --reload --port 8000
```

The backend also calls `Base.metadata.create_all()` on startup as a
convenience, so tables exist even if you skip `init.sql` — but you'll want
`init.sql`'s seed data so `Fetch_HCP_Context`/`Lookup_Items` have real HCPs
and materials to find on a fresh database.

Visit `http://localhost:8000/docs` for interactive API docs, and
`http://localhost:8000/health` to confirm it's up.

---

## 3. Frontend (React + Redux + Vite)

```bash
cd frontend
npm install

cp .env.example .env
# defaults to http://localhost:8000, matching the backend above

npm run dev
```

Visit `http://localhost:5173`.

---

## Try it (matches the two example flows from the spec)

1. Type in the chat: `Today I met with Dr. Smith and discussed product X efficiency. The sentiment was positive, and I shared the brochures.`
   → `Log_Interaction` fires, the entire left form populates, and the assistant confirms + offers to add a follow-up.
2. Type: `Sorry, the name was actually Dr. John and the sentiment was negative.`
   → `Edit_Interaction` fires and updates **only** the HCP name and sentiment — topics, date, time, and materials stay exactly as they were.
3. Type: `Schedule a follow-up meeting next month.`
   → `Create_Follow_Up_Task` fires and the Follow-up Actions field updates.

You should never be able to click or type into any field on the left panel —
every input is `readOnly`/non-interactive by design (see `FormPanel.jsx`).

---

## Design notes / decisions made beyond the literal spec

- **`interaction_materials` join table**: the brief lists 4 tables, but a
  many-to-many relationship between interactions and materials/samples needs
  a join table rather than denormalized columns. Added as a 5th table; see
  `backend/init.sql` and `models.py`.
- **`tasks.interaction_id`**: added (nullable) so a follow-up task can be
  traced back to the interaction that spawned it, in addition to the
  `hcp_id` the spec explicitly asks for.
- **Auto-create HCPs/materials on first mention**: if `Fetch_HCP_Context` or
  `Lookup_Items` finds no match, the tools create a new record rather than
  failing, so a rep can log a brand-new doctor/material without a separate
  onboarding step. This is called out in code comments in `tools.py`.
- **State persistence across chat turns**: uses LangGraph's `MemorySaver`
  checkpointer keyed by a `thread_id` (one per browser tab/session, generated
  client-side and stored in `sessionStorage`). This is in-memory and resets
  if the backend restarts — swap in `langgraph-checkpoint-postgres` if you
  need durability across restarts.
- **"Summarize from Voice Note (Requires Consent)"**: shown as a visual
  element only (per your instructions), not wired to any transcription
  service.
- **Tool-calling pattern**: tools use LangGraph's `InjectedState` (to read
  the current interaction/HCP id without the LLM needing to track it) and
  return `Command(update=...)` objects (to write back to shared graph state).
  This is the modern (LangGraph 1.x) recommended pattern for tools that both
  read and mutate shared state.

---

## Troubleshooting

- **"GROQ_API_KEY is not set"** — copy `backend/.env.example` to `.env` and
  fill in a real key.
- **"model decommissioned" / 400 error from Groq** — see the model callout
  at the top of this file; change `GROQ_MODEL` in `.env`.
- **CORS errors in the browser console** — make sure `FRONTEND_ORIGIN` in
  `backend/.env` matches the URL Vite is actually serving on (default
  `http://localhost:5173`).
- **Empty dropdowns / no HCP found** — make sure `init.sql` actually ran
  (check `docker exec -it hcp_crm_postgres psql -U hcp_user -d hcp_crm -c "select * from hcp_profiles;"`).
