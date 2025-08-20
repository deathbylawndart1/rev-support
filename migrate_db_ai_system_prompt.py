#!/usr/bin/env python3
"""
Database migration script to add `system_prompt` column to ai_service_config table.
Follows the project's manual SQLite migration style.
"""

import sqlite3
import os
from flask import Flask
from models import db, AIServiceConfig  # noqa: F401 (import ensures table naming stays consistent)


def migrate_database():
    """Add missing system_prompt column to ai_service_config table if absent."""
    # Initialize Flask app and database (for consistent config and table names)
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///support_system.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    with app.app_context():
        # Determine sqlite DB path (prefer instance path, fallback to local path)
        candidates = [
            os.path.join('instance', 'support_system.db'),
            'support_system.db',
        ]
        db_path = next((p for p in candidates if os.path.exists(p)), None)
        if not db_path:
            print("❌ Database file not found at instance/support_system.db or ./support_system.db!")
            return

        # Connect directly to SQLite to add column
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        print("🔍 Checking current ai_service_config table structure...")
        cursor.execute("PRAGMA table_info(ai_service_config)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        print(f"📋 Existing columns: {existing_columns}")

        # Add column if missing
        if 'system_prompt' not in existing_columns:
            print("➕ Adding column: system_prompt (TEXT)")
            try:
                cursor.execute("ALTER TABLE ai_service_config ADD COLUMN system_prompt TEXT")
                conn.commit()
                print("✅ Successfully added system_prompt")
            except sqlite3.Error as e:
                print(f"❌ Error adding system_prompt: {e}")
        else:
            print("⚠️ Column system_prompt already exists, skipping")

        # Verify new structure
        print("\n🔍 Verifying updated table structure...")
        cursor.execute("PRAGMA table_info(ai_service_config)")
        updated_columns = [row[1] for row in cursor.fetchall()]
        print(f"📋 Updated columns: {updated_columns}")

        conn.close()
        print("\n✅ Database migration completed successfully!")


if __name__ == "__main__":
    migrate_database()
