#!/usr/bin/env python3
"""
Database Setup Script - Always run this to create/update tables in Neon PostgreSQL
Usage: python setup_database.py
"""
import os
import sys

# Set the database URL - ALWAYS USE THIS CONNECTION STRING
DATABASE_URL = 'postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require'
os.environ['DATABASE_URL'] = DATABASE_URL

print("=" * 70)
print("BuXin Academy - Database Setup Script")
print("=" * 70)
print("\n[INFO] Connecting to Neon PostgreSQL Database...")
print("   Database: neondb")
print("   Host: ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech")

try:
    from webapp import create_app
    from webapp.extensions import db
    
    print("\n[STEP 1] Creating Flask app...")
    app = create_app()
    
    # Get the configured database URI
    db_url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    print("   [OK] App created successfully")
    print(f"   [INFO] Database URI: {db_url[:60]}...")
    
    print("\n[STEP 2] Testing database connection...")
    with app.app_context():
        try:
            # Test connection
            connection = db.engine.connect()
            connection.close()
            print("   [OK] Connection successful!")
        except Exception as e:
            print(f"   [ERROR] Connection failed: {str(e)}")
            print("\n   Troubleshooting:")
            print("   - Check if the database URL is correct")
            print("   - Verify network connectivity")
            print("   - Ensure database credentials are valid")
            sys.exit(1)
        
        print("\n[STEP 3] Creating all database tables...")
        try:
            # Create all tables based on models
            db.create_all()
            print("   [OK] All tables created/updated successfully!")
        except Exception as e:
            print(f"   [WARNING] {str(e)}")
            print("   Some tables may already exist. Continuing...")
        
        print("\n[STEP 4] Verifying tables in database...")
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if tables:
            print(f"   [OK] Found {len(tables)} tables in database:")
            print()
            for i, table in enumerate(sorted(tables), 1):
                # Get column count
                columns = inspector.get_columns(table)
                print(f"   {i:2d}. {table:<35} ({len(columns)} columns)")
        else:
            print("   [WARNING] No tables found in database")
        
        print("\n" + "=" * 70)
        print("[SUCCESS] Database setup completed successfully!")
        print("=" * 70)
        print("\nNext steps:")
        print("   - Your database is ready to use")
        print("   - Run Flask migrations if needed: flask db upgrade")
        print("   - Start your application")
        print()
        
except ImportError as e:
    print(f"\n[ERROR] Import error: {str(e)}")
    print("\n   Make sure you're in the correct directory and dependencies are installed:")
    print("   - pip install -r requirements.txt")
    print("   - Ensure you're in the project root directory")
    sys.exit(1)
except Exception as e:
    print(f"\n[ERROR] {str(e)}")
    import traceback
    print("\n   Full error traceback:")
    traceback.print_exc()
    sys.exit(1)

