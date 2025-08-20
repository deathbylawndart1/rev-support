from app import app
from models import db


def ensure_db() -> None:
    """Ensure database tables exist before starting the server."""
    with app.app_context():
        try:
            db.create_all()
            app.logger.info("Database tables ensured.")
        except Exception as e:
            app.logger.error(f"Database initialization failed: {e}")


# Expose `app` for Gunicorn
# Usage: gunicorn -w 3 -k gthread -b 0.0.0.0:5001 wsgi:app
if __name__ == "__main__":
    ensure_db()
    # Optional local run: `python wsgi.py` will initialize DB only.
