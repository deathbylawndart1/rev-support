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

# Start the bot
exec python -u bot.py
