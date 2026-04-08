# Loss Run Triage Agent — Enterprise Workflow Plan

## Architecture Decisions (Pre-Sprint)

### Where Gemini Is Used (and Where It Isn't)

| Stage | Technology | Reason |
|---|---|---|
| PDF → ClaimsArray | Gemini 2.5 Flash (Files API, structured output) | Native document intelligence, no OCR layer |
| Data normalization | Pure Python | Deterministic schema mapping |
| Statistical analytics | pandas + numpy | Zero ambiguity in math |
| Red flag detection | Pure Python rules engine | Hard thresholds = zero false positives |
| Red flag explanation | Gemini 2.5 Flash | Only narrativizes confirmed flags |
| Underwriter summary | Gemini 2.5 Flash | Narrative generation from structured data |
| Carrier/LOB detection | Regex + lookup table (no LLM) | Carrier codes in filenames + headers are deterministic |

> **Critical principle:** Gemini never decides whether a red flag exists. Python rules decide. Gemini only writes the sentence explaining a flag that has already been confirmed deterministically.

---

### Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI + Uvicorn |
| Pipeline Orchestration | LangGraph (StateGraph with HITL interrupt) |
| LLM | google-generativeai → gemini-2.5-flash-preview |
| Analytics | pandas, numpy |
| Database | SQLite via SQLAlchemy (zero-setup local) |
| File Storage | Local filesystem (configurable base path) |
| PDF Generation | WeasyPrint (HTML template → PDF) |
| Charts | matplotlib (server-side, embedded in PDF + returned as base64) |
| Frontend | React 18 + TypeScript + Vite + TailwindCSS + shadcn/ui |
| HTTP Client (FE) | axios + React Query (TanStack Query v5) |
| Real-time status | Server-Sent Events (SSE) |
| Validation | Pydantic v2 (BE) + Zod (FE) |
| Env management | python-dotenv |

---

### Project Folder Structure

```
loss-run-triage/
├── backend/
│   ├── app/
│   │   ├── main.py                        # FastAPI app, CORS, lifespan
│   │   ├── config.py                      # Settings via pydantic-settings
│   │   ├── database.py                    # SQLAlchemy engine + session
│   │   │
│   │   ├── models/                        # SQLAlchemy ORM models
│   │   │   ├── job.py                     # Job, JobFile
│   │   │   └── hitl.py                    # HitlAction audit log
│   │   │
│   │   ├── schemas/                       # Pydantic v2 schemas
│   │   │   ├── claims.py                  # Claim, ClaimsArray, PolicyPeriod
│   │   │   ├── analytics.py               # AnalyticsResult, YearlyStats
│   │   │   ├── redflags.py                # RedFlag, RedFlagReport
│   │   │   ├── summary.py                 # UnderwriterSummary
│   │   │   └── jobs.py                    # JobCreate, JobResponse, JobStatus
│   │   │
│   │   ├── api/
│   │   │   ├── deps.py                    # DB session dependency
│   │   │   └── routes/
│   │   │       ├── jobs.py                # Upload, create, list, trigger
│   │   │       ├── hitl.py                # Queue, approve, edit, reject
│   │   │       ├── outputs.py             # Summary, PDF, claims, redflags
│   │   │       └── stream.py              # SSE job status stream
│   │   │
│   │   ├── pipeline/
│   │   │   ├── state.py                   # PipelineState TypedDict
│   │   │   ├── graph.py                   # LangGraph StateGraph definition
│   │   │   └── nodes/
│   │   │       ├── ingest.py              # File validation, job prep
│   │   │       ├── extract.py             # Gemini Files API + structured output
│   │   │       ├── normalize.py           # Multi-carrier schema normalization
│   │   │       ├── analytics.py           # pandas stats engine
│   │   │       ├── redflags.py            # Deterministic rules engine
│   │   │       ├── summary.py             # Gemini narrative generation
│   │   │       ├── hitl_gate.py           # LangGraph interrupt node
│   │   │       └── deliver.py             # PDF generation + job finalization
│   │   │
│   │   ├── prompts/
│   │   │   ├── extraction.py              # Carrier-aware extraction prompt
│   │   │   └── summary.py                 # Underwriter narrative prompt
│   │   │
│   │   └── services/
│   │       ├── gemini_client.py           # Gemini wrapper (upload + generate)
│   │       ├── pdf_generator.py           # WeasyPrint HTML→PDF
│   │       ├── chart_generator.py         # matplotlib charts → base64
│   │       └── storage.py                 # Local file I/O service
│   │
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── test_analytics.py
│   │   │   ├── test_redflags.py
│   │   │   └── test_normalize.py
│   │   └── integration/
│   │       └── test_pipeline.py
│   │
│   ├── pyproject.toml
│   ├── .env.example
│   └── alembic/                           # DB migrations
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api/
│   │   │   ├── client.ts                  # axios instance
│   │   │   ├── jobs.ts                    # job API calls
│   │   │   ├── hitl.ts                    # HITL API calls
│   │   │   └── outputs.ts                 # output API calls
│   │   ├── types/
│   │   │   ├── job.ts
│   │   │   ├── claims.ts
│   │   │   ├── analytics.ts
│   │   │   └── redflags.ts
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── NewJob.tsx
│   │   │   ├── JobDetail.tsx
│   │   │   ├── HitlQueue.tsx
│   │   │   └── HitlReview.tsx
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── AppShell.tsx
│   │   │   │   └── Sidebar.tsx
│   │   │   ├── jobs/
│   │   │   │   ├── JobCard.tsx
│   │   │   │   ├── PipelineTracker.tsx    # Stage progress with SSE
│   │   │   │   └── FileUploadZone.tsx
│   │   │   ├── hitl/
│   │   │   │   ├── QueueItem.tsx          # Color-coded card
│   │   │   │   ├── SummaryEditor.tsx      # Editable narrative
│   │   │   │   └── RedFlagPanel.tsx
│   │   │   └── output/
│   │   │       ├── ClaimsTable.tsx
│   │   │       ├── AnalyticsPanel.tsx
│   │   │       └── TrendChart.tsx
│   │   └── hooks/
│   │       ├── useJobStream.ts            # SSE hook
│   │       └── useHitlQueue.ts
│   ├── package.json
│   └── vite.config.ts
│
└── samples/                               # Your existing sample PDFs
```

---

### LangGraph Pipeline Graph

```
[ingest] → [extract] → [normalize] → [analytics] → [redflags] → [summary] → [HITL interrupt] → [deliver]
                                                                                      ↓ (rejected)
                                                                                  [summary] (retry)
```

HITL uses LangGraph's native `interrupt()` — pipeline pauses, writes state to SQLite checkpoint, resumes on API call from frontend approval.

---

### API Contract

```
# Jobs
POST   /api/v1/jobs/                       Upload PDFs + create job
GET    /api/v1/jobs/                       List jobs (paginated)
GET    /api/v1/jobs/{job_id}               Job detail + current stage
POST   /api/v1/jobs/{job_id}/run           Trigger pipeline execution
GET    /api/v1/jobs/{job_id}/stream        SSE — live stage updates

# HITL
GET    /api/v1/hitl/queue                  Pending review items
GET    /api/v1/hitl/{job_id}               Full draft for review
POST   /api/v1/hitl/{job_id}/approve       Resume pipeline as-is
POST   /api/v1/hitl/{job_id}/edit          Submit edits + approve
POST   /api/v1/hitl/{job_id}/reject        Reject → re-run summary node

# Outputs
GET    /api/v1/outputs/{job_id}/claims     ClaimsArray JSON
GET    /api/v1/outputs/{job_id}/analytics  Analytics + metrics JSON
GET    /api/v1/outputs/{job_id}/redflags   RedFlagReport JSON
GET    /api/v1/outputs/{job_id}/summary    Final narrative JSON
GET    /api/v1/outputs/{job_id}/pdf        Download PDF (binary)
GET    /api/v1/outputs/{job_id}/charts     Chart images (base64 JSON)
```

---

## Sprint Plan

---

## Current Repo Status (2026-04-08)

### Implementation Snapshot

- Phase 1: In progress (core backend scaffold, models, schemas, storage, jobs route, Gemini client, extraction prompt, graph/state, and extract node are implemented)
- Phase 2: In progress (normalize and analytics nodes implemented; red flags node and tests not implemented)
- Phase 3: Not started except prompt scaffold (`prompts/summary.py` exists)
- Phase 4: Not started (HITL, stream, outputs routes/nodes missing)
- Phase 5: Not started (no frontend scaffold in this repo)
- Phase 6: Not started (validation/performance hardening pending)

### Known Blocking Gaps

- `backend/app/main.py` imports `hitl`, `outputs`, and `stream` routes that are not present under `backend/app/api/routes/`
- `backend/app/pipeline/graph.py` imports `redflags`, `summary`, `hitl_gate`, and `deliver` nodes that are not present under `backend/app/pipeline/nodes/`
- `backend/app/api/routes/jobs.py` references `app.pipeline.runner.run_pipeline`, but `runner.py` is not present

## Phase 1 — Foundation + Gemini Extraction

**Goal:** Working pipeline from PDF upload → structured ClaimsArray JSON stored in DB

### 1.1 Project Scaffold

- [x] Create `backend/` directory, init `pyproject.toml` with uv or pip
- [x] Add dependencies: `fastapi`, `uvicorn[standard]`, `sqlalchemy`, `alembic`, `pydantic-settings`, `python-dotenv`, `google-generativeai`, `langgraph`, `pandas`, `numpy`, `aiofiles`, `python-multipart`
- [x] Create `backend/app/config.py` — Settings class via pydantic-settings:
  - `GEMINI_API_KEY`
  - `STORAGE_BASE_PATH` (default: `./data/jobs`)
  - `DATABASE_URL` (default: `sqlite:///./loss_run.db`)
  - `GEMINI_MODEL` (default: `gemini-2.5-flash-preview`)
- [x] Create `backend/app/database.py` — SQLAlchemy engine, SessionLocal, Base, get_db dependency
- [ ] Create `backend/.env.example` with all required keys
- [x] Create `backend/app/main.py` — FastAPI app with CORS (`*` for local dev), lifespan hook to create DB tables
- [ ] Verify: `uvicorn app.main:app --reload` starts with 200 on `/health`

### 1.2 Database Models

- [x] Create `backend/app/models/job.py`:

```
Job:     id (uuid), insured_name, status (enum: pending/running/hitl_pending/
         completed/failed), current_stage, created_at, completed_at, error_message
JobFile: id, job_id (FK), filename, file_path, carrier_code, lob_code,
         policy_period_start, policy_period_end, extraction_status
```

- [x] Create `backend/app/models/hitl.py`:

```
HitlAction: id, job_id (FK), action (approve/edit/reject), user_id,
            timestamp, edit_content, reason
```

- [x] Create `backend/app/models/output.py`:

```
JobOutput: id, job_id (FK, unique), claims_json, analytics_json,
           redflags_json, draft_summary, final_summary, pdf_path,
           charts_json, created_at, updated_at
```

- [ ] Run `alembic init alembic`, configure `env.py` to use `Base.metadata`, create initial migration, `alembic upgrade head`

### 1.3 Pydantic Schemas

- [x] Create `backend/app/schemas/claims.py`:

```python
class Claim(BaseModel):
    claim_id: str
    carrier_code: str
    lob: Literal["GL", "CA", "WC", "PROP", "PL", "UMB"]
    policy_period: str           # "2023-01-01/2024-01-01"
    occurrence_date: date | None
    close_date: date | None
    status: Literal["open", "closed"]
    claim_type: str              # "slip-and-fall", "auto collision", etc.
    description: str
    amount_paid: Decimal
    amount_reserved: Decimal
    amount_incurred: Decimal     # paid + reserved
    earned_premium: Decimal | None
    subrogation_potential: bool
    litigation_flag: bool        # set by normalize, not LLM

class PolicyPeriodSummary(BaseModel):
    carrier_code: str
    lob: str
    period: str
    earned_premium: Decimal
    claims: List[Claim]

class ClaimsArray(BaseModel):
    job_id: str
    insured_name: str
    policy_periods: List[PolicyPeriodSummary]
    extraction_notes: List[str]  # per-file warnings from Gemini
```

- [x] Create `backend/app/schemas/analytics.py`:

```python
class YearlyStats(BaseModel):
    year: int
    claim_count: int
    total_incurred: Decimal
    total_paid: Decimal
    total_reserved: Decimal
    earned_premium: Decimal
    loss_ratio: Decimal          # incurred / premium
    loss_frequency: Decimal      # claims per $1M premium
    loss_severity: Decimal       # incurred / claim_count
    large_loss_count: int        # claims > $25K
    open_claim_count: int

class AnalyticsResult(BaseModel):
    job_id: str
    yearly_stats: List[YearlyStats]
    overall_loss_ratio: Decimal
    frequency_trend: Decimal     # % change first→last year
    severity_trend: Decimal
    avg_days_to_close: float
    total_open_reserves: Decimal
    large_loss_ratio: Decimal    # large losses / total incurred
    years_analyzed: List[int]
    missing_years: List[int]
```

- [x] Create `backend/app/schemas/redflags.py`:

```python
class RedFlagSeverity(str, Enum):
    CRITICAL = "critical"   # red
    WARNING = "warning"     # amber
    INFO = "info"           # green

class RedFlag(BaseModel):
    flag_id: str
    flag_type: str          # matches taxonomy from spec
    severity: RedFlagSeverity
    triggered_by: str       # specific claim_id or year or rule name
    rule_description: str   # what rule triggered (deterministic)
    narrative: str          # Gemini-written explanation (generated later)
    source_data: dict       # the raw numbers that triggered it

class RedFlagReport(BaseModel):
    job_id: str
    flags: List[RedFlag]
    critical_count: int
    warning_count: int
    info_count: int
```

### 1.4 Storage Service

- [x] Create `backend/app/services/storage.py`:
  - `save_upload(job_id, filename, file_bytes) → str` — saves to `{STORAGE_BASE_PATH}/{job_id}/uploads/{filename}`
  - `save_output(job_id, filename, content) → str` — saves to `{STORAGE_BASE_PATH}/{job_id}/outputs/{filename}`
  - `read_file(path) → bytes`
  - `job_dir(job_id) → Path` — creates if not exists
- [ ] All paths resolved relative to `STORAGE_BASE_PATH`, no path traversal possible

### 1.5 Jobs API Route

- [x] Create `backend/app/api/routes/jobs.py`:
  - `POST /api/v1/jobs/` — accepts `insured_name: str`, `files: List[UploadFile]`
    - Validate: 1–10 files, PDF only, max 50MB each
    - Create Job record (`status=pending`)
    - Create JobFile record per file, save via storage service
    - Return `JobResponse` with `job_id`
  - `GET /api/v1/jobs/` — list with pagination, filter by status
  - `GET /api/v1/jobs/{job_id}` — full job detail including files
  - `POST /api/v1/jobs/{job_id}/run` — enqueue pipeline execution (background task)
- [x] Register router in `main.py`

### 1.6 Gemini Client

- [x] Create `backend/app/services/gemini_client.py`:

```python
class GeminiClient:
    def __init__(self, api_key: str, model: str)

    async def upload_pdf(self, file_path: str) -> FileRef
        # genai.upload_file(path, mime_type="application/pdf")
        # Returns file reference for use in generate_content

    async def extract_claims(self, file_ref: FileRef, prompt: str,
                              response_schema: dict) -> dict
        # generate_content with structured output
        # response_mime_type="application/json"
        # response_schema = ClaimsExtractionSchema

    async def generate_text(self, prompt: str, context: str) -> str
        # For summary and flag narrative generation

    def delete_file(self, file_ref: FileRef)
        # Clean up uploaded file after extraction
```

- [x] Implement retry logic: 3 attempts with exponential backoff on `ResourceExhausted`
- [ ] Implement rate limiting: respect Gemini API quotas

### 1.7 Extraction Prompt

- [x] Create `backend/app/prompts/extraction.py` — the most critical prompt in the system:

**Prompt design principles:**

- Provide the exact JSON schema inline so Gemini uses structured output
- Instruct Gemini to extract ALL claims, not summarize
- Handle tables where column names vary per carrier
- Distinguish "incurred" = paid + reserve explicitly
- Flag when a value is missing vs. genuinely zero
- Do not infer or estimate — extract only what is present
- If a field is not present in the document, use `null`, never guess

**Structured output schema passed to Gemini:**

```json
{
  "carrier_name": "string",
  "carrier_code": "string | null",
  "lob": "GL|CA|WC|PROP|PL|UMB|UNKNOWN",
  "policy_period_start": "YYYY-MM-DD",
  "policy_period_end": "YYYY-MM-DD",
  "earned_premium": "number | null",
  "claims": [
    {
      "claim_number": "string",
      "occurrence_date": "YYYY-MM-DD | null",
      "close_date": "YYYY-MM-DD | null",
      "status": "open|closed",
      "claim_type": "string",
      "description": "string",
      "amount_paid": "number",
      "amount_reserved": "number",
      "amount_incurred": "number"
    }
  ],
  "extraction_notes": ["string"]
}
```

- [x] LOB code lookup table in `normalize.py` (not LLM): maps carrier-specific line names → standard LOB codes

| Carrier Terms | LOB Code |
|---|---|
| `"CPKG"`, `"Commercial Package"`, `"BOP"` | `"GL"` |
| `"WCOM"`, `"Workers Comp"`, `"WC"` | `"WC"` |
| `"BAUT"`, `"Business Auto"`, `"Commercial Auto"` | `"CA"` |
| `"CUMB"`, `"Commercial Umbrella"` | `"UMB"` |
| `"CRIM"`, `"Crime"` | `"PROP"` |

### 1.8 LangGraph Pipeline State + Graph

- [x] Create `backend/app/pipeline/state.py`:

```python
class PipelineState(TypedDict):
    job_id: str
    insured_name: str
    file_paths: List[str]

    # Stage outputs (None until stage completes)
    raw_extractions: List[dict]
    claims_array: Optional[dict]         # ClaimsArray as dict
    analytics: Optional[dict]            # AnalyticsResult as dict
    red_flags: Optional[dict]            # RedFlagReport as dict
    draft_summary: Optional[str]
    final_summary: Optional[str]

    # HITL
    hitl_action: Optional[str]           # approve/edit/reject
    hitl_edit_content: Optional[str]

    # Tracking
    current_stage: str
    errors: List[str]
    completed: bool
```

- [x] Create `backend/app/pipeline/graph.py`:

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

def build_graph(db_path: str) -> CompiledGraph:
    checkpointer = SqliteSaver.from_conn_string(db_path)
    graph = StateGraph(PipelineState)

    graph.add_node("ingest", ingest_node)
    graph.add_node("extract", extract_node)
    graph.add_node("normalize", normalize_node)
    graph.add_node("analytics", analytics_node)
    graph.add_node("redflags", redflag_node)
    graph.add_node("summary", summary_node)
    graph.add_node("hitl_gate", hitl_gate_node)   # interrupt here
    graph.add_node("deliver", deliver_node)

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "extract")
    graph.add_edge("extract", "normalize")
    graph.add_edge("normalize", "analytics")
    graph.add_edge("analytics", "redflags")
    graph.add_edge("redflags", "summary")
    graph.add_edge("summary", "hitl_gate")
    graph.add_conditional_edges(
        "hitl_gate",
        route_hitl,                      # approve→deliver, reject→summary
        {"deliver": "deliver", "summary": "summary", "end": END}
    )
    graph.add_edge("deliver", END)

    return graph.compile(checkpointer=checkpointer,
                         interrupt_before=["hitl_gate"])
```

- Use `SqliteSaver` — LangGraph's built-in SQLite checkpointer, zero extra infrastructure
- `interrupt_before=["hitl_gate"]` pauses pipeline before HITL node; resumed via API

### 1.9 Extract Node

- [x] Create `backend/app/pipeline/nodes/extract.py`:
  - For each file in `state["file_paths"]`:
    - Upload to Gemini Files API
    - Run extraction prompt with structured output schema
    - Append result to `raw_extractions`
    - Delete uploaded file from Gemini after extraction (cleanup)
  - If extraction fails for a file, append error to `state["errors"]`, continue with others
  - Update `current_stage = "extract"`
  - Persist raw extractions to `JobOutput.claims_json` (intermediate)
- [ ] Test against sample: `samples/Westech Mechanical Inc/2627 BAUT Loss Runs From PROIN (2022-2026).pdf`

### Phase 1 Done Criteria

- [ ] Can upload 3 sample PDFs via API (`POST /api/v1/jobs/`)
- [ ] Pipeline runs to extract node and produces valid `ClaimsArray` JSON
- [ ] Raw extraction stored in DB
- [ ] No crashes on the Westech, T-P Enterprises, and Charlotte samples

---

## Phase 2 — Normalization, Analytics & Red Flag Engine

**Goal:** From `ClaimsArray` → deterministic analytics → zero-false-positive red flag detection

### 2.1 Normalize Node

- [x] Create `backend/app/pipeline/nodes/normalize.py`:
  - Merge all `raw_extractions` (from multiple PDFs for same insured) into unified `ClaimsArray`
  - Deduplicate claims by `claim_number + carrier_code` (same claim appearing in two loss run years)
  - Normalize dates: parse all date format variants (`MM/DD/YYYY`, `YYYY-MM-DD`, `"01-Jan-23"`) → ISO date
  - Normalize amounts: strip `$`, `,`, handle `(negative)` format → `Decimal`
  - Validate: `amount_incurred` must equal `amount_paid + amount_reserved ± 1.00` (rounding); if mismatch > $1, log extraction note
  - Set `litigation_flag = True` if claim description contains any keyword from `LITIGATION_KEYWORDS` frozenset (case-insensitive exact match, not semantic)
  - Set `subrogation_potential = True` if `"subroga"` in description (covers subrogation/subrogated)
  - Assign `claim_id = {carrier_code}-{claim_number}` (stable, deterministic)

### 2.2 Analytics Node

- [x] Create `backend/app/pipeline/nodes/analytics.py`:

Build a pandas DataFrame from `ClaimsArray.claims`, then calculate:

**Per-year calculations** (group by policy year):

- `claim_count` — count of claims with occurrence in that year
- `total_incurred` — sum of `amount_incurred`
- `total_paid`, `total_reserved`
- `earned_premium` — from `PolicyPeriodSummary`
- `loss_ratio = total_incurred / earned_premium` (skip year if premium is null)
- `loss_frequency = claim_count / (earned_premium / 1_000_000)` (per $1M premium)
- `loss_severity = total_incurred / claim_count` (0 if no claims)
- `large_loss_count` — claims with `amount_incurred > 25_000`
- `open_claim_count` — claims with `status == "open"`

**Overall/trend calculations:**

- `overall_loss_ratio = total_incurred_all_years / total_premium_all_years`
- `frequency_trend` — linear regression slope on yearly frequency, expressed as % change
- `severity_trend` — same for severity
- `avg_days_to_close` — mean of `(close_date - occurrence_date).days` for closed claims only
- `total_open_reserves` — sum of `amount_reserved` where `status == "open"`
- `large_loss_ratio = total_large_loss_incurred / total_all_incurred`
- `missing_years` — gaps in the year sequence within the 5-year window
- `claims_aging` — groupby `claim_type`, mean days to close per type

- [x] All calculations pure pandas/numpy, no LLM involvement
- [x] Handle edge cases: 0-claim year, null premiums, single-year data

### 2.3 Red Flag Rules Engine

- [ ] Create `backend/app/pipeline/nodes/redflags.py`:

Each rule is an independent function returning `RedFlag | None`. Rules run in isolation, no chaining.

```python
LARGE_LOSS_THRESHOLD = Decimal("25000")
CATASTROPHIC_LOSS_THRESHOLD = Decimal("100000")
FREQUENCY_INCREASE_THRESHOLD = 0.20      # 20%
RESERVE_ESCALATION_THRESHOLD = 0.25      # 25%
LOSS_RATIO_CRITICAL = Decimal("0.85")
PATTERN_CONCENTRATION_COUNT = 3
RECENT_CLAIM_DAYS = 90
```

| Rule | Description | Severity |
|---|---|---|
| **Rule 1: Large Single Loss** | Each claim where `amount_incurred > 25_000` emits one flag. No aggregation. | WARNING |
| **Rule 2: Catastrophic Loss** | `amount_incurred > 100_000` OR any year's `loss_ratio > 0.85` | CRITICAL |
| **Rule 3: Deteriorating Frequency** | Consecutive-year pair shows > 20% frequency increase AND persists 2+ years. Single-year spikes do NOT trigger. Requires minimum 3 years of data. | WARNING |
| **Rule 4: Open Claim with Growing Reserve** | Requires claims data from two different loss run years. If `current_reserved / prior_reserved > 1.25`. If only one year of data, rule does NOT fire. | WARNING |
| **Rule 5: Litigation Indicator** | `claim.litigation_flag == True` (set deterministically in normalize node) | WARNING |
| **Rule 6: Pattern Concentration** | Group by normalized `claim_type`. If count >= 4 for any single type across all years. (Threshold is 4 because spec says ">3 claims of same type.") | WARNING |
| **Rule 7: Recent Claims** | `occurrence_date >= today - 90 days` (not warning — reserves undeveloped) | INFO |
| **Rule 8: Missing Years** | From `analytics.missing_years`, if any gap exists | WARNING |
| **Rule 9: High Open Reserve Ratio** | `total_open_reserves / total_incurred_all_years > 0.30` (potential adverse development) | WARNING |

**Implementation notes:**
- Every rule logs its trigger condition in `source_data` (the exact numbers)
- `narrative` field is `""` at this stage — filled in `summary_node`
- Rules are independently testable functions, not a chain

- [ ] Write unit tests in `tests/unit/test_redflags.py` — one test per rule, including boundary conditions (e.g., exactly at 20% = no flag, 20.01% = flag)

### 2.4 Analytics Unit Tests

- [ ] `tests/unit/test_analytics.py`:
  - Test `loss_ratio` calculation with known values
  - Test `frequency_trend` with 3-year increasing dataset
  - Test `missing_years` detection (`2019, 2020, 2022` → missing `2021`)
  - Test with 0-claim year (no division-by-zero)
  - Test with null premium years (graceful skip)
- [ ] `tests/unit/test_normalize.py`:
  - Test date format normalization for all known carrier formats
  - Test `litigation_flag` for each keyword in the frozenset
  - Test `amount_incurred` reconciliation

### Phase 2 Done Criteria

- [ ] Analytics node produces correct metrics verified against manually calculated values from sample PDFs
- [ ] Red flag engine produces no false positives on clean accounts (e.g., Flat And Square Foundation Solutions LLC sample with minimal loss history)
- [ ] All 9 rules have passing unit tests at boundary conditions
- [ ] `missing_years` correctly identified on A Cut Above Landscape LLC (two carriers, different periods)

---

## Phase 3 — Summary Generation + PDF Output

**Goal:** Gemini-generated underwriter narrative + downloadable PDF

### 3.1 Red Flag Narrative Generation

- [ ] In `summary_node`, before writing the main narrative, call Gemini once per confirmed red flag to generate `RedFlag.narrative`:
  - Prompt: *"Given this confirmed insurance red flag [flag_type], triggered by [source_data], write one professional sentence for inclusion in an underwriter summary. Do not speculate beyond the data provided. Do not add caveats or disclaimers."*
  - Input: deterministic `source_data` dict (numbers, dates, claim types)
  - Output: single sentence, ≤ 100 words
  - Do NOT ask Gemini whether the flag exists — that was already decided by the rules engine

### 3.2 Underwriter Summary Prompt

- [x] Create `backend/app/prompts/summary.py`:

**Prompt receives structured data only (no raw PDF text):**

- `insured_name`
- `years_analyzed`
- `yearly_stats[]` (all metrics per year)
- `red_flags[]` (with narratives already filled)
- `overall_loss_ratio`, `frequency_trend`, `severity_trend`
- `large_losses[]` (claims > $25K with descriptions)
- `open_claims[]` (status=open with current reserves)

**Prompt instructions:**

- Write in formal insurance underwriting style
- Structure: Executive Summary → Year-by-Year Analysis → Large Loss Detail → Open Claim Status → Red Flag Disclosure → Risk Management Observations
- Do not invent claims or figures not in the provided data
- Do not make coverage recommendations
- Include mandatory disclaimer at footer
- Output: structured JSON with sections as separate fields (not one blob) so frontend can render/edit sections independently

**Output schema:**

```json
{
  "executive_summary": "string",
  "year_by_year": "string",
  "large_loss_detail": "string",
  "open_claim_status": "string",
  "red_flag_disclosure": "string",
  "risk_management_observations": "string",
  "disclaimer": "string (fixed text)"
}
```

### 3.3 Chart Generator

- [ ] Create `backend/app/services/chart_generator.py` using matplotlib:
  - `loss_ratio_bar_chart(yearly_stats) → base64_png` — grouped bar chart, year on X-axis, loss ratio on Y, red line at 65%
  - `frequency_trend_chart(yearly_stats) → base64_png` — line chart with year-on-year claim count + frequency
  - `severity_trend_chart(yearly_stats) → base64_png` — line chart for average severity trend
  - `claims_by_type_pie(claims_array) → base64_png` — distribution of claim types
  - All charts styled consistently (dark blue palette, professional font, no decorative elements)
  - Return `dict: {chart_name: base64_string}`

### 3.4 PDF Generator

- [ ] Create `backend/app/services/pdf_generator.py` using WeasyPrint:
  - HTML template (Jinja2) that renders:
    - Header: insured name, report date, SovereignAI branding, job ID
    - Executive Summary section
    - Claims Summary table (year, count, incurred, premium, loss ratio)
    - Embedded chart images (base64 → `<img>` tags)
    - Large Loss Detail table (claim #, date, type, amount, status)
    - Open Claims table
    - Red Flag section — color-coded by severity (`critical=red bg`, `warning=amber`, `info=green`)
    - Year-by-year narrative sections
    - Risk Management Observations
    - Mandatory disclaimer footer on every page
    - Page numbers, generation timestamp
  - `generate_pdf(summary_data, analytics, red_flags, charts) → bytes`
  - Save to `{STORAGE_BASE_PATH}/{job_id}/outputs/underwriter_summary.pdf`

### 3.5 Deliver Node

- [ ] Create `backend/app/pipeline/nodes/deliver.py`:
  - Generate charts
  - Assemble final summary (draft + HITL edits if any)
  - Generate PDF
  - Write `JobOutput` record (all fields populated)
  - Update `Job.status = "completed"`, `Job.completed_at`
  - Return final state

### Phase 3 Done Criteria

- [ ] Underwriter summary generated from T-P Enterprises Inc (multi-carrier, multiple LOBs, has OPEN CLAIM sample) produces structured JSON with all 6 sections
- [ ] PDF downloads and contains all required sections
- [ ] Charts render correctly and embed in PDF
- [ ] Red flag narratives in PDF are coherent and factually grounded in source data
- [ ] No hallucinated claim numbers or amounts in summary

---

## Phase 4 — HITL Gate + Complete API

**Goal:** Full pipeline pause/resume, HITL queue API, audit logging

### 4.1 HITL Gate Node

- [ ] Create `backend/app/pipeline/nodes/hitl_gate.py`:
  - LangGraph `interrupt()` pauses here
  - Before pausing: update `Job.status = "hitl_pending"`, write draft to `JobOutput.draft_summary`
  - On resume (approved): pass `final_summary = draft_summary` → deliver node
  - On resume (edited): pass `final_summary = hitl_edit_content` → deliver node
  - On resume (rejected): clear draft, route back to summary node (re-generate)
  - Maximum 2 rejections before flagging for manual escalation

### 4.2 HITL API Routes

- [ ] Create `backend/app/api/routes/hitl.py`:
  - `GET /api/v1/hitl/queue` — all jobs with `status = "hitl_pending"`, ordered by `created_at`, include severity summary (critical/warning/info counts)
  - `GET /api/v1/hitl/{job_id}` — full draft summary + red flags + claims table + analytics (everything needed for review in one call)
  - `POST /api/v1/hitl/{job_id}/approve` — body: `{user_id: str}` — resume LangGraph thread with `hitl_action = "approve"`
  - `POST /api/v1/hitl/{job_id}/edit` — body: `{user_id: str, edited_sections: dict}` — merge edits, resume with `hitl_action = "edit"`
  - `POST /api/v1/hitl/{job_id}/reject` — body: `{user_id: str, reason: str}` — resume with `hitl_action = "reject"`
  - All actions write immutable `HitlAction` record to DB (audit log)

### 4.3 LangGraph Thread Management

- [ ] Pipeline runs in asyncio background task (FastAPI `BackgroundTasks`)
- [ ] Thread ID = `job_id` (deterministic, resumable)
- [ ] `POST /api/v1/jobs/{job_id}/run` → `background_tasks.add_task(run_pipeline, job_id)`
- [ ] `run_pipeline()` calls `graph.astream(state, config={"configurable": {"thread_id": job_id}})`
- [ ] HITL resume: `graph.astream(None, config={"configurable": {"thread_id": job_id}}, input=hitl_resume_state)`
- [ ] Store graph instance in FastAPI app state (singleton, shared across requests)

### 4.4 SSE Status Stream

- [ ] Create `backend/app/api/routes/stream.py`:
  - `GET /api/v1/jobs/{job_id}/stream` — SSE endpoint
  - Emits events as pipeline progresses: `{"stage": "extract", "status": "running", "progress": 2, "total": 3}`
  - Events: `stage_start`, `stage_complete`, `stage_error`, `hitl_pending`, `completed`, `failed`
  - Frontend `EventSource` subscribes on job detail page
  - On disconnect: SSE handler cleanup without affecting pipeline

### 4.5 Outputs API Routes

- [ ] Create `backend/app/api/routes/outputs.py`:
  - `GET /api/v1/outputs/{job_id}/claims` — return `ClaimsArray` JSON
  - `GET /api/v1/outputs/{job_id}/analytics` — return `AnalyticsResult` JSON
  - `GET /api/v1/outputs/{job_id}/redflags` — return `RedFlagReport` JSON
  - `GET /api/v1/outputs/{job_id}/summary` — return final summary sections JSON
  - `GET /api/v1/outputs/{job_id}/pdf` — `FileResponse` with correct content-type, filename header
  - `GET /api/v1/outputs/{job_id}/charts` — return `{chart_name: base64}` dict
  - All routes: `404` if job not found or output not yet generated; `409` if job not completed

### Phase 4 Done Criteria

- [ ] Full pipeline runs end-to-end with Aesthetic Tree Service Inc sample (3 LOBs in one PDF: BAUT + CPKG + CUMB)
- [ ] Pipeline pauses at HITL gate, `Job.status = "hitl_pending"` in DB
- [ ] Approve via API resumes pipeline, PDF generated, `Job.status = "completed"`
- [ ] Reject routes back to summary node, re-generates, pauses again at HITL
- [ ] `HitlAction` audit records written for every HITL interaction
- [ ] SSE stream emits all stage events to a `curl` listener

---

## Phase 5 — Frontend

**Goal:** Full React UI for upload, job tracking, HITL review, output viewing

### 5.1 Frontend Scaffold

- [ ] `npm create vite@latest frontend -- --template react-ts`
- [ ] Install: `tailwindcss`, `@tailwindcss/vite`, `shadcn/ui`, `@tanstack/react-query`, `axios`, `react-router-dom`, `recharts`, `zod`, `react-hook-form`, `@hookform/resolvers`
- [ ] Init shadcn/ui: `npx shadcn@latest init` (use slate theme, CSS variables)
- [ ] Create `src/api/client.ts` — axios instance with `baseURL = "http://localhost:8000"`, default headers
- [ ] Create `src/types/` — TypeScript interfaces mirroring all Pydantic schemas
- [ ] Configure React Router: routes for `/`, `/jobs/new`, `/jobs/:id`, `/hitl`, `/hitl/:id`
- [ ] `ReactQueryDevtools` in dev only

### 5.2 App Shell + Navigation

- [ ] Create `AppShell.tsx` — sidebar navigation with:
  - Logo / "Loss Run Triage" title
  - Links: Dashboard, New Job, HITL Queue (with badge showing pending count)
  - Connection status indicator (backend alive check)
- [ ] Sidebar badge auto-refreshes pending HITL count every 30s via React Query `refetchInterval`

### 5.3 Dashboard Page

- [ ] Job list table with columns: Insured Name, Status (color-coded badge), Files, Created, Stage, Actions
- [ ] Status badge colors: `pending=gray`, `running=blue`, `hitl_pending=amber`, `completed=green`, `failed=red`
- [ ] Sortable by created date
- [ ] Filter by status (tabs)
- [ ] "View" button → `/jobs/:id`, "Review" button for `hitl_pending` → `/hitl/:id`
- [ ] Empty state with "Create first job" CTA

### 5.4 New Job Page

- [ ] Insured name text input (required)
- [ ] Drag-and-drop file zone using native HTML5 + shadcn styling:
  - Shows file thumbnails with name, size
  - Validates PDF only, max 50MB per file, max 10 files client-side before upload
  - Remove individual files
- [ ] "Start Analysis" button → `POST /api/v1/jobs/` with `multipart/form-data`
- [ ] On success → redirect to `/jobs/:id` immediately

### 5.5 Job Detail Page

- [ ] Header: insured name, job ID, status badge, created timestamp
- [ ] `PipelineTracker` component — horizontal stepper showing 8 stages:

```
[Ingest] → [Extract] → [Normalize] → [Analytics] → [Red Flags] → [Summary] → [HITL Review] → [Deliver]
```

  - Each stage: icon, name, status (pending/running/complete/error)
  - Active stage pulses with animation
  - SSE via `useJobStream(jobId)` custom hook drives stage updates
  - Error stage shows inline error message
- [ ] Files section: list of uploaded PDFs with extraction status per file
- [ ] If `status = "hitl_pending"`: prominent amber banner "Awaiting Review" with "Review Now" button → `/hitl/:id`
- [ ] If `status = "completed"`: output section (see 5.8)

### 5.6 HITL Queue Page

- [ ] Grid of `QueueItem` cards, sorted by severity then age
- [ ] Each card shows:
  - Insured name
  - Critical/Warning/Info counts as colored pills
  - Time waiting (e.g., "Waiting 2h 15m")
  - Red flags summary (first critical flag description)
  - "Review" button
- [ ] Color of card left border: red if any critical, amber if warnings only, green if info only
- [ ] SLA indicator: amber at 12h, red at 24h waiting time

### 5.7 HITL Review Page

Two-panel layout:

**Left Panel — AI Output (read-only)**

- Expandable sections for each summary section (Executive Summary, Year-by-Year, etc.)
- Red Flag panel with severity-colored cards, each showing flag type, trigger data, and AI narrative
- Claims table (filterable by LOB, status, year)
- Analytics panel: key metrics (loss ratio, frequency, severity, open reserves)
- Trend charts (Recharts `LineChart` for frequency/severity, `BarChart` for loss ratio)

**Right Panel — Review Actions**

- Editable summary sections (one `Textarea` per section, pre-filled with AI draft)
- "Accept AI Draft" toggle per section or globally
- `RedFlagPanel` — each flag can be marked "Acknowledged", "Dismissed" (with required reason), or "Escalate"
- Reviewer notes field
- Action buttons:
  - "Approve & Generate Report" (green) → `POST /hitl/:id/approve`
  - "Submit Edits & Approve" (blue) — only active if edits made → `POST /hitl/:id/edit`
  - "Reject & Regenerate" (red) — requires reason → `POST /hitl/:id/reject`
- Confirmation modal for Approve with summary of any dismissed flags

### 5.8 Output View (on completed Job Detail)

- [ ] Download PDF button (primary CTA)
- [ ] Tabs: Summary | Claims | Analytics | Red Flags | Charts
- [ ] **Summary tab:** rendered sections, read-only
- [ ] **Claims tab:** full `ClaimsTable` — sortable, filterable by LOB/carrier/year/status; exportable to CSV
- [ ] **Analytics tab:** `AnalyticsPanel` with metric cards (loss ratio, frequency, severity, open reserves) + yearly stats table
- [ ] **Red Flags tab:** full `RedFlagReport` with severity grouping
- [ ] **Charts tab:** all 4 charts rendered via Recharts (not embedded images — use the JSON data to re-render interactively)

### Phase 5 Done Criteria

- [ ] Full workflow completable in UI: upload → watch pipeline → review in HITL → download PDF
- [ ] HITL review with edits saves correctly and final PDF reflects edits
- [ ] Dashboard badge reflects real HITL queue count
- [ ] SSE pipeline tracker works without page refresh
- [ ] All 3 insured samples (Westech, T-P, Aesthetic Tree) completable end-to-end via UI

---

## Phase 6 — Hardening & Sample Validation

**Goal:** Validate against all 16 sample files, tighten extraction accuracy, confirm zero false positives

### 6.1 Extraction Accuracy Validation

- [ ] Run extraction on all 16 sample PDFs
- [ ] Manually review `extraction_notes` for each — any "could not extract" warnings need prompt tuning
- [ ] Cross-check totals: Gemini-extracted `total_incurred` vs. loss run summary page totals (most carriers print a summary row)
- [ ] Known edge cases to verify:
  - `2627 WCOM Loss Runs From PININ (2019-2026).pdf` — 7-year span, test that all years captured
  - `2627 CPKG Loss Runs From EMPMU (2022-2026) OPEN CLAIM.pdf` — verify open claim flagged with correct reserve
  - `2627 BAUT CPKG CUMB Loss Runs from SECIN (2020-2026).pdf` — 3 LOBs in one PDF, verify each extracted independently
  - `2627 CRIM Loss Runs From CONWE (2025-2026).pdf` — Crime line, verify mapped to PROP LOB correctly

### 6.2 Red Flag Validation

- [ ] For each sample, manually verify every red flag triggered is correct:
  - Flat And Square Foundation Solutions LLC — minimal history, expect few/no flags
  - Hydropro Fire Sprinkler Company — verify no false frequency flags from short policy period
  - Source Communications LLP (2020-2024) — 5-year history, verify trend calculation
- [ ] For the OPEN CLAIM sample: verify `open_claim_growing_reserve` rule only fires if prior year reserve data available (cannot fire on single-year run)
- [ ] Document any rule adjustments with rationale

### 6.3 Performance Baseline

- [ ] Measure and log time per pipeline stage for a 3-file, 5-year job
- [ ] Target: total end-to-end (extract → PDF) under 90 seconds for a 5-file job
- [ ] If Gemini extraction is slow per file, implement concurrent extraction: `asyncio.gather(*[extract_file(f) for f in files])`

### 6.4 Error Handling Hardening

- [ ] If Gemini returns malformed JSON despite structured output schema: retry once, then store raw text + error flag
- [ ] If any analytics calculation raises exception: fail gracefully, set `current_stage = "analytics_failed"`, surface error in UI
- [ ] Corrupted or password-protected PDF: detect at ingest node (file magic bytes check), reject immediately with clear error message before hitting Gemini
- [ ] Missing earned premium across all years: analytics still runs, loss ratio marked null, no division-by-zero crash

### Phase 6 Done Criteria

- [ ] All 16 sample PDFs process successfully with no crashes
- [ ] Extraction accuracy: claim counts match manual review for 14/16 samples (2 allowed edge cases with known limitations)
- [ ] Zero confirmed false-positive red flags across all samples
- [ ] End-to-end time under 90 seconds for largest sample set (Westech: 3 files)

---

## Dependencies & Local Dev Setup

### Backend `.env.example`

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash-preview
STORAGE_BASE_PATH=./data/jobs
DATABASE_URL=sqlite:///./loss_run.db
CORS_ORIGINS=http://localhost:5173
```

### Python Dependencies (`pyproject.toml`)

```toml
fastapi>=0.115
uvicorn[standard]>=0.30
sqlalchemy>=2.0
alembic>=1.13
pydantic>=2.7
pydantic-settings>=2.3
google-generativeai>=0.8
langgraph>=0.2
langchain-core>=0.3
pandas>=2.2
numpy>=1.26
matplotlib>=3.9
weasyprint>=62
jinja2>=3.1
aiofiles>=23.2
python-multipart>=0.0.9
python-dotenv>=1.0
```

### Frontend `package.json` key deps

```
react, react-dom, react-router-dom v6
@tanstack/react-query v5
axios
tailwindcss v4
shadcn/ui (latest)
recharts
zod
react-hook-form
@hookform/resolvers
```

### Run Locally

```bash
# Backend
cd backend && pip install -e . && uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
# Runs on http://localhost:5173
```

---

## Summary Checklist by Phase

| Phase | Weeks | Key Output | Current Status |
|---|---|---|---|
| 1 — Foundation + Extraction | 1–2 | PDF → ClaimsArray JSON via Gemini | In progress |
| 2 — Analytics + Red Flags | 3–4 | Deterministic metrics + zero-FP flags | In progress (partial) |
| 3 — Summary + PDF | 5–6 | Gemini narrative + downloadable PDF | Not started (prompt scaffold only) |
| 4 — HITL + Full API | 7–8 | Complete pipeline with pause/resume | Not started |
| 5 — Frontend | 9–10 | Full React UI end-to-end | Not started |
| 6 — Hardening | 11–12 | Validated against all 16 samples | Not started |
