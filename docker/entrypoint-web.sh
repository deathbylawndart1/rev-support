#!/usr/bin/env bash
set -euo pipefail

# Ensure instance directory exists for SQLite persistence
mkdir -p /app/instance

# Ensure database tables exist before starting (retry for DB readiness)
MAX_WAIT=${DB_WAIT_TIMEOUT:-60}
SLEEP=2
ELAPSED=0
echo "Initializing database (will retry up to ${MAX_WAIT}s if needed)..."
until python - <<'PY'
from wsgi import ensure_db
try:
    ensure_db()
    print("DB initialized (or already present)")
    import sys; sys.exit(0)
except Exception as e:
    print(f"DB init attempt failed: {e}")
    import sys; sys.exit(1)
PY
do
  if [ "$ELAPSED" -ge "$MAX_WAIT" ]; then
    echo "Database is not ready after ${MAX_WAIT}s. Exiting."
    exit 1
  fi
  sleep "$SLEEP"
  ELAPSED=$((ELAPSED + SLEEP))
  echo "Retrying DB initialization... (${ELAPSED}s)"
done

# Default runtime variables
: "${PORT:=5001}"
: "${WEB_CONCURRENCY:=3}"
: "${WEB_THREADS:=4}"
: "${LOG_LEVEL:=info}"

# Start Gunicorn
exec gunicorn -w "$WEB_CONCURRENCY" -k gthread --threads "$WEB_THREADS" \
  --log-level "$LOG_LEVEL" -b 0.0.0.0:"$PORT" wsgi:app
