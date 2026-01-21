"""
MEF Portal - Mentor Blueprint
Handles mentor-specific routes and functionality
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, date
import logging

# Create blueprint
mentor_bp = Blueprint('mentor', __name__)

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

@mentor_bp.route('/dashboard')
def dashboard():
    """Mentor dashboard"""
    if 'username' not in session:
        flash("Please log in to access this page", "warning")
        return redirect(url_for('auth.login'))

    if session.get('role') not in ['Mentor', 'Advisor']:
        flash("Access denied. This page is for mentors and advisors only.", "danger")
        return redirect(url_for('auth.login'))

    try:
        User = get_user_model()
        Request = get_request_model()
        Permission = get_permission_model()

        user_id = session.get('id')
        user = User.query.get(user_id)

        # Get requests from students in the same department
        department_requests = Request.query.filter_by(department=user.department).order_by(Request.created_at.desc()).all()

        # Get permissions from students in the same department
        department_permissions = Permission.query.filter_by(department=user.department).order_by(Permission.created_at.desc()).all()

        # Statistics
        total_requests = len(department_requests)
        pending_requests = len([r for r in department_requests if r.status == 'Pending'])
        approved_requests = len([r for r in department_requests if r.status == 'Mentor Approved'])

        return render_template('mentor.html',
                             user=user,
                             requests=department_requests,
                             permissions=department_permissions,
                             total_requests=total_requests,
                             pending_requests=pending_requests,
                             approved_requests=approved_requests)

    except Exception as e:
        logger.exception("Mentor dashboard error")
        flash("Error loading dashboard. Please try again.", "danger")
        return redirect(url_for('auth.login'))

@mentor_bp.route('/review/<int:request_id>', methods=['GET', 'POST'])
def review_request(request_id):
    """Review a student request"""
    if 'username' not in session:
        flash("Please log in to access this page", "warning")
        return redirect(url_for('auth.login'))

    if session.get('role') not in ['Mentor', 'Advisor']:
        flash("Access denied. This page is for mentors and advisors only.", "danger")
        return redirect(url_for('auth.login'))

    try:
        Request = get_request_model()
        request_obj = Request.query.get_or_404(request_id)

        # Check if request is in the same department
        user_department = session.get('department')
        if request_obj.department != user_department:
            flash("Access denied. You can only review requests from your department.", "danger")
            return redirect(url_for('mentor.dashboard'))

        if request.method == 'POST':
            action = request.form.get('action')
            note = request.form.get('note', '').strip()

            if action == 'approve':
                if session.get('role') == 'Mentor':
                    request_obj.status = 'Mentor Approved'
                else:  # Advisor
                    request_obj.status = 'Advisor Approved'
                request_obj.advisor_note = note
                flash("Request approved successfully!", "success")
            elif action == 'reject':
                if session.get('role') == 'Mentor':
                    request_obj.status = 'Mentor Rejected'
                else:  # Advisor
                    request_obj.status = 'Advisor Rejected'
                request_obj.advisor_note = note
                flash("Request rejected.", "info")
            else:
                flash("Invalid action", "danger")
                return render_template('review.html', request=request_obj)

            # Save changes
            from app_modular import db
            request_obj.updated_at = datetime.now()
            db.session.commit()

            logger.info(f"Request {request_id} {action}d by {session.get('name')}")
            return redirect(url_for('mentor.dashboard'))

        return render_template('review.html', request=request_obj)

    except Exception as e:
        logger.exception(f"Review request error for ID {request_id}")
        flash("Error processing request. Please try again.", "danger")
        return redirect(url_for('mentor.dashboard'))

@mentor_bp.route('/review-permission/<int:permission_id>', methods=['GET', 'POST'])
def review_permission(permission_id):
    """Review a student permission"""
    if 'username' not in session:
        flash("Please log in to access this page", "warning")
        return redirect(url_for('auth.login'))

    if session.get('role') not in ['Mentor', 'Advisor']:
        flash("Access denied. This page is for mentors and advisors only.", "danger")
        return redirect(url_for('auth.login'))

    try:
        Permission = get_permission_model()
        permission = Permission.query.get_or_404(permission_id)

        # Check if permission is in the same department
        user_department = session.get('department')
        if permission.department != user_department:
            flash("Access denied. You can only review permissions from your department.", "danger")
            return redirect(url_for('mentor.dashboard'))

        if request.method == 'POST':
            action = request.form.get('action')

            if action == 'approve':
                permission.status = 'Approved'
                flash("Permission approved successfully!", "success")
            elif action == 'reject':
                permission.status = 'Rejected'
                flash("Permission rejected.", "info")
            else:
                flash("Invalid action", "danger")
                return render_template('review_permission.html', permission=permission)

            # Save changes
            from app_modular import db
            permission.updated_at = datetime.now()
            db.session.commit()

            logger.info(f"Permission {permission_id} {action}d by {session.get('name')}")
            return redirect(url_for('mentor.dashboard'))

        return render_template('review_permission.html', permission=permission)

    except Exception as e:
        logger.exception(f"Review permission error for ID {permission_id}")
        flash("Error processing permission. Please try again.", "danger")
        return redirect(url_for('mentor.dashboard'))

@mentor_bp.route('/students')
def view_students():
    """View students in the department"""
    if 'username' not in session:
        flash("Please log in to access this page", "warning")
        return redirect(url_for('auth.login'))

    if session.get('role') not in ['Mentor', 'Advisor']:
        flash("Access denied. This page is for mentors and advisors only.", "danger")
        return redirect(url_for('auth.login'))

    try:
        User = get_user_model()
        department = session.get('department')

        # Get all students in the department
        students = User.query.filter_by(department=department, role='Student').order_by(User.name).all()

        return render_template('students.html', students=students)

    except Exception as e:
        logger.exception("View students error")
        flash("Error loading students list. Please try again.", "danger")
        return redirect(url_for('mentor.dashboard'))

@mentor_bp.route('/reports')
def reports():
    """View department reports"""
    if 'username' not in session:
        flash("Please log in to access this page", "warning")
        return redirect(url_for('auth.login'))

    if session.get('role') not in ['Mentor', 'Advisor']:
        flash("Access denied. This page is for mentors and advisors only.", "danger")
        return redirect(url_for('auth.login'))

    try:
        Request = get_request_model()
        Permission = get_permission_model()
        department = session.get('department')

        # Get monthly statistics
        current_month = datetime.now().month
        current_year = datetime.now().year

        monthly_requests = Request.query.filter(
            Request.department == department,
            Request.created_at >= f'{current_year}-{current_month:02d}-01'
        ).count()

        monthly_permissions = Permission.query.filter(
            Permission.department == department,
            Permission.created_at >= f'{current_year}-{current_month:02d}-01'
        ).count()

        return render_template('reports.html',
                             monthly_requests=monthly_requests,
                             monthly_permissions=monthly_permissions)

    except Exception as e:
        logger.exception("Reports error")
        flash("Error loading reports. Please try again.", "danger")
        return redirect(url_for('mentor.dashboard'))
