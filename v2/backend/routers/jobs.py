# -- /api/jobs — list and inspect scrape jobs. --

from fastapi import APIRouter, HTTPException
from services.job_manager import job_manager

router = APIRouter()

@router.get("/")
async def list_jobs():
    return [j.to_dict() for j in job_manager.all()]

@router.get("/{job_id}")
async def get_job(job_id: str):
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job.to_dict()

@router.delete("/{job_id}")
async def delete_job(job_id: str):
    ok = job_manager.delete(job_id)
    if not ok:
        raise HTTPException(404, "Job not found")
    return {"deleted": True}
