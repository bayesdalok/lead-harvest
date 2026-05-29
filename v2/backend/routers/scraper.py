# -- /api/scraper - start and manage scrape jobs. --

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from services.job_manager import JobStatus, job_manager
from services.scraper_service import GoogleMapsScraper, ScraperFilters
from services.export_service import export_leads

logger = logging.getLogger(__name__)
router = APIRouter()

class ScrapeRequest(BaseModel):
    keywords: list[str] = Field(..., min_length=1)
    city: str = ""
    state: str = ""
    max_results: int = Field(60, ge=1, le=200)
    export_format: str = "xlsx"
    # Filters
    min_rating: float = 0.0
    require_phone: bool = False
    require_website: bool = False
    categories: list[str] = []

@router.post("/start")
async def start_scrape(req: ScrapeRequest, background_tasks: BackgroundTasks):
    job = job_manager.create(
        keywords=req.keywords,
        city=req.city,
        state=req.state,
        max_results=req.max_results,
    )
    background_tasks.add_task(_run_job, job.id, req)
    return {"job_id": job.id, "status": job.status}

@router.post("/cancel/{job_id}")
async def cancel_scrape(job_id: str):
    ok = job_manager.cancel(job_id)
    if not ok:
        raise HTTPException(404, "Job not found")
    return {"cancelled": True}


# -- background task that runs the scraper and updates the job status --

async def _run_job(job_id: str, req: ScrapeRequest):
    job = job_manager.get(job_id)
    if not job:
        return

    job.status = JobStatus.RUNNING
    job.touch()

    def progress_cb(event: dict):
        job.add_log(event)
        ev = event.get("event", "")
        if ev == "start":
            job.total_queries = event.get("total_queries", 0)
        elif ev == "lead_found":
            job.leads_found += 1
        elif ev == "query_done":
            job.queries_done += 1

    filters = ScraperFilters(
        min_rating=req.min_rating,
        require_phone=req.require_phone,
        require_website=req.require_website,
        categories=req.categories,
    )
    scraper = GoogleMapsScraper(
        max_results=req.max_results,
        filters=filters,
        progress_cb=progress_cb,
    )

    # Store scraper ref for cancellation
    job.task = asyncio.current_task()

    try:
        leads = await scraper.scrape_all(req.keywords, req.city, req.state)
        path = export_leads(leads, fmt=req.export_format)
        job.export_path = str(path)
        job.status = JobStatus.DONE
        job.add_log({"event": "exported", "path": str(path), "count": len(leads)})
    except asyncio.CancelledError:
        job.status = JobStatus.CANCELLED
    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        job.status = JobStatus.ERROR
        job.error = str(exc)
    finally:
        job.touch()
