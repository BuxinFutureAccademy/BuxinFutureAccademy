#!/usr/bin/env python3
"""
Create or Update Admin User
Usage: python create_admin_user.py
"""
import os
import sys

# Set the database URL
DATABASE_URL = 'postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require'
os.environ['DATABASE_URL'] = DATABASE_URL

print("=" * 70)
print("BuXin Academy - Create Admin User")
print("=" * 70)

try:
    from webapp import create_app
    from webapp.extensions import db
    from webapp.models.users import User
    
    print("\n[STEP 1] Creating Flask app...")
    app = create_app()
    
    with app.app_context():
        print("\n[STEP 2] Checking for admin user...")
        
        # Check if admin user exists
        admin_user = User.query.filter_by(username='buxin').first()
        
        if admin_user:
            print(f"   [FOUND] Admin user 'buxin' already exists")
            print(f"   - ID: {admin_user.id}")
            print(f"   - Email: {admin_user.email}")
            print(f"   - Is Admin: {admin_user.is_admin}")
            
            # Update admin status and password
            admin_user.is_admin = True
            admin_user.set_password('buxin')
            db.session.commit()
            print("\n[STEP 3] Updated admin user:")
            print("   - Set is_admin = True")
            print("   - Updated password to 'buxin'")
        else:
            print("   [NOT FOUND] Creating new admin user...")
            
            # Check if email exists
            existing_email = User.query.filter_by(email='admin@buxin.com').first()
            if existing_email:
                email = f'admin{admin_user.id}@buxin.com'
            else:
                email = 'admin@buxin.com'
            
            # Create admin user
            admin_user = User(
                username='buxin',
                email=email,
                first_name='Admin',
                last_name='BuXin',
                is_admin=True,
                is_student=False
            )
            admin_user.set_password('buxin')
            
            db.session.add(admin_user)
            db.session.commit()
            
            print("\n[STEP 3] Created admin user:")
            print(f"   - Username: buxin")
            print(f"   - Email: {email}")
            print(f"   - Password: buxin")
            print(f"   - Is Admin: True")
        
        # Verify the user
        print("\n[STEP 4] Verifying admin user...")
        verify_user = User.query.filter_by(username='buxin').first()
        
        if verify_user and verify_user.is_admin:
            # Test password
            if verify_user.check_password('buxin'):
                print("   [OK] Admin user verified successfully!")
                print("   [OK] Password check passed!")
                print("\n" + "=" * 70)
                print("[SUCCESS] Admin user is ready!")
                print("=" * 70)
                print("\nLogin credentials:")
                print("   Username: buxin")
                print("   Password: buxin")
                print("\nLogin URL: https://edu.techbuxin.com/login")
                print()
            else:
                print("   [ERROR] Password check failed!")
                sys.exit(1)
        else:
            print("   [ERROR] Admin user not found or not set as admin!")
            sys.exit(1)
        
except ImportError as e:
    print(f"\n[ERROR] Import error: {str(e)}")
    print("\n   Make sure you're in the correct directory and dependencies are installed:")
    print("   - pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"\n[ERROR] {str(e)}")
    import traceback
    print("\n   Full error traceback:")
    traceback.print_exc()
    sys.exit(1)

