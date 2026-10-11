"""Source registry: seed loading, automatic refresh, CSV import, and the active data set."""
import logging
import threading
import time
from pathlib import Path

from .. import store
from . import csvio
from .base import FetchError, fetch
from .parsers import PARSERS, ParseError

log = logging.getLogger("auction.sources")
SEED_DIR = Path(__file__).resolve().parent.parent.parent / "seed"

SOURCES = {
    "hashtag_adp": {"label": "Hashtag Basketball ADP", "provides": "Draft order, teams, positions", "url_key": "hashtag_adp_url"},
    "hashtag_auction": {"label": "Hashtag Basketball auction values", "provides": "Yahoo and ESPN average cost (free top 30)", "url_key": "hashtag_auction_url"},
    "fantasypros_proj": {"label": "FantasyPros projections", "provides": "Season stat projections", "url_key": "fantasypros_proj_url"},
    # Dated articles: fetched once per URL; set a new URL in Settings to follow a newer article.
    "rotoworld_rank": {"label": "Rotoworld Top 200", "provides": "Expert 9-cat rankings", "url_key": "rotoworld_rank_url", "static": True},
    "rotoworld_mock": {"label": "Rotoworld salary mock", "provides": "Industry mock auction prices", "url_key": "rotoworld_mock_url", "static": True},
}

_refreshing: set[str] = set()
_rlock = threading.Lock()


def ensure_seed():
    for sid in SOURCES:
        if store.active_snapshot(sid, with_rows=False) is None:
            rows = csvio.validate(sid, csvio.read_csv((SEED_DIR / f"{sid}.csv").read_text()))
            store.add_snapshot(sid, "seed", "seed/" + sid + ".csv", rows)


def active_data() -> tuple[dict, dict]:
    data, meta = {}, {}
    for sid in SOURCES:
        snap = store.active_snapshot(sid)
        data[sid] = snap["rows"] if snap else []
        meta[sid] = {"snapshot_id": snap["id"], "retrieved_at": snap["retrieved_at"], "method": snap["method"]} if snap else None
    return data, meta


def refresh(sid: str, settings) -> dict:
    url = getattr(settings.sources, SOURCES[sid]["url_key"])
    with _rlock:
        if sid in _refreshing:
            return {"source_id": sid, "status": "busy", "error": "Already refreshing."}
        _refreshing.add(sid)
    try:
        html = fetch(url)
        rows = csvio.validate(sid, PARSERS[sid](html))
        snap_id = store.add_snapshot(sid, "fetch", url, rows)
        log.info("refreshed %s: %d rows", sid, len(rows))
        return {"source_id": sid, "status": "ok", "rows": len(rows), "snapshot_id": snap_id}
    except (FetchError, ParseError, csvio.InvalidData) as e:
        store.add_snapshot(sid, "fetch", url, None, status="failed", error=str(e))
        log.warning("refresh %s failed: %s", sid, e)
        return {"source_id": sid, "status": "failed", "error": str(e)}
    except Exception as e:  # unexpected parser crash: keep the old data and report it
        store.add_snapshot(sid, "fetch", url, None, status="failed", error=f"Unexpected error: {e.__class__.__name__}: {e}")
        log.exception("refresh %s crashed", sid)
        return {"source_id": sid, "status": "failed", "error": f"Unexpected error: {e}"}
    finally:
        with _rlock:
            _refreshing.discard(sid)


def refresh_stale(settings, force=False) -> list[dict]:
    out = []
    if not settings.sources.auto_fetch and not force:
        return out
    max_age = settings.sources.fetch_max_age_hours * 3600
    for sid in SOURCES:
        snap = store.active_snapshot(sid, with_rows=False)
        last = store.last_attempt(sid)
        url = getattr(settings.sources, SOURCES[sid]["url_key"])
        fresh = snap and snap["method"] != "seed" and (
            (SOURCES[sid].get("static") and snap["url"] == url) or time.time() - snap["retrieved_at"] < max_age)
        tried_recently = last and last["status"] == "failed" and time.time() - last["retrieved_at"] < 600
        if force or not (fresh or tried_recently):
            out.append(refresh(sid, settings))
    return out


def import_csv(sid: str, text: str) -> dict:
    rows = csvio.validate(sid, csvio.read_csv(text))
    snap_id = store.add_snapshot(sid, "import", "uploaded CSV", rows)
    return {"source_id": sid, "status": "ok", "rows": len(rows), "snapshot_id": snap_id}


def status() -> list[dict]:
    out = []
    for sid, info in SOURCES.items():
        snap = store.active_snapshot(sid, with_rows=False)
        last = store.last_attempt(sid)
        out.append({"id": sid, **{k: v for k, v in info.items() if k not in ("url_key", "static")}, "static": bool(info.get("static")),
                    "active": snap and {k: snap[k] for k in ("id", "retrieved_at", "method", "url", "row_count")},
                    "last_attempt": last and {k: last[k] for k in ("retrieved_at", "method", "status", "error")},
                    "refreshing": sid in _refreshing})
    return out
