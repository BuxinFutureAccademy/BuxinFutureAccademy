#!/usr/bin/env python3
"""
Add missing columns to user table
"""
import os

DATABASE_URL = 'postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require'
os.environ['DATABASE_URL'] = DATABASE_URL

print("=" * 70)
print("Adding Missing Columns to User Table")
print("=" * 70)

try:
    from webapp import create_app
    from webapp.extensions import db
    from sqlalchemy import text
    
    app = create_app()
    
    with app.app_context():
        print("\n[STEP 1] Checking existing columns...")
        result = db.session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'user'
            ORDER BY column_name
        """))
        existing_columns = [row[0] for row in result.fetchall()]
        print(f"   Found {len(existing_columns)} columns")
        
        # Add student_id column if it doesn't exist
        if 'student_id' not in existing_columns:
            print("\n[STEP 2] Adding student_id column...")
            try:
                db.session.execute(text("""
                    ALTER TABLE "user" 
                    ADD COLUMN student_id VARCHAR(20) UNIQUE
                """))
                db.session.commit()
                print("   [OK] student_id column added")
            except Exception as e:
                print(f"   [ERROR] {str(e)}")
                db.session.rollback()
        else:
            print("\n[STEP 2] student_id column already exists")
        
        # Add class_type column if it doesn't exist
        if 'class_type' not in existing_columns:
            print("\n[STEP 3] Adding class_type column...")
            try:
                db.session.execute(text("""
                    ALTER TABLE "user" 
                    ADD COLUMN class_type VARCHAR(20)
                """))
                db.session.commit()
                print("   [OK] class_type column added")
            except Exception as e:
                print(f"   [ERROR] {str(e)}")
                db.session.rollback()
        else:
            print("\n[STEP 3] class_type column already exists")
        
        # Verify columns
        print("\n[STEP 4] Verifying columns...")
        result = db.session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'user'
            ORDER BY column_name
        """))
        final_columns = [row[0] for row in result.fetchall()]
        print(f"   Total columns: {len(final_columns)}")
        
        if 'student_id' in final_columns and 'class_type' in final_columns:
            print("\n" + "=" * 70)
            print("[SUCCESS] All required columns exist!")
            print("=" * 70)
        else:
            print("\n[WARNING] Some columns may still be missing")
            
except Exception as e:
    print(f"\n[ERROR] {str(e)}")
    import traceback
    traceback.print_exc()

