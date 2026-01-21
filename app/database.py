import os
import mysql.connector
from mysql.connector import Error
from flask import g
import logging

logger = logging.getLogger('mefportal')

DB_CONFIG = {
    'host': os.environ.get('MEF_DB_HOST', 'localhost'),
    'user': os.environ.get('MEF_DB_USER', 'ram'),
    'password': os.environ.get('MEF_DB_PASSWORD', 'ram123'),
    'database': os.environ.get('MEF_DB_NAME', 'mefportal'),
    'autocommit': False
}

def get_db():
    """Get database connection for the current request context"""
    db = getattr(g, '_database', None)
    if db is None:
        try:
            # Attempt MySQL connection
            db = g._database = mysql.connector.connect(**DB_CONFIG)
        except Error as e:
            raise Exception(f"MySQL connection required but failed: {e}")
    return db

def close_db(e=None):
    """Close database connection on teardown"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_app(app):
    """Register database functions with the Flask app"""
    app.teardown_appcontext(close_db)

def init_db():
    """Initialize the database with tables"""
    db = get_db()
    if db is None:
        return
        
    cur = db.cursor()
    try:
        create_tables_if_not_exist(cur, db)
        add_missing_columns(cur, db)
        db.commit()
    except Exception:
        logger.exception("Database update error")
        db.rollback()
    finally:
        cur.close()

def create_tables_if_not_exist(cur, db):
    """Create tables if they don't exist"""
    try:
        # Create users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL,
                role ENUM('Student', 'Mentor', 'Advisor', 'HOD') DEFAULT 'Student',
                password VARCHAR(255),
                register_number VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                department VARCHAR(100) NOT NULL,
                year VARCHAR(10) DEFAULT '1',
                dob DATE NOT NULL,
                student_type ENUM('Day Scholar', 'Hosteller') DEFAULT 'Day Scholar',
                mentor_email VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        # Create requests table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                type VARCHAR(50) NOT NULL,
                reason TEXT NOT NULL,
                from_date DATE NOT NULL,
                to_date DATE NOT NULL,
                status ENUM('Pending', 'Mentor Approved', 'Mentor Rejected', 'Advisor Approved', 'Advisor Rejected', 'Approved', 'Rejected') DEFAULT 'Pending',
                student_name VARCHAR(100) NOT NULL,
                department VARCHAR(100) NOT NULL,
                request_type ENUM('Leave', 'Permission', 'Apology', 'Bonafide', 'OD') DEFAULT 'Leave',
                advisor_note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # Create permissions table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS permissions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                student_name VARCHAR(100) NOT NULL,
                department VARCHAR(100) NOT NULL,
                custom_subject VARCHAR(200) NOT NULL,
                reason TEXT NOT NULL,
                from_date DATE NOT NULL,
                to_date DATE NOT NULL,
                status ENUM('Pending', 'Approved', 'Rejected') DEFAULT 'Pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Create auth_lockouts table for DB-backed lockouts
        cur.execute("""
            CREATE TABLE IF NOT EXISTS auth_lockouts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                register_number VARCHAR(50) UNIQUE NOT NULL,
                failed_attempts INT NOT NULL DEFAULT 0,
                lockout_until DATETIME NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)

        # Create push_subscriptions table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                endpoint TEXT NOT NULL,
                p256dh VARCHAR(255),
                auth VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_user_endpoint (user_id, endpoint(255)),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
    except Exception:
        logger.exception("Error creating tables")
        raise

def add_missing_columns(cur, db):
    """Add missing columns to existing tables"""
    try:
        # Check if student_type column exists in users table
        cur.execute("SHOW COLUMNS FROM users LIKE 'student_type'")
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE users 
                ADD COLUMN student_type ENUM('Day Scholar', 'Hosteller') DEFAULT 'Day Scholar'
            """)
        
        # Check if mentor_email column exists in users table
        cur.execute("SHOW COLUMNS FROM users LIKE 'mentor_email'")
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE users 
                ADD COLUMN mentor_email VARCHAR(100)
            """)
        
        # Check if request_type column exists in requests table
        cur.execute("SHOW COLUMNS FROM requests LIKE 'request_type'")
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE requests 
                ADD COLUMN request_type ENUM('Leave', 'Permission', 'Apology', 'Bonafide', 'OD') DEFAULT 'Leave'
            """)
        
        # Check if advisor_note column exists in requests table
        cur.execute("SHOW COLUMNS FROM requests LIKE 'advisor_note'")
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE requests 
                ADD COLUMN advisor_note TEXT
            """)
            
    except Exception:
        raise
