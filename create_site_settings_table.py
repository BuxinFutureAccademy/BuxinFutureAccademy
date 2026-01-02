#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create site_settings table in PostgreSQL database
"""
import os
import sys

# Configure stdout for Unicode (Windows compatibility)
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

DATABASE_URL = 'postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require'
os.environ['DATABASE_URL'] = DATABASE_URL

print("=" * 70)
print("Creating Site Settings Table")
print("=" * 70)

try:
    from webapp import create_app
    from webapp.extensions import db
    from sqlalchemy import text, inspect
    
    app = create_app()
    
    with app.app_context():
        print("\n[STEP 1] Testing database connection...")
        try:
            connection = db.engine.connect()
            connection.close()
            print("   [OK] Connection successful!")
        except Exception as e:
            print(f"   [ERROR] Connection failed: {str(e)}")
            sys.exit(1)
        
        print("\n[STEP 2] Checking if site_settings table exists...")
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        if 'site_settings' in existing_tables:
            print("   [INFO] site_settings table already exists!")
            print("   [OK] No action needed.")
        else:
            print("   [INFO] site_settings table does not exist. Creating...")
            
            try:
                create_table_sql = text("""
                    CREATE TABLE site_settings (
                        id SERIAL PRIMARY KEY,
                        setting_key VARCHAR(100) UNIQUE NOT NULL,
                        setting_value TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_by INTEGER REFERENCES "user"(id)
                    )
                """)
                db.session.execute(create_table_sql)
                db.session.commit()
                print("   [OK] site_settings table created successfully!")
            except Exception as e:
                print(f"   [ERROR] Failed to create table: {str(e)}")
                db.session.rollback()
                sys.exit(1)
        
        print("\n[STEP 3] Verifying table structure...")
        try:
            columns = inspector.get_columns('site_settings')
            print(f"   [OK] Table has {len(columns)} columns:")
            for col in columns:
                print(f"      - {col['name']} ({col['type']})")
        except Exception as e:
            print(f"   [WARNING] Could not verify table: {str(e)}")
        
        print("\n" + "=" * 70)
        print("✅ Setup Complete!")
        print("=" * 70)
        
except Exception as e:
    print(f"\n❌ Fatal Error: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

