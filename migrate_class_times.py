#!/usr/bin/env python3
"""
Migration script to create class_time and student_class_time_selection tables
Run this once to create the tables in your database.
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
    """Create class_time and student_class_time_selection tables"""
    try:
        # Configure stdout for Unicode
        sys.stdout.reconfigure(encoding='utf-8')
        
        # Create engine
        engine = create_engine(DATABASE_URL)
        
        # Check if tables already exist
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        tables_created = []
        
        # Create class_time table
        if 'class_time' not in existing_tables:
            with engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE class_time (
                        id SERIAL PRIMARY KEY,
                        class_type VARCHAR(20) NOT NULL,
                        class_id INTEGER,
                        day VARCHAR(20) NOT NULL,
                        start_time TIME NOT NULL,
                        end_time TIME NOT NULL,
                        is_selectable BOOLEAN DEFAULT TRUE,
                        is_active BOOLEAN DEFAULT TRUE,
                        max_capacity INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by INTEGER REFERENCES "user"(id)
                    )
                """))
                conn.commit()
            tables_created.append('class_time')
            print("✅ Created 'class_time' table")
        else:
            print("✅ Table 'class_time' already exists")
        
        # Create student_class_time_selection table
        if 'student_class_time_selection' not in existing_tables:
            with engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE student_class_time_selection (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES "user"(id),
                        enrollment_id INTEGER NOT NULL REFERENCES class_enrollment(id),
                        class_time_id INTEGER NOT NULL REFERENCES class_time(id),
                        class_type VARCHAR(20) NOT NULL,
                        selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT unique_enrollment_time_selection UNIQUE (enrollment_id)
                    )
                """))
                conn.commit()
            tables_created.append('student_class_time_selection')
            print("✅ Created 'student_class_time_selection' table")
        else:
            print("✅ Table 'student_class_time_selection' already exists")
        
        if tables_created:
            print("\n✅ Migration successful!")
            print(f"✅ Created {len(tables_created)} table(s): {', '.join(tables_created)}")
            print("✅ Class Time Management functionality is now ready to use.")
        else:
            print("\n✅ All tables already exist. No migration needed.")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        return False

if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)

