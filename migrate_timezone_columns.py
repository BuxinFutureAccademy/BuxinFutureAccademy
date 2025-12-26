"""
Migration script to add timezone columns to ClassTime and User tables
Run this once to add timezone support to the database
"""
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("Error: DATABASE_URL not found in environment variables")
    sys.exit(1)

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
            print("✓ Added timezone column to class_time table")
            
            # Add timezone column to user table
            print("Adding timezone column to user table...")
            conn.execute(text("""
                ALTER TABLE user 
                ADD COLUMN IF NOT EXISTS timezone VARCHAR(50)
            """))
            conn.commit()
            print("✓ Added timezone column to user table")
            
            print("\n✅ Migration completed successfully!")
            
    except Exception as e:
        print(f"\n❌ Error during migration: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    print("Starting timezone columns migration...")
    migrate()

