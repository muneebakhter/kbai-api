from __future__ import annotations

import os
import secrets
import time
from pathlib import Path
import json
import uuid
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST


from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
# Canonical storage root in HOME as requested
HOME_ROOT = Path.home()
PROJ_MAP_FILE = HOME_ROOT / "proj_mapping.txt"
LOG_DIR = HOME_ROOT / ".kbai"
LOG_DIR.mkdir(parents=True, exist_ok=True)
REQUEST_LOG = LOG_DIR / "requests.jsonl"

load_dotenv(dotenv_path=APP_DIR.parent / ".env", override=False)
SECURE_TOKEN = os.environ.get("KBAI_API_TOKEN") or secrets.token_hex(16)


app = FastAPI(title="Knowledge Base AI API", version="1.0.0")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
security = HTTPBearer(auto_error=False)


# Prometheus metrics
REQUEST_COUNT = Counter("kbai_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("kbai_request_latency_seconds", "Request latency", ["endpoint"])
READY_GAUGE = Gauge("kbai_ready", "Readiness state (1 ready, 0 not)")


def require_auth(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if not credentials or credentials.scheme.lower() != "bearer" or credentials.credentials != SECURE_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _append_request_log(entry: dict) -> None:
    try:
        with REQUEST_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # Best-effort logging; ignore errors
        pass


@app.middleware("http")
async def request_logger(request: Request, call_next):
    start = time.perf_counter()
    trace_id = uuid.uuid4().hex
    request.state.trace_id = trace_id
    client_ip = request.client.host if request.client else ""
    path = request.url.path
    method = request.method
    query = dict(request.query_params)
    ua = request.headers.get("user-agent", "")

    try:
        response = await call_next(request)
        status = response.status_code
    except HTTPException as exc:
        status = exc.status_code
        raise
    finally:
        latency = (time.perf_counter() - start) * 1000.0
        # attach trace header
        try:
            if 'X-Trace-Id' not in response.headers:
                response.headers['X-Trace-Id'] = trace_id
        except Exception:
            pass
        content_length = None
        try:
            cl = response.headers.get('content-length')
            content_length = int(cl) if cl is not None else None
        except Exception:
            content_length = None

        log_entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "trace_id": trace_id,
            "ip": client_ip,
            "method": method,
            "path": path,
            "query": query,
            "status": int(locals().get("status", 500)),
            "latency_ms": round(latency, 2),
            "content_length": content_length,
            "user_agent": ua,
        }
        _append_request_log(log_entry)
        # Metrics
        try:
            REQUEST_COUNT.labels(method, path, str(log_entry["status"])).inc()
        except Exception:
            pass
        try:
            REQUEST_LATENCY.labels(path).observe(latency / 1000.0)
        except Exception:
            pass

    return response


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
@track_metrics("/healthz")
async def healthz():
    return "ok"


@app.get("/readyz", response_class=PlainTextResponse)
@track_metrics("/readyz")
async def readyz():
    ready = REQUEST_LOG.exists()
    READY_GAUGE.set(1 if ready else 0)
    return "ready" if ready else "not ready"


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@app.post("/auth/token", response_model=TokenResponse)
@track_metrics("/auth/token")
async def auth_token(req: TokenRequest):
    # Extremely simple demo auth; replace with real verification
    if not req.username or not req.password:
        raise HTTPException(status_code=400, detail="Missing credentials")
    return TokenResponse(access_token=SECURE_TOKEN)


@app.post("/v1/projects", dependencies=[Depends(require_auth)])
@track_metrics("/v1/projects:post")
async def add_or_rename_project(project: Project, request: Request):
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse({"detail": "Not implemented", "trace_id": trace_id}, status_code=501)


@app.get("/v1/projects", response_model=List[Project])
@track_metrics("/v1/projects:get")
async def list_projects(request: Request):
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse({"detail": "Not implemented", "trace_id": trace_id}, status_code=501)


@app.get("/v1/projects/{project_id}", response_model=Project)
@track_metrics("/v1/projects/{id}:get")
async def get_project(project_id: str, request: Request):
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse({"detail": "Not implemented", "trace_id": trace_id}, status_code=501)


@app.delete("/v1/projects/{project_id}", dependencies=[Depends(require_auth)])
@track_metrics("/v1/projects/{id}:delete")
async def soft_delete_project(project_id: str, request: Request):
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse({"detail": "Not implemented", "trace_id": trace_id}, status_code=501)


@app.get("/v1/projects/{project_id}/faqs", response_model=List[FAQ])
@track_metrics("/v1/projects/{id}/faqs:get")
async def list_faqs(project_id: str, request: Request):
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse({"detail": "Not implemented", "trace_id": trace_id}, status_code=501)


class BatchFAQUpsertRequest(BaseModel):
    items: List[FAQ]


@app.post("/v1/projects/{project_id}/faqs:batch_upsert", dependencies=[Depends(require_auth)])
@track_metrics("/v1/projects/{id}/faqs:batch_upsert")
async def batch_upsert_faqs(project_id: str, req: BatchFAQUpsertRequest, request: Request):
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse({"detail": "Not implemented", "trace_id": trace_id}, status_code=501)


@app.delete("/v1/projects/{project_id}/faqs/{faq_id}", dependencies=[Depends(require_auth)])
@track_metrics("/v1/projects/{id}/faqs:delete")
async def delete_faq(project_id: str, faq_id: str, request: Request):
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse({"detail": "Not implemented", "trace_id": trace_id}, status_code=501)


@app.get("/v1/projects/{project_id}/kb", response_model=List[KBArticle])
@track_metrics("/v1/projects/{id}/kb:get")
async def list_kb(project_id: str, request: Request):
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse({"detail": "Not implemented", "trace_id": trace_id}, status_code=501)


class BatchKBUpsertRequest(BaseModel):
    items: List[KBArticle]


@app.post("/v1/projects/{project_id}/kb:batch_upsert", dependencies=[Depends(require_auth)])
@track_metrics("/v1/projects/{id}/kb:batch_upsert")
async def batch_upsert_kb(project_id: str, req: BatchKBUpsertRequest, request: Request):
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse({"detail": "Not implemented", "trace_id": trace_id}, status_code=501)


@app.delete("/v1/projects/{project_id}/kb/{kb_id}", dependencies=[Depends(require_auth)])
@track_metrics("/v1/projects/{id}/kb:delete")
async def delete_kb(project_id: str, kb_id: str, request: Request):
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse({"detail": "Not implemented", "trace_id": trace_id}, status_code=501)


@app.post("/v1/projects/{project_id}/ingest", dependencies=[Depends(require_auth)])
@track_metrics("/v1/projects/{id}/ingest")
async def ingest_data(project_id: str, request: Request, file: UploadFile = File(...)):
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse({"detail": "Not implemented", "trace_id": trace_id}, status_code=501)


@app.post("/v1/projects/{project_id}/reindex", dependencies=[Depends(require_auth)])
@track_metrics("/v1/projects/{id}/reindex")
async def reindex(project_id: str, request: Request):
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse({"detail": "Not implemented", "trace_id": trace_id}, status_code=501)


class QueryRequest(BaseModel):
    project_id: str
    question: str


class QueryResponse(BaseModel):
    answer: str
    sources: List[str] = []


@app.post("/v1/query", response_model=QueryResponse)
@track_metrics("/v1/query")
async def query_kb(req: QueryRequest, request: Request):
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse({"detail": "Not implemented", "trace_id": trace_id}, status_code=501)


@app.get("/v1/projects/{project_id}/stats")
@track_metrics("/v1/projects/{id}/stats")
async def project_stats(project_id: str, request: Request):
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse({"detail": "Not implemented", "trace_id": trace_id}, status_code=501)


@app.get("/admin", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
@track_metrics("/admin")
def _tail_jsonl(path: Path, max_lines: int) -> List[dict]:
    results: List[dict] = []
    if not path.exists():
        return results
    try:
        from collections import deque
        dq = deque(maxlen=max_lines)
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                dq.append(line)
        for line in dq:
            try:
                results.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        pass
    return list(reversed(results))


@app.get("/admin", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
@track_metrics("/admin")
async def admin_dashboard(request: Request):
    logs = _tail_jsonl(REQUEST_LOG, 200)
    return templates.TemplateResponse("admin.html", {"request": request, "logs": logs})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=False)


