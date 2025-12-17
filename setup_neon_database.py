#!/usr/bin/env python3
"""Setup Neon PostgreSQL database - Create all tables"""
import os
import sys

# Set the database URL
DATABASE_URL = 'postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require'
os.environ['DATABASE_URL'] = DATABASE_URL

print("=" * 60)
print("Setting up Neon PostgreSQL Database")
print("=" * 60)

try:
    from webapp import create_app
    from webapp.extensions import db
    
    print("\n1. Creating Flask app...")
    app = create_app()
    
    # Convert postgresql:// to postgresql+psycopg:// for SQLAlchemy
    db_url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    print(f"   Database URI: {db_url[:80]}...")
    
    print("\n2. Testing database connection...")
    with app.app_context():
        # Test connection
        try:
            db.engine.connect()
            print("   ✅ Connection successful!")
        except Exception as e:
            print(f"   ❌ Connection failed: {str(e)}")
            sys.exit(1)
        
        print("\n3. Creating all database tables...")
        try:
            # Create all tables
            db.create_all()
            print("   ✅ All tables created successfully!")
        except Exception as e:
            print(f"   ⚠️  Error creating tables: {str(e)}")
            print("   Trying to continue...")
        
        print("\n4. Verifying tables...")
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if tables:
            print(f"   ✅ Found {len(tables)} tables:")
            for table in sorted(tables):
                print(f"      - {table}")
        else:
            print("   ⚠️  No tables found")
        
        print("\n" + "=" * 60)
        print("✅ Database setup completed!")
        print("=" * 60)
        
except ImportError as e:
    print(f"❌ Import error: {str(e)}")
    print("Make sure you're in the correct directory and dependencies are installed.")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

