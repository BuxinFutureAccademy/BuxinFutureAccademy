# Database Setup Instructions

## Quick Setup

To create/update all database tables in the Neon PostgreSQL database, simply run:

```bash
python setup_database.py
```

Or on Windows, double-click:
```
setup_db.bat
```

## Database Connection

The script automatically uses this connection string:
```
postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require
```

## What This Script Does

1. Connects to the Neon PostgreSQL database
2. Tests the connection
3. Creates all required tables (if they don't exist)
4. Verifies all tables are present
5. Shows a summary of all tables

## Tables Created

The script creates 26 tables including:
- `user` - User accounts
- `class_enrollment` - Class enrollments
- `individual_class`, `group_class` - Class types
- `family_member` - Family class members
- `school`, `school_student_registered` - School management
- `attendance` - Attendance records
- `learning_material` - Learning materials
- `student_project` - Student projects
- And more...

## Troubleshooting

If you encounter errors:
1. Make sure you're in the project root directory
2. Ensure all dependencies are installed: `pip install -r requirements.txt`
3. Check your internet connection (Neon is a cloud database)
4. Verify the database credentials are correct

## Running After Code Changes

After adding new models or modifying existing ones, run this script again to update the database schema.

