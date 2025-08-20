#!/usr/bin/env python3
"""
Migration script to add telegram_default_users field to AppearanceSettings table
"""
import sqlite3
import sys
import os

def migrate():
    """Add telegram_default_users column to appearance_settings table if it doesn't exist"""
    
    # Database path - adjust if needed
    db_path = 'instance/support_system.db'
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(appearance_settings)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'telegram_default_users' in column_names:
            print("Column 'telegram_default_users' already exists in appearance_settings table")
            return True
        
        # Add the new column
        cursor.execute("""
            ALTER TABLE appearance_settings 
            ADD COLUMN telegram_default_users TEXT
        """)
        
        conn.commit()
        print("Successfully added 'telegram_default_users' column to appearance_settings table")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        return False

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
