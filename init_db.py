#!/usr/bin/env python3
"""
Database Initialization Script for MEF Portal
Creates database and initial admin users
"""

import mysql.connector
from mysql.connector import Error
import os
from werkzeug.security import generate_password_hash
from datetime import date

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('MEF_DB_HOST', 'localhost'),
    'user': os.environ.get('MEF_DB_USER', 'ram'),
    'password': os.environ.get('MEF_DB_PASSWORD', 'ram123'),
    'autocommit': False
}

DB_NAME = os.environ.get('MEF_DB_NAME', 'mefportal')

def create_database():
    """Create the database if it doesn't exist"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        print(f"Database '{DB_NAME}' created/verified successfully")
        
        cursor.close()
        connection.close()
        return True
        
    except Error as e:
        print(f"Error creating database: {e}")
        return False

def create_tables():
    """Create all required tables"""
    try:
        # Connect to the specific database
        config = DB_CONFIG.copy()
        config['database'] = DB_NAME
        connection = mysql.connector.connect(**config)
        cursor = connection.cursor()
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL,
                role ENUM('Student', 'Mentor', 'Advisor', 'HOD') DEFAULT 'Student',
                password VARCHAR(512),
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
        cursor.execute("""
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
        cursor.execute("""
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
        
        connection.commit()
        print(" All tables created successfully")
        
        cursor.close()
        connection.close()
        return True
        
    except Error as e:
        print(f" Error creating tables: {e}")
        return False

def create_sample_users():
    """Create sample users for testing"""
    try:
        config = DB_CONFIG.copy()
        config['database'] = DB_NAME
        connection = mysql.connector.connect(**config)
        cursor = connection.cursor()
        
        # Sample users data
        sample_users = [
            {
                'username': 'hod001',
                'name': 'Dr. John Smith',
                'role': 'HOD',
                'register_number': 'HOD001',
                'email': 'hod@mefportal.edu',
                'department': 'computer science',
                'year': '1',
                'dob': '1975-01-15',
                'password': generate_password_hash('hod123')
            },
            {
                'username': 'advisor001',
                'name': 'Prof. Jane Doe',
                'role': 'Advisor',
                'register_number': 'ADV001',
                'email': 'advisor@mefportal.edu',
                'department': 'computer science',
                'year': '1',
                'dob': '1980-05-20',
                'password': generate_password_hash('advisor123')
            },
            {
                'username': 'mentor001',
                'name': 'Dr. Mike Johnson',
                'role': 'Mentor',
                'register_number': 'MEN001',
                'email': 'mentor@mefportal.edu',
                'department': 'computer science',
                'year': '1',
                'dob': '1985-08-10',
                'password': generate_password_hash('mentor123')
            },
            {
                'username': 'student001',
                'name': 'Alice Student',
                'role': 'Student',
                'register_number': '2025001',
                'email': 'alice@student.edu',
                'department': 'computer science',
                'year': '2',
                'dob': '2003-12-01',
                'student_type': 'Day Scholar',
                'mentor_email': 'mentor@mefportal.edu',
                'password': generate_password_hash('student123')
            }
        ]
        
        for user in sample_users:
            # Check if user already exists
            cursor.execute("SELECT id FROM users WHERE register_number = %s", (user['register_number'],))
            if cursor.fetchone():
                print(f"  User {user['register_number']} already exists, skipping...")
                continue
            
            # Insert user
            if user['role'] == 'Student':
                cursor.execute("""
                    INSERT INTO users (username, name, role, register_number, email, department, year, dob, student_type, mentor_email, password)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user['username'], user['name'], user['role'], user['register_number'],
                    user['email'], user['department'], user['year'], user['dob'],
                    user['student_type'], user['mentor_email'], user['password']
                ))
            else:
                cursor.execute("""
                    INSERT INTO users (username, name, role, register_number, email, department, year, dob, password)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user['username'], user['name'], user['role'], user['register_number'],
                    user['email'], user['department'], user['year'], user['dob'], user['password']
                ))
            
            print(f" Created {user['role']}: {user['name']} ({user['register_number']})")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        print("\n🎓 Sample Login Credentials:")
        print("=" * 50)
        print("HOD Login:")
        print("  Registration Number: HOD001")
        print("  Password: hod123")
        print("\nAdvisor Login:")
        print("  Registration Number: ADV001")
        print("  Password: advisor123")
        print("\nMentor Login:")
        print("  Registration Number: MEN001")
        print("  Password: mentor123")
        print("\nStudent Login:")
        print("  Registration Number: 2025001")
        print("  Password: student123")
        print("=" * 50)
        
        return True
        
    except Error as e:
        print(f"Error creating sample users: {e}")
        return False

def main():
    """Main initialization function"""
    print("Initializing MEF Portal Database...")
    print("=" * 50)
    
    # Create database
    if not create_database():
        print("Database creation failed")
        return False
    
    # Create tables
    if not create_tables():
        print("Table creation failed")
        return False
    
    # Create sample users
    print("\nCreating sample users...")
    if not create_sample_users():
        print("Sample user creation failed")
        return False
    
    print("\nDatabase initialization completed successfully!")
    print("You can now run the application using: python run.py")
    return True

if __name__ == "__main__":
    main()
