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

# Import our modules
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

# Use SQLite database in app directory
TRACE_DB_PATH = env("TRACE_DB_PATH", "./app/kbai_api.db")
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

# Data directory for project storage
DATA_DIR = HOME_ROOT / ".kbai" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

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

# Test endpoint
@app.get("/v1/test/ping", tags=["Test"])
async def ping(request: Request, _: dict = Depends(get_current_session), echo: Optional[str]=Query(None)):
    from datetime import datetime, timezone
    return {
        "ok": True,
        "pong": datetime.now(timezone.utc).isoformat(),
        "echo": echo,
        "trace_id": "see /v1/traces"
    }

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
    if "read:basic" not in scopes and "read:traces" not in scopes:
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
    if "read:basic" not in scopes and "read:metrics" not in scopes:
        raise HTTPException(status_code=403, detail="insufficient permissions")
    
    data = app.state.db.metrics_summary(window_seconds=window_seconds)
    return data

# Admin dashboard with no authentication requirement - handles auth in the frontend
@app.get("/admin", response_class=HTMLResponse, tags=["Admin"])
async def admin_dashboard(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request, "title": TITLE})

# Dashboard redirect (legacy support)
@app.get("/dashboard", response_class=HTMLResponse, tags=["Admin"])
async def dashboard_redirect(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request, "title": TITLE})

# Project endpoints
@app.post("/v1/projects", tags=["Projects"])
async def add_or_rename_project(project: Project, request: Request, _: dict = Depends(get_current_session)):
    mapping = _read_proj_map()
    mapping[project.id] = project
    _write_proj_map(mapping)
    _project_dir(project.id)  # Ensure directory exists
    return {"detail": "Project created/updated", "project": project}

@app.get("/v1/projects", response_model=List[Project], tags=["Projects"])
async def list_projects(request: Request, _: dict = Depends(get_current_session)):
    mapping = _read_proj_map()
    return list(mapping.values())

@app.get("/v1/projects/{project_id}", response_model=Project, tags=["Projects"])
async def get_project(project_id: str, request: Request, _: dict = Depends(get_current_session)):
    mapping = _read_proj_map()
    if project_id not in mapping:
        raise HTTPException(status_code=404, detail="Project not found")
    return mapping[project_id]

@app.delete("/v1/projects/{project_id}", tags=["Projects"])
async def soft_delete_project(project_id: str, request: Request, _: dict = Depends(get_current_session)):
    mapping = _read_proj_map()
    if project_id not in mapping:
        raise HTTPException(status_code=404, detail="Project not found")
    mapping[project_id].active = False
    _write_proj_map(mapping)
    return {"detail": "Project deactivated"}

@app.get("/v1/projects/{project_id}/faqs", response_model=List[FAQ], tags=["Projects"])
async def list_faqs(project_id: str, request: Request, _: dict = Depends(get_current_session)):
    project_dir = _project_dir(project_id)
    faqs_dir = project_dir / "faqs"
    items = _list_json(faqs_dir)
    return [FAQ(**item) for item in items]

@app.post("/v1/projects/{project_id}/faqs:batch_upsert", tags=["Projects"])
async def batch_upsert_faqs(project_id: str, req: BatchFAQUpsertRequest, request: Request, _: dict = Depends(get_current_session)):
    project_dir = _project_dir(project_id)
    faqs_dir = project_dir / "faqs"
    
    for faq in req.items:
        file_path = faqs_dir / f"{faq.id}.json"
        _write_json(file_path, faq.dict())
    
    return {"detail": f"Upserted {len(req.items)} FAQs"}

@app.delete("/v1/projects/{project_id}/faqs/{faq_id}", tags=["Projects"])
async def delete_faq(project_id: str, faq_id: str, request: Request, _: dict = Depends(get_current_session)):
    project_dir = _project_dir(project_id)
    file_path = project_dir / "faqs" / f"{faq_id}.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="FAQ not found")
    _delete_json(file_path)
    return {"detail": "FAQ deleted"}

@app.get("/v1/projects/{project_id}/kb", response_model=List[KBArticle], tags=["Projects"])
async def list_kb(project_id: str, request: Request, _: dict = Depends(get_current_session)):
    project_dir = _project_dir(project_id)
    kb_dir = project_dir / "kb"
    items = _list_json(kb_dir)
    return [KBArticle(**item) for item in items]

@app.post("/v1/projects/{project_id}/kb:batch_upsert", tags=["Projects"])
async def batch_upsert_kb(project_id: str, req: BatchKBUpsertRequest, request: Request, _: dict = Depends(get_current_session)):
    project_dir = _project_dir(project_id)
    kb_dir = project_dir / "kb"
    
    for kb in req.items:
        file_path = kb_dir / f"{kb.id}.json"
        _write_json(file_path, kb.dict())
    
    return {"detail": f"Upserted {len(req.items)} KB articles"}

@app.delete("/v1/projects/{project_id}/kb/{kb_id}", tags=["Projects"])
async def delete_kb(project_id: str, kb_id: str, request: Request, _: dict = Depends(get_current_session)):
    project_dir = _project_dir(project_id)
    file_path = project_dir / "kb" / f"{kb_id}.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="KB article not found")
    _delete_json(file_path)
    return {"detail": "KB article deleted"}

@app.post("/v1/projects/{project_id}/ingest", tags=["Projects"])
async def ingest_data(project_id: str, request: Request, file: UploadFile = File(...), _: dict = Depends(get_current_session)):
    project_dir = _project_dir(project_id)
    ingest_dir = project_dir / "ingest"
    
    # Save uploaded file
    file_path = ingest_dir / file.filename
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    return {"detail": f"File '{file.filename}' uploaded successfully", "size": len(content)}

@app.post("/v1/projects/{project_id}/reindex", tags=["Projects"])
async def reindex(project_id: str, request: Request, _: dict = Depends(get_current_session)):
    # This would typically trigger a background reindexing process
    return {"detail": "Reindexing initiated (not implemented)"}

@app.post("/v1/query", response_model=QueryResponse, tags=["Projects"])
async def query_kb(req: QueryRequest, request: Request, _: dict = Depends(get_current_session)):
    # This would typically perform semantic search or AI-based query processing
    return QueryResponse(
        answer="This is a placeholder response. Query processing not yet implemented.",
        sources=[]
    )

@app.get("/v1/projects/{project_id}/stats", tags=["Projects"])
async def project_stats(project_id: str, request: Request, _: dict = Depends(get_current_session)):
    project_dir = _project_dir(project_id)
    
    faqs_count = len(list((project_dir / "faqs").glob("*.json")))
    kb_count = len(list((project_dir / "kb").glob("*.json")))
    ingest_count = len(list((project_dir / "ingest").iterdir()))
    
    return {
        "project_id": project_id,
        "faqs_count": faqs_count,
        "kb_articles_count": kb_count,
        "ingested_files_count": ingest_count
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=False)