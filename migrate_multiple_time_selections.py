#!/usr/bin/env python3
"""
Migration script to update StudentClassTimeSelection table
to allow multiple time selections per enrollment (up to 2)

Changes:
1. Remove old unique constraint on enrollment_id only
2. Add new unique constraint on (enrollment_id, class_time_id)
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from webapp import create_app
from webapp.extensions import db
import sys

def migrate():
    """Update the unique constraint on student_class_time_selection table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Reconfigure stdout for Windows Unicode support
            if sys.platform == 'win32':
                sys.stdout.reconfigure(encoding='utf-8')
            
            print("🔄 Starting migration: Allow multiple time selections per enrollment...")
            print()
            
            # Check if table exists
            result = db.session.execute(db.text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'student_class_time_selection'
                );
            """))
            table_exists = result.scalar()
            
            if not table_exists:
                print("❌ Table 'student_class_time_selection' does not exist. Skipping migration.")
                return
            
            # Check current constraints
            result = db.session.execute(db.text("""
                SELECT constraint_name, constraint_type
                FROM information_schema.table_constraints
                WHERE table_name = 'student_class_time_selection'
                AND constraint_type = 'UNIQUE';
            """))
            constraints = result.fetchall()
            
            print(f"📋 Found {len(constraints)} unique constraint(s):")
            for constraint_name, constraint_type in constraints:
                print(f"   - {constraint_name} ({constraint_type})")
            print()
            
            # Drop old constraint if it exists (enrollment_id only)
            old_constraint_name = 'unique_enrollment_time_selection'
            result = db.session.execute(db.text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.table_constraints
                    WHERE table_name = 'student_class_time_selection'
                    AND constraint_name = :constraint_name
                );
            """), {'constraint_name': old_constraint_name})
            
            if result.scalar():
                print(f"🗑️  Dropping old constraint: {old_constraint_name}...")
                db.session.execute(db.text(f"""
                    ALTER TABLE student_class_time_selection
                    DROP CONSTRAINT IF EXISTS {old_constraint_name};
                """))
                db.session.commit()
                print(f"✅ Dropped old constraint: {old_constraint_name}")
            else:
                print(f"ℹ️  Old constraint '{old_constraint_name}' not found (may have been already removed)")
            print()
            
            # Add new unique constraint on (enrollment_id, class_time_id)
            new_constraint_name = 'unique_enrollment_time_selection'
            result = db.session.execute(db.text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.table_constraints
                    WHERE table_name = 'student_class_time_selection'
                    AND constraint_name = :constraint_name
                );
            """), {'constraint_name': new_constraint_name})
            
            if not result.scalar():
                print(f"➕ Adding new constraint: {new_constraint_name} on (enrollment_id, class_time_id)...")
                db.session.execute(db.text(f"""
                    ALTER TABLE student_class_time_selection
                    ADD CONSTRAINT {new_constraint_name}
                    UNIQUE (enrollment_id, class_time_id);
                """))
                db.session.commit()
                print(f"✅ Added new constraint: {new_constraint_name}")
            else:
                print(f"ℹ️  New constraint '{new_constraint_name}' already exists")
            print()
            
            # Verify the constraint
            result = db.session.execute(db.text("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = 'student_class_time_selection'
                AND constraint_name = :constraint_name;
            """), {'constraint_name': new_constraint_name})
            
            if result.scalar():
                print("✅ Migration completed successfully!")
                print()
                print("📝 Summary:")
                print("   - Students can now select up to 2 different time slots per enrollment")
                print("   - The same time slot cannot be selected twice for the same enrollment")
                print("   - Time slots selected by one student are hidden from other students")
            else:
                print("❌ Warning: Could not verify the new constraint was created")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error during migration: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == '__main__':
    migrate()

