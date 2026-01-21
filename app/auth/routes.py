import logging
import re
import datetime
from flask import render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
import bleach

from app.auth import bp
from app.database import get_db
from app.models import AuthUser
from app.utils import validate_password, normalize_department_name
from app.extensions import limiter

logger = logging.getLogger('mefportal')

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_TIME = 15 * 60  # 15 minutes

@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
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
                still_locked_res = cur.fetchone()
                still_locked = still_locked_res[0] if still_locked_res else False
                if still_locked:
                    flash("Account locked due to too many failed attempts. Try again later.", "danger")
                    cur.close()
                    return render_template('login.html')
    except Exception:
        pass

    try:
        cur.execute("SELECT * FROM users WHERE register_number=%s", (register_number,))
        user = cur.fetchone()
    except Exception:
        logger.exception("Database error during login")
        flash("Database error. Please try again.", "danger")
        cur.close()
        return render_template('login.html')
    cur.close()

    if user:
        # user structure: 0:id, 1:username, 2:name, 3:role, 4:password ...
        stored_password = user[4] if len(user) > 4 else None
        is_valid_password = False
        try:
            # Standard password verification
            if stored_password and isinstance(stored_password, str) and (
                stored_password.startswith('pbkdf2:') or stored_password.startswith('scrypt:')
            ):
                is_valid_password = check_password_hash(stored_password, password)
            else:
                # Plaintext fallback for dev
                allow_plaintext = current_app.config.get('DEBUG')
                if allow_plaintext and stored_password is not None and stored_password == password:
                    is_valid_password = True
                    try:
                        # Auto-migrate to hash
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

        # Maintain session keys (Legacy Support)
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
            # Note: mentor route not yet defined in new structure, but url_for will look for it
            # We need to ensure endpoint names match. 
            # If mentor route is in 'staff' blueprint, it might be 'staff.mentor'.
            # For now, let's assume we alias or create endpoints that match.
            # I will create dummy endpoints in main to handle this if needed, or implement staff BP.
            return redirect(url_for('staff.mentor')) # Anticipating 'staff' blueprint
        elif user[3] == "Advisor":
            return redirect(url_for('staff.advisor'))
        elif user[3] == "HOD":
            return redirect(url_for('staff.hod'))
        else:
            return redirect(url_for('main.dashboard'))

    else:
        flash("Invalid credentials", "danger")
        return render_template('login.html')

@bp.route('/logout')
def logout():
    try:
        logout_user()
    except Exception:
        pass
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for('auth.login'))

@bp.route('/register', methods=['GET', 'POST'])
def register():
    # Remove rate limiter for testing if needed, or keep default
    try:
        db = get_db()
        if db is None:
            flash("Database connection error", "danger")
            return render_template('register.html', mentors=[])
    except Exception:
        flash("Database connection error", "danger")
        return render_template('register.html', mentors=[])
        
    cur = db.cursor()
    try:
        # Fetch mentors
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
    except Exception:
        logger.exception("Database error fetching mentors")
        cur.close()
        flash("Error loading form", "danger")
        return render_template('register.html', mentors=[])

    if request.method == 'POST':
        name = bleach.clean(request.form['name'], strip=True)
        role = bleach.clean(request.form.get('role', 'Student'), strip=True)
        
        # Generator for IDs
        if role == 'Mentor':
            cur.execute("SELECT COUNT(*) FROM users WHERE role='Mentor'")
            count = cur.fetchone()[0]
            register_number = f"MEN{count + 1:03d}"
        elif role == 'Advisor':
            cur.execute("SELECT COUNT(*) FROM users WHERE role='Advisor'")
            count = cur.fetchone()[0]
            register_number = f"ADV{count + 1:03d}"
        elif role == 'HOD':
            cur.execute("SELECT COUNT(*) FROM users WHERE role='HOD'")
            count = cur.fetchone()[0]
            register_number = f"HOD{count + 1:03d}"
        else:
            register_number = bleach.clean(request.form['register_number'], strip=True)
        
        password = request.form['password']
        confirm = request.form['confirm_password']
        email = bleach.clean(request.form['email'], strip=True)
        dept = bleach.clean(request.form.get('department', 'General').strip().lower(), strip=True)
        dept = re.sub(r'^(iv-|v-)', '', dept)
        year = bleach.clean(request.form.get('year', '1'), strip=True)
        dob = bleach.clean(request.form['dob'], strip=True)
        
        if role == 'Student':
            student_type = bleach.clean(request.form.get('student_type', 'Day Scholar'), strip=True)
        else:
            student_type = 'Day Scholar'
            
        mentor_email = bleach.clean(request.form.get('mentor'), strip=True) if request.form.get('mentor') else None

        if password != confirm:
            flash("Passwords do not match", "danger")
            return render_template('register.html', mentors=mentors)

        valid, msg = validate_password(password)
        if not valid:
            flash(msg, "danger")
            return render_template('register.html', mentors=mentors)

        try:
            cur.execute("SELECT register_number FROM users WHERE register_number=%s", (register_number,))
            if cur.fetchone():
                flash("Registration number already exists", "danger")
                return render_template('register.html', mentors=mentors)
        except Exception:
            flash("Database error", "danger")
            return render_template('register.html', mentors=mentors)

        try:
            hashed_pw = generate_password_hash(password)
            
            # Normalize student type
            st_lower = student_type.lower()
            if 'day' in st_lower:
                student_type = 'Day Scholar'
            elif 'hostel' in st_lower:
                student_type = 'Hosteller'
            
            # Date formatting
            date_obj = datetime.datetime.strptime(dob, "%Y-%m-%d")
            formatted_dob = date_obj.strftime("%Y-%m-%d")

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
                
            cur.execute(query, params)
            db.commit()
            cur.close()
            
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
                flash("Registration successful! Please log in.", "success")
                return redirect(url_for('auth.login'))
                
        except Exception as e:
            logger.exception("Registration error")
            flash("Registration failed (DB Error). Try again.", "danger")
            db.rollback()
            cur.close()
            return render_template('register.html', mentors=mentors)

    return render_template('register.html', mentors=mentors)
