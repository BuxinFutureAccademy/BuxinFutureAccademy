#!/usr/bin/env python3
"""
Script to add image_url column to group_class table
"""
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

# Database connection string
DATABASE_URL = "postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

def add_image_url_column():
    """Add image_url column to group_class table if it doesn't exist"""
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # Check if column already exists
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='group_class' AND column_name='image_url'
            """)
            result = conn.execute(check_query)
            
            if result.fetchone():
                print("[SUCCESS] Column 'image_url' already exists in 'group_class' table.")
                return True
            
            # Add the column
            alter_query = text("""
                ALTER TABLE group_class 
                ADD COLUMN image_url VARCHAR(500)
            """)
            conn.execute(alter_query)
            conn.commit()
            
            print("[SUCCESS] Successfully added 'image_url' column to 'group_class' table.")
            return True
            
    except ProgrammingError as e:
        if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
            print("[SUCCESS] Column 'image_url' already exists in 'group_class' table.")
            return True
        else:
            print(f"[ERROR] Error adding column: {e}")
            return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("Adding image_url column to group_class table...")
    success = add_image_url_column()
    sys.exit(0 if success else 1)

