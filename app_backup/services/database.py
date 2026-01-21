"""Database utilities and migration helpers for MEF Portal"""

import logging
from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from datetime import date

logger = logging.getLogger(__name__)

def init_database(db):
    """Initialize database with tables and sample data"""
    try:
        # Create all tables
        db.create_all()
        logger.info("Database tables created successfully")
        
        # Create sample data if none exists
        create_sample_data(db)
        
        return True
    except Exception as e:
        logger.exception("Failed to initialize database")
        return False

def create_sample_data(db):
    """Create sample users for development and testing"""
    try:
        # Safe import of models
        from app.models import register_models
        models = register_models()
        
        if not models:
            logger.warning("No models available, skipping sample data creation")
            return True
            
        User = models.get('User')
        if not User:
            logger.warning("User model not available, skipping sample data creation")  
            return True
            
        # Get enum classes from models
        from app.models.user import UserRole, StudentType
        # Check if sample data already exists
        if User.query.first():
            logger.info("Sample data already exists, skipping creation")
            return
        
        # Create sample users
        sample_users = [
            {
                'username': 'hod001',
                'name': 'Dr. John Smith',
                'role': UserRole.HOD,
                'register_number': 'HOD001',
                'email': 'hod@mefportal.edu',
                'department': 'cse',
                'year': '1',
                'dob': date(1975, 1, 15),
                'password': 'hod123'
            },
            {
                'username': 'admin001',
                'name': 'System Administrator',
                'role': UserRole.ADMIN,
                'register_number': 'ADM001',
                'email': 'admin@mefportal.edu',
                'department': 'administration',
                'year': '1',
                'dob': date(1970, 6, 1),
                'password': 'admin123'
            },
            {
                'username': 'advisor001',
                'name': 'Prof. Jane Doe',
                'role': UserRole.ADVISOR,
                'register_number': 'ADV001',
                'email': 'advisor@mefportal.edu',
                'department': 'cse',
                'year': '1',
                'dob': date(1980, 5, 20),
                'password': 'advisor123'
            },
            {
                'username': 'mentor001',
                'name': 'Dr. Mike Johnson',
                'role': UserRole.MENTOR,
                'register_number': 'MEN001',
                'email': 'mentor@mefportal.edu',
                'department': 'cse',
                'year': '1',
                'dob': date(1985, 8, 10),
                'password': 'mentor123'
            },
            {
                'username': 'student001',
                'name': 'Alice Student',
                'role': UserRole.STUDENT,
                'register_number': '2025001',
                'email': 'alice@student.edu',
                'department': 'cse',
                'year': '2',
                'dob': date(2003, 12, 1),
                'student_type': StudentType.DAY_SCHOLAR,
                'mentor_email': 'mentor@mefportal.edu',
                'password': 'student123'
            },
            {
                'username': 'student002',
                'name': 'Bob Johnson',
                'role': UserRole.STUDENT,
                'register_number': '2025002',
                'email': 'bob@student.edu',
                'department': 'ece',
                'year': '3',
                'dob': date(2002, 8, 15),
                'student_type': StudentType.HOSTELLER,
                'mentor_email': 'mentor@mefportal.edu',
                'password': 'student123'
            }
        ]
        
        created_count = 0
        for user_data in sample_users:
            password = user_data.pop('password')
            user = User(**user_data)
            user.set_password(password)
            db.session.add(user)
            created_count += 1
            logger.info(f"Created user: {user.name} ({user.register_number})")
        
        db.session.commit()
        logger.info(f"Successfully created {created_count} sample users")
        
        # Log login credentials
        logger.info("MEF Portal - Sample Login Credentials")
        logger.info("HOD Login:     HOD001 / hod123")
        logger.info("Admin Login:   ADM001 / admin123") 
        logger.info("Advisor Login: ADV001 / advisor123")
        logger.info("Mentor Login:  MEN001 / mentor123")
        logger.info("Student Login: 2025001 / student123")
        logger.info("Student Login: 2025002 / student123")
        
    except Exception as e:
        logger.exception("Failed to create sample data")
        db.session.rollback()

def migrate_legacy_data(db):
    """Migrate data from legacy MySQL structure to SQLAlchemy"""
    try:
        import mysql.connector
        from mysql.connector import Error
        import os
        
        # Legacy database configuration
        legacy_config = {
            'host': os.environ.get('MEF_DB_HOST', 'localhost'),
            'user': os.environ.get('MEF_DB_USER', 'ram'),
            'password': os.environ.get('MEF_DB_PASSWORD', 'ram123'),
            'database': os.environ.get('MEF_DB_NAME', 'mefportal')
        }
        
        # Connect to legacy database
        legacy_db = mysql.connector.connect(**legacy_config)
        cursor = legacy_db.cursor()
        
        # Import models
        from app.models.user import User, UserRole, StudentType
        from app.models.request import Request, RequestType, RequestStatus
        from app.models.permission import Permission, PermissionStatus
        
        logger.info("Starting legacy data migration...")
        
        # Migrate users
        cursor.execute("SELECT * FROM users")
        legacy_users = cursor.fetchall()
        
        user_count = 0
        for row in legacy_users:
            if not User.query.filter_by(register_number=row[5]).first():
                # Map legacy data to new model
                user = User(
                    username=row[1],
                    name=row[2],
                    role=UserRole(row[3]),
                    password_hash=row[4],
                    register_number=row[5],
                    email=row[6],
                    department=row[7],
                    year=row[8] or '1',
                    dob=row[9],
                    student_type=StudentType(row[10]) if row[10] else StudentType.DAY_SCHOLAR,
                    mentor_email=row[11]
                )
                db.session.add(user)
                user_count += 1
        
        # Migrate requests
        cursor.execute("SELECT * FROM requests")
        legacy_requests = cursor.fetchall()
        
        request_count = 0
        for row in legacy_requests:
            if not Request.query.get(row[0]):
                request = Request(
                    id=row[0],
                    user_id=row[1],
                    type=row[2],
                    reason=row[3],
                    from_date=row[4],
                    to_date=row[5],
                    status=RequestStatus(row[6]),
                    student_name=row[7],
                    department=row[8],
                    request_type=RequestType(row[9]) if len(row) > 9 and row[9] else RequestType.LEAVE,
                    advisor_note=row[10] if len(row) > 10 else None,
                    created_at=row[11] if len(row) > 11 else None,
                    updated_at=row[12] if len(row) > 12 else None
                )
                db.session.add(request)
                request_count += 1
        
        # Migrate permissions
        try:
            cursor.execute("SELECT * FROM permissions")
            legacy_permissions = cursor.fetchall()
            
            permission_count = 0
            for row in legacy_permissions:
                if not Permission.query.get(row[0]):
                    permission = Permission(
                        id=row[0],
                        user_id=row[1],
                        student_name=row[2],
                        department=row[3],
                        custom_subject=row[4],
                        reason=row[5],
                        from_date=row[6],
                        to_date=row[7],
                        status=PermissionStatus(row[8]),
                        created_at=row[9] if len(row) > 9 else None,
                        updated_at=row[10] if len(row) > 10 else None
                    )
                    db.session.add(permission)
                    permission_count += 1
        except Error:
            logger.info("Permissions table not found in legacy database, skipping")
            permission_count = 0
        
        # Commit all changes
        db.session.commit()
        cursor.close()
        legacy_db.close()
        
        logger.info(f"Migration completed: {user_count} users, {request_count} requests, {permission_count} permissions")
        return True
        
    except ImportError:
        logger.info("mysql-connector-python not available, skipping legacy migration")
        return False
    except Error as e:
        logger.warning(f"Legacy database not accessible: {e}")
        return False
    except Exception as e:
        logger.exception("Failed to migrate legacy data")
        db.session.rollback()
        return False

def check_database_health(db):
    """Check database connectivity and basic functionality"""
    try:
        # Test basic query (using text() for SQLAlchemy compatibility)
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        
        # Check if tables exist
        from app.models.user import User
        from app.models.request import Request
        from app.models.permission import Permission
        
        user_count = User.query.count()
        request_count = Request.query.count()
        permission_count = Permission.query.count()
        
        logger.info(f"Database health check passed - Users: {user_count}, Requests: {request_count}, Permissions: {permission_count}")
        return True
        
    except Exception as e:
        logger.exception("Database health check failed")
        return False