#!/usr/bin/env bash
set -euo pipefail

# Ensure instance directory exists for SQLite persistence
mkdir -p /app/instance

# Ensure database tables exist before starting
python - <<'PY'
from wsgi import ensure_db
ensure_db()
print("DB initialized (or already present)")
PY

# Default runtime variables
: "${PORT:=5001}"
: "${WEB_CONCURRENCY:=3}"
: "${WEB_THREADS:=4}"
: "${LOG_LEVEL:=info}"

# Start Gunicorn
exec gunicorn -w "$WEB_CONCURRENCY" -k gthread --threads "$WEB_THREADS" \
  --log-level "$LOG_LEVEL" -b 0.0.0.0:"$PORT" wsgi:app
