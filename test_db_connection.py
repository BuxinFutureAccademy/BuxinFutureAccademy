#!/usr/bin/env python3
"""Test PostgreSQL database connection"""
import os
import sys

# Set the database URL
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require'

try:
    from webapp import create_app
    from webapp.extensions import db
    
    print("Creating Flask app...")
    app = create_app()
    
    print(f"\nDatabase URI configured: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Not set')[:80]}...")
    
    print("\nTesting database connection...")
    with app.app_context():
        # Try to connect
        db.engine.connect()
        print("✅ Database connection successful!")
        
        # List tables
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"\n📊 Found {len(tables)} tables in database:")
        for table in tables:
            print(f"   - {table}")
        
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

