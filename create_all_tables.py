#!/usr/bin/env python3
"""
Script to create all database tables
"""
import os
import sys

# Set the database URL
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require'

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from webapp import create_app
from webapp.extensions import db

def create_tables():
    """Create all database tables"""
    app = create_app()
    
    with app.app_context():
        try:
            print("Creating all database tables...")
            db.create_all()
            print("[OK] All tables created successfully!")
            
            # Verify by checking if id_card table exists
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"\nTotal tables created: {len(tables)}")
            print("\nTables:")
            for table in sorted(tables):
                print(f"  - {table}")
            
            if 'id_card' in tables:
                print("\n[OK] ID Card table exists!")
            else:
                print("\n[WARNING] ID Card table not found!")
                
        except Exception as e:
            print(f"[ERROR] Error creating tables: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

if __name__ == '__main__':
    success = create_tables()
    sys.exit(0 if success else 1)
