from __future__ import annotations

import os
import secrets
import time
from pathlib import Path
import json
import uuid
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

from dotenv import load_dotenv

# Import our new modules
from .storage import DB
from .auth import make_session, issue_token, authenticate_user, get_current_session, require_scopes
from .models import (
    TokenRequest, TokenResponse, TracesResponse, TraceItem, MetricsSummary,
    Project, FAQ, KBArticle, BatchFAQUpsertRequest, BatchKBUpsertRequest, 
    QueryRequest, QueryResponse
)
from .middleware import TraceMiddleware

APP_DIR = Path(__file__).resolve().parent
# Canonical storage root in HOME as requested
HOME_ROOT = Path.home()
PROJ_MAP_FILE = HOME_ROOT / "proj_mapping.txt"
LOG_DIR = HOME_ROOT / ".kbai"
LOG_DIR.mkdir(parents=True, exist_ok=True)
REQUEST_LOG = LOG_DIR / "requests.jsonl"

load_dotenv(dotenv_path=APP_DIR.parent / ".env", override=False)

# Environment variables
def env(name: str, default: Optional[str]=None) -> str:
    return os.getenv(name, default)

TRACE_DB_PATH = env("TRACE_DB_PATH", "./secure_api/secure_api_traces.db")
MAX_REQUEST_BYTES = int(env("MAX_REQUEST_BYTES","65536"))
ALLOWED_ORIGINS = [o.strip() for o in env("ALLOWED_ORIGINS","*").split(",")]
SECURE_TOKEN = os.environ.get("KBAI_API_TOKEN") or secrets.token_hex(16)

TITLE = "Knowledge Base AI API"
VERSION = "1.0.0"

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

templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
security = HTTPBearer(auto_error=False)


# Prometheus metrics
REQUEST_COUNT = Counter("kbai_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("kbai_request_latency_seconds", "Request latency", ["endpoint"])
READY_GAUGE = Gauge("kbai_ready", "Readiness state (1 ready, 0 not)")

# Remove the old middleware since we're using TraceMiddleware now


class Project(BaseModel):
    id: str = Field(..., description="Project identifier")
    name: str = Field(..., description="Human-readable name")
    active: bool = True


class FAQ(BaseModel):
    id: str
    question: str
    answer: str


class KBArticle(BaseModel):
    id: str
    title: str
    content: str


def _project_dir(project_id: str) -> Path:
    d = DATA_DIR / project_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "faqs").mkdir(exist_ok=True)
    (d / "kb").mkdir(exist_ok=True)
    (d / "ingest").mkdir(exist_ok=True)
    return d


def _read_proj_map() -> Dict[str, Project]:
    mapping: Dict[str, Project] = {}
    if PROJ_MAP_FILE.exists():
        for line in PROJ_MAP_FILE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            parts = line.split("|", 2)
            if len(parts) == 3:
                pid, name, active_str = parts
                mapping[pid] = Project(id=pid, name=name, active=(active_str == "1"))
    return mapping


def _write_proj_map(mapping: Dict[str, Project]) -> None:
    tmp = PROJ_MAP_FILE.with_suffix(".tmp")
    content = "\n".join(f"{p.id}|{p.name}|{'1' if p.active else '0'}" for p in mapping.values())
    tmp.write_text(content + "\n", encoding="utf-8")
    tmp.replace(PROJ_MAP_FILE)


def _list_json(dir_path: Path) -> List[dict]:
    items: List[dict] = []
    for file in sorted(dir_path.glob("*.json")):
        try:
            items.append(json.loads(file.read_text(encoding="utf-8")))
        except Exception:
            continue
    return items


def _write_json(file_path: Path, obj: dict) -> None:
    file_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _delete_json(file_path: Path) -> None:
    if file_path.exists():
        file_path.unlink()


def track_metrics(endpoint: str):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                response = await func(*args, **kwargs)
                status = getattr(response, "status_code", 200)
                return response
            except HTTPException as exc:
                status = exc.status_code
                raise
            finally:
                REQUEST_COUNT.labels("ANY", endpoint, str(locals().get("status", 200))).inc()
                REQUEST_LATENCY.labels(endpoint).observe(time.perf_counter() - start)
        return wrapper
    return decorator


@app.get("/healthz", response_class=PlainTextResponse)
async def healthz():
    return "ok"

@app.get("/readyz", response_class=PlainTextResponse)
async def readyz():
    # Check database connectivity
    try:
        app.state.db.query("SELECT 1")
        ready = True
    except Exception:
        ready = False
    READY_GAUGE.set(1 if ready else 0)
    return "ready" if ready else "not ready"

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Authentication endpoints
@app.post("/v1/auth/token", response_model=TokenResponse, tags=["Auth"])
async def create_token(req: TokenRequest):
    # Authenticate user with username/password
    if not authenticate_user(req.username, req.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create session with appropriate scopes
    sess = make_session(req.client_name, req.scopes, req.ttl_seconds, None)
    out = issue_token(app.state.db, sess)
    return TokenResponse(
        access_token=out["token"], 
        expires_at=out["expires_at"], 
        session_id=out["session_id"]
    )


# Observability endpoints
@app.get("/v1/traces", response_model=TracesResponse, tags=["Observability"])
async def list_traces(
    request: Request,
    session: dict = Depends(get_current_session),
    since: Optional[str] = Query(None, description="ISO timestamp"),
    limit: int = Query(100, ge=1, le=1000),
    status_code: Optional[int] = Query(None, ge=100, le=599),
    path: Optional[str] = Query(None),
    ip: Optional[str] = Query(None),
):
    # Check if user has required scopes
    scopes = session.get("scopes", [])
    if "read:basic" not in scopes:
        raise HTTPException(status_code=403, detail="insufficient permissions")
    
    rows = app.state.db.list_traces(since=since, limit=limit, status=status_code, path=path, ip=ip)
    items = []
    for r in rows:
        items.append(TraceItem(
            id=r["id"], ts=r["ts"], method=r["method"], path=r["path"],
            status=r["status"], latency_ms=r["latency_ms"], ip=r["ip"], ua=r["ua"],
            headers_slim=(json.loads(r["headers_slim"]) if r["headers_slim"] else None),
            query=(json.loads(r["query"]) if r["query"] else None),
            body_sha256=r["body_sha256"], token_sub=r["token_sub"], error=r["error"]
        ))
    return TracesResponse(items=items, next_cursor=None)

@app.get("/v1/metrics/summary", response_model=MetricsSummary, tags=["Observability"])
async def metrics_summary(
    request: Request,
    session: dict = Depends(get_current_session),
    window_seconds: int = Query(3600, ge=60, le=24*3600)
):
    # Check if user has required scopes  
    scopes = session.get("scopes", [])
    if "read:basic" not in scopes:
        raise HTTPException(status_code=403, detail="insufficient permissions")
    
    data = app.state.db.metrics_summary(window_seconds=window_seconds)
    return data

# Admin dashboard with no authentication requirement - handles auth in the frontend
@app.get("/admin", response_class=HTMLResponse, tags=["Admin"])
async def admin_dashboard(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request, "title": TITLE})

# Project endpoints - updated to check auth and return proper status codes
@app.post("/v1/projects", tags=["Projects"])
async def add_or_rename_project(project: Project, request: Request, _: dict = Depends(get_current_session)):
    return JSONResponse({"detail": "Not implemented", "authenticated": True}, status_code=501)

@app.get("/v1/projects", response_model=List[Project], tags=["Projects"])
async def list_projects(request: Request, _: dict = Depends(get_current_session)):
    return JSONResponse({"detail": "Not implemented", "authenticated": True}, status_code=501)

@app.get("/v1/projects/{project_id}", response_model=Project, tags=["Projects"])
async def get_project(project_id: str, request: Request, _: dict = Depends(get_current_session)):
    return JSONResponse({"detail": "Not implemented", "authenticated": True}, status_code=501)

@app.delete("/v1/projects/{project_id}", tags=["Projects"])
async def soft_delete_project(project_id: str, request: Request, _: dict = Depends(get_current_session)):
    return JSONResponse({"detail": "Not implemented", "authenticated": True}, status_code=501)

@app.get("/v1/projects/{project_id}/faqs", response_model=List[FAQ], tags=["Projects"])
async def list_faqs(project_id: str, request: Request, _: dict = Depends(get_current_session)):
    return JSONResponse({"detail": "Not implemented", "authenticated": True}, status_code=501)

@app.post("/v1/projects/{project_id}/faqs:batch_upsert", tags=["Projects"])
async def batch_upsert_faqs(project_id: str, req: BatchFAQUpsertRequest, request: Request, _: dict = Depends(get_current_session)):
    return JSONResponse({"detail": "Not implemented", "authenticated": True}, status_code=501)

@app.delete("/v1/projects/{project_id}/faqs/{faq_id}", tags=["Projects"])
async def delete_faq(project_id: str, faq_id: str, request: Request, _: dict = Depends(get_current_session)):
    return JSONResponse({"detail": "Not implemented", "authenticated": True}, status_code=501)

@app.get("/v1/projects/{project_id}/kb", response_model=List[KBArticle], tags=["Projects"])
async def list_kb(project_id: str, request: Request, _: dict = Depends(get_current_session)):
    return JSONResponse({"detail": "Not implemented", "authenticated": True}, status_code=501)

@app.post("/v1/projects/{project_id}/kb:batch_upsert", tags=["Projects"])
async def batch_upsert_kb(project_id: str, req: BatchKBUpsertRequest, request: Request, _: dict = Depends(get_current_session)):
    return JSONResponse({"detail": "Not implemented", "authenticated": True}, status_code=501)

@app.delete("/v1/projects/{project_id}/kb/{kb_id}", tags=["Projects"])
async def delete_kb(project_id: str, kb_id: str, request: Request, _: dict = Depends(get_current_session)):
    return JSONResponse({"detail": "Not implemented", "authenticated": True}, status_code=501)

@app.post("/v1/projects/{project_id}/ingest", tags=["Projects"])
async def ingest_data(project_id: str, request: Request, file: UploadFile = File(...), _: dict = Depends(get_current_session)):
    return JSONResponse({"detail": "Not implemented", "authenticated": True}, status_code=501)

@app.post("/v1/projects/{project_id}/reindex", tags=["Projects"])
async def reindex(project_id: str, request: Request, _: dict = Depends(get_current_session)):
    return JSONResponse({"detail": "Not implemented", "authenticated": True}, status_code=501)

@app.post("/v1/query", response_model=QueryResponse, tags=["Projects"])
async def query_kb(req: QueryRequest, request: Request, _: dict = Depends(get_current_session)):
    return JSONResponse({"detail": "Not implemented", "authenticated": True}, status_code=501)

@app.get("/v1/projects/{project_id}/stats", tags=["Projects"])
async def project_stats(project_id: str, request: Request, _: dict = Depends(get_current_session)):
    return JSONResponse({"detail": "Not implemented", "authenticated": True}, status_code=501)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=False)


