# LeadHarvest - Google Maps Scraper FastAPI backend entry point

import logging
import os
from contextlib import asynccontextmanager
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from routers import scraper, exports, jobs
from utils.logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

os.makedirs("exports", exist_ok=True)
os.makedirs("logs", exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("LeadHarvest backend starting up")
    yield
    logger.info("LeadHarvest backend shutting down")

app = FastAPI(
    title="LeadHarvest API",
    description="Local-first Google Maps lead scraper",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scraper.router, prefix="/api/scraper", tags=["Scraper"])
app.include_router(exports.router, prefix="/api/exports", tags=["Exports"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])

app.mount("/static", StaticFiles(directory="../frontend/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("../frontend/templates/index.html", "r", encoding ="utf-8") as f:
        return f.read()

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
