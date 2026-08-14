"""
FastAPI application for the Google Maps Lead Intelligence prototype.

Pipeline:
Discovery
    -> Detail Enrichment
    -> Website Enrichment
    -> Lead Processing
    -> Scoring
    -> Export

Local prototype only.
No Redis/Celery/external job queue.
"""

import asyncio
import logging
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from playwright.async_api import async_playwright
from pydantic import BaseModel

from backend.config import (
    CORS_ORIGINS,
    DEFAULT_WORKERS,
    DEFAULT_TARGET_LEADS,
    PER_RECORD_TIMEOUT,
    MAX_RETRIES,
    CHECKPOINT_EVERY,
    RETRYABLE_STATUSES,
    HEADLESS,
    NAV_TIMEOUT_MS,
    DATA_PROCESSED_DIR,
    OUTPUT_DIR,
)
from backend.scraper.maps_discovery import discover_leads
from backend.scraper.detail_enricher import enrich_business_detail
from backend.scraper.website_enricher import enrich_website
from backend.services.lead_processor import (
    process_leads,
    summarize_leads,
)
from backend.services.exporter import export_all
from backend.utils.helpers import safe_write_json


# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger("app")


# =============================================================================
# FASTAPI
# =============================================================================

app = FastAPI(
    title="Google Maps Lead Intelligence",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# REQUEST MODEL
# =============================================================================

class RunRequest(BaseModel):
    query: str
    target_leads: int = DEFAULT_TARGET_LEADS
    workers: int = DEFAULT_WORKERS


# =============================================================================
# PIPELINE STATE
# =============================================================================

class PipelineState:
    """
    In-memory prototype pipeline state.

    Only one pipeline run is supported at a time.
    """

    def __init__(self):
        self.lock = asyncio.Lock()
        self.reset()

    def reset(self):
        self.running = False
        self.phase = "idle"

        self.discovered = 0
        self.detail_completed = 0
        self.website_completed = 0
        self.processed = 0
        self.target = 0

        self.errors = []
        self.started_at = None
        self.stop_requested = False

        # lead_id -> latest lead record
        self.leads = {}

        self.final_leads = []
        self.summary = {}
        self.export_paths = {}

    def elapsed_seconds(self) -> float:
        if not self.started_at:
            return 0.0

        return round(
            time.time() - self.started_at,
            1,
        )

    def to_status_dict(self) -> dict:
        return {
            "running": self.running,
            "phase": self.phase,
            "discovered": self.discovered,
            "detail_completed": self.detail_completed,
            "website_completed": self.website_completed,
            "processed": self.processed,
            "target": self.target,
            "errors": self.errors[-20:],
            "elapsed_seconds": self.elapsed_seconds(),
        }


state = PipelineState()


# =============================================================================
# CHECKPOINT
# =============================================================================

def _save_checkpoint():
    """
    Save the latest state of every discovered/enriched lead.
    """
    checkpoint_path = (
        DATA_PROCESSED_DIR /
        "checkpoint_leads.json"
    )

    safe_write_json(
        checkpoint_path,
        list(state.leads.values()),
    )


# =============================================================================
# SINGLE LEAD ENRICHMENT
# =============================================================================

async def _enrich_one_lead(
    lead: dict,
    browser,
    semaphore: asyncio.Semaphore,
) -> dict:
    """
    Detail-enrich and website-enrich a single lead.

    The actual enrichment operation is wrapped in a hard timeout.
    """

    async with semaphore:

        # ---------------------------------------------------------------------
        # DETAIL ENRICHMENT
        # ---------------------------------------------------------------------

        detail_status = "TIMEOUT"
        detail_result = {}
        attempt = 0

        while attempt <= MAX_RETRIES:

            page = None

            try:
                page = await browser.new_page()

                page.set_default_timeout(
                    NAV_TIMEOUT_MS
                )

                detail_result = await asyncio.wait_for(
                    enrich_business_detail(
                        page,
                        lead["maps_url"],
                    ),
                    timeout=PER_RECORD_TIMEOUT,
                )

                detail_status = detail_result.get(
                    "detail_status",
                    "SUCCESS",
                )

            except asyncio.TimeoutError:

                detail_status = "TIMEOUT"

                detail_result = {
                    "detail_status": "TIMEOUT",
                    "detail_error": (
                        "Detail enrichment timed out."
                    ),
                }

            except Exception as exc:

                detail_status = "NAVIGATION_ERROR"

                detail_result = {
                    "detail_status": "NAVIGATION_ERROR",
                    "detail_error": str(exc)[:300],
                }

            finally:

                if page is not None:
                    try:
                        await page.close()
                    except Exception:
                        pass

            if detail_status not in RETRYABLE_STATUSES:
                break

            attempt += 1

        lead.update(detail_result)

        async with state.lock:

            state.detail_completed += 1

            if detail_status not in {
                "SUCCESS",
                "PARTIAL",
            }:

                state.errors.append(
                    f"{lead.get('name', 'unknown')}: "
                    f"detail {detail_status}"
                )

            # IMPORTANT:
            # Keep the latest detail-enriched record in shared state.
            state.leads[lead["lead_id"]] = dict(lead)

        # ---------------------------------------------------------------------
        # WEBSITE ENRICHMENT
        # ---------------------------------------------------------------------

        website_url = (
            lead.get("website") or ""
        ).strip()

        website_result = {}

        if website_url:

            website_status = "TIMEOUT"
            attempt = 0

            while attempt <= MAX_RETRIES:

                try:

                    website_result = await asyncio.wait_for(
                        enrich_website(website_url),
                        timeout=PER_RECORD_TIMEOUT,
                    )

                    website_status = website_result.get(
                        "website_status",
                        "INSPECTED",
                    )

                except asyncio.TimeoutError:

                    website_status = "TIMEOUT"

                    website_result = {
                        "website_status": "TIMEOUT",
                        "website_error": (
                            "Website enrichment timed out."
                        ),
                    }

                except Exception as exc:

                    website_status = "NAVIGATION_ERROR"

                    website_result = {
                        "website_status": "NAVIGATION_ERROR",
                        "website_error": str(exc)[:300],
                    }

                if website_status not in RETRYABLE_STATUSES:
                    break

                attempt += 1

        else:

            website_result = {
                "website_status": "NO_WEBSITE"
            }

        lead.update(website_result)

        async with state.lock:

            state.website_completed += 1

            # CRITICAL FIX:
            # Save the fully enriched record before checkpointing.
            state.leads[lead["lead_id"]] = dict(lead)

            if state.website_completed % CHECKPOINT_EVERY == 0:
                _save_checkpoint()

            if website_result.get("website_status") not in {
                None,
                "ENRICHED",
                "INSPECTED",
                "EXTERNAL_PROFILE",
                "NO_WEBSITE",
            }:

                state.errors.append(
                    f"{lead.get('name', 'unknown')}: "
                    f"website "
                    f"{website_result.get('website_status')}"
                )

        return lead


# =============================================================================
# MAIN PIPELINE
# =============================================================================

async def _run_pipeline(
    query: str,
    target_leads: int,
    workers: int,
):

    async with state.lock:

        state.reset()

        state.running = True
        state.phase = "discovery"
        state.target = target_leads
        state.started_at = time.time()

    try:

        # ---------------------------------------------------------------------
        # PHASE 1 - DISCOVERY
        # ---------------------------------------------------------------------

        def on_discovery_progress(
            payload: dict,
        ):
            state.discovered = payload.get(
                "discovered",
                state.discovered,
            )

        def should_stop() -> bool:
            return state.stop_requested

        raw_leads = await discover_leads(
            query=query,
            target_leads=target_leads,
            on_progress=on_discovery_progress,
            should_stop=should_stop,
        )

        for lead in raw_leads:

            lead_id = lead.get("lead_id")

            if lead_id:
                state.leads[lead_id] = dict(lead)

        state.discovered = len(raw_leads)

        _save_checkpoint()

        if state.stop_requested:

            state.phase = "stopped"
            state.running = False

            return

        # ---------------------------------------------------------------------
        # PHASE 2 + 3 - DETAIL + WEBSITE ENRICHMENT
        # ---------------------------------------------------------------------

        state.phase = "detail_enrichment"

        async with async_playwright() as p:

            browser = await p.chromium.launch(
                headless=HEADLESS
            )

            semaphore = asyncio.Semaphore(
                max(1, min(workers, 8))
            )

            tasks = [
                asyncio.create_task(
                    _enrich_one_lead(
                        lead,
                        browser,
                        semaphore,
                    )
                )
                for lead in raw_leads
            ]

            async def _phase_watcher():

                while not all(
                    task.done()
                    for task in tasks
                ):

                    if (
                        state.detail_completed
                        >= len(tasks)
                        and state.phase
                        == "detail_enrichment"
                    ):
                        state.phase = (
                            "website_enrichment"
                        )

                    await asyncio.sleep(0.25)

            watcher = asyncio.create_task(
                _phase_watcher()
            )

            try:

                enriched_leads = await asyncio.gather(
                    *tasks,
                    return_exceptions=True,
                )

            finally:

                watcher.cancel()

                try:
                    await watcher
                except asyncio.CancelledError:
                    pass

                await browser.close()

        # ---------------------------------------------------------------------
        # CLEAN RESULTS
        # ---------------------------------------------------------------------

        clean_leads = []

        for result in enriched_leads:

            if isinstance(
                result,
                Exception,
            ):

                state.errors.append(
                    f"worker error: {result}"
                )

                continue

            clean_leads.append(result)

            state.leads[
                result["lead_id"]
            ] = dict(result)

        _save_checkpoint()

        if state.stop_requested:

            state.phase = "stopped"
            state.running = False

            return

        # ---------------------------------------------------------------------
        # PHASE 4 + 5 - PROCESSING / SCORING
        # ---------------------------------------------------------------------

        state.phase = "lead_processing"

        processed = process_leads(
            clean_leads
        )

        state.processed = len(processed)
        state.final_leads = processed

        state.summary = summarize_leads(
            processed
        )

        # ---------------------------------------------------------------------
        # PHASE 6 - EXPORT
        # ---------------------------------------------------------------------

        state.export_paths = export_all(
            processed,
            state.summary,
        )

        state.phase = "done"

    except Exception as exc:

        logger.exception(
            "Pipeline failed"
        )

        state.phase = "error"

        state.errors.append(
            f"pipeline error: {str(exc)[:300]}"
        )

    finally:

        state.running = False


# =============================================================================
# ROUTES
# =============================================================================

@app.get("/")
async def root():

    return {
        "service": "Google Maps Lead Intelligence",
        "status": "ok",
    }


@app.post("/api/run")
async def run_pipeline(
    req: RunRequest,
):

    if state.running:

        raise HTTPException(
            status_code=409,
            detail=(
                "A pipeline run is already in progress."
            ),
        )

    query = req.query.strip()

    if not query:

        raise HTTPException(
            status_code=400,
            detail="query is required.",
        )

    if req.target_leads < 1:

        raise HTTPException(
            status_code=400,
            detail="target_leads must be >= 1.",
        )

    if req.target_leads > 200:

        raise HTTPException(
            status_code=400,
            detail="target_leads must be <= 200 for this prototype.",
        )

    if req.workers < 1:

        raise HTTPException(
            status_code=400,
            detail="workers must be >= 1.",
        )

    if req.workers > 8:

        raise HTTPException(
            status_code=400,
            detail="workers must be <= 8 for this prototype.",
        )

    asyncio.create_task(
        _run_pipeline(
            query,
            req.target_leads,
            req.workers,
        )
    )

    return {
        "started": True,
        "query": query,
        "target_leads": req.target_leads,
        "workers": req.workers,
    }


@app.get("/api/status")
async def get_status():

    return state.to_status_dict()


@app.get("/api/leads")
async def get_leads():

    leads = (
        state.final_leads
        if state.final_leads
        else list(state.leads.values())
    )

    return {
        "leads": leads,
        "count": len(leads),
    }


@app.get("/api/leads/{lead_id}")
async def get_lead(
    lead_id: str,
):

    leads = (
        state.final_leads
        if state.final_leads
        else list(state.leads.values())
    )

    for lead in leads:

        if lead.get("lead_id") == lead_id:
            return lead

    raise HTTPException(
        status_code=404,
        detail="Lead not found.",
    )


@app.get("/api/summary")
async def get_summary():

    if state.summary:
        return state.summary

    leads = (
        state.final_leads
        if state.final_leads
        else list(state.leads.values())
    )

    return summarize_leads(leads)


def _require_export(
    kind: str,
    filename: str,
) -> Path:

    path = OUTPUT_DIR / filename

    if not path.exists():

        raise HTTPException(
            status_code=404,
            detail=(
                f"No {kind} export available yet. "
                "Run the pipeline first."
            ),
        )

    return path


@app.get("/api/export/json")
async def export_json_route():

    path = _require_export(
        "JSON",
        "leads.json",
    )

    return FileResponse(
        path,
        media_type="application/json",
        filename="leads.json",
    )


@app.get("/api/export/csv")
async def export_csv_route():

    path = _require_export(
        "CSV",
        "leads.csv",
    )

    return FileResponse(
        path,
        media_type="text/csv",
        filename="leads.csv",
    )


@app.get("/api/export/excel")
async def export_excel_route():

    path = _require_export(
        "Excel",
        "leads.xlsx",
    )

    return FileResponse(
        path,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        filename="leads.xlsx",
    )


@app.post("/api/stop")
async def stop_pipeline():

    if not state.running:

        return {
            "stopped": False,
            "message": (
                "No pipeline is currently running."
            ),
        }

    state.stop_requested = True

    return {
        "stopped": True,
        "message": (
            "Stop requested. "
            "The pipeline will halt shortly."
        ),
    }