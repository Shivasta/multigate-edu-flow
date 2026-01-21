"""
MEF Portal - Authentication Blueprint
Clean implementation for immediate use
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, date
import re
import logging

# Create blueprint
auth_bp = Blueprint('auth', __name__)

# Set up logging
logger = logging.getLogger(__name__)

# Import models (will be available after SQLAlchemy setup)
def get_user_model():
    from app.models.user import User
    return User

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login with basic security"""
    if request.method == 'GET':
        return render_template('login.html')

    # Get form data
    register_number = request.form.get('register_number', '').strip()
    password = request.form.get('password', '')

    if not register_number or not password:
        flash("Please provide both register number and password", "danger")
        return render_template('login.html')

    try:
        User = get_user_model()
        user = User.query.filter_by(register_number=register_number).first()

        if user and user.check_password(password):
            # Successful login
            session.clear()
            session['id'] = user.id
            session['username'] = user.username
            session['name'] = user.name
            session['register_number'] = user.register_number
            session['email'] = user.email
            session['role'] = user.role.value
            session['department'] = user.department
            session['year'] = user.year
            session.permanent = True

            logger.info(f"User {user.register_number} logged in successfully")
            flash(f"Welcome back, {user.name}!", "success")

            # Redirect based on role
            if user.role.value == 'HOD':
                return redirect(url_for('admin.hod_dashboard'))
            elif user.role.value == 'Mentor':
                return redirect(url_for('mentor.dashboard'))
            elif user.role.value == 'Advisor':
                return redirect(url_for('mentor.dashboard'))
            elif user.role.value == 'Student':
                return redirect(url_for('student.dashboard'))
            else:
                return redirect(url_for('student.dashboard'))
        else:
            logger.warning(f"Failed login attempt for register number: {register_number}")
            flash("Invalid register number or password", "danger")

    except Exception as e:
        logger.exception(f"Login error for {register_number}")
        flash("Login system error. Please try again.", "danger")

    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name', '').strip()
            register_number = request.form.get('register_number', '').strip()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
            email = request.form.get('email', '').strip()
            role = request.form.get('role', 'Student').strip()
            department = request.form.get('department', '').strip()
            year = request.form.get('year', '')
            dob_str = request.form.get('dob', '')
            student_type = request.form.get('student_type', 'Day Scholar').strip()
            mentor_email = request.form.get('mentor', '').strip() or None

            # Validation
            if not all([name, register_number, password, email, department, dob_str]):
                flash("Please fill in all required fields", "danger")
                return render_template('register.html')

            if password != confirm_password:
                flash("Passwords do not match", "danger")
                return render_template('register.html')

            if len(password) < 8:
                flash("Password must be at least 8 characters long", "danger")
                return render_template('register.html')

            # Parse date
            try:
                dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
            except ValueError:
                flash("Invalid date format", "danger")
                return render_template('register.html')

            User = get_user_model()

            # Check if user already exists
            if User.query.filter_by(register_number=register_number).first():
                flash("Register number already exists", "danger")
                return render_template('register.html')

            if User.query.filter_by(email=email).first():
                flash("Email already registered", "danger")
                return render_template('register.html')

            # Create new user
            from app.models.user import UserRole, StudentType

            new_user = User(
                username=register_number,
                name=name,
                register_number=register_number,
                email=email,
                role=UserRole(role),
                department=department.lower(),
                year=year,
                dob=dob,
                student_type=StudentType(student_type) if student_type else StudentType.DAY_SCHOLAR,
                mentor_email=mentor_email
            )

            new_user.set_password(password)

            # Save to database
            from app_modular import db
            db.session.add(new_user)
            db.session.commit()

            logger.info(f"New user registered: {register_number} - {name}")
            flash("Registration successful! You can now log in.", "success")
            return redirect(url_for('auth.login'))

        except Exception as e:
            logger.exception("Registration error")
            flash("Registration failed. Please try again.", "danger")
            return render_template('register.html')

    return render_template('register.html')

@auth_bp.route('/logout')
def logout():
    """User logout"""
    user_name = session.get('name', 'User')
    session.clear()
    flash(f"Goodbye, {user_name}! You have been logged out.", "info")
    return redirect(url_for('auth.login'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Password reset request"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()

        if not email:
            flash("Please provide your email address", "danger")
            return render_template('forgot_password.html')

        try:
            User = get_user_model()
            user = User.query.filter_by(email=email).first()

            if user:
                # TODO: Implement email sending with reset token
                flash("Password reset instructions have been sent to your email", "success")
                logger.info(f"Password reset requested for email: {email}")
            else:
                # Don't reveal if email exists or not for security
                flash("Password reset instructions have been sent to your email", "success")
                logger.warning(f"Password reset requested for non-existent email: {email}")

            return redirect(url_for('auth.login'))

        except Exception as e:
            logger.exception("Password reset error")
            flash("Error processing password reset. Please try again.", "danger")

    return render_template('forgot_password.html')

# Utility functions for login requirement
def login_required(f):
    """Decorator to require login"""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash("Please log in to access this page", "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    """Decorator to require specific roles"""
    from functools import wraps

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session:
                flash("Please log in to access this page", "warning")
                return redirect(url_for('auth.login'))

            user_role = session.get('role')
            if user_role not in roles:
                flash("Access denied. Insufficient permissions.", "danger")
                return redirect(url_for('student.dashboard'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator
