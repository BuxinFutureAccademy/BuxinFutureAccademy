#!/usr/bin/env python3
"""
Create Admin User - Simple SQL Approach
"""
import os
from werkzeug.security import generate_password_hash

DATABASE_URL = 'postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require'
os.environ['DATABASE_URL'] = DATABASE_URL

print("=" * 70)
print("Creating Admin User: buxin / buxin")
print("=" * 70)

try:
    from webapp import create_app
    from webapp.extensions import db
    from sqlalchemy import text
    
    app = create_app()
    
    with app.app_context():
        # Generate password hash
        password_hash = generate_password_hash('buxin')
        
        # Check if user exists
        result = db.session.execute(text("SELECT id, is_admin FROM \"user\" WHERE username = 'buxin'"))
        user = result.fetchone()
        
        if user:
            print(f"\n[FOUND] User 'buxin' exists (ID: {user[0]})")
            print(f"   Current is_admin: {user[1]}")
            
            # Update user to be admin
            db.session.execute(text("""
                UPDATE "user" 
                SET is_admin = TRUE, 
                    password_hash = :password_hash,
                    email = COALESCE(email, 'admin@buxin.com')
                WHERE username = 'buxin'
            """), {"password_hash": password_hash})
            db.session.commit()
            print("\n[UPDATED] Admin user updated successfully!")
        else:
            print("\n[CREATING] New admin user...")
            
            # Create admin user
            db.session.execute(text("""
                INSERT INTO "user" (username, email, password_hash, first_name, last_name, is_admin, is_student, created_at)
                VALUES ('buxin', 'admin@buxin.com', :password_hash, 'Admin', 'BuXin', TRUE, FALSE, NOW())
            """), {"password_hash": password_hash})
            db.session.commit()
            print("\n[CREATED] Admin user created successfully!")
        
        # Verify
        result = db.session.execute(text("""
            SELECT id, username, email, is_admin 
            FROM "user" 
            WHERE username = 'buxin'
        """))
        verify = result.fetchone()
        
        if verify and verify[3]:  # is_admin
            print("\n" + "=" * 70)
            print("[SUCCESS] Admin user is ready!")
            print("=" * 70)
            print(f"\nUser ID: {verify[0]}")
            print(f"Username: {verify[1]}")
            print(f"Email: {verify[2]}")
            print(f"Is Admin: {verify[3]}")
            print("\nLogin credentials:")
            print("   Username: buxin")
            print("   Password: buxin")
            print("\nLogin URL: https://edu.techbuxin.com/login")
            print()
        else:
            print("\n[ERROR] Admin user verification failed!")
            
except Exception as e:
    print(f"\n[ERROR] {str(e)}")
    import traceback
    traceback.print_exc()

