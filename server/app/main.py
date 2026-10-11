"""FastAPI app: JSON API under /api and the built React client at /."""
import contextlib
import logging
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import draft, jobs, store
from .core.engine import compute_board
from .optimizer import Infeasible
from .settings import CAT_LABEL, Settings, defaults, reference
from .sources import csvio, service

log = logging.getLogger("auction")
CLIENT_DIST = Path(__file__).resolve().parent.parent.parent / "client" / "dist"

_board_memo: dict = {"key": None, "value": None}
_memo_lock = threading.Lock()
# Handlers run in a threadpool, so draft writes take this lock to validate and record a sale atomically.
_draft_lock = threading.Lock()


# ---------- helpers ----------
def err(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


def load_settings() -> Settings:
    saved = store.get_kv("settings")
    if saved:
        try:
            return Settings.model_validate(saved)
        except ValidationError:
            log.warning("saved settings invalid; using defaults")
    return defaults()


def board() -> dict:
    settings = load_settings()
    data, meta = service.active_data()
    key = (tuple((m or {}).get("snapshot_id") for m in meta.values()), settings.model_dump_json())
    with _memo_lock:
        if _board_memo["key"] == key:
            return _board_memo["value"]
    b = compute_board(data, settings)
    b["sources"] = meta
    b["settings"] = settings.model_dump()
    b["roster"] = settings.league.roster
    b["categories"] = [{"key": c, "label": CAT_LABEL[c]} for c in settings.league.categories]
    with _memo_lock:
        _board_memo.update(key=key, value=b)
    return b


def draft_state(settings: Settings) -> dict:
    teams = store.get_kv("draft_teams")
    sales = store.list_sales()
    if not teams or (len(teams) != settings.league.teams and not sales):
        teams = [{"id": i, "name": "My team" if i == 0 else f"Team {i + 1}", "is_me": i == 0} for i in range(settings.league.teams)]
        store.set_kv("draft_teams", teams)
    return {"teams": teams, "sales": sales}


# ---------- request bodies ----------
class BuildsIn(BaseModel):
    anchors: list[str] | None = None


class RefreshIn(BaseModel):
    source_id: str | None = None


class SetupIn(BaseModel):
    teams: list[str] = []
    me: int = 0


class SaleIn(BaseModel):
    player_id: str
    team_id: int
    price: int


class Force(BaseModel):
    player_id: str
    price: int


class PlanIn(BaseModel):
    force: Force | None = None


# ---------- app ----------
def startup():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    store.init()
    service.ensure_seed()
    settings = load_settings()
    if settings.sources.auto_fetch:
        threading.Thread(target=service.refresh_stale, args=(settings,), daemon=True).start()


@contextlib.asynccontextmanager
async def lifespan(app):
    startup()
    yield


app = FastAPI(title="Auction Board", lifespan=lifespan)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    first = exc.errors()[0]
    if first["type"] == "json_invalid":
        return err("The request body isn't valid JSON.", 422)
    where = ".".join(str(x) for x in first["loc"][1:])  # drop the leading "body"/"path"
    return err(f"{where}: {first['msg']}" if where else first["msg"], 422)


# ---------- settings ----------
@app.get("/api/settings")
def get_settings():
    s = load_settings()
    return {"settings": s.model_dump(), "defaults": defaults().model_dump(),
            "reference": reference().model_dump(), "roster": s.league.roster}


@app.put("/api/settings")
def put_settings(s: Settings):
    store.set_kv("settings", s.model_dump())
    return {"settings": s.model_dump(), "roster": s.league.roster}


@app.post("/api/settings/reset")
def reset_settings():
    store.set_kv("settings", defaults().model_dump())
    return {"settings": defaults().model_dump()}


# ---------- board & builds ----------
@app.get("/api/board")
def get_board():
    return board()


@app.post("/api/builds")
def post_builds(payload: BuildsIn = BuildsIn()):
    b = board()
    settings = load_settings()
    ids = {r["id"] for r in b["rows"] if r["proj"]}
    anchors = payload.anchors or [r["id"] for r in b["rows"] if r["proj"]][: settings.model.anchors]
    bad = [a for a in anchors if a not in ids]
    if bad:
        raise HTTPException(422, f"Can't build around {', '.join(bad)}: not on the board or no projection.")
    snap_ids = [(m or {}).get("snapshot_id") for m in b["sources"].values()]
    return jobs.start(b["rows"], settings, anchors, jobs.cache_key(snap_ids, settings, anchors))


@app.get("/api/builds/{job_id}")
def get_build(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "That build job doesn't exist; start a new build.")
    return job


# ---------- sources ----------
@app.get("/api/sources")
def get_sources():
    b = board()
    return {"sources": service.status(), "unmatched": b["unmatched"], "auto_fetch": load_settings().sources.auto_fetch}


@app.post("/api/sources/refresh")
def refresh_sources(payload: RefreshIn = RefreshIn()):
    settings = load_settings()
    sid = payload.source_id
    if sid and sid not in service.SOURCES:
        raise HTTPException(404, f"Unknown source {sid}.")
    results = [service.refresh(sid, settings)] if sid else service.refresh_stale(settings, True)
    return {"results": results, "sources": service.status()}


@app.post("/api/sources/{source_id}/import")
def import_source(source_id: str, file: UploadFile | None = None):
    if source_id not in service.SOURCES:
        raise HTTPException(404, f"Unknown source {source_id}.")
    if file is None:
        raise HTTPException(400, "Attach a CSV file in the 'file' field.")
    text = file.file.read().decode("utf-8", errors="replace")
    try:
        result = service.import_csv(source_id, text)
    except csvio.InvalidData as e:
        raise HTTPException(422, f"That CSV can't be used: {e}")
    return {"result": result, "sources": service.status()}


# ---------- draft ----------
def _draft_payload():
    settings = load_settings()
    b = board()
    state = draft_state(settings)
    d = draft.derive(b["rows"], settings, state)
    d["setup"] = state["teams"]
    d["budget"], d["roster"] = settings.league.budget, settings.league.roster
    d["warning"] = (f"The draft has {len(state['teams'])} teams but settings say {settings.league.teams}. "
                    "Reset the draft to match." if len(state["teams"]) != settings.league.teams else None)
    return d


@app.get("/api/draft")
def get_draft():
    return _draft_payload()


@app.post("/api/draft/setup")
def setup_draft(payload: SetupIn):
    settings = load_settings()
    names, me = payload.teams, payload.me
    if len(names) != settings.league.teams:
        raise HTTPException(422, f"Enter exactly {settings.league.teams} team names.")
    if not 0 <= me < len(names):
        raise HTTPException(422, "Pick which team is yours.")
    clean = [n.strip()[:40] or f"Team {i + 1}" for i, n in enumerate(names)]
    with _draft_lock:
        store.clear_sales()
        store.set_kv("draft_teams", [{"id": i, "name": n, "is_me": i == me} for i, n in enumerate(clean)])
    return _draft_payload()


@app.post("/api/draft/sales")
def add_sale(payload: SaleIn):
    settings = load_settings()
    b = board()
    with _draft_lock:
        state = draft_state(settings)
        try:
            draft.validate_sale({r["id"]: r for r in b["rows"]}, settings, state, payload.player_id, payload.team_id, payload.price)
        except draft.SaleError as e:
            raise HTTPException(409, str(e))
        store.add_sale(payload.player_id, payload.team_id, payload.price)
    return _draft_payload()


@app.delete("/api/draft/sales/{sale_id}")
def delete_sale(sale_id: int):
    with _draft_lock:
        if not store.delete_sale(sale_id):
            raise HTTPException(404, "That sale was already removed.")
    return _draft_payload()


@app.post("/api/draft/plan")
def draft_plan(payload: PlanIn = PlanIn()):
    settings = load_settings()
    b = board()
    state = draft_state(settings)
    force = payload.force.model_dump() if payload.force else None
    try:
        p = draft.plan(b["rows"], settings, state, force)
        p["nominations"] = draft.nominations(b["rows"], settings, state, p["plan_ids"])
    except Infeasible as e:
        raise HTTPException(422, str(e))
    return p


# ---------- client ----------
NO_CLIENT = """<!doctype html><meta charset="utf-8"><title>Auction Board</title>
<body style="font-family:system-ui;max-width:640px;margin:48px auto;padding:0 16px;line-height:1.5">
<h1>Auction Board server is running</h1><p>The web client hasn't been built yet. In <code>client/</code> run
<code>npm install</code> then <code>npm run build</code>, and reload this page. For development, run
<code>npm run dev</code> and open <a href="http://127.0.0.1:5173">http://127.0.0.1:5173</a>.</p>
<p>The API is live at <a href="/api/board">/api/board</a>.</p></body>"""

if CLIENT_DIST.exists():
    app.mount("/", StaticFiles(directory=CLIENT_DIST, html=True), name="client")
else:
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def no_client():
        return NO_CLIENT
