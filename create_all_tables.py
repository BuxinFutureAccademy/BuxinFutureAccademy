"""
Script to create all database tables
This will create all tables defined in the models
"""
import os
import sys
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import ProgrammingError

# Database connection string
DATABASE_URL = "postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

def create_all_tables():
    """Create all tables using SQLAlchemy models"""
    try:
        # Import Flask app and models
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        # Import the Flask app
        from webapp import create_app
        from webapp.extensions import db
        
        # Create Flask app context
        app = create_app()
        
        with app.app_context():
            # Get list of existing tables
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            print(f"Existing tables: {len(existing_tables)}")
            if existing_tables:
                print(f"  - {', '.join(existing_tables[:10])}{'...' if len(existing_tables) > 10 else ''}")
            
            # Create all tables
            print("\nCreating all tables...")
            db.create_all()
            
            # Get list of tables after creation
            inspector = inspect(db.engine)
            new_tables = inspector.get_table_names()
            
            print(f"\n[OK] All tables created successfully!")
            print(f"Total tables: {len(new_tables)}")
            print(f"Tables:")
            for table in sorted(new_tables):
                print(f"  - {table}")
            
            return True
            
    except Exception as e:
        print(f"[ERROR] Failed to create tables: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Creating All Database Tables")
    print("=" * 60)
    success = create_all_tables()
    if success:
        print("\n" + "=" * 60)
        print("[OK] Migration completed successfully!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("[ERROR] Migration failed!")
        print("=" * 60)
        sys.exit(1)
