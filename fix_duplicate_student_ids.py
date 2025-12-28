#!/usr/bin/env python3
"""
Script to fix duplicate student_ids in the database
Each user should have a unique student_id
"""
import os
import sys
from collections import defaultdict

# Set the database URL
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require'

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from webapp import create_app
from webapp.extensions import db
from webapp.models.users import User
from webapp.models.classes import generate_student_id_for_class

def fix_duplicate_student_ids():
    """Find and fix duplicate student_ids"""
    app = create_app()
    
    with app.app_context():
        try:
            # Find all users with student_ids
            all_users = User.query.filter(User.student_id.isnot(None)).all()
            
            # Group users by student_id
            id_to_users = defaultdict(list)
            for user in all_users:
                if user.student_id:
                    id_to_users[user.student_id].append(user)
            
            # Find duplicates
            duplicates = {sid: users for sid, users in id_to_users.items() if len(users) > 1}
            
            if not duplicates:
                print("[OK] No duplicate student_ids found!")
                return True
            
            print(f"[INFO] Found {len(duplicates)} duplicate student_ids:")
            for sid, users in duplicates.items():
                print(f"  {sid}: {len(users)} users")
                for user in users:
                    print(f"    - User ID {user.id}: {user.first_name} {user.last_name} ({user.email})")
            
            # Fix duplicates: Keep the first user's ID, assign new IDs to others
            fixed_count = 0
            for sid, users in duplicates.items():
                # Keep the first user's ID (oldest enrollment or first created)
                # Sort by user.id to keep the first registered user
                users_sorted = sorted(users, key=lambda u: u.id)
                keep_user = users_sorted[0]
                
                print(f"\n[INFO] Keeping {sid} for User {keep_user.id} ({keep_user.first_name} {keep_user.last_name})")
                
                # Assign new IDs to the rest
                for user in users_sorted[1:]:
                    # Generate a new unique ID
                    new_student_id = generate_student_id_for_class(user.class_type or 'individual')
                    
                    # Double-check uniqueness
                    while User.query.filter_by(student_id=new_student_id).first():
                        new_student_id = generate_student_id_for_class(user.class_type or 'individual')
                    
                    old_id = user.student_id
                    user.student_id = new_student_id
                    fixed_count += 1
                    print(f"  [FIXED] User {user.id} ({user.first_name} {user.last_name}): {old_id} -> {new_student_id}")
            
            if fixed_count > 0:
                db.session.commit()
                print(f"\n[OK] Successfully fixed {fixed_count} duplicate student_ids!")
            else:
                print("\n[INFO] No fixes needed")
                
        except Exception as e:
            print(f"[ERROR] Error fixing duplicate student_ids: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return False
    
    return True

if __name__ == '__main__':
    success = fix_duplicate_student_ids()
    sys.exit(0 if success else 1)

