from __future__ import annotations
import os
from typing import Optional
from fastapi import FastAPI, Request, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta

from .storage import DB
from .auth import make_session, issue_token, verify_admin_key, get_current_session, require_scopes
from .models import TokenRequest, TokenResponse, TracesResponse, TraceItem, MetricsSummary
from .middleware import TraceMiddleware

TITLE = "KB Platform – Secure API"
VERSION = "1.0.0"

def env(name: str, default: Optional[str]=None) -> str:
    return os.getenv(name, default)

TRACE_DB_PATH = env("TRACE_DB_PATH", "./secure_api/secure_api_traces.db")
MAX_REQUEST_BYTES = int(env("MAX_REQUEST_BYTES","65536"))
ALLOWED_ORIGINS = [o.strip() for o in env("ALLOWED_ORIGINS","*").split(",")]

app = FastAPI(title=TITLE, version=VERSION)
app.state.db = DB(TRACE_DB_PATH)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS != ["*"] else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tracing middleware (log every request/response)
app.add_middleware(TraceMiddleware, db=app.state.db, max_request_bytes=MAX_REQUEST_BYTES)

# Templating for dashboard
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "dashboards", "templates"))

@app.get("/healthz")
async def healthz():
    return {"ok": True, "service": TITLE, "version": VERSION}

@app.get("/readyz")
async def readyz():
    # simple checks
    try:
        app.state.db.query("SELECT 1")
        ok_db = True
    except Exception:
        ok_db = False
    return {"ready": ok_db}

# ---------- Auth ----------
@app.post("/v1/auth/token", response_model=TokenResponse, tags=["Auth"])
async def create_token(req: Request, body: TokenRequest):
    verify_admin_key(req)
    sess = make_session(body.client_name, body.scopes, body.ttl_seconds, body.ip_lock)
    out = issue_token(app.state.db, sess)
    return TokenResponse(token=out["token"], expires_at=out["expires_at"], session_id=out["session_id"])

# ---------- Test ----------
@app.get("/v1/test/ping", tags=["Test"])
async def ping(request: Request, _: dict = Depends(get_current_session), echo: Optional[str]=Query(None)):
    return {
        "ok": True,
        "pong": datetime.now(timezone.utc).isoformat(),
        "echo": echo,
        "trace_id": "see /v1/traces"
    }

# ---------- Traces ----------
@app.get("/v1/traces", response_model=TracesResponse, tags=["Observability"])
async def list_traces(
    request: Request,
    _: bool = Depends(require_scopes(["read:traces"])),
    since: Optional[str] = Query(None, description="ISO timestamp"),
    limit: int = Query(100, ge=1, le=1000),
    status_code: Optional[int] = Query(None, ge=100, le=599),
    path: Optional[str] = Query(None),
    ip: Optional[str] = Query(None),
):
    rows = app.state.db.list_traces(since=since, limit=limit, status=status_code, path=path, ip=ip)
    items = []
    for r in rows:
        items.append(TraceItem(
            id=r["id"], ts=r["ts"], method=r["method"], path=r["path"],
            status=r["status"], latency_ms=r["latency_ms"], ip=r["ip"], ua=r["ua"],
            headers_slim=(__import__("json").loads(r["headers_slim"]) if r["headers_slim"] else None),
            query=(__import__("json").loads(r["query"]) if r["query"] else None),
            body_sha256=r["body_sha256"], token_sub=r["token_sub"], error=r["error"]
        ))
    return TracesResponse(items=items, next_cursor=None)

@app.get("/v1/metrics/summary", response_model=MetricsSummary, tags=["Observability"])
async def metrics_summary(
    request: Request,
    _: bool = Depends(require_scopes(["read:metrics"])),
    window_seconds: int = Query(3600, ge=60, le=24*3600)
):
    data = app.state.db.metrics_summary(window_seconds=window_seconds)
    return data

# ---------- Dashboard ----------
@app.get("/dashboard", response_class=HTMLResponse, tags=["Observability"])
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": TITLE})

