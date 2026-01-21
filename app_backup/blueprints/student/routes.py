"""
MEF Portal - Student Blueprint
Handles student-specific routes and functionality
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, date
import logging

# Create blueprint
student_bp = Blueprint('student', __name__)

# Set up logging
logger = logging.getLogger(__name__)

# Import models (will be available after SQLAlchemy setup)
def get_user_model():
    from app.models.user import User
    return User

def get_request_model():
    from app.models.request import Request
    return Request

def get_permission_model():
    from app.models.permission import Permission
    return Permission

@student_bp.route('/dashboard')
def dashboard():
    """Student dashboard"""
    if 'username' not in session:
        flash("Please log in to access this page", "warning")
        return redirect(url_for('auth.login'))

    if session.get('role') != 'Student':
        flash("Access denied. This page is for students only.", "danger")
        return redirect(url_for('auth.login'))

    try:
        User = get_user_model()
        Request = get_request_model()
        Permission = get_permission_model()

        user_id = session.get('id')
        user = User.query.get(user_id)

        # Get user's requests
        requests = Request.query.filter_by(user_id=user_id).order_by(Request.created_at.desc()).limit(10).all()

        # Get user's permissions
        permissions = Permission.query.filter_by(user_id=user_id).order_by(Permission.created_at.desc()).limit(10).all()

        # Statistics
        total_requests = Request.query.filter_by(user_id=user_id).count()
        pending_requests = Request.query.filter_by(user_id=user_id, status='Pending').count()
        approved_requests = Request.query.filter_by(user_id=user_id, status='Approved').count()

        return render_template('dashboard.html',
                             user=user,
                             requests=requests,
                             permissions=permissions,
                             total_requests=total_requests,
                             pending_requests=pending_requests,
                             approved_requests=approved_requests)

    except Exception as e:
        logger.exception("Dashboard error")
        flash("Error loading dashboard. Please try again.", "danger")
        return redirect(url_for('auth.login'))

@student_bp.route('/request', methods=['GET', 'POST'])
def request_form():
    """Student request form"""
    if 'username' not in session:
        flash("Please log in to access this page", "warning")
        return redirect(url_for('auth.login'))

    if session.get('role') != 'Student':
        flash("Access denied. This page is for students only.", "danger")
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        try:
            # Get form data
            request_type = request.form.get('request_type', '').strip()
            reason = request.form.get('reason', '').strip()
            from_date_str = request.form.get('from_date', '')
            to_date_str = request.form.get('to_date', '')

            # Validation
            if not all([request_type, reason, from_date_str, to_date_str]):
                flash("Please fill in all required fields", "danger")
                return render_template('request_form.html')

            # Parse dates
            try:
                from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
                to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash("Invalid date format", "danger")
                return render_template('request_form.html')

            if from_date > to_date:
                flash("From date cannot be after to date", "danger")
                return render_template('request_form.html')

            User = get_user_model()
            Request = get_request_model()

            user_id = session.get('id')
            user = User.query.get(user_id)

            # Create new request
            new_request = Request(
                user_id=user_id,
                type=request_type,
                reason=reason,
                from_date=from_date,
                to_date=to_date,
                student_name=user.name,
                department=user.department,
                request_type=request_type
            )

            # Save to database
            from app_modular import db
            db.session.add(new_request)
            db.session.commit()

            logger.info(f"New request created: {user.register_number} - {request_type}")
            flash("Request submitted successfully!", "success")
            return redirect(url_for('student.dashboard'))

        except Exception as e:
            logger.exception("Request submission error")
            flash("Error submitting request. Please try again.", "danger")
            return render_template('request_form.html')

    return render_template('request_form.html')

@student_bp.route('/permission', methods=['GET', 'POST'])
def permission_form():
    """Student permission form"""
    if 'username' not in session:
        flash("Please log in to access this page", "warning")
        return redirect(url_for('auth.login'))

    if session.get('role') != 'Student':
        flash("Access denied. This page is for students only.", "danger")
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        try:
            # Get form data
            custom_subject = request.form.get('custom_subject', '').strip()
            reason = request.form.get('reason', '').strip()
            from_date_str = request.form.get('from_date', '')
            to_date_str = request.form.get('to_date', '')

            # Validation
            if not all([custom_subject, reason, from_date_str, to_date_str]):
                flash("Please fill in all required fields", "danger")
                return render_template('permission_form.html')

            # Parse dates
            try:
                from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
                to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash("Invalid date format", "danger")
                return render_template('permission_form.html')

            if from_date > to_date:
                flash("From date cannot be after to date", "danger")
                return render_template('permission_form.html')

            User = get_user_model()
            Permission = get_permission_model()

            user_id = session.get('id')
            user = User.query.get(user_id)

            # Create new permission
            new_permission = Permission(
                user_id=user_id,
                student_name=user.name,
                department=user.department,
                custom_subject=custom_subject,
                reason=reason,
                from_date=from_date,
                to_date=to_date
            )

            # Save to database
            from app_modular import db
            db.session.add(new_permission)
            db.session.commit()

            logger.info(f"New permission created: {user.register_number} - {custom_subject}")
            flash("Permission request submitted successfully!", "success")
            return redirect(url_for('student.dashboard'))

        except Exception as e:
            logger.exception("Permission submission error")
            flash("Error submitting permission request. Please try again.", "danger")
            return render_template('permission_form.html')

    return render_template('permission_form.html')

@student_bp.route('/status')
def status():
    """View request status"""
    if 'username' not in session:
        flash("Please log in to access this page", "warning")
        return redirect(url_for('auth.login'))

    if session.get('role') != 'Student':
        flash("Access denied. This page is for students only.", "danger")
        return redirect(url_for('auth.login'))

    try:
        Request = get_request_model()
        Permission = get_permission_model()

        user_id = session.get('id')

        # Get all requests and permissions
        requests = Request.query.filter_by(user_id=user_id).order_by(Request.created_at.desc()).all()
        permissions = Permission.query.filter_by(user_id=user_id).order_by(Permission.created_at.desc()).all()

        return render_template('status.html', requests=requests, permissions=permissions)

    except Exception as e:
        logger.exception("Status page error")
        flash("Error loading status page. Please try again.", "danger")
        return redirect(url_for('student.dashboard'))

@student_bp.route('/profile')
def profile():
    """Student profile"""
    if 'username' not in session:
        flash("Please log in to access this page", "warning")
        return redirect(url_for('auth.login'))

    if session.get('role') != 'Student':
        flash("Access denied. This page is for students only.", "danger")
        return redirect(url_for('auth.login'))

    try:
        User = get_user_model()
        user_id = session.get('id')
        user = User.query.get(user_id)

        return render_template('profile.html', user=user)

    except Exception as e:
        logger.exception("Profile page error")
        flash("Error loading profile page. Please try again.", "danger")
        return redirect(url_for('student.dashboard'))
