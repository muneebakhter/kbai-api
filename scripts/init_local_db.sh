#!/usr/bin/env bash
set -euo pipefail
DB="./secure_api/secure_api_traces.db"
SQL="./secure_api/migrations/bootstrap_traces.sql"
mkdir -p ./secure_api/migrations
if [ -f "$DB" ]; then
  rm -f "$DB"
fi
sqlite3 "$DB" < "$SQL"
echo "OK: $DB initialized"
