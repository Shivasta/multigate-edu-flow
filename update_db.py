import mysql.connector
from mysql.connector import Error
import os

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('MEF_DB_HOST', 'localhost'),
    'user': os.environ.get('MEF_DB_USER', 'ram'),
    'password': os.environ.get('MEF_DB_PASSWORD', 'ram123'),
    'database': os.environ.get('MEF_DB_NAME', 'mefportal')
}

def alter_users_table():
    """Alter the password column in the users table"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        print("Altering users table...")
        cursor.execute("ALTER TABLE users MODIFY password VARCHAR(512)")
        print(" 'password' column in 'users' table updated to VARCHAR(512).")
        
        connection.commit()
        cursor.close()
        connection.close()
        
    except Error as e:
        print(f" Error altering table: {e}")

if __name__ == "__main__":
    alter_users_table()
