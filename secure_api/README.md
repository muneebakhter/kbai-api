# Secure API (FastAPI)

This service issues JWT tokens, protects routes, traces **every** request (including 401s) to SQLite, serves a simple dashboard, and exposes OpenAPI docs.

## Quickstart

```bash
# 1) Create and activate a venv (optional)
python3 -m venv .venv && source .venv/bin/activate

# 2) Install deps
pip install -r secure_api/requirements.txt

# 3) Initialize local DB
./scripts/init_local_db.sh

# 4) Run
uvicorn secure_api.main:app --host 0.0.0.0 --port 8081 --reload
```

## Get a token

```bash
curl -s -X POST http://localhost:8081/v1/auth/token \  -H 'X-Admin-Api-Key: dev-admin-key-change-me' \  -H 'Content-Type: application/json' \  -d '{"client_name":"me","scopes":["read:test","read:traces","read:metrics"],"ttl_seconds":600}' | jq .
```

Copy the `token` value; for the dashboard, open the browser dev console and run:
```js
sessionStorage.setItem('jwt', '<paste token here>')
```

## Test (authorized)

```bash
curl -i 'http://localhost:8081/v1/test/ping?echo=yo' -H "Authorization: Bearer <token>"
```

## Docs
- Swagger UI: http://localhost:8081/docs
- ReDoc: http://localhost:8081/redoc
- Dashboard: http://localhost:8081/dashboard
