# Google Maps Lead Intelligence (Local Demo Prototype)

Discover, enrich and prioritize business leads from Google Maps. This is a
**local demo prototype** — not a production system. It runs entirely on your
machine with no external infrastructure (no Docker, Redis, Celery, or cloud
services).

## Pipeline

```
Google Maps Discovery
      ↓
Google Maps Detail Enrichment
      ↓
Website Enrichment
      ↓
Lead Processing / Validation
      ↓
Lead Scoring
      ↓
Dashboard
      ↓
CSV / Excel / JSON Export
```

Everything runs from the React UI — you never need to run a scraper script
by hand.

## Prerequisites

- Python 3.10+
- Node.js 18+
- ~500MB free disk space for the Chromium browser Playwright installs

## 1. Backend setup

From the project root:

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
playwright install chromium
```

Start the API server:

```bash
uvicorn backend.app:app --reload
```

The backend runs at `http://127.0.0.1:8000`. You can view interactive API
docs at `http://127.0.0.1:8000/docs`.

Alternatively, `python run.py` starts the same server.

## 2. Frontend setup

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The UI runs at `http://localhost:5173` and talks to the backend at
`http://127.0.0.1:8000` (CORS is already configured).

## 3. Using the app

1. Open `http://localhost:5173`.
2. Enter a query such as `dentists in Pune`.
3. Set target leads (e.g. 20) and worker count (e.g. 3).
4. Click **Start Search**.
5. Watch live pipeline progress (Discovery → Detail Enrichment → Website
   Enrichment → Lead Processing).
6. Browse the stats cards, filter/search/sort the lead table, and click a
   row to open the details drawer.
7. Export **CSV**, **Excel**, or **JSON** from the Export panel.

Exported files are also written to `output/leads.csv`, `output/leads.xlsx`,
`output/leads.json`, and `output/summary.json` on disk.

## Notes on reliability

- One stuck record never freezes the whole pipeline — each record enrichment
  is wrapped in a hard timeout (`PER_RECORD_TIMEOUT` in `backend/config.py`,
  default 60s) and only transient failures (`TIMEOUT`, `NAVIGATION_ERROR`,
  `NETWORK_BLOCKED`, `CONNECTION_REFUSED`) are retried.
- Partial progress is checkpointed to `data/processed/checkpoint_leads.json`
  every 5 completed records.
- Google Maps' DOM changes frequently — extraction uses aria-labels, roles,
  and multiple fallback strategies rather than one fragile CSS selector, and
  validates fields (e.g. rating vs. address, category vs. name) before
  accepting them.

## Project structure

```
backend/
  app.py                  FastAPI app + in-memory pipeline orchestration
  config.py                All tunables (timeouts, retries, scoring weights)
  scraper/
    maps_discovery.py      Stage 1: Playwright search + scroll discovery
    detail_enricher.py     Stage 2: Playwright per-business detail page
    website_enricher.py    Stage 3: httpx-based email/social extraction
  services/
    lead_processor.py      Stage 4/5: normalize, dedupe, score
    exporter.py             Stage 7: CSV/Excel/JSON export
  utils/
    validators.py           Field validation / sanity checks
    helpers.py               Normalization, ids, JSON IO

frontend/
  components/               SearchPanel, PipelineProgress, StatsCards,
                             LeadTable, LeadDetails, ExportButtons
  src/                       App.jsx, api.js, main.jsx
  styles/app.css

data/raw, data/processed     Checkpoints and intermediate data
output/                      Final CSV/Excel/JSON exports
```

## Troubleshooting

- **"Could not reach the backend"** in the UI banner: make sure
  `uvicorn backend.app:app --reload` is running on port 8000.
- **Playwright browser not found**: re-run `playwright install chromium`.
- **No results discovered**: Google Maps' markup changes over time; if
  selectors stop matching, check `backend/scraper/maps_discovery.py` first.
- **A pipeline run is already in progress (409)**: click **Stop**, wait for
  `phase` to leave `running`, then start a new search.