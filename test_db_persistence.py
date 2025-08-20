#!/usr/bin/env python3
"""
Database persistence test script
Run this to check if admin settings and other data persist correctly
"""

from flask import Flask
from models import db, AppearanceSettings, User
import os

# Create test Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///support_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def test_database_persistence():
    """Test if database changes persist correctly"""
    with app.app_context():
        print("=== Database Persistence Test ===")
        print(f"Database location: {os.path.abspath('support_system.db')}")
        
        # Check if admin user exists
        admin = User.query.filter_by(username='admin').first()
        if admin:
            print(f"✅ Admin user exists: {admin.username} ({admin.email})")
        else:
            print("❌ Admin user not found!")
        
        # Check appearance settings
        appearance = AppearanceSettings.query.first()
        if appearance:
            print(f"✅ Appearance settings exist:")
            print(f"   Company Name: {appearance.company_name}")
            print(f"   Color Scheme: {appearance.color_scheme}")
            print(f"   Primary Color: {appearance.primary_color}")
            if appearance.logo_filename:
                print(f"   Logo: {appearance.logo_filename}")
        else:
            print("❌ No appearance settings found!")
            
        # Test creating a new setting and committing
        print("\n=== Testing New Data Creation ===")
        if not appearance:
            test_appearance = AppearanceSettings(
                company_name="TEST PERSISTENCE",
                color_scheme="red",
                primary_color="#ff0000"
            )
            db.session.add(test_appearance)
            db.session.commit()
            print("✅ Created test appearance settings")
        else:
            # Update existing
            old_name = appearance.company_name
            appearance.company_name = "TEST PERSISTENCE UPDATED"
            db.session.commit()
            print(f"✅ Updated company name from '{old_name}' to '{appearance.company_name}'")
            
        print("\n=== Verifying Data After Commit ===")
        # Re-query to verify
        appearance_check = AppearanceSettings.query.first()
        if appearance_check:
            print(f"✅ Data verified: Company Name = '{appearance_check.company_name}'")
        else:
            print("❌ Data verification failed!")
            
        # Count total records
        user_count = User.query.count()
        appearance_count = AppearanceSettings.query.count()
        print(f"\n=== Database Summary ===")
        print(f"Users: {user_count}")
        print(f"Appearance Settings: {appearance_count}")

if __name__ == '__main__':
    test_database_persistence()
