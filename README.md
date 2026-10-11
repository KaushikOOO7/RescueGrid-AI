# RescueGrid AI

**RescueGrid AI** is a local, synthetic-data-first disaster-response decision-support prototype for a hackathon demo. It helps coordinators review fragmented flood and earthquake reports, extract structured details, inspect possible duplicates, prioritize incidents using explainable rules, and identify reporting-information gaps.

> **Safety boundary:** This application is not an emergency service, a live monitoring product, or an operationally validated standard. Seeded incidents and coverage cells are fictional. Scores are heuristic rule outputs, not calibrated probabilities. The app never authorizes dispatch or claims that an area is safe. Human coordinators must approve consequential actions.

## Core principle

**Urgency is evaluated independently from report reliability.** A low-confidence, high-urgency report remains visible in the queue and prompts verification. Message volume, social popularity, and duplicate-copy count do not add urgency points. A possible duplicate is never merged automatically.

## What is implemented

- **Operations overview:** database-backed active/high-urgency/verification/gap metrics, priority distribution, recent changes, review queue, and interactive map.
- **Incident register:** searchable, sortable, paginated API-backed records; filters for disaster, urgency, status, and report time; detail drawer with original text, provenance, score explanations, history, notes, and duplicate review.
- **Report intake:** rule-based local extraction preview for manual text, editable structured fields before saving, example synthetic SMS/field/social messages, and UTF-8 CSV preview/import (up to 500 rows / 2 MB).
- **Map:** React-Leaflet/OpenStreetMap, pan/zoom, urgency/status styling, coverage-gap overlay, popups that open records, and an offline tile warning. Only explicitly entered coordinates are mapped; place names are not geocoded.
- **Explainable scores:** deterministic urgency score (0–100) and a separate heuristic evidence-quality score (0–100). Human priority overrides require a reason and never overwrite the rule urgency score.
- **Duplicate review:** RapidFuzz text similarity with disaster-type, time, and reliable-coordinate checks. Similar reports remain separate until a coordinator confirms a merge; original text/source records stay attached to the primary incident.
- **Reporting-gap monitor:** clearly synthetic monitored cells, stale confirmation checks, connectivity/access observations, and an explicit warning that missing information is not evidence of safety.
- **Human decision log:** verify/reject/request-more-info, edit details, resolve, add notes, adjust queue priority with a reason, confirm/decline duplicate candidates, and review saved audit history.
- **Resource inventory & allocations:** register, track, and update staging depot inventory (boats, medical teams, water, shelter, personnel). Allocations validate against available quantities to prevent over-allocation.
- **SQLite persistence:** SQLAlchemy tables are created without dropping existing data. Demo reset only targets records tagged as demo.
- **Tests and evaluation:** deterministic unit/API tests, 16-step end-to-end workflow verification, and an illustrative scoring walkthrough.

## Project structure

```text
rescuegrid-ai/
├── backend/
│   ├── app/                 # FastAPI, SQLAlchemy models, extraction, scoring, services
│   ├── tests/               # Unit, API, and 16-step E2E workflow tests
│   ├── data/                # SQLite file is created here at runtime
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/                 # React/Vite pages and components
│   ├── package.json
│   └── .env.example
├── data/                    # Sample CSV and synthetic coverage reference
└── docs/                    # Scoring, data model, and demo walkthrough
```

## Requirements

- Python 3.10+ (tested in this workspace with Python 3.13)
- Node.js 18+ and npm
- No paid APIs, AI-service keys, or cloud services are required
- Map tiles use OpenStreetMap over the internet; the app remains usable if tile loading fails

## Run locally (VS Code friendly)

Open the project root in VS Code and use two terminals.

### 1. Backend

```bash
cd backend
python -m venv .venv
```

Activate it:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install and start:

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

On first startup, the backend creates the SQLite schema and seeds the fictional demo dataset **only if the database is empty**. The default database is `backend/data/rescuegrid.db`. Existing records are not dropped on startup.

Optional configuration:

```bash
# macOS / Linux
cp .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --env-file .env

# PowerShell
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --env-file .env
```

Settings: `DATABASE_URL`, `RESCUEGRID_AUTO_SEED` (default `true`), `DUPLICATE_SIMILARITY_THRESHOLD` (default `78`), and `CORS_ORIGINS`. Core functionality does not use an API key.

### 2. Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. The Vite dev server proxies relative `/api` requests to `http://127.0.0.1:8000` server-side; browser code does not call localhost directly. To use another backend host, set `API_PROXY_TARGET` for Vite (for example, in the Vite process environment).

### Local URLs

- App: http://localhost:5173
- API health: http://localhost:8000/api/health
- Interactive API docs: http://localhost:8000/docs
- OpenAPI schema: http://localhost:8000/openapi.json

## Demo workflow

1. Open **Report intake** and choose a sample flood or earthquake message, or import `data/sample_reports.csv`.
2. Click **Extract for review**. Inspect and edit extracted details; unresolved places stay unresolved and coordinates are never guessed.
3. Save the record. The API persists the incident and original report, computes independent urgency/evidence scores, and surfaces possible duplicates without merging them.
4. Open **Overview**, **Incident register**, or **Operations map**. Select a marker/row to open the detail drawer.
5. Review score reasons and source provenance. Verify, reject, request details, add coordinator notes, or record a reasoned priority override.
6. Review duplicate candidates; choose **Confirm same** only after human review, or **Keep separate**. A confirmed merge retains source reports.
7. Open **Resources** to inspect tracked equipment, update depot capacity/status, and review incident allocations.
8. Open **Reporting gaps** to discuss stale/limited synthetic coverage. These are information warnings, not incident claims.
9. Open **Decision log** to inspect the saved actions.

A judge-facing walkthrough and safe talking points are in [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md).

## Reset the demo dataset safely

From `backend/`, with the virtual environment active:

```bash
python -m app.seed --reset-demo
```

This deletes and recreates only rows explicitly tagged with a `demo_key` (and their demo-linked history/reports/relations). Untagged user incidents and unrelated records are retained. **Do not delete the SQLite file** if you need to preserve user-entered records.

To insert the demo dataset manually into a non-empty database (for example, when auto-seeding is disabled), run:

```bash
python -m app.seed
```

The command is idempotent for already-seeded demo records.

## Tests and evaluation

```bash
# In backend/ (or with $env:PYTHONPATH="backend" from workspace root):
python -m pytest -q
python -m app.evaluate
```

The test suite covers score bounds/explanations and separation, duplicate candidate safety, uncertain locations, CSV validation/import, persistence, human priority/audit history, verification flow, resource inventory management, and reporting-gap warnings.

Frontend production build:

```bash
cd frontend
npm run build
```

## API overview

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Service and local mode status |
| `GET /api/dashboard` | Stored-data dashboard metrics, queue, and map records |
| `GET /api/incidents` | Search, filters, sort, and pagination (`limit`, `offset`) |
| `POST /api/incidents` | Save an incident and original manual report |
| `GET /api/incidents/{id}` | Full incident detail and decision history |
| `PATCH /api/incidents/{id}` | Coordinator edits to incident details |
| `POST /api/incidents/{id}/verify` | Verify, reject, or request more information |
| `POST /api/incidents/{id}/resolve` | Record a human resolution decision |
| `POST /api/incidents/{id}/priority` | Reason-required queue-priority override (supports POST & PATCH) |
| `POST /api/incidents/{id}/notes` | Timestamped coordinator note |
| `POST /api/reports/preview` | Preview local text extraction without saving |
| `POST /api/reports/preview-csv` | Preview CSV extraction without saving |
| `POST /api/reports/import` | Import CSV text or JSON `{"reports": [...]}` |
| `POST /api/reports/{id}/confirm-duplicate` | Human-confirmed duplicate merge |
| `POST /api/reports/{id}/mark-separate` | Human decision to retain two incidents separately |
| `GET /api/resources` | List resource items and available capacity |
| `POST /api/resources` | Register new resource item |
| `PATCH /api/resources/{id}` | Update resource capacity, base location, or availability |
| `POST /api/resources/allocate` | Allocate resources to incident with capacity validation |
| `DELETE /api/resources/allocate/{id}` | Release allocation back to inventory |
| `GET /api/coverage-gaps` | Synthetic information-gap monitor |
| `GET /api/analytics` | Stored-data distributions |
| `GET /api/audit-log` | Paginated audit events; optional `incident_id` |

CSV must include a `text`, `report`, `message`, `description`, `body`, or `original_text` column. Other recognized optional headers include `source_type`, `source_name`, `reported_at`, `location_name`, `latitude`, `longitude`, `location_precision`, `disaster_type`, `needs`, and scoring inputs. Coordinates must be supplied as a pair and marked approximate or verified; no geocoder is used.

## Troubleshooting

- **Frontend says API unavailable:** start the backend first and confirm `http://localhost:8000/api/health`. Vite proxies `/api`; restart Vite after changing `API_PROXY_TARGET`.
- **Port already in use:** change Uvicorn's `--port` and set `API_PROXY_TARGET` to the same backend port before starting Vite.
- **Map looks blank:** the app uses OpenStreetMap tiles and needs internet access for the basemap. Look for the tile warning; incident details, markers, and all non-map functions remain available.
- **CSV import rejected:** save as UTF-8 CSV; include one recognized report-text header; remove malformed numeric values; coordinates require both latitude and longitude plus `location_precision`.
- **Database file/path issue:** run backend commands from `backend/`, or set an absolute `DATABASE_URL` such as `sqlite:////absolute/path/rescuegrid.db`.
- **No demo data:** a non-empty database is intentionally not modified or seeded during startup. Run `python -m app.seed` to add the clearly tagged synthetic sample records.

## Known limitations

- Text extraction and scoring are deterministic heuristics with limited language coverage; coordinators must review every field.
- There is no external geocoding, live feed, SMS integration, social-media ingestion, route data, inventory synchronization, or dispatch mechanism.
- Coordinates and named places in the seeded data are fictional, approximate demonstration values; they must not be used for real response.
- Similarity candidates can be false positives/negatives. Similarity is not proof of a duplicate, and automatic merges are intentionally disabled.
- Scores have not been calibrated or validated against incident outcomes or operational standards.
- Database creation uses SQLAlchemy `create_all` to add missing tables without destructive startup actions. It is suitable for the prototype; schema evolution beyond this version should use explicit migrations/backups.
- OpenStreetMap tile service availability and usage policies are external dependencies for map imagery only.
