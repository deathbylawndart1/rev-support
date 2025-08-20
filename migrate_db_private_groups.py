#!/usr/bin/env python3
"""
Database migration script to add private support group fields to SupportMessage table.
This fixes the OperationalError: no such column: support_message.private_group_id
"""

import sqlite3
import os
from flask import Flask
from models import db, SupportMessage

def migrate_database():
    """Add missing private group columns to support_message table"""
    
    # Initialize Flask app and database
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///support_system.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    
    with app.app_context():
        # Get database connection
        db_path = 'instance/support_system.db'
        if not os.path.exists(db_path):
            print(f"❌ Database file not found at {db_path}!")
            return
            
        # Connect directly to SQLite to add columns
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔍 Checking current table structure...")
        
        # Check current columns
        cursor.execute("PRAGMA table_info(support_message)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        print(f"📋 Existing columns: {existing_columns}")
        
        # Add missing columns
        columns_to_add = [
            ('private_group_id', 'TEXT'),
            ('private_group_title', 'TEXT'),
            ('private_group_invite_link', 'TEXT'),
            ('private_group_created', 'BOOLEAN DEFAULT FALSE')
        ]
        
        for column_name, column_type in columns_to_add:
            if column_name not in existing_columns:
                print(f"➕ Adding column: {column_name} ({column_type})")
                try:
                    cursor.execute(f"ALTER TABLE support_message ADD COLUMN {column_name} {column_type}")
                    conn.commit()
                    print(f"✅ Successfully added {column_name}")
                except sqlite3.Error as e:
                    print(f"❌ Error adding {column_name}: {e}")
            else:
                print(f"⚠️ Column {column_name} already exists, skipping")
        
        # Verify new structure
        print("\n🔍 Verifying updated table structure...")
        cursor.execute("PRAGMA table_info(support_message)")
        updated_columns = [row[1] for row in cursor.fetchall()]
        print(f"📋 Updated columns: {updated_columns}")
        
        conn.close()
        print("\n✅ Database migration completed successfully!")

if __name__ == "__main__":
    migrate_database()
