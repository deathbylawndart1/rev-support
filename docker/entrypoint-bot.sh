#!/usr/bin/env bash
set -euo pipefail

# Ensure instance directory exists for SQLite persistence
mkdir -p /app/instance

# Initialize DB via bot's Flask app context
python - <<'PY'
from bot import init_flask_app
init_flask_app()
print("DB initialized for bot (or already present)")
PY

# Optionally wait for web service health before starting the bot
python - <<'PY'
import os, time, sys
import requests

base = os.getenv("WEB_DASHBOARD_URL", "http://web:5001").rstrip('/')
url = f"{base}/healthz"
timeout = int(os.getenv("WEB_WAIT_TIMEOUT", "60"))
interval = 2
deadline = time.time() + timeout
print(f"Waiting for web health at {url} up to {timeout}s...")
while time.time() < deadline:
    try:
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            print("Web is healthy. Starting bot...")
            sys.exit(0)
    except Exception:
        pass
    time.sleep(interval)
print("Warning: Web health not confirmed; proceeding to start bot.")
PY

# Start the bot
exec python -u bot.py
