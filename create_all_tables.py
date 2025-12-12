#!/usr/bin/env python3
"""
Script to create all database tables in PostgreSQL
"""
import os
import sys

# Set the database URL
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require'

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from webapp import create_app
from webapp.extensions import db

def create_all_tables():
    """Create all database tables"""
    try:
        print("Initializing app...")
        app = create_app()
        
        with app.app_context():
            print("Connecting to database...")
            db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', 'Not set')
            if len(db_uri) > 50:
                print(f"   Database URL: {db_uri[:50]}...")
            else:
                print(f"   Database URL: {db_uri}")
            
            print("Creating all database tables...")
            db.create_all()
            print("SUCCESS: All tables created successfully!")
            
            # Print list of created tables
            try:
                from sqlalchemy import inspect
                inspector = inspect(db.engine)
                tables = inspector.get_table_names()
                print(f"\nCreated {len(tables)} tables:")
                for table in sorted(tables):
                    print(f"   - {table}")
            except Exception as e:
                print(f"Note: Could not list tables: {e}")
            
            print("\nDone!")
            return True
    except Exception as e:
        print(f"ERROR: Error creating tables: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = create_all_tables()
    sys.exit(0 if success else 1)

