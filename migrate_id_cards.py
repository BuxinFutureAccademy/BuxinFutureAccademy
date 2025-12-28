"""
Migration script to create id_card table
Run this script to create the ID card table in the database
"""
import os
import sys
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import ProgrammingError

# Database connection string
DATABASE_URL = "postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

def create_id_card_table():
    """Create the id_card table if it doesn't exist"""
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # Check if table already exists
            inspector = inspect(engine)
            if 'id_card' in inspector.get_table_names():
                print("[OK] id_card table already exists. No migration needed.")
                return True
            
            # Create the table
            create_table_sql = text("""
                CREATE TABLE id_card (
                    id SERIAL PRIMARY KEY,
                    entity_type VARCHAR(20) NOT NULL,
                    entity_id INTEGER NOT NULL,
                    system_id VARCHAR(20) NOT NULL,
                    name VARCHAR(200) NOT NULL,
                    photo_url VARCHAR(500),
                    class_name VARCHAR(200),
                    school_name VARCHAR(200),
                    school_system_id VARCHAR(20),
                    group_system_id VARCHAR(20),
                    family_system_id VARCHAR(20),
                    email VARCHAR(120),
                    phone VARCHAR(20),
                    guardian_name VARCHAR(100),
                    guardian_contact VARCHAR(20),
                    registration_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    approved_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    approved_by INTEGER REFERENCES "user"(id),
                    qr_code_data TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    is_locked BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute(create_table_sql)
            conn.commit()
            
            print("[OK] id_card table created successfully!")
            return True
            
    except ProgrammingError as e:
        print(f"[ERROR] Database error: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("Creating id_card table...")
    success = create_id_card_table()
    if success:
        print("\n[OK] Migration completed successfully!")
        sys.exit(0)
    else:
        print("\n[ERROR] Migration failed!")
        sys.exit(1)

