#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to create/update all database tables in PostgreSQL
"""
import os
import sys

# Configure stdout for Unicode (Windows compatibility)
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Set the database URL
DATABASE_URL = 'postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require'
os.environ['DATABASE_URL'] = DATABASE_URL

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from webapp import create_app
from webapp.extensions import db
from sqlalchemy import inspect, text

def create_tables():
    """Create all database tables and add missing columns"""
    app = create_app()
    
    with app.app_context():
        try:
            print("=" * 70)
            print("Creating/Updating Database Tables")
            print("=" * 70)
            
            # Test connection
            print("\n[1/4] Testing database connection...")
            try:
                connection = db.engine.connect()
                connection.close()
                print("   [OK] Connection successful!")
            except Exception as e:
                print(f"   [ERROR] Connection failed: {str(e)}")
                return False
            
            # Create all tables
            print("\n[2/4] Creating all tables...")
            try:
                db.create_all()
                print("   [OK] All tables created/updated successfully!")
            except Exception as e:
                print(f"   [WARNING] {str(e)}")
                print("   Continuing with column updates...")
            
            # Add curriculum column if it doesn't exist
            print("\n[3/4] Checking for curriculum column in group_class table...")
            try:
                inspector = inspect(db.engine)
                columns = [col['name'] for col in inspector.get_columns('group_class')]
                
                if 'curriculum' not in columns:
                    print("   Adding curriculum column...")
                    db.session.execute(text('ALTER TABLE group_class ADD COLUMN curriculum TEXT'))
                    db.session.commit()
                    print("   [OK] Curriculum column added!")
                else:
                    print("   [OK] Curriculum column already exists!")
            except Exception as e:
                print(f"   [WARNING] Could not check/add curriculum column: {str(e)}")
                # Try to continue anyway
            
            # Verify tables
            print("\n[4/4] Verifying tables...")
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if tables:
                print(f"   [OK] Found {len(tables)} tables:")
                for i, table in enumerate(sorted(tables), 1):
                    columns = inspector.get_columns(table)
                    print(f"      {i:2d}. {table:<35} ({len(columns)} columns)")
            else:
                print("   [WARNING] No tables found")
            
            print("\n" + "=" * 70)
            print("[SUCCESS] Database setup completed successfully!")
            print("=" * 70)
            return True
            
        except Exception as e:
            print(f"\n[ERROR] {str(e)}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return False

if __name__ == '__main__':
    success = create_tables()
    sys.exit(0 if success else 1)

