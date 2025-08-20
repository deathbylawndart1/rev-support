#!/usr/bin/env python3
"""
Fix duplicate AppearanceSettings records
Consolidate multiple records into a single master record
"""

from flask import Flask
from models import db, AppearanceSettings
import os

# Create Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///support_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def fix_duplicate_settings():
    """Fix duplicate AppearanceSettings records"""
    with app.app_context():
        print("=== Fixing Duplicate AppearanceSettings ===")
        
        # Get all appearance settings
        all_settings = AppearanceSettings.query.all()
        print(f"Found {len(all_settings)} AppearanceSettings records")
        
        if len(all_settings) <= 1:
            print("✅ No duplicates found - settings are clean!")
            return
            
        # Find the most complete/recent record to keep
        master_record = None
        best_score = -1
        
        for setting in all_settings:
            score = 0
            print(f"\nRecord ID {setting.id}:")
            print(f"  Company Name: {setting.company_name}")
            print(f"  Color Scheme: {setting.color_scheme}")
            print(f"  Primary Color: {setting.primary_color}")
            print(f"  Logo: {setting.logo_filename}")
            
            # Score based on completeness
            if setting.company_name and setting.company_name != "Support System":
                score += 10  # Custom company name
            if setting.logo_filename:
                score += 5   # Has logo
            if setting.color_scheme != "blue":
                score += 3   # Custom color scheme
            if setting.primary_color != "#0d6efd":
                score += 2   # Custom primary color
                
            print(f"  Score: {score}")
            
            if score > best_score:
                best_score = score
                master_record = setting
        
        if master_record:
            print(f"\n🎯 Selected master record: ID {master_record.id}")
            print(f"  Company: {master_record.company_name}")
            print(f"  Logo: {master_record.logo_filename}")
            
            # Delete all other records
            deleted_count = 0
            for setting in all_settings:
                if setting.id != master_record.id:
                    print(f"🗑️ Deleting duplicate record ID {setting.id}")
                    db.session.delete(setting)
                    deleted_count += 1
            
            # Commit changes
            db.session.commit()
            print(f"✅ Deleted {deleted_count} duplicate records")
            print(f"✅ Kept master record with your custom settings")
            
            # Verify cleanup
            remaining = AppearanceSettings.query.count()
            final_record = AppearanceSettings.query.first()
            print(f"\n=== Cleanup Complete ===")
            print(f"Remaining records: {remaining}")
            print(f"Master settings:")
            print(f"  Company: {final_record.company_name}")
            print(f"  Color: {final_record.color_scheme}")
            print(f"  Logo: {final_record.logo_filename}")
        
if __name__ == '__main__':
    fix_duplicate_settings()
