"""
Migration script to add timezone columns to ClassTime and User tables
Run with: python migrate_timezone_direct.py
"""
import sys
from sqlalchemy import create_engine, text

# Database connection string
DATABASE_URL = "postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

# Create engine
engine = create_engine(DATABASE_URL)

def migrate():
    """Add timezone columns to ClassTime and User tables"""
    try:
        with engine.connect() as conn:
            # Add timezone column to class_time table
            print("Adding timezone column to class_time table...")
            conn.execute(text("""
                ALTER TABLE class_time 
                ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Kolkata'
            """))
            conn.commit()
            print("[OK] Added timezone column to class_time table")
            
            # Add timezone column to user table
            print("Adding timezone column to user table...")
            conn.execute(text("""
                ALTER TABLE "user" 
                ADD COLUMN IF NOT EXISTS timezone VARCHAR(50)
            """))
            conn.commit()
            print("[OK] Added timezone column to user table")
            
            print("\n[SUCCESS] Migration completed successfully!")
            
    except Exception as e:
        print(f"\n[ERROR] Error during migration: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        engine.dispose()

if __name__ == '__main__':
    print("Starting timezone columns migration...")
    print(f"Connecting to database...")
    migrate()

