#!/usr/bin/env python3
"""
Database Update Script for Conversation Tracking
Adds the ConversationState table to support reply detection
"""

from app import app, db
from models import ConversationState

def update_database():
    """Update database with conversation tracking table"""
    with app.app_context():
        try:
            # Create the new table
            db.create_all()
            print("✅ Database updated successfully!")
            print("✅ ConversationState table created for reply detection")
            
            # Test the model
            test_count = ConversationState.query.count()
            print(f"✅ ConversationState table is working (current count: {test_count})")
            
        except Exception as e:
            print(f"❌ Error updating database: {e}")
            return False
    
    return True

if __name__ == "__main__":
    print("🔄 Updating database for conversation tracking...")
    success = update_database()
    if success:
        print("🎉 Database update completed successfully!")
    else:
        print("💥 Database update failed!")
