#!/usr/bin/env python3
"""
Migration script to add group_system_id column to class_enrollment table
Run this once to add the column to your database.
"""
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sqlalchemy import create_engine, text, inspect
import sys

# Database connection string
DATABASE_URL = "postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

def migrate():
    """Add group_system_id column to class_enrollment table"""
    try:
        # Configure stdout for Unicode
        sys.stdout.reconfigure(encoding='utf-8')
        
        # Create engine
        engine = create_engine(DATABASE_URL)
        
        # Check if column already exists
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('class_enrollment')]
        
        if 'group_system_id' in columns:
            print("✅ Column 'group_system_id' already exists in class_enrollment table.")
            print("No migration needed.")
            return True
        
        # Add the column
        with engine.connect() as conn:
            conn.execute(text('ALTER TABLE class_enrollment ADD COLUMN group_system_id VARCHAR(20)'))
            conn.commit()
        
        print("✅ Migration successful!")
        print("✅ Column 'group_system_id' added to class_enrollment table.")
        print("✅ Group System ID functionality is now ready to use.")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        return False

if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)

