#!/usr/bin/env python3
"""
Initialize Units database with the 4 specific units requested by the user.
Based on the Portal - RevPAD page data.
"""

from app import app, db
from models import Unit
from datetime import datetime, timedelta
import random

def initialize_units():
    """Initialize the Units table with the 4 specific units"""
    
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
        
        # Check if units already exist
        existing_units = Unit.query.all()
        if existing_units:
            print(f"Found {len(existing_units)} existing units. Clearing...")
            for unit in existing_units:
                db.session.delete(unit)
            db.session.commit()
        
        # Define the 4 specific units based on Portal - RevPAD data
        units_data = [
            {
                'name': 'Ascent - Crowell',
                'device_name': 'NexusOne Unit 2',
                'description': 'Field operations unit at Crowell site',
                'status': 'online',
                'last_online': datetime.utcnow()  # Now
            },
            {
                'name': 'Fesco - Conoco Fransen',
                'device_name': 'NexusOne Unit 4',
                'description': 'Conoco Fransen operations unit',
                'status': 'online',
                'last_online': datetime.utcnow()  # Now
            },
            {
                'name': 'Unit 1 - Coterra',
                'device_name': 'RevPAD Link_box1',
                'description': 'Coterra operations - primary unit',
                'status': 'offline',
                'last_online': datetime.utcnow() - timedelta(days=30)  # 1 month ago
            },
            {
                'name': 'Unit 3 - Range - Harmon creek C',
                'device_name': 'RevPAD Link _Unit 3',
                'description': 'Range operations at Harmon creek C location',
                'status': 'online',
                'last_online': datetime.utcnow()  # Now
            }
        ]
        
        # Create and insert the units
        created_units = []
        for unit_data in units_data:
            unit = Unit(
                name=unit_data['name'],
                device_name=unit_data['device_name'],
                description=unit_data['description'],
                status=unit_data['status'],
                last_online=unit_data['last_online'],
                is_active=True
            )
            db.session.add(unit)
            created_units.append(unit)
        
        # Commit all units to database
        try:
            db.session.commit()
            print("✅ Successfully initialized Units database!")
            print("\nCreated Units:")
            for unit in created_units:
                print(f"  - {unit.name} ({unit.device_name}) - Status: {unit.status}")
            
            print(f"\n🎉 Total units created: {len(created_units)}")
            print("Units page is now ready to use!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error creating units: {e}")
            return False
        
        return True

if __name__ == '__main__':
    print("🚀 Initializing Units database...")
    success = initialize_units()
    
    if success:
        print("\n✅ Units database initialization completed successfully!")
        print("You can now view the Units page in your dashboard.")
    else:
        print("\n❌ Units database initialization failed!")
