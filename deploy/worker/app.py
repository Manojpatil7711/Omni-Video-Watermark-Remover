"""Authenticated GPU-worker HTTP contract.

Large video binaries stay in object storage. Jobs reference URLs and are
processed by the worker pipeline.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from threading import Lock
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, HttpUrl

app = FastAPI(title="Omni Watermark GPU Worker", version="0.1.1")
_jobs: dict[str, dict[str, Any]] = {}
_lock = Lock()


class JobRequest(BaseModel):
    input_url: HttpUrl
    output_url: HttpUrl | None = None
    mode: str = "auto"
    backend: str = "auto"


@dataclass(frozen=True)
class WorkerConfig:
    api_key: str


def _config() -> WorkerConfig:
    return WorkerConfig(api_key=os.environ.get("WORKER_API_KEY", ""))


def _authorize(value: str | None) -> None:
    key = _config().api_key
    if not key or not value or not secrets.compare_digest(value, key):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/jobs", status_code=202)
def create_job(payload: JobRequest, x_worker_key: str | None = Header(default=None)) -> dict[str, str]:
    _authorize(x_worker_key)
    job_id = secrets.token_urlsafe(12)
    with _lock:
        _jobs[job_id] = {
            "id": job_id,
            "status": "queued",
            "progress": 0,
            "input_url": str(payload.input_url),
            "output_url": str(payload.output_url) if payload.output_url else None,
            "mode": payload.mode,
            "backend": payload.backend,
        }
    return {"id": job_id, "status": "queued"}


@app.get("/v1/jobs/{job_id}")
def get_job(job_id: str, x_worker_key: str | None = Header(default=None)) -> dict[str, Any]:
    _authorize(x_worker_key)
    with _lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
