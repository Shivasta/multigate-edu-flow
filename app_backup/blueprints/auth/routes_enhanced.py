"""
MEF Portal - Enhanced Authentication Blueprint
Vibe-to-Pro Implementation: Enterprise security with developer-friendly syntax
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, date
import re
import logging

# Import our vibe-to-pro security framework
from app.security.vibe_security import (
    secure_endpoint,
    validate_input,
    password_manager,
    input_validator,
    audit_logger,
    create_secure_session,
    secure_logout,
    rate_limiter,
    is_user_authenticated,
    get_current_user_data
)

# Create blueprint
auth_bp = Blueprint('auth', __name__)

# Set up logging
logger = logging.getLogger(__name__)

# Import models (will be available after SQLAlchemy setup)
def get_user_model():
    from app.models.user import User
    return User

@auth_bp.route('/login', methods=['GET', 'POST'])
@secure_endpoint(require_auth=False, rate_limit=5)  # 5 attempts per minute per IP
def login():
    """
    Enhanced user login with enterprise security
    
    Vibe-to-Pro: Same simple logic, but now bulletproof
    """
    if request.method == 'GET':
        return render_template('login.html')
    
    # Get and validate inputs (secure by default)
    register_number = input_validator.sanitize_user_input(request.form.get('register_number', ''))
    password = request.form.get('password', '')
    
    if not register_number or not password:
        flash("Please provide both register number and password", "danger")
        return render_template('login.html')
    
    # Rate limiting per user (prevent brute force attacks)
    user_key = f"login_user_{register_number}"
    if rate_limiter.is_rate_limited(user_key, limit=5, window_minutes=15):
        audit_logger.log_security_event(
            'LOGIN_RATE_LIMITED',
            f'Login rate limited for user: {register_number}',
            'WARNING',
            username=register_number
        )
        flash("Too many failed attempts. Please wait 15 minutes.", "danger")
        return render_template('login.html')
    
    try:
        User = get_user_model()
        user = User.query.filter_by(register_number=register_number).first()
        
        if user and user.check_password(password):
            # SUCCESS: Create secure session (enterprise-grade)
            session_token = create_secure_session({
                'id': user.id,
                'username': user.username,
                'name': user.name,
                'register_number': user.register_number,
                'email': user.email,
                'role': user.role.value,
                'department': user.department,
                'year': user.year
            })
            
            # Log successful authentication
            audit_logger.log_authentication(register_number, True, request.remote_addr)
            
            flash(f"Welcome back, {user.name}!", "success")
            
            # Redirect based on role (keep existing logic)
            if user.role.value == 'HOD':
                return redirect(url_for('admin.hod_dashboard'))
            elif user.role.value == 'Mentor':
                return redirect(url_for('mentor.dashboard'))
            elif user.role.value == 'Advisor':
                return redirect(url_for('mentor.dashboard'))  # Advisors use mentor dashboard
            elif user.role.value == 'Student':
                return redirect(url_for('student.dashboard'))
            else:
                return redirect(url_for('student.dashboard'))  # Default fallback
        
        else:
            # FAILURE: Log and provide feedback
            audit_logger.log_authentication(register_number, False, request.remote_addr, {
                'reason': 'invalid_credentials'
            })
            
            # Show remaining attempts
            attempts = rate_limiter.get_attempt_count(user_key, window_minutes=15)
            remaining = 5 - attempts
            
            if remaining > 0:
                flash(f"Invalid credentials. {remaining} attempts remaining.", "danger")
            else:
                flash("Account temporarily locked. Please wait 15 minutes.", "danger")
            
            return render_template('login.html')
    
    except Exception as e:
        # System error - log and fail gracefully
        audit_logger.log_security_event(
            'LOGIN_SYSTEM_ERROR',
            f'System error during login: {str(e)}',
            'ERROR',
            username=register_number
        )
        logger.error(f"Login system error: {e}")
        flash("System error. Please try again later.", "danger")
        return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
@secure_endpoint(require_auth=False, rate_limit=3)  # Prevent spam registration
@validate_input(
    email=input_validator.validate_email,
    name=lambda x: len(x.strip()) >= 2
)
def register():
    """
    Enhanced registration with input validation and security
    
    Vibe-to-Pro: Simple form handling with professional validation
    """
    if request.method == 'GET':
        return render_template('register.html')
    
    # Get sanitized form data
    form_data = {
        'register_number': input_validator.sanitize_user_input(request.form.get('register_number', '')),
        'name': input_validator.sanitize_user_input(request.form.get('name', '')),
        'email': request.form.get('email', '').strip().lower(),
        'department': input_validator.sanitize_user_input(request.form.get('department', '')),
        'year': request.form.get('year', ''),
        'role': request.form.get('role', 'Student'),
        'dob': request.form.get('dob', ''),
        'student_type': request.form.get('student_type', 'Day Scholar'),
        'mentor_email': request.form.get('mentor', '').strip() or None,
        'password': request.form.get('password', ''),
        'confirm_password': request.form.get('confirm_password', '')
    }
    
    # Validation with clear error messages
    errors = []
    
    # Required fields
    required_fields = ['register_number', 'name', 'email', 'department', 'year', 'dob', 'password']
    for field in required_fields:
        if not form_data[field]:
            errors.append(f"{field.replace('_', ' ').title()} is required")
    
    # Password validation
    if form_data['password'] != form_data['confirm_password']:
        errors.append("Passwords don't match")
    
    password_valid, password_errors = password_manager.validate_strength(form_data['password'])
    if not password_valid:
        errors.extend(password_errors)
    
    # Date validation
    try:
        dob = datetime.strptime(form_data['dob'], '%Y-%m-%d').date()
    except ValueError:
        errors.append("Invalid date format")
    
    # Check for existing user
    User = get_user_model()
    if User.query.filter_by(register_number=form_data['register_number']).first():
        errors.append("Register number already exists")
    
    if User.query.filter_by(email=form_data['email']).first():
        errors.append("Email already registered")
    
    if errors:
        for error in errors:
            flash(error, "danger")
        return render_template('register.html')
    
    try:
        # Create new user (your existing model logic)
        from app.models.user import UserRole, StudentType
        
        new_user = User(
            register_number=form_data['register_number'],
            username=form_data['register_number'],  # Use register_number as username
            name=form_data['name'],
            email=form_data['email'],
            role=UserRole(form_data['role']),
            department=form_data['department'].lower(),
            year=int(form_data['year']),
            dob=dob,
            student_type=StudentType(form_data['student_type']) if form_data['student_type'] else StudentType.DAY_SCHOLAR,
            mentor_email=form_data['mentor_email']
        )
        
        # Set secure password
        new_user.set_password(form_data['password'])
        
        # Save to database
        from app_modular import db
        db.session.add(new_user)
        db.session.commit()
        
        # Log successful registration
        audit_logger.log_security_event(
            'USER_REGISTERED',
            f'New user registered: {form_data["register_number"]}',
            'INFO',
            username=form_data['register_number'],
            email=form_data['email']
        )
        
        logger.info(f"New user registered: {form_data['register_number']} - {form_data['name']}")
        flash("Registration successful! Please login.", "success")
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        # Log error and roll back
        audit_logger.log_security_event(
            'REGISTRATION_ERROR',
            f'Registration failed: {str(e)}',
            'ERROR',
            username=form_data.get('register_number', 'unknown')
        )
        
        db.session.rollback()
        logger.exception("Registration error")
        flash("Registration failed. Please try again.", "danger")
        return render_template('register.html')

@auth_bp.route('/logout')
@secure_endpoint(require_auth=True)
def logout():
    """Enhanced logout with audit trail"""
    user_name = session.get('name', 'User')
    secure_logout()
    flash(f"Goodbye, {user_name}! You have been logged out.", "info")
    return redirect(url_for('auth.login'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@secure_endpoint(require_auth=False, rate_limit=2)  # Very limited for security
def forgot_password():
    """Password reset request with secure token generation"""
    
    if request.method == 'GET':
        return render_template('forgot_password.html')
    
    email = request.form.get('email', '').strip().lower()
    
    if not input_validator.validate_email(email):
        flash("Please enter a valid email address.", "danger")
        return render_template('forgot_password.html')
    
    try:
        User = get_user_model()
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate secure reset token
            reset_token = password_manager.generate_secure_token(32)
            
            # Store token (in real app, save to database with expiration)
            # For now, we'll just log it (in production, send via email)
            
            audit_logger.log_security_event(
                'PASSWORD_RESET_REQUESTED',
                f'Password reset requested for user',
                'INFO',
                username=user.username,
                email=email
            )
            
            logger.info(f"Password reset requested for: {email}")
            # TODO: Send email with reset link
            # send_password_reset_email(user.email, reset_token)
            
        # Always show same message (security: don't reveal if email exists)
        flash("If this email is registered, you'll receive reset instructions.", "info")
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        audit_logger.log_security_event(
            'PASSWORD_RESET_ERROR',
            f'Error in password reset: {str(e)}',
            'ERROR'
        )
        logger.exception("Password reset error")
        flash("Unable to process request. Please try again later.", "danger")
        return render_template('forgot_password.html')

@auth_bp.route('/profile')
@secure_endpoint(require_auth=True, roles=['Student', 'Mentor', 'Admin', 'HOD'])
def profile():
    """
    User profile page - demonstrates role-based access
    
    Vibe-to-Pro: One decorator handles all security
    """
    user_data = get_current_user_data()
    
    # Log profile access
    audit_logger.log_security_event(
        'PROFILE_ACCESSED',
        f'User accessed profile page',
        'INFO',
        username=user_data['username']
    )
    
    return render_template('profile.html', user=user_data)

# Utility functions for backward compatibility
def login_required(f):
    """
    Decorator to require login (backward compatibility)
    
    Note: Use @secure_endpoint instead for new code
    """
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_user_authenticated():
            flash("Please log in to access this page", "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    """
    Decorator to require specific roles (backward compatibility)
    
    Note: Use @secure_endpoint(roles=...) instead for new code
    """
    from functools import wraps
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not is_user_authenticated():
                flash("Please log in to access this page", "warning")
                return redirect(url_for('auth.login'))
            
            user_role = session.get('role')
            if user_role not in roles:
                audit_logger.log_security_event(
                    'UNAUTHORIZED_ACCESS',
                    f'User {session.get("username")} attempted to access {request.endpoint} without proper role',
                    'WARNING'
                )
                flash("Access denied. Insufficient permissions.", "danger")
                return redirect(url_for('student.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator