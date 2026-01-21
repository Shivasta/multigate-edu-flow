# (moved health check route below after app initialization)
import mysql.connector
from mysql.connector import Error
from flask import Flask, render_template, request, redirect, url_for, g, flash, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin  
from flask_wtf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import bleach
import datetime
import os
import sqlite3
import re
import time
import warnings
import logging

# Suppress Flask-Limiter warnings
warnings.filterwarnings("ignore", category=UserWarning, module="flask_limiter")

# --- DATABASE INITIALIZATION ---

app = Flask(__name__)

# Import the configuration from config.py
from config import SECRET_KEY, FLASK_DEBUG, REQUESTS_PER_PAGE

# Load secret config from environment for security
secret_from_env = (
    os.environ.get('MEF_SECRET_KEY')
    or os.environ.get('FLASK_SECRET_KEY')
    or os.environ.get('SECRET_KEY')
    or SECRET_KEY  # Use the SECRET_KEY from config.py as a fallback
)
# In development, fall back to a random secret to avoid crashes
app.secret_key = secret_from_env or os.urandom(32).hex()
# Ensure DEBUG is set from environment early so checks below behave correctly in development
app.config['DEBUG'] = FLASK_DEBUG or str(os.environ.get('FLASK_DEBUG', '')).lower() in ('1', 'true', 'yes')

# Insecure plaintext login toggle for development/testing only
ALLOW_PLAINTEXT_LOGIN = bool(os.environ.get('FLASK_DEBUG', 'false').lower() in ('1', 'true', 'yes'))
DEV_MASTER_PASSWORD = None

# Secure session cookie settings
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=not app.debug
)

# Session lifetime (e.g., 8 hours)
app.config['PERMANENT_SESSION_LIFETIME'] = 8 * 60 * 60

# Secret key check disabled for easier development
# if not app.debug and os.environ.get('MEF_SECRET_KEY') in (None, '') and secret_from_env == os.urandom(32).hex():
#     raise RuntimeError("SECRET_KEY must be set via MEF_SECRET_KEY in production")

# Flask-Login setup
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class AuthUser(UserMixin):
    def __init__(self, user_row):
        # user_row should be a tuple from SELECT * FROM users
        self.id = user_row[0]
        self.username = user_row[1]
        self.name = user_row[2]
        self.role = user_row[3]
        self.register_number = user_row[5]
        self.email = user_row[6]
        self.department = user_row[7]
        self.year = user_row[8]
        self.dob = user_row[9]
        self.student_type = user_row[10] if len(user_row) > 10 else 'Day Scholar'

@login_manager.user_loader
def load_user(user_id):
    try:
        db = get_db()
        if db is None:
            return None
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
        row = cur.fetchone()
        cur.close()
        if row:
            return AuthUser(row)
        return None
    except Exception:
        return None

# Initialize rate limiter with in-memory storage explicitly
from flask_limiter.util import get_remote_address
limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri="memory://",
    storage_options={},
    strategy="fixed-window"
)

# Enable CSRF protection for all forms
csrf = CSRFProtect(app)

# --- Logging ---
logging.basicConfig(
    level=logging.DEBUG if app.debug else logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger('mefportal')

# ---------- HEALTH CHECK ----------
@app.route('/healthz')
def healthz():
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        return jsonify({"status": "ok"})
    except Exception:
        logger.exception("Health check failed")
        return jsonify({"status": "error"}), 500

# Initialize database tables
def init_db():
    db = get_db()
    if db is None:
        return
        
    cur = db.cursor()
    try:
        # Create tables if they don't exist
        create_tables_if_not_exist(cur, db)
        
        # Check and add missing columns
        add_missing_columns(cur, db)
        
        db.commit()
        # Database structure updated successfully
    except Exception as e:
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
        
        # Database tables created/verified successfully
        
    except Exception as e:
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
            # Added student_type column to users table
        
        # Check if mentor_email column exists in users table
        cur.execute("SHOW COLUMNS FROM users LIKE 'mentor_email'")
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE users 
                ADD COLUMN mentor_email VARCHAR(100)
            """)
            # Added mentor_email column to users table
        
        # Check if request_type column exists in requests table
        cur.execute("SHOW COLUMNS FROM requests LIKE 'request_type'")
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE requests 
                ADD COLUMN request_type ENUM('Leave', 'Permission', 'Apology', 'Bonafide', 'OD') DEFAULT 'Leave'
            """)
            # Added request_type column to requests table
        
        # Check if advisor_note column exists in requests table
        cur.execute("SHOW COLUMNS FROM requests LIKE 'advisor_note'")
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE requests 
                ADD COLUMN advisor_note TEXT
            """)
            # Added advisor_note column to requests table
            
    except Exception as e:
        # Error adding missing columns
        raise

# Lockout policy
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_TIME = 15 * 60  # 15 minutes

# HTTPS enforcement in production
@app.before_request
def before_request():
    if not request.is_secure and not app.debug:
        url = request.url.replace('http://', 'https://', 1)
        return redirect(url, code=301)

# Password validation function
def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one digit"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    return True, ""

def validate_date_range(from_date_str, to_date_str):
    try:
        from_dt = datetime.datetime.strptime(from_date_str, "%Y-%m-%d").date()
        to_dt = datetime.datetime.strptime(to_date_str, "%Y-%m-%d").date()
        if to_dt < from_dt:
            return False, "To date must be the same or after From date"
        return True, ""
    except Exception:
        return False, "Invalid date format"

def validate_enum(value, allowed_values, field_name):
    if value not in allowed_values:
        return False, f"Invalid {field_name}"
    return True, ""

# Helper: normalize department text consistently
def normalize_department_name(department_value):
    try:
        text = str(department_value or "").strip().lower()
        return re.sub(r'^(iv[\s-]*|IV[\s-]*|v[\s-]*|V[\s-]*)', '', text)
    except Exception:
        return ""

# Save push subscription from client
@app.route('/save-subscription', methods=['POST'])
@login_required
def save_subscription():
    sub = request.get_json(force=True, silent=True) or {}
    endpoint = sub.get('endpoint')
    keys = (sub.get('keys') or {}) if isinstance(sub.get('keys'), dict) else {}
    p256dh = keys.get('p256dh')
    auth_key = keys.get('auth')
    if not endpoint:
        return jsonify({'error': 'Invalid subscription'}), 400
    try:
        db = get_db()
        if db is None:
            return jsonify({'error': 'DB error'}), 500
        cur = db.cursor()
        # Upsert-like behavior
        cur.execute("""
            SELECT id FROM push_subscriptions WHERE user_id=%s AND endpoint=%s
        """, (current_user.id, endpoint))
        existing = cur.fetchone()
        if existing:
            cur.execute(
                "UPDATE push_subscriptions SET p256dh=%s, auth=%s WHERE id=%s",
                (p256dh, auth_key, existing[0])
            )
        else:
            cur.execute(
                """
                INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth)
                VALUES (%s,%s,%s,%s)
                """,
                (current_user.id, endpoint, p256dh, auth_key)
            )
        db.commit()
        cur.close()
        return jsonify({'success': True})
    except Exception as e:
        if 'cur' in locals():
            cur.close()
        return jsonify({'error': 'DB error'}), 500

# ---------- ROOT ROUTE ----------
@app.route('/')
def root():
    return render_template('welcome.html')

DB_CONFIG = {
    'host': os.environ.get('MEF_DB_HOST', 'localhost'),
    'user': os.environ.get('MEF_DB_USER', 'ram'),
    'password': os.environ.get('MEF_DB_PASSWORD', 'ram123'),
    'database': os.environ.get('MEF_DB_NAME', 'mefportal'),
    'autocommit': False
}
DB_ALTERNATIVES = [
    {'host': 'localhost', 'user': 'root', 'password': '', 'database': 'mefportal', 'autocommit': False},
    {'host': 'localhost', 'user': 'root', 'password': 'root', 'database': 'mefportal', 'autocommit': False}
]
USING_SQLITE = False

def get_db():
    global USING_SQLITE
    db = getattr(g, '_database', None)
    if db is None:
        try:
            # Attempt MySQL connection (without debug messages)
            db = g._database = mysql.connector.connect(**DB_CONFIG)
            return db
        except Error as e:
            # Don't fall back to SQLite - force MySQL usage
            raise Exception(f"MySQL connection required but failed: {e}")
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# ---------- LOGIN ----------
@limiter.limit("5 per minute")
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    register_number = bleach.clean(request.form.get('register_number', '').strip(), strip=True)
    password = request.form.get('password', '')
    if not register_number or not password:
        flash("Registration number and password are required", "danger")
        return render_template('login.html')

    db = get_db()
    if db is None:
        flash("Database connection error", "danger")
        return render_template('login.html')
        
    cur = db.cursor()
    # Check DB-backed lockout
    try:
        cur.execute("SELECT failed_attempts, lockout_until FROM auth_lockouts WHERE register_number=%s", (register_number,))
        row = cur.fetchone()
        if row:
            attempts, lockout_until = row[0], row[1]
            if attempts >= MAX_FAILED_ATTEMPTS and lockout_until is not None:
                # If still locked
                cur.execute("SELECT NOW() < %s", (lockout_until,))
                still_locked = cur.fetchone()[0]
                if still_locked:
                    flash("Account locked due to too many failed attempts. Try again later.", "danger")
                    cur.close()
                    return render_template('login.html')
    except Exception:
        pass

    try:
        cur.execute("SELECT * FROM users WHERE register_number=%s", (register_number,))
        user = cur.fetchone()
    except Exception as e:
        logger.exception("Database error during login")
        flash("Database error. Please try again.", "danger")
        cur.close()
        return render_template('login.html')
    cur.close()

    if user:
        stored_password = user[4] if len(user) > 4 else None
        is_valid_password = False
        try:
            # Standard password verification for hashed passwords
            if stored_password and isinstance(stored_password, str) and (
                stored_password.startswith('pbkdf2:') or stored_password.startswith('scrypt:')
            ):
                is_valid_password = check_password_hash(stored_password, password)
            else:
                # Plaintext fallback allowed only in debug/dev
                if ALLOW_PLAINTEXT_LOGIN and stored_password is not None and stored_password == password:
                    is_valid_password = True
                    try:
                        new_hash = generate_password_hash(password)
                        cur = db.cursor()
                        cur.execute("UPDATE users SET password=%s, updated_at=NOW() WHERE id=%s", (new_hash, user[0]))
                        db.commit()
                        cur.close()
                    except Exception:
                        pass
                else:
                    is_valid_password = False
        except Exception:
            is_valid_password = False

        if not stored_password or not is_valid_password:
            # Update failed attempts
            try:
                cur = db.cursor()
                cur.execute("SELECT failed_attempts FROM auth_lockouts WHERE register_number=%s", (register_number,))
                row = cur.fetchone()
                if row:
                    attempts = row[0] + 1
                    if attempts >= MAX_FAILED_ATTEMPTS:
                        cur.execute(
                            "UPDATE auth_lockouts SET failed_attempts=%s, lockout_until=DATE_ADD(NOW(), INTERVAL %s SECOND) WHERE register_number=%s",
                            (attempts, LOCKOUT_TIME, register_number)
                        )
                    else:
                        cur.execute(
                            "UPDATE auth_lockouts SET failed_attempts=%s WHERE register_number=%s",
                            (attempts, register_number)
                        )
                else:
                    cur.execute(
                        "INSERT INTO auth_lockouts (register_number, failed_attempts, lockout_until) VALUES (%s,%s,NULL)",
                        (register_number, 1)
                    )
                db.commit()
                cur.close()
            except Exception:
                pass
            flash("Invalid credentials", "danger")
            return render_template('login.html')

        # Successful login: reset lockouts
        try:
            cur = db.cursor()
            cur.execute("DELETE FROM auth_lockouts WHERE register_number=%s", (register_number,))
            db.commit()
            cur.close()
        except Exception:
            pass

        # Login the user
        auth_user = AuthUser(user)
        login_user(auth_user)

        # Maintain existing session keys for downstream code
        session['id'] = user[0]
        session['username'] = user[1]
        session['name'] = user[2]
        session['role'] = user[3]
        session['register_number'] = user[5]
        session['email'] = user[6]
        session['department'] = normalize_department_name(user[7])
        session['student_type'] = user[10] if len(user) > 10 else 'Day Scholar'

        # Redirect based on role
        if user[3] == "Mentor":
            return redirect(url_for('mentor'))
        elif user[3] == "Advisor":
            return redirect(url_for('advisor'))
        elif user[3] == "HOD":
            return redirect(url_for('hod'))
        else:
            return redirect(url_for('dashboard'))

    else:
        flash("Invalid credentials", "danger")
        return render_template('login.html')

# ---------- REGISTER ----------
@app.route('/register', methods=['GET', 'POST'])
def register():
    # Remove rate limiter to allow testing
    logger.debug("Register route accessed")
    try:
        db = get_db()
        if db is None:
            logger.error("Database connection returned None")
            flash("Database connection error", "danger")
            return render_template('register.html', mentors=[])
    except Exception as e:
        logger.exception("Exception getting DB")
        flash("Database connection error", "danger")
        return render_template('register.html', mentors=[])
        
    cur = db.cursor()
    try:
        # Fetch all mentors with normalized department names for dropdown
        cur.execute("""
            SELECT name, email, 
                   UPPER(TRIM(
                       REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                           department,
                           'iv-', ''), 'IV-', ''), 'v-', ''), 'V-', ''),
                           'iv ', ''), 'IV ', ''), 'v ', ''), 'V ', '')
                   )) as normalized_department
            FROM users 
            WHERE role='Mentor' 
            ORDER BY normalized_department, name ASC
        """)
        mentors_data = cur.fetchall()
        mentors = [{'name': m[0], 'email': m[1], 'department': m[2]} for m in mentors_data]
    except Exception as e:
        logger.exception("Database error fetching mentors")
        cur.close()
        flash("Error loading registration form", "danger")
        return render_template('register.html', mentors=[])

    if request.method == 'POST':
        logger.debug("POST request received for registration")
        
        name = bleach.clean(request.form['name'], strip=True)
        role = bleach.clean(request.form.get('role', 'Student'), strip=True)
        
        # Generate register number based on role
        if role == 'Mentor':
            # Find the next available MEN number
            cur.execute("SELECT COUNT(*) FROM users WHERE role='Mentor'")
            mentor_count = cur.fetchone()[0]
            register_number = f"MEN{mentor_count + 1:03d}"
        elif role == 'Advisor':
            # Find the next available ADV number
            cur.execute("SELECT COUNT(*) FROM users WHERE role='Advisor'")
            advisor_count = cur.fetchone()[0]
            register_number = f"ADV{advisor_count + 1:03d}"
        elif role == 'HOD':
            # Find the next available HOD number
            cur.execute("SELECT COUNT(*) FROM users WHERE role='HOD'")
            hod_count = cur.fetchone()[0]
            register_number = f"HOD{hod_count + 1:03d}"
        else:
            # For Student role, use the provided register number
            register_number = bleach.clean(request.form['register_number'], strip=True)
        
        password = request.form['password']
        confirm = request.form['confirm_password']
        email = bleach.clean(request.form['email'], strip=True)
        dept = bleach.clean(request.form.get('department', 'General').strip().lower(), strip=True)
        dept = re.sub(r'^(iv-|v-)', '', dept)  # Normalize prefix
        year = bleach.clean(request.form.get('year', '1'), strip=True)
        dob = bleach.clean(request.form['dob'], strip=True)
        
        # Only get student_type for Student role
        if role == 'Student':
            student_type = bleach.clean(request.form.get('student_type', 'Day Scholar'), strip=True)
        else:
            student_type = 'Day Scholar'  # Default value for non-students
            
        mentor_email = bleach.clean(request.form.get('mentor'), strip=True) if request.form.get('mentor') else None

        logger.debug(f"Parsed registration data for {name} role={role}")

        if password != confirm:
            flash("Passwords do not match", "danger")
            return render_template('register.html', mentors=mentors)

        # Validate password complexity
        valid, msg = validate_password(password)
        if not valid:
            flash(msg, "danger")
            return render_template('register.html', mentors=mentors)

        try:
            cur.execute("SELECT register_number FROM users WHERE register_number=%s", (register_number,))
            if cur.fetchone():
                flash("Registration number already exists", "danger")
                return render_template('register.html', mentors=mentors)
        except Exception as e:
            logger.exception("Database error during registration check")
            flash("Database error. Please try again.", "danger")
            return render_template('register.html', mentors=mentors)

        # Add mentor_email to DB if you have a column, else skip for now
        try:
            # Hash password before storing
            hashed_pw = generate_password_hash(password)
            logger.debug(f"Attempting to register user: {name}, role: {role}")
            
            # Force student_type to match enum values exactly
            logger.debug(f"Original student_type value: '{student_type}'")
            
            # Normalize student_type to match the exact ENUM values
            if student_type.lower() == 'day scholar' or student_type.lower() == 'dayscholar':
                student_type = 'Day Scholar'
            elif student_type.lower() == 'hosteller' or student_type.lower() == 'hostel':
                student_type = 'Hosteller'
                
            logger.debug(f"Normalized student_type value: '{student_type}'")
            
            # Only validate student_type for Student role
            if role == 'Student' and student_type not in ['Day Scholar', 'Hosteller']:
                logger.error(f"Invalid student_type: '{student_type}'")
                flash("Invalid student type selected", "danger")
                return render_template('register.html', mentors=mentors)
                
            # Ensure data types match database column requirements
            logger.debug(f"Register number: '{register_number}', Role: '{role}'")
            
            try:
                # Format the date correctly for MySQL
                from datetime import datetime
                date_obj = datetime.strptime(dob, "%Y-%m-%d")
                formatted_dob = date_obj.strftime("%Y-%m-%d")
                logger.debug(f"Formatted DOB: {formatted_dob}")
            except Exception as date_error:
                logger.error(f"Date parsing error: {date_error}")
                flash("Invalid date format", "danger")
                return render_template('register.html', mentors=mentors)
                
            # Build the query
            query = ""
            params = []
            
            if mentor_email:
                query = """
                    INSERT INTO users (username, name, register_number, password, email, role, department, year, dob, student_type, mentor_email)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """
                params = [register_number, name, register_number, hashed_pw, email, role, dept, year, formatted_dob, student_type, mentor_email]
            else:
                query = """
                    INSERT INTO users (username, name, register_number, password, email, role, department, year, dob, student_type)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """
                params = [register_number, name, register_number, hashed_pw, email, role, dept, year, formatted_dob, student_type]
                
            logger.debug("Running user insert query")
            
            cur.execute(query, params)
            db.commit()
            
            logger.info(f"New user registered: {name} ({role}) dept={dept}")
            cur.close()
            
            # For non-student roles, show the success page with register number
            if role in ['Mentor', 'Advisor', 'HOD']:
                user_data = {
                    'name': name,
                    'register_number': register_number,
                    'email': email,
                    'department': dept.upper(),
                    'role': role
                }
                return render_template('registration_success.html', user_data=user_data)
            else:
                # For students, redirect to login with flash message
                flash("Registration successful! Please log in.", "success")
                return redirect(url_for('login'))
        except Exception as e:
            logger.exception("Database error during user registration")
            
            # Try to determine the specific error
            error_message = str(e)
            if "Duplicate entry" in error_message:
                if "email" in error_message:
                    flash("Email address already registered", "danger")
                elif "register_number" in error_message:
                    flash("Registration number already in use", "danger")
                else:
                    flash("A user with this information already exists", "danger")
            elif "foreign key constraint" in error_message.lower():
                flash("Invalid reference to another record", "danger")
            elif "data too long" in error_message.lower():
                flash("One of your entries is too long", "danger")
            elif "doesn't have a default value" in error_message:
                flash("A required field is missing", "danger")
            elif "cannot be null" in error_message.lower():
                flash("A required field is missing", "danger")
            elif "incorrect date value" in error_message.lower():
                flash("The date format is incorrect", "danger")
            elif "incorrect value" in error_message.lower() and "for column" in error_message.lower() and "student_type" in error_message.lower():
                flash("Invalid student type selected", "danger")
            else:
                flash("Registration failed. Please try again.", "danger")
                
            db.rollback()
            cur.close()
            return render_template('register.html', mentors=mentors)

    return render_template('register.html', mentors=mentors)

# ---------- DASHBOARD (Date Filter) ----------
@app.route('/dashboard')
@login_required
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    user_id = session['id']
    selected_date_str = request.args.get('date')
    db = get_db()
    cur = db.cursor()

    selected_date = None
    if selected_date_str:
        try:
            selected_date = datetime.datetime.strptime(selected_date_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid date format", "danger")
            selected_date = None

    try:
        # Get requests based on filter
        if selected_date:
            # Filter by specific date
            cur.execute("""
                SELECT id, user_id, type, reason, from_date, to_date, status,
                       COALESCE(DATE_FORMAT(updated_at, '%Y-%m-%d %H:%i'), DATE_FORMAT(created_at, '%Y-%m-%d %H:%i')) as updation,
                       student_name, department
                FROM requests 
                WHERE user_id=%s AND DATE(created_at) = %s
                ORDER BY created_at DESC
            """, (user_id, selected_date))
        else:
            # Show all requests if no date filter
            cur.execute("""
                SELECT id, user_id, type, reason, from_date, to_date, status,
                       COALESCE(DATE_FORMAT(updated_at, '%Y-%m-%d %H:%i'), DATE_FORMAT(created_at, '%Y-%m-%d %H:%i')) as updation,
                       student_name, department
                FROM requests 
                WHERE user_id=%s
                ORDER BY created_at DESC
                LIMIT 5
            """, (user_id,))
        
        requests_data = cur.fetchall()
        
        # Calculate statistics for all user requests
        cur.execute("SELECT COUNT(*) FROM requests WHERE user_id=%s", (user_id,))
        total_requests = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM requests WHERE user_id=%s AND status='Pending'", (user_id,))
        pending_requests = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM requests WHERE user_id=%s AND status='Approved'", (user_id,))
        approved_requests = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM requests WHERE user_id=%s AND status='Rejected'", (user_id,))
        rejected_requests = cur.fetchone()[0] or 0

        # Get recent updates (all recent requests - submitted, approved, rejected)
        cur.execute("""
            SELECT id, type, status, 
                   COALESCE(updated_at, created_at) as activity_time, 
                   student_name FROM requests 
            WHERE user_id=%s 
            ORDER BY COALESCE(updated_at, created_at) DESC LIMIT 4
        """, (user_id,))
        recent_updates = cur.fetchall()
        
        # If no requests exist, create some sample data for testing
        if total_requests == 0:
            pass

        cur.close()
    except Exception as e:
        # Database error in dashboard
        cur.close()
        flash("Error loading dashboard data", "danger")
        return render_template('dashboard_professional.html', 
                               requests=[], 
                               selected_date=selected_date, 
                               stats={'total_requests': 0, 'pending_requests': 0, 'approved_requests': 0, 'rejected_requests': 0},
                               recent_updates=[])

    stats = {
        'total_requests': total_requests,
        'pending_requests': pending_requests,
        'approved_requests': approved_requests,
        'rejected_requests': rejected_requests
    }

    return render_template('dashboard_professional.html', 
                           requests=requests_data, 
                           selected_date=selected_date, 
                           stats=stats,
                           recent_updates=recent_updates)

# ---------- UNIFIED REQUEST FORM ----------
@app.route('/unified_request', methods=['GET', 'POST'])
@login_required
@limiter.limit("20 per hour")
def unified_request():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        request_type = (request.form.get('request_type') or 'leave').strip().lower()
        ok, msg = validate_enum(request_type, ['leave', 'permission', 'apology', 'bonafide', 'od'], 'request type')
        if not ok:
            flash(msg, 'danger')
            return render_template('unified_request_form.html')

        student_name = bleach.clean((request.form.get('student_name') or '').strip(), strip=True)[:100]
        department = normalize_department_name(request.form.get('department'))
        if not student_name or not department:
            flash('Student name and department are required', 'danger')
            return render_template('unified_request_form.html')

        try:
            db = get_db()
            if db is None:
                flash("Database connection error", "danger")
                return render_template('unified_request_form.html')
                
            cur = db.cursor()
            
            if request_type == 'leave':
                # Handle leave request
                req_type = bleach.clean((request.form.get('type') or 'Leave').strip(), strip=True)[:50]
                reason = bleach.clean((request.form.get('reason') or '').strip(), strip=True)[:1000]
                from_date = (request.form.get('from_date') or '').strip()
                to_date = (request.form.get('to_date') or '').strip()
                if not all([req_type, reason, from_date, to_date]):
                    flash('All leave fields are required', 'danger')
                    return render_template('unified_request_form.html')
                ok, msg = validate_date_range(from_date, to_date)
                if not ok:
                    flash(msg, 'danger')
                    return render_template('unified_request_form.html')
                
                cur.execute("""
                    INSERT INTO requests (user_id, type, reason, from_date, to_date, status, student_name, department, request_type)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (session['id'], req_type, reason, from_date, to_date, 'Pending', student_name, department, 'Leave'))
                
            elif request_type == 'apology':
                # Handle apology request
                apology_date = (request.form.get('apology_date') or '').strip()
                apology_reason = bleach.clean((request.form.get('apology_reason') or '').strip(), strip=True)[:1000]
                if not apology_date or not apology_reason:
                    flash('Apology date and reason are required', 'danger')
                    return render_template('unified_request_form.html')
                
                cur.execute("""
                    INSERT INTO requests (user_id, type, reason, from_date, to_date, status, student_name, department, request_type)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (session['id'], 'Apology', apology_reason, apology_date, apology_date, 'Pending', student_name, department, 'Apology'))
                
            elif request_type == 'bonafide':
                # Handle bonafide request
                purpose = bleach.clean((request.form.get('bonafide_purpose') or '').strip(), strip=True)[:100]
                details = bleach.clean((request.form.get('bonafide_details') or '').strip(), strip=True)[:500]
                if not purpose:
                    flash('Purpose is required for bonafide', 'danger')
                    return render_template('unified_request_form.html')
                reason = f"Bonafide Certificate - Purpose: {purpose}. Details: {details}"
                
                cur.execute("""
                    INSERT INTO requests (user_id, type, reason, from_date, to_date, status, student_name, department, request_type)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (session['id'], 'Bonafide', reason, datetime.date.today(), datetime.date.today(), 'Pending', student_name, department, 'Bonafide'))
                
            elif request_type == 'permission':
                # Handle permission request
                custom_subject = bleach.clean((request.form.get('custom_subject') or '').strip(), strip=True)[:200]
                reason = bleach.clean((request.form.get('permission_reason') or '').strip(), strip=True)[:1000]
                from_date = (request.form.get('permission_from_date') or '').strip()
                to_date = (request.form.get('permission_to_date') or '').strip()
                if not all([custom_subject, reason, from_date, to_date]):
                    flash('All permission fields are required', 'danger')
                    return render_template('unified_request_form.html')
                ok, msg = validate_date_range(from_date, to_date)
                if not ok:
                    flash(msg, 'danger')
                    return render_template('unified_request_form.html')
                
                cur.execute("""
                    INSERT INTO requests (user_id, type, reason, from_date, to_date, status, student_name, department, request_type)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (session['id'], 'Permission', reason, from_date, to_date, 'Pending', student_name, department, 'Permission'))
                
            elif request_type == 'od':
                # Handle on duty request
                event = bleach.clean((request.form.get('od_event') or '').strip(), strip=True)[:200]
                organization = bleach.clean((request.form.get('od_organization') or '').strip(), strip=True)[:200]
                from_date = (request.form.get('od_from_date') or '').strip()
                to_date = (request.form.get('od_to_date') or '').strip()
                od_reason = bleach.clean((request.form.get('od_reason') or '').strip(), strip=True)[:1000]
                if not all([event, organization, from_date, to_date, od_reason]):
                    flash('All on-duty fields are required', 'danger')
                    return render_template('unified_request_form.html')
                ok, msg = validate_date_range(from_date, to_date)
                if not ok:
                    flash(msg, 'danger')
                    return render_template('unified_request_form.html')
                reason = f"On Duty - Event: {event}, Organization: {organization}. Details: {od_reason}"
                
                cur.execute("""
                    INSERT INTO requests (user_id, type, reason, from_date, to_date, status, student_name, department, request_type)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (session['id'], 'On Duty', reason, from_date, to_date, 'Pending', student_name, department, 'OD'))
            
            db.commit()
            cur.close()
            flash(f"{request_type.title()} request submitted successfully!", "success")
            return redirect(url_for('status'))
            
        except Exception as e:
            logger.exception(f"Error submitting {request_type} request")
            flash(f"Error submitting {request_type} request. Please try again.", "danger")
            return render_template('unified_request_form.html')

    return render_template('unified_request_form.html')

# ---------- STATUS ----------
@app.route('/permission_form', methods=['GET', 'POST'])
@login_required
@limiter.limit("20 per hour")
def permission_form():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        student_name = bleach.clean((request.form.get('student_name') or '').strip(), strip=True)[:100]
        department = (request.form.get('department') or '').strip().lower()
        custom_subject = bleach.clean((request.form.get('customSubject') or '').strip(), strip=True)[:200]
        reason = bleach.clean((request.form.get('reason') or '').strip(), strip=True)[:1000]
        from_date = (request.form.get('from_date') or '').strip()
        to_date = (request.form.get('to_date') or '').strip()

        if not all([student_name, department, custom_subject, reason, from_date, to_date]):
            flash("All fields are required", "danger")
            return render_template('permission_form.html')
        ok, msg = validate_date_range(from_date, to_date)
        if not ok:
            flash(msg, 'danger')
            return render_template('permission_form.html')

        try:
            db = get_db()
            if db is None:
                flash("Database connection error", "danger")
                return render_template('permission_form.html')
                
            cur = db.cursor()
            cur.execute('''
                INSERT INTO permissions (user_id, student_name, department, custom_subject, reason, from_date, to_date, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                session['id'], student_name, department, custom_subject, reason, from_date, to_date, 'Pending'
            ))
            db.commit()
            cur.close()
            flash("Permission request submitted successfully!", "success")
            return redirect(url_for('dashboard'))
        except Exception as e:
            logger.exception("Database error in permission form")
            if 'cur' in locals():
                cur.close()
            flash("Error submitting permission request", "danger")
            return render_template('permission_form.html')

    return render_template('permission_form.html')

# ---------- STATUS ----------
@app.route('/status')
@login_required
def status():
    if 'username' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cur = db.cursor()
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = REQUESTS_PER_PAGE
    offset = (page - 1) * per_page
    
    # Get filter parameters
    date_filter = request.args.get('date', '')
    status_filter = request.args.get('status', '')
    search_query = request.args.get('search', '')
    
    # Build WHERE clause
    where_conditions = ["user_id = %s"]
    params = [session['id']]
    
    # Add date filter
    if date_filter:
        where_conditions.append("DATE(created_at) = %s")
        params.append(date_filter)
    
    # Add status filter
    if status_filter:
        where_conditions.append("status = %s")
        params.append(status_filter)
    
    # Add search filter
    if search_query:
        where_conditions.append("(type LIKE %s OR reason LIKE %s)")
        search_param = f"%{search_query}%"
        params.extend([search_param, search_param])
    
    where_clause = " AND ".join(where_conditions)
    
    try:
        # Get total count for pagination
        count_query = f"SELECT COUNT(*) FROM requests WHERE {where_clause}"
        cur.execute(count_query, params)
        total_requests = cur.fetchone()[0]
        
        # Calculate pagination info
        total_pages = (total_requests + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages
        
        # Get requests with pagination
        main_query = f"""
            SELECT id, user_id, type, reason, from_date, to_date, status,
                   COALESCE(DATE_FORMAT(updated_at, '%Y-%m-%d %H:%i'), DATE_FORMAT(created_at, '%Y-%m-%d %H:%i')) as updation,
                   student_name, department, created_at
            FROM requests 
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        cur.execute(main_query, params)
        requests_list = cur.fetchall()
        cur.close()
    except Exception as e:
        # Database error in status
        cur.close()
        flash("Error loading status data", "danger")
        return render_template('status.html', 
                               requests=[], 
                               pagination={'page': 1, 'per_page': per_page, 'total': 0, 'total_pages': 0, 'has_prev': False, 'has_next': False, 'prev_num': None, 'next_num': None},
                               date_filter=date_filter,
                               status_filter=status_filter,
                               search_query=search_query)
    
    # Pagination info
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total_requests,
        'total_pages': total_pages,
        'has_prev': has_prev,
        'has_next': has_next,
        'prev_num': page - 1 if has_prev else None,
        'next_num': page + 1 if has_next else None
    }
    
    return render_template('status.html', 
                           requests=requests_list, 
                           pagination=pagination,
                           date_filter=date_filter,
                           status_filter=status_filter,
                           search_query=search_query)

# ---------- DOWNLOAD STATUS (PDF) ----------
@app.route('/download_status')
@login_required
def download_status():
    if 'username' not in session:
        return redirect(url_for('login'))

    # Get filter parameters from query string
    date_filter = request.args.get('date', '')
    status_filter = request.args.get('status', '')
    search_query = request.args.get('search', '')
    
    try:
        db = get_db()
        if db is None:
            flash("Database connection error", "danger")
            return redirect(url_for('status'))
            
        cur = db.cursor()
        
        # Build WHERE clause (same as status route)
        where_conditions = ["user_id = %s"]
        params = [session['id']]
        
        # Add date filter
        if date_filter:
            where_conditions.append("DATE(created_at) = %s")
            params.append(date_filter)
        
        # Add status filter
        if status_filter:
            where_conditions.append("status = %s")
            params.append(status_filter)
        
        # Add search filter
        if search_query:
            where_conditions.append("(type LIKE %s OR reason LIKE %s)")
            search_param = f"%{search_query}%"
            params.extend([search_param, search_param])
        
        where_clause = " AND ".join(where_conditions)
        
        # Get all filtered requests
        query = f"""
            SELECT id, user_id, type, reason, from_date, to_date, status,
                   COALESCE(DATE_FORMAT(updated_at, '%Y-%m-%d %H:%i'), DATE_FORMAT(created_at, '%Y-%m-%d %H:%i')) as updation,
                   student_name, department, created_at
            FROM requests 
            WHERE {where_clause}
            ORDER BY created_at DESC
        """
        cur.execute(query, params)
        requests_list = cur.fetchall()
        cur.close()
        
        if not requests_list:
            flash("No requests found to download", "info")
            return redirect(url_for('status'))
        
        # Generate PDF using FPDF
        try:
            from fpdf import FPDF
            
            # Create PDF instance
            pdf = FPDF()
            
            for request_data in requests_list:
                pdf.add_page()
                
                # Set font
                pdf.set_font("Arial", size=12)
                
                # Add header
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(200, 10, txt="REQUEST STATUS REPORT", ln=1, align='C')
                pdf.ln(5)
                
                # Add application details
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(200, 10, txt="REQUEST DETAILS", ln=1, align='L')
                pdf.ln(5)
                
                pdf.set_font("Arial", size=12)
                details = [
                    ("Application ID", f"LEV-2025-{request_data[0]}"),
                    ("Student Name", request_data[8] or session.get('name', 'N/A')),
                    ("Department", request_data[9] or session.get('department', 'N/A')),
                    ("Request Type", request_data[2]),
                    ("Duration", f"{request_data[4]} to {request_data[5]}"),
                    ("Status", request_data[6]),
                    ("Reason", request_data[3]),
                    ("Submitted Date", str(request_data[10]) if len(request_data) > 10 else "N/A"),
                    ("Last Updated", request_data[7] if len(request_data) > 7 else "N/A")
                ]
                
                for label, value in details:
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(50, 8, txt=f"{label}:", ln=0)
                    pdf.set_font("Arial", size=12)
                    pdf.cell(0, 8, txt=str(value), ln=1)
                
                pdf.ln(10)
                
                # Add separator for multiple requests
                if requests_list.index(request_data) < len(requests_list) - 1:
                    pdf.set_draw_color(200, 200, 200)
                    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                    pdf.ln(10)
            
            # Add summary page
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(200, 10, txt="REQUEST SUMMARY", ln=1, align='C')
            pdf.ln(10)
            
            pdf.set_font("Arial", size=12)
            summary_stats = [
                ("Total Requests", len(requests_list)),
                ("Approved Requests", len([r for r in requests_list if r[6] == 'Approved'])),
                ("Pending Requests", len([r for r in requests_list if r[6] == 'Pending'])),
                ("Rejected Requests", len([r for r in requests_list if r[6] == 'Rejected'])),
                ("Mentor Approved", len([r for r in requests_list if r[6] == 'Mentor Approved'])),
                ("Advisor Approved", len([r for r in requests_list if r[6] == 'Advisor Approved']))
            ]
            
            for label, value in summary_stats:
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(60, 8, txt=f"{label}:", ln=0)
                pdf.set_font("Arial", size=12)
                pdf.cell(0, 8, txt=str(value), ln=1)
            
            pdf.ln(10)
            
            # Add footer
            pdf.set_font("Arial", 'I', 10)
            pdf.cell(0, 10, txt=f"Generated by MEF Portal - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=1, align='C')
            
            # Generate PDF content
            pdf_output = pdf.output(dest='S').encode('latin1')
            
            # Create response with PDF
            from flask import Response
            response = Response(pdf_output)
            response.headers['Content-Type'] = 'application/pdf'
            
            # Create filename with filters
            filename_parts = ["requests_report"]
            if date_filter:
                filename_parts.append(f"date_{date_filter}")
            if status_filter:
                filename_parts.append(f"status_{status_filter.lower()}")
            if search_query:
                filename_parts.append(f"search_{search_query[:10]}")
            
            filename = f"{'_'.join(filename_parts)}.pdf"
            response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response
            
        except ImportError:
            flash("PDF generation library not available", "danger")
            return redirect(url_for('status'))
        except Exception as e:
            logger.exception("PDF generation error")
            flash("Error generating PDF report", "danger")
            return redirect(url_for('status'))
            
    except Exception as e:
        logger.exception("Database error in download status")
        if 'cur' in locals():
            cur.close()
        flash("Error loading requests data", "danger")
        return redirect(url_for('status'))

# ---------- APPROVED REQUEST VIEW ----------
@app.route('/approved/<int:req_id>')
@login_required
def approved(req_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    try:
        db = get_db()
        if db is None:
            flash("Database connection error", "danger")
            return redirect(url_for('dashboard'))
            
        cur = db.cursor()
        cur.execute("""
            SELECT id, user_id, type, reason, from_date, to_date, status,
                   COALESCE(DATE_FORMAT(updated_at, '%Y-%m-%d %H:%i'), DATE_FORMAT(created_at, '%Y-%m-%d %H:%i')) as updation,
                   student_name, department, created_at
            FROM requests 
            WHERE id=%s AND user_id=%s
        """, (req_id, session['id']))
        request_data = cur.fetchone()
        cur.close()
    except Exception as e:
        logger.exception("Database error in approved view")
        if 'cur' in locals():
            cur.close()
        flash("Error loading request details", "danger")
        return redirect(url_for('dashboard'))
    
    if not request_data:
        flash("Request not found", "danger")
        return redirect(url_for('dashboard'))
    
    if request_data[6] != 'Approved':  # Status is at index 6
        flash("Request is not approved", "warning")
        return redirect(url_for('dashboard'))
    
    return render_template('approved.html', request_data=request_data)

# ---------- DOWNLOAD APPROVED REQUEST PDF ----------
@app.route('/download_approved/<int:req_id>')
@login_required
def download_single_approved(req_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    try:
        db = get_db()
        if db is None:
            flash("Database connection error", "danger")
            return redirect(url_for('dashboard'))
            
        cur = db.cursor()
        cur.execute("SELECT * FROM requests WHERE id=%s AND user_id=%s AND status='Approved'", (req_id, session['id']))
        request_data = cur.fetchone()
        cur.close()
    except Exception as e:
        logger.exception("Database error in download approved")
        if 'cur' in locals():
            cur.close()
        flash("Error loading approved request", "danger")
        return redirect(url_for('dashboard'))
    
    if not request_data:
        flash("Approved request not found", "danger")
        return redirect(url_for('dashboard'))
    
    # Generate PDF using FPDF
    try:
        from fpdf import FPDF
        
        # Create PDF instance
        pdf = FPDF()
        pdf.add_page()
        
        # Set font
        pdf.set_font("Arial", size=12)
        
        # Add header
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt="LEAVE APPLICATION - APPROVED", ln=1, align='C')
        pdf.ln(10)
        
        # Add application details
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(200, 10, txt="APPLICATION DETAILS", ln=1, align='L')
        pdf.ln(5)
        
        pdf.set_font("Arial", size=12)
        details = [
            ("Application ID", f"LEV-2025-{request_data[0]}"),
            ("Student Name", request_data[8] or session.get('name', 'N/A')),
            ("Department", request_data[9] or session.get('department', 'N/A')),
            ("Leave Type", request_data[2]),
            ("Duration", f"{request_data[4]} to {request_data[5]}"),
            ("Status", request_data[6]),
            ("Reason", request_data[3]),
            ("Submitted Date", str(request_data[10]) if len(request_data) > 10 else "N/A")
        ]
        
        for label, value in details:
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(50, 8, txt=f"{label}:", ln=0)
            pdf.set_font("Arial", size=12)
            pdf.cell(0, 8, txt=str(value), ln=1)
        
        pdf.ln(10)
        
        # Add approval section
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(200, 10, txt="APPROVAL INFORMATION", ln=1, align='L')
        pdf.ln(5)
        
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 8, txt=f"This application has been officially approved by the Head of Department. The request was processed and approved on {request_data[7] if len(request_data) > 7 else 'N/A'}.")
        
        pdf.ln(10)
        
        # Add footer
        pdf.set_font("Arial", 'I', 10)
        pdf.cell(0, 10, txt="Generated by MEF Portal - Selvam College of Technology", ln=1, align='C')
        
        # Generate PDF content
        pdf_output = pdf.output(dest='S').encode('latin1')
        
        # Create response with PDF
        from flask import Response
        response = Response(pdf_output)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="approved_leave_{request_data[0]}.pdf"'
        
        return response
        
    except ImportError:
        flash("PDF generation library not available", "danger")
        return redirect(url_for('status'))
    except Exception as e:
        logger.exception("PDF generation error")
        flash("Error generating PDF", "danger")
        return redirect(url_for('status'))

# ---------- MENTOR ----------
@app.route('/mentor')
@login_required
def mentor():
    if 'username' not in session or session.get('role') != 'Mentor':
        return redirect(url_for('login'))

    db = get_db()
    if db is None:
        flash("Database connection error", "danger")
        return render_template('mentor.html', requests=[])
        
    cur = db.cursor()
    
    # Debug: print all mentor session values
    logger.debug(f"Mentor session: {dict(session)}")
    
    # Debug: print all pending requests and compare departments
    try:
        cur.execute("SELECT id, student_name, department, status FROM requests WHERE status='Pending'")
        pending_reqs = cur.fetchall()
        mentor_dept = normalize_department_name(session.get('department'))
    except Exception as e:
        logger.exception("Database error in mentor debug queries")
        cur.close()
        flash("Error loading mentor dashboard", "danger")
        return render_template('mentor.html', requests=[])
    logger.debug('All Pending requests:')
    for req in pending_reqs:
        db_dept = str(req[2]).strip().lower()
        db_dept_norm = re.sub(r'^(iv[\s-]*|IV[\s-]*|v[\s-]*|V[\s-]*)', '', db_dept)
        logger.debug(f"  Request ID: {req[0]}, Dept: '{req[2]}' (db), Normalized: '{db_dept_norm}' vs '{mentor_dept}' (mentor session)")
    logger.debug(f"Mentor session department: {mentor_dept}")
    
    # Debug: Print the actual query parameters for mentor
    logger.debug(f"Mentor query department parameter: '{mentor_dept}'")
    
    try:
        # Case-insensitive, trimmed department match
        # Normalize department in SQL: remove 'iv-' and 'v-' prefix, lower, trim
        # Normalize department in SQL: remove iv/v/IV/V with dash or space
        cur.execute("""
            SELECT id, user_id, type, reason, from_date, to_date, status,
                   COALESCE(DATE_FORMAT(updated_at, '%Y-%m-%d %H:%i'), DATE_FORMAT(created_at, '%Y-%m-%d %H:%i')) as updation,
                   student_name, department, created_at
            FROM requests
            WHERE 
                (
                    LOWER(TRIM(
                        REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                            department,
                            'iv-', ''), 'IV-', ''), 'v-', ''), 'V-', ''),
                            'iv ', ''), 'IV ', ''), 'v ', ''), 'V ', '')
                    ))
                ) = %s
                AND status='Pending'
            ORDER BY created_at DESC
        """, (mentor_dept,))
        requests_data = cur.fetchall()
        
        logger.debug(f"Fetched requests for mentor: {len(requests_data)} rows")
        
        cur.close()
        return render_template('mentor.html', requests=requests_data)
    except Exception as e:
        logger.exception("Database error in mentor dashboard")
        cur.close()
        flash("Error loading mentor dashboard", "danger")
        return render_template('mentor.html', requests=[])

@app.route('/mentor_action', methods=['POST'])
@login_required
@limiter.limit("30 per hour")
def mentor_action():
    if 'username' not in session or session.get('role') != 'Mentor':
        return redirect(url_for('login'))

    req_id = request.form['request_id']
    action = request.form['action']
    status_value = 'Mentor Approved' if action == 'Approve' else 'Mentor Rejected'

    try:
        db = get_db()
        if db is None:
            flash("Database connection error", "danger")
            return redirect(url_for('mentor'))
            
        cur = db.cursor()
        cur.execute("UPDATE requests SET status=%s, updated_at=NOW() WHERE id=%s", (status_value, req_id))
        db.commit()
        cur.close()
        flash(f"Request #{req_id} {status_value}", "success")
        return redirect(url_for('mentor'))
    except Exception as e:
        # Database error in mentor action
        if 'cur' in locals():
            cur.close()
        flash("Error updating request status", "danger")
        return redirect(url_for('mentor'))

# ---------- LOGOUT ----------
@app.route('/logout')
def logout():
    try:
        logout_user()
    except Exception:
        pass
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for('login'))

# ---------- ADVISOR DASHBOARD ----------
@app.route('/advisor')
@login_required
def advisor():
    if 'username' not in session or session.get('role') != 'Advisor':
        return redirect(url_for('login'))

    db = get_db()
    if db is None:
        flash("Database connection error", "danger")
        return render_template('advisor.html', requests=[], students_list=[])
        
    cur = db.cursor()
    
    # Get advisor's normalized department
    advisor_dept = normalize_department_name(session.get('department'))

    try:
        # Fetch all students in advisor's department (normalize department in SQL)
        # Get all mentors in this department
        cur.execute("""
            SELECT name FROM users
            WHERE role='Mentor' AND (
                LOWER(TRIM(
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                        department,
                        'iv-', ''), 'IV-', ''), 'v-', ''), 'V-', ''),
                        'iv ', ''), 'IV ', ''), 'v ', ''), 'V ', '')
                ))
            ) = %s
            ORDER BY name ASC
        """, (advisor_dept,))
        mentors_in_dept = [row[0] for row in cur.fetchall()]

        cur.execute("""
            SELECT name, register_number, year, email FROM users
            WHERE role='Student' AND (
                LOWER(TRIM(
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                        department,
                        'iv-', ''), 'IV-', ''), 'v-', ''), 'V-', ''),
                        'iv ', ''), 'IV ', ''), 'v ', ''), 'V ', '')
                ))
            ) = %s
            ORDER BY name ASC
        """, (advisor_dept,))
        students_list = cur.fetchall()

        # Fetch mentor approved requests for advisor's department
        cur.execute("""
            SELECT id, user_id, type, reason, from_date, to_date, status,
                   COALESCE(DATE_FORMAT(updated_at, '%Y-%m-%d %H:%i'), DATE_FORMAT(created_at, '%Y-%m-%d %H:%i')) as updation,
                   student_name, department, created_at
            FROM requests
            WHERE 
                (
                    LOWER(TRIM(
                        REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                            department,
                            'iv-', ''), 'IV-', ''), 'v-', ''), 'V-', ''),
                            'iv ', ''), 'IV ', ''), 'v ', ''), 'V ', '')
                    ))
                ) = %s
                AND status='Mentor Approved'
            ORDER BY created_at DESC
        """, (advisor_dept,))
        requests_data = cur.fetchall()

        cur.close()
        return render_template('advisor.html', requests=requests_data, students_list=students_list, mentors_in_dept=mentors_in_dept)
    except Exception as e:
        logger.exception("Database error in advisor dashboard")
        cur.close()
        flash("Error loading advisor dashboard", "danger")
        return render_template('advisor.html', requests=[], students_list=[], mentors_in_dept=[])

# ---------- ADVISOR ACTION ----------
@app.route('/advisor_action', methods=['POST'])
@login_required
@limiter.limit("30 per hour")
def advisor_action():
    if 'username' not in session or session.get('role') != 'Advisor':
        return redirect(url_for('login'))

    req_id = request.form['request_id']
    action = request.form['action']
    advisor_note = request.form.get('advisor_note', '').strip()
    status_value = 'Advisor Approved' if action == 'Approve' else 'Advisor Rejected'

    try:
        db = get_db()
        if db is None:
            flash("Database connection error", "danger")
            return redirect(url_for('advisor'))
            
        cur = db.cursor()
        if action == 'Approve':
            cur.execute("UPDATE requests SET status=%s, updated_at=NOW(), advisor_note=%s WHERE id=%s", (status_value, advisor_note, req_id))
        else:
            cur.execute("UPDATE requests SET status=%s, updated_at=NOW(), advisor_note=%s WHERE id=%s", (status_value, advisor_note, req_id))
        db.commit()
        cur.close()
        flash(f"Request #{req_id} {status_value}", "success")
        return redirect(url_for('advisor'))
    except Exception as e:
        # Database error in advisor action
        if 'cur' in locals():
            cur.close()
        flash("Error updating request status", "danger")
        return redirect(url_for('advisor'))

# ---------- HOD DASHBOARD ----------
@app.route('/hod')
@login_required
def hod():
    if 'username' not in session or session.get('role') != 'HOD':
        return redirect(url_for('login'))

    db = get_db()
    if db is None:
        flash("Database connection error", "danger")
        return render_template('hodd.html', requests=[], mentors=[])
        
    cur = db.cursor()
    
    # Get HOD's normalized department
    hod_dept = normalize_department_name(session.get('department'))

    try:
        # Fetch all requests for HOD's department
        cur.execute("""
            SELECT r.id, r.user_id, r.type, r.reason, r.from_date, r.to_date, r.status,
                   COALESCE(DATE_FORMAT(r.updated_at, '%Y-%m-%d %H:%i'), DATE_FORMAT(r.created_at, '%Y-%m-%d %H:%i')) as updation,
                   r.student_name, r.department, r.created_at, r.advisor_note
            FROM requests r
            WHERE 
                (
                    LOWER(TRIM(
                        REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                            r.department,
                            'iv-', ''), 'IV-', ''), 'v-', ''), 'V-', ''),
                            'iv ', ''), 'IV ', ''), 'v ', ''), 'V ', '')
                    ))
                ) = %s
            ORDER BY r.created_at DESC
        """, (hod_dept,))
        requests_data = cur.fetchall()

        # Fetch all mentors in HOD's department
        cur.execute("""
            SELECT name, email FROM users
            WHERE role='Mentor' AND (
                LOWER(TRIM(
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                        department,
                        'iv-', ''), 'IV-', ''), 'v-', ''), 'V-', ''),
                        'iv ', ''), 'IV ', ''), 'v ', ''), 'V ', '')
                ))
            ) = %s
            ORDER BY name ASC
        """, (hod_dept,))
        mentors_data = cur.fetchall()
        mentors = [{'name': m[0], 'email': m[1]} for m in mentors_data]

        cur.close()

        return render_template('hodd.html', requests=requests_data, mentors=mentors)
    except Exception as e:
        logger.exception("Database error in HOD dashboard")
        cur.close()
        flash("Error loading HOD dashboard", "danger")
        return render_template('hodd.html', requests=[], mentors=[])

# ---------- HOD ACTION ----------
@app.route('/hod_action', methods=['POST'])
@login_required
@limiter.limit("30 per hour")
def hod_action():
    if 'username' not in session or session.get('role') != 'HOD':
        return redirect(url_for('login'))

    req_id = request.form['request_id']
    action = request.form['action']
    status_value = 'Approved' if action == 'Approve' else 'Rejected'

    try:
        db = get_db()
        if db is None:
            flash("Database connection error", "danger")
            return redirect(url_for('hod'))
            
        cur = db.cursor()
        cur.execute("UPDATE requests SET status=%s, updated_at=NOW() WHERE id=%s", (status_value, req_id))
        db.commit()
        cur.close()
        flash(f"Request #{req_id} {status_value}", "success")
        return redirect(url_for('hod'))
    except Exception as e:
        # Database error in HOD action
        if 'cur' in locals():
            cur.close()
        flash("Error updating request status", "danger")
        return redirect(url_for('hod'))

# ---------- USER MANAGEMENT ----------
@app.route('/user_management')
@login_required
def user_management():
    if 'username' not in session or session.get('role') not in ['HOD', 'Admin']:
        flash("Access denied. Only HODs and Admins can access user management.", "danger")
        return redirect(url_for('dashboard'))

    db = get_db()
    if db is None:
        flash("Database connection error", "danger")
        return render_template('user_management.html', users=[], departments=[])
        
    cur = db.cursor()
    
    # Get filter parameters
    dept_filter = request.args.get('department', '')
    role_filter = request.args.get('role', '')
    search_query = request.args.get('search', '')
    
    # Get user's department if they're HOD (limit to their department)
    user_dept = normalize_department_name(session.get('department'))
    
    try:
        # Build WHERE clause
        where_conditions = []
        params = []
        
        # If HOD, limit to their department only
        if session.get('role') == 'HOD':
            where_conditions.append("""
                LOWER(TRIM(
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                        department,
                        'iv-', ''), 'IV-', ''), 'v-', ''), 'V-', ''),
                        'iv ', ''), 'IV ', ''), 'v ', ''), 'V ', '')
                )) = %s
            """)
            params.append(user_dept)
        
        # Add department filter
        if dept_filter:
            where_conditions.append("""
                LOWER(TRIM(
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                        department,
                        'iv-', ''), 'IV-', ''), 'v-', ''), 'V-', ''),
                        'iv ', ''), 'IV ', ''), 'v ', ''), 'V ', '')
                )) = %s
            """)
            params.append(normalize_department_name(dept_filter))
        
        # Add role filter
        if role_filter:
            where_conditions.append("role = %s")
            params.append(role_filter)
        
        # Add search filter
        if search_query:
            where_conditions.append("(name LIKE %s OR register_number LIKE %s OR email LIKE %s)")
            search_param = f"%{search_query}%"
            params.extend([search_param, search_param, search_param])
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Get users
        query = f"""
            SELECT id, username, name, role, register_number, email, department, year, dob, student_type, mentor_email
            FROM users 
            WHERE {where_clause}
            ORDER BY role, department, name
        """
        cur.execute(query, params)
        users_data = cur.fetchall()
        
        # Get all departments for filter dropdown
        cur.execute("SELECT DISTINCT department FROM users WHERE department IS NOT NULL ORDER BY department")
        departments = [row[0] for row in cur.fetchall()]
        
        cur.close()
        
        return render_template('user_management.html', 
                               users=users_data, 
                               departments=departments,
                               current_dept_filter=dept_filter,
                               current_role_filter=role_filter,
                               current_search=search_query)
        
    except Exception as e:
        logger.exception("Database error in user management")
        cur.close()
        flash("Error loading user management data", "danger")
        return render_template('user_management.html', users=[], departments=[])

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if 'username' not in session or session.get('role') not in ['HOD', 'Admin']:
        flash("Access denied. Only HODs and Admins can edit users.", "danger")
        return redirect(url_for('dashboard'))

    db = get_db()
    if db is None:
        flash("Database connection error", "danger")
        return redirect(url_for('user_management'))
        
    cur = db.cursor()
    
    try:
        # Get user details
        cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
        user = cur.fetchone()
        
        if not user:
            flash("User not found", "danger")
            return redirect(url_for('user_management'))
        
        # Check if HOD can edit this user (same department)
        if session.get('role') == 'HOD':
            user_dept = normalize_department_name(session.get('department'))
            target_dept = str(user[7]).strip().lower()
            target_dept = re.sub(r'^(iv[\s-]*|IV[\s-]*|v[\s-]*|V[\s-]*)', '', target_dept)
            
            if user_dept != target_dept:
                flash("You can only edit users from your department", "danger")
                return redirect(url_for('user_management'))
        
        if request.method == 'POST':
            # Update user details
            name = bleach.clean(request.form['name'], strip=True)
            email = bleach.clean(request.form['email'], strip=True)
            role = bleach.clean(request.form['role'], strip=True)
            department = bleach.clean(request.form['department'], strip=True)
            year = bleach.clean(request.form.get('year', ''), strip=True)
            student_type = bleach.clean(request.form.get('student_type', 'Day Scholar'), strip=True)
            mentor_email = bleach.clean(request.form.get('mentor_email', ''), strip=True) or None
            
            # Validate inputs
            if not all([name, email, role, department]):
                flash("Name, email, role, and department are required", "danger")
                return render_template('edit_user.html', user=user)
            
            try:
                cur.execute("""
                    UPDATE users 
                    SET name=%s, email=%s, role=%s, department=%s, year=%s, student_type=%s, mentor_email=%s, updated_at=NOW()
                    WHERE id=%s
                """, (name, email, role, department, year, student_type, mentor_email, user_id))
                db.commit()
                flash(f"User {name} updated successfully", "success")
                return redirect(url_for('user_management'))
            except Exception as e:
                logger.exception("Error updating user")
                flash("Error updating user", "danger")
                return render_template('edit_user.html', user=user)
        
        cur.close()
        return render_template('edit_user.html', user=user)
        
    except Exception as e:
        logger.exception("Database error in edit user")
        if 'cur' in locals():
            cur.close()
        flash("Error loading user details", "danger")
        return redirect(url_for('user_management'))

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
@limiter.limit("10 per hour")
def delete_user(user_id):
    if 'username' not in session or session.get('role') not in ['HOD', 'Admin']:
        flash("Access denied. Only HODs and Admins can delete users.", "danger")
        return redirect(url_for('user_management'))

    db = get_db()
    if db is None:
        flash("Database connection error", "danger")
        return redirect(url_for('user_management'))
        
    cur = db.cursor()
    
    try:
        # Get user details first
        cur.execute("SELECT name, role, department FROM users WHERE id=%s", (user_id,))
        user = cur.fetchone()
        
        if not user:
            flash("User not found", "danger")
            return redirect(url_for('user_management'))
        
        # Check if HOD can delete this user (same department)
        if session.get('role') == 'HOD':
            user_dept = normalize_department_name(session.get('department'))
            target_dept = str(user[2]).strip().lower()
            target_dept = re.sub(r'^(iv[\s-]*|IV[\s-]*|v[\s-]*|V[\s-]*)', '', target_dept)
            
            if user_dept != target_dept:
                flash("You can only delete users from your department", "danger")
                return redirect(url_for('user_management'))
        
        # Prevent deletion of self
        if user_id == session.get('id'):
            flash("You cannot delete your own account", "danger")
            return redirect(url_for('user_management'))
        
        # Delete user
        cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
        db.commit()
        cur.close()
        
        flash(f"User {user[0]} deleted successfully", "success")
        return redirect(url_for('user_management'))
        
    except Exception as e:
        logger.exception("Database error in delete user")
        if 'cur' in locals():
            cur.close()
        flash("Error deleting user", "danger")
        return redirect(url_for('user_management'))

if __name__ == "__main__":
    # Initialize database with new columns
    with app.app_context():
        init_db()
    
    # Enable mobile testing - accessible from any device on the network
    # host='0.0.0.0' allows connections from other devices (like your phone)
    # Make sure your firewall allows port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)
