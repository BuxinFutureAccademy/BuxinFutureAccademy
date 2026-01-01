"""
Cleanup Script: Remove individual student IDs (STU-XXXXX) from group students
Group students should only have Group System IDs (GRO-XXXXX), not individual student IDs
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from webapp import create_app
from webapp.extensions import db
from webapp.models import User, ClassEnrollment

def cleanup_group_student_ids():
    """Remove individual student IDs from users who are ONLY in group classes"""
    app = create_app()
    
    with app.app_context():
        try:
            # Get all users with student_id
            users_with_student_id = User.query.filter(
                User.student_id.isnot(None),
                User.student_id.like('STU-%')
            ).all()
            
            cleaned_count = 0
            kept_count = 0
            
            print("=" * 60)
            print("CLEANUP: Removing individual student IDs from group-only students")
            print("=" * 60)
            
            for user in users_with_student_id:
                # Check if user has any individual class enrollments
                individual_enrollment = ClassEnrollment.query.filter_by(
                    user_id=user.id,
                    class_type='individual',
                    status='completed'
                ).first()
                
                # Check if user has any group class enrollments
                group_enrollment = ClassEnrollment.query.filter_by(
                    user_id=user.id,
                    class_type='group',
                    status='completed'
                ).first()
                
                if individual_enrollment:
                    # User has individual enrollment - KEEP student_id
                    print(f"✓ KEEPING {user.student_id} for {user.first_name} {user.last_name} (has individual enrollment)")
                    kept_count += 1
                elif group_enrollment:
                    # User only has group enrollment - REMOVE student_id
                    old_student_id = user.student_id
                    user.student_id = None
                    user.class_type = 'group'
                    cleaned_count += 1
                    print(f"✗ REMOVED {old_student_id} from {user.first_name} {user.last_name} (group-only student)")
                else:
                    # User has no completed enrollments - keep for now (might be pending)
                    print(f"? KEEPING {user.student_id} for {user.first_name} {user.last_name} (no completed enrollments)")
                    kept_count += 1
            
            # Commit all changes
            db.session.commit()
            
            print("=" * 60)
            print(f"✓ Cleanup complete!")
            print(f"  - Removed student_id from {cleaned_count} group-only students")
            print(f"  - Kept student_id for {kept_count} students (have individual enrollments or pending)")
            print("=" * 60)
            
            return {
                'success': True,
                'cleaned': cleaned_count,
                'kept': kept_count
            }
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error during cleanup: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }

if __name__ == '__main__':
    result = cleanup_group_student_ids()
    if result['success']:
        print(f"\n✅ Successfully cleaned {result['cleaned']} group student IDs")
        sys.exit(0)
    else:
        print(f"\n❌ Cleanup failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)

