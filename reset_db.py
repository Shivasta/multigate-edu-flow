#!/usr/bin/env python3
"""
Database Reset Script - Drops and recreates the entire database
"""

import mysql.connector
from mysql.connector import Error
import os

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('MEF_DB_HOST', 'localhost'),
    'user': os.environ.get('MEF_DB_USER', 'ram'),
    'password': os.environ.get('MEF_DB_PASSWORD', 'ram123'),
    'autocommit': False
}

DB_NAME = os.environ.get('MEF_DB_NAME', 'mefportal')

def reset_database():
    """Drop and recreate the database"""
    try:
        print("Connecting to MySQL server...")
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        print(f"Dropping database '{DB_NAME}' if it exists...")
        cursor.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
        
        print(f"Creating fresh database '{DB_NAME}'...")
        cursor.execute(f"CREATE DATABASE {DB_NAME}")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        print(f"✓ Database '{DB_NAME}' has been reset successfully!")
        return True
        
    except Error as e:
        print(f"✗ Error resetting database: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("MEF Portal Database Reset")
    print("=" * 50)
    print("\nWARNING: This will delete ALL data in the database!")
    confirm = input("Type 'YES' to continue: ")
    
    if confirm == 'YES':
        if reset_database():
            print("\nNow run: python init_db.py")
            print("to create tables and sample users.")
    else:
        print("Reset cancelled.")
