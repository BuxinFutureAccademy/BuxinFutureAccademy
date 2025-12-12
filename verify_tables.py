#!/usr/bin/env python3
"""
Script to verify all database tables exist
"""
import os
import sys

# Set the database URL
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from webapp import create_app
from webapp.extensions import db

def verify_tables():
    """Verify all database tables exist"""
    try:
        print("Initializing app...")
        app = create_app()
        
        with app.app_context():
            print("Connecting to database...")
            db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', 'Not set')
            if len(db_uri) > 60:
                print(f"   Database: {db_uri[:40]}...")
            else:
                print(f"   Database: {db_uri}")
            
            print("\nChecking tables...")
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            print(f"\nFound {len(tables)} tables:")
            for table in sorted(tables):
                # Get row count
                try:
                    result = db.session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    print(f"   - {table:30} ({count} rows)")
                except Exception as e:
                    print(f"   - {table:30} (error: {str(e)[:30]})")
            
            # Check for new tables we added
            new_tables = ['attendance', 'school_student', 'family_member', 'class_pricing', 'home_gallery', 'student_victory']
            print(f"\nNew feature tables:")
            for table in new_tables:
                if table in tables:
                    print(f"   [OK] {table} - EXISTS")
                else:
                    print(f"   [X] {table} - MISSING")
            
            print("\nDone!")
            return True
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = verify_tables()
    sys.exit(0 if success else 1)

