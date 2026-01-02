#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create monthly_payment table in PostgreSQL database
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
print("Creating Monthly Payment Table")
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
        
        print("\n[STEP 2] Checking if monthly_payment table exists...")
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        if 'monthly_payment' in existing_tables:
            print("   [INFO] monthly_payment table already exists!")
            print("   [OK] No action needed.")
        else:
            print("   [INFO] monthly_payment table does not exist. Creating...")
            
            try:
                create_table_sql = text("""
                    CREATE TABLE monthly_payment (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES "user"(id),
                        enrollment_id INTEGER NOT NULL REFERENCES class_enrollment(id),
                        class_type VARCHAR(20) NOT NULL,
                        payment_month INTEGER NOT NULL,
                        payment_year INTEGER NOT NULL,
                        amount FLOAT NOT NULL,
                        receipt_url VARCHAR(500) NOT NULL,
                        receipt_filename VARCHAR(255),
                        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status VARCHAR(20) DEFAULT 'pending',
                        verified_by INTEGER REFERENCES "user"(id),
                        verified_at TIMESTAMP,
                        notes TEXT,
                        CONSTRAINT unique_monthly_payment UNIQUE (user_id, enrollment_id, payment_month, payment_year)
                    )
                """)
                db.session.execute(create_table_sql)
                db.session.commit()
                print("   [OK] monthly_payment table created successfully!")
            except Exception as e:
                print(f"   [ERROR] Failed to create table: {str(e)}")
                db.session.rollback()
                sys.exit(1)
        
        print("\n[STEP 3] Verifying table structure...")
        try:
            columns = inspector.get_columns('monthly_payment')
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

