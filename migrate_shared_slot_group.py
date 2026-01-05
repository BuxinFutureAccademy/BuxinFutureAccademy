"""
Migration script to add shared_slot_group_id column to ClassTime table
Run this once to add shared slot group support to the database
"""
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL from environment or use provided connection string
DATABASE_URL = os.getenv('DATABASE_URL') or "postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

if not DATABASE_URL:
    print("Error: DATABASE_URL not found in environment variables")
    sys.exit(1)

# Create engine
engine = create_engine(DATABASE_URL)

def migrate():
    """Add shared_slot_group_id column to ClassTime table"""
    try:
        with engine.connect() as conn:
            # Add shared_slot_group_id column to class_time table
            print("Adding shared_slot_group_id column to class_time table...")
            conn.execute(text("""
                ALTER TABLE class_time 
                ADD COLUMN IF NOT EXISTS shared_slot_group_id VARCHAR(100)
            """))
            conn.commit()
            print("[OK] Added shared_slot_group_id column to class_time table")
            
            print("\n[SUCCESS] Migration completed successfully!")
            
    except Exception as e:
        print(f"\n[ERROR] Error during migration: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        engine.dispose()

if __name__ == '__main__':
    print("Starting shared_slot_group_id column migration...")
    print(f"Database: {DATABASE_URL.split('@')[1].split('/')[0] if '@' in DATABASE_URL else 'Unknown'}")
    migrate()

