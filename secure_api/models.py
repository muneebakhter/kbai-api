from __future__ import annotations
from pydantic import BaseModel, Field, conlist, constr
from typing import List, Optional
from datetime import datetime

class TokenRequest(BaseModel):
    client_name: constr(strip_whitespace=True, min_length=1)
    scopes: conlist(str, min_length=1) = ["read:test"]
    ttl_seconds: int = 3600
    ip_lock: Optional[str] = None

class TokenResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    expires_at: datetime
    session_id: str

class TraceItem(BaseModel):
    id: str
    ts: str
    method: str
    path: str
    status: int
    latency_ms: float
    ip: Optional[str] = None
    ua: Optional[str] = None
    headers_slim: Optional[dict] = None
    query: Optional[dict] = None
    body_sha256: Optional[str] = None
    token_sub: Optional[str] = None
    error: Optional[str] = None

class TracesResponse(BaseModel):
    items: List[TraceItem]
    next_cursor: Optional[str] = None

class MetricsSummary(BaseModel):
    window: str
    total: int
    by_status: dict
    top_paths: list
    unauthorized: int
    p95_latency_ms: Optional[float] = None
