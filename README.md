# Loss Run Process

Full-stack app for insurance loss-run triage:
- Backend: FastAPI + LangGraph + Gemini extraction + SQLite
- Frontend: React + Vite workflow UI for upload, HITL review, and final delivery

## Prerequisites

- Python 3.11+ (tested with 3.12)
- Node.js 18+
- Gemini API key

## Backend Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python -m pip install .[dev]
Copy-Item .env.example .env
```

Set `backend/.env` values, especially:
- `GEMINI_API_KEY`
- `GEMINI_MOCK_MODE=false` for real extraction (`true` for local mock mode)

Run DB migrations:

```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python -m alembic upgrade head
```

Start backend:

```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Health check:

```powershell
curl http://localhost:8000/health
```

## Frontend Setup

```powershell
cd frontend
npm ci
npm run dev
```

Frontend runs on `http://localhost:5173`.

## Running Process

1. Open `http://localhost:5173`
2. Select 1-10 PDF files
3. Click `Start Workflow`
4. On the workflow page, click `Start Draft Generation`
5. The UI shows extraction and processing progress
6. When the draft is ready, the screen switches to HITL review
7. Approve as-is, approve with edits, or reject for regeneration
8. After approval, the final result screen appears and the PDF is available for download

## Tests

```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python -m pytest -q
```
