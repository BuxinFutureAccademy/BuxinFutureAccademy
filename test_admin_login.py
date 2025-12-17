#!/usr/bin/env python3
"""
Test Admin Login
"""
import os
from werkzeug.security import check_password_hash, generate_password_hash

DATABASE_URL = 'postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require'
os.environ['DATABASE_URL'] = DATABASE_URL

print("=" * 70)
print("Testing Admin Login: buxin / buxin")
print("=" * 70)

try:
    from webapp import create_app
    from webapp.extensions import db
    from webapp.models.users import User
    from sqlalchemy import text
    
    app = create_app()
    
    with app.app_context():
        # Method 1: Using User model
        print("\n[TEST 1] Using User model...")
        user = User.query.filter_by(username='buxin').first()
        
        if user:
            print(f"   Found user: {user.username}")
            print(f"   Email: {user.email}")
            print(f"   Is Admin: {user.is_admin}")
            print(f"   Password hash exists: {bool(user.password_hash)}")
            
            # Test password
            if user.check_password('buxin'):
                print("   [OK] Password check PASSED!")
            else:
                print("   [FAIL] Password check FAILED!")
                print("   Updating password...")
                user.set_password('buxin')
                db.session.commit()
                print("   Password updated. Testing again...")
                if user.check_password('buxin'):
                    print("   [OK] Password check PASSED after update!")
                else:
                    print("   [FAIL] Password check still failing!")
        else:
            print("   [ERROR] User not found!")
        
        # Method 2: Direct SQL check
        print("\n[TEST 2] Direct SQL check...")
        result = db.session.execute(text("""
            SELECT id, username, email, password_hash, is_admin 
            FROM "user" 
            WHERE username = 'buxin'
        """))
        row = result.fetchone()
        
        if row:
            print(f"   Found user: {row[1]}")
            print(f"   Email: {row[2]}")
            print(f"   Is Admin: {row[4]}")
            
            # Test password hash directly
            if check_password_hash(row[3], 'buxin'):
                print("   [OK] Direct password hash check PASSED!")
            else:
                print("   [FAIL] Direct password hash check FAILED!")
                print("   Generating new hash and updating...")
                new_hash = generate_password_hash('buxin')
                db.session.execute(text("""
                    UPDATE "user" 
                    SET password_hash = :hash 
                    WHERE username = 'buxin'
                """), {"hash": new_hash})
                db.session.commit()
                print("   Password hash updated!")
        else:
            print("   [ERROR] User not found in database!")
        
        # Method 3: Test login logic
        print("\n[TEST 3] Testing login logic...")
        identifier = 'buxin'
        password = 'buxin'
        
        user = User.query.filter(
            (User.email == identifier) | (User.username == identifier)
        ).first()
        
        if user:
            print(f"   User found: {user.username}")
            if user.check_password(password):
                print("   [OK] Login logic PASSED!")
                print(f"   User is_admin: {user.is_admin}")
                if user.is_admin:
                    print("   [OK] User is admin - will redirect to admin dashboard")
                else:
                    print("   [WARNING] User is NOT admin!")
            else:
                print("   [FAIL] Login logic FAILED - password incorrect")
        else:
            print("   [ERROR] User not found with identifier 'buxin'")
        
        print("\n" + "=" * 70)
        print("Test Complete")
        print("=" * 70)
        
except Exception as e:
    print(f"\n[ERROR] {str(e)}")
    import traceback
    traceback.print_exc()

