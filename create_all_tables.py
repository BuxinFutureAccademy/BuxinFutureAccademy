"""
Script to create all database tables
Run with: python create_all_tables.py
"""
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database connection string
DATABASE_URL = "postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

def create_tables():
    """Create all tables using Flask app's models"""
    try:
        # Import Flask app to get models
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        from webapp import create_app
        from webapp.extensions import db
        
        app = create_app()
        
        with app.app_context():
            print("Creating all database tables...")
            db.create_all()
            print("[SUCCESS] All tables created successfully!")
            
            # Verify tables were created
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"\nCreated {len(tables)} tables:")
            for table in sorted(tables):
                print(f"  - {table}")
            
    except Exception as e:
        print(f"\n[ERROR] Error creating tables: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    print("Starting database table creation...")
    print(f"Connecting to database...")
    create_tables()
