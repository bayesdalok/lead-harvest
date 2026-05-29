# --Job manager - tracks scraping jobs in memory
# Supports: create, cancel, progress updates, result storage.

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    CANCELLED = "cancelled"
    ERROR = "error"

@dataclass
class ScrapeJob:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Config
    keywords: list[str] = field(default_factory=list)
    city: str = ""
    state: str = ""
    max_results: int = 60

    # Progress
    logs: list[dict] = field(default_factory=list)
    leads_found: int = 0
    queries_done: int = 0
    total_queries: int = 0

    # Result
    export_path: Optional[str] = None
    error: Optional[str] = None

    # Internal
    task: Optional[asyncio.Task] = field(default=None, repr=False)

    def touch(self):
        self.updated_at = datetime.now().isoformat()

    def add_log(self, event: dict):
        self.logs.append(event)
        if len(self.logs) > 500:
            self.logs = self.logs[-500:]
        self.touch()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "keywords": self.keywords,
            "city": self.city,
            "state": self.state,
            "max_results": self.max_results,
            "leads_found": self.leads_found,
            "queries_done": self.queries_done,
            "total_queries": self.total_queries,
            "export_path": self.export_path,
            "error": self.error,
            "logs": self.logs[-50:],
        }

class JobManager:
    # Singleton-style in-memory job store.

    def __init__(self):
        self._jobs: dict[str, ScrapeJob] = {}

    def create(self, **kwargs) -> ScrapeJob:
        job = ScrapeJob(**kwargs)
        self._jobs[job.id] = job
        logger.info("Job created: %s", job.id)
        return job

    def get(self, job_id: str) -> Optional[ScrapeJob]:
        return self._jobs.get(job_id)

    def all(self) -> list[ScrapeJob]:
        return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.task and not job.task.done():
            job.task.cancel()
        job.status = JobStatus.CANCELLED
        job.touch()
        logger.info("Job cancelled: %s", job_id)
        return True

    def delete(self, job_id: str) -> bool:
        if job_id in self._jobs:
            self.cancel(job_id)
            del self._jobs[job_id]
            return True
        return False

# Global singleton
job_manager = JobManager()
