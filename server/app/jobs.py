"""Background build-around jobs: one task per anchor across a process pool, with progress and a result cache."""
import hashlib
import json
import os
import threading
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed

from . import store
from .optimizer import Infeasible, build_around
from .settings import Settings

_jobs: dict[str, dict] = {}
_lock = threading.Lock()
_pool: ProcessPoolExecutor | None = None


def _executor() -> ProcessPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ProcessPoolExecutor(max_workers=max(1, min(4, (os.cpu_count() or 2))))
    return _pool


def _one(rows, settings_dump, anchor_id):
    settings = Settings.model_validate(settings_dump)
    try:
        return build_around(rows, settings, anchor_id)
    except Infeasible as e:
        name = next((r["player"] for r in rows if r["id"] == anchor_id), anchor_id)
        return {"anchor_id": anchor_id, "anchor": name, "error": str(e)}


def cache_key(snapshot_ids, settings: Settings, anchors) -> str:
    blob = json.dumps({"snap": snapshot_ids, "league": settings.league.model_dump(), "model": settings.model.model_dump(),
                       "anchors": anchors}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:24]


def start(rows, settings: Settings, anchors: list[str], key: str) -> dict:
    cached = store.cache_get(key)
    job_id = uuid.uuid4().hex[:12]
    if cached is not None:
        job = {"id": job_id, "status": "done", "done": len(anchors), "total": len(anchors), "results": cached, "cached": True}
        _jobs[job_id] = job
        return job
    job = {"id": job_id, "status": "running", "done": 0, "total": len(anchors), "results": None, "cached": False}
    _jobs[job_id] = job

    def run():
        try:
            futures = {_executor().submit(_one, rows, settings.model_dump(), a): a for a in anchors}
            results = {}
            for f in as_completed(futures):
                results[futures[f]] = f.result()
                with _lock:
                    job["done"] += 1
            ordered = [results[a] for a in anchors]
            store.cache_set(key, ordered)
            job.update(status="done", results=ordered)
        except Exception as e:  # report instead of leaving the job hanging
            job.update(status="failed", error=f"Build failed: {e.__class__.__name__}: {e}")

    threading.Thread(target=run, daemon=True).start()
    return job


def get(job_id: str) -> dict | None:
    return _jobs.get(job_id)
