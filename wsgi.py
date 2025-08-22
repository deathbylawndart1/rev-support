from app import app
from models import db, User
import os


def ensure_db() -> None:
    """Ensure database tables exist before starting the server."""
    with app.app_context():
        try:
            db.create_all()
            app.logger.info("Database tables ensured.")

            # Optionally create an initial admin user if configured
            create_flag = str(os.getenv("ADMIN_AUTO_CREATE", "")).strip().lower() in ("1", "true", "yes")
            admin_username = os.getenv("ADMIN_USERNAME")
            admin_email = os.getenv("ADMIN_EMAIL")
            admin_password = os.getenv("ADMIN_PASSWORD")
            admin_first = os.getenv("ADMIN_FIRST_NAME", "Admin")
            admin_last = os.getenv("ADMIN_LAST_NAME", "User")

            if create_flag:
                if not (admin_username and admin_email and admin_password):
                    app.logger.warning("ADMIN_AUTO_CREATE is enabled but one or more required variables are missing: ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD")
                else:
                    # Only create/elevate if there is no admin user yet
                    existing_admin = User.query.filter_by(is_admin=True).first()
                    if existing_admin:
                        app.logger.info("Admin user already exists; skipping auto-creation.")
                    else:
                        # Check if a user with the given username or email exists
                        user_by_username = User.query.filter_by(username=admin_username).first()
                        user_by_email = User.query.filter_by(email=admin_email).first()

                        if user_by_username or user_by_email:
                            # Elevate existing user to admin (do not reset password by default)
                            user = user_by_username or user_by_email
                            user.is_admin = True
                            db.session.commit()
                            app.logger.info(f"Elevated existing user '{user.username}' to admin.")
                        else:
                            # Create new admin user
                            user = User(
                                username=admin_username,
                                email=admin_email,
                                first_name=admin_first,
                                last_name=admin_last,
                                is_admin=True,
                            )
                            user.set_password(admin_password)
                            db.session.add(user)
                            db.session.commit()
                            app.logger.info(f"Created initial admin user '{admin_username}'.")
        except Exception as e:
            app.logger.error(f"Database initialization failed: {e}")


# Expose `app` for Gunicorn
# Usage: gunicorn -w 3 -k gthread -b 0.0.0.0:5001 wsgi:app
if __name__ == "__main__":
    ensure_db()
    # Optional local run: `python wsgi.py` will initialize DB only.
