"""
MEF Portal - Admin Blueprint
Handles admin-specific routes and functionality (HOD)
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, date
import logging

# Create blueprint
admin_bp = Blueprint('admin', __name__)

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

@admin_bp.route('/hod-dashboard')
def hod_dashboard():
    """HOD dashboard"""
    if 'username' not in session:
        flash("Please log in to access this page", "warning")
        return redirect(url_for('auth.login'))

    if session.get('role') != 'HOD':
        flash("Access denied. This page is for HOD only.", "danger")
        return redirect(url_for('auth.login'))

    try:
        User = get_user_model()
        Request = get_request_model()
        Permission = get_permission_model()

        user_id = session.get('id')
        user = User.query.get(user_id)

        # Get all requests and permissions for final approval
        pending_requests = Request.query.filter(
            (Request.status == 'Mentor Approved') | (Request.status == 'Advisor Approved')
        ).order_by(Request.created_at.desc()).all()

        pending_permissions = Permission.query.filter_by(status='Approved').order_by(Permission.created_at.desc()).all()

        # Statistics
        total_users = User.query.count()
        total_requests = Request.query.count()
        total_permissions = Permission.query.count()
        approved_requests = Request.query.filter_by(status='Approved').count()

        return render_template('hodd.html',
                             user=user,
                             pending_requests=pending_requests,
                             pending_permissions=pending_permissions,
                             total_users=total_users,
                             total_requests=total_requests,
                             total_permissions=total_permissions,
                             approved_requests=approved_requests)

    except Exception as e:
        logger.exception("HOD dashboard error")
        flash("Error loading dashboard. Please try again.", "danger")
        return redirect(url_for('auth.login'))

@admin_bp.route('/approve-request/<int:request_id>', methods=['POST'])
def approve_request(request_id):
    """Final approval of a request by HOD"""
    if 'username' not in session:
        flash("Please log in to access this page", "warning")
        return redirect(url_for('auth.login'))

    if session.get('role') != 'HOD':
        flash("Access denied. This action requires HOD privileges.", "danger")
        return redirect(url_for('auth.login'))

    try:
        Request = get_request_model()
        request_obj = Request.query.get_or_404(request_id)

        request_obj.status = 'Approved'
        request_obj.updated_at = datetime.now()

        # Save changes
        from app_modular import db
        db.session.commit()

        logger.info(f"Request {request_id} finally approved by HOD {session.get('name')}")
        flash("Request approved successfully!", "success")

    except Exception as e:
        logger.exception(f"Approve request error for ID {request_id}")
        flash("Error approving request. Please try again.", "danger")

    return redirect(url_for('admin.hod_dashboard'))

@admin_bp.route('/reject-request/<int:request_id>', methods=['POST'])
def reject_request(request_id):
    """Final rejection of a request by HOD"""
    if 'username' not in session:
        flash("Please log in to access this page", "warning")
        return redirect(url_for('auth.login'))

    if session.get('role') != 'HOD':
        flash("Access denied. This action requires HOD privileges.", "danger")
        return redirect(url_for('auth.login'))

    try:
        Request = get_request_model()
        request_obj = Request.query.get_or_404(request_id)

        request_obj.status = 'Rejected'
        request_obj.updated_at = datetime.now()

        # Save changes
        from app_modular import db
        db.session.commit()

        logger.info(f"Request {request_id} finally rejected by HOD {session.get('name')}")
        flash("Request rejected.", "info")

    except Exception as e:
        logger.exception(f"Reject request error for ID {request_id}")
        flash("Error rejecting request. Please try again.", "danger")

    return redirect(url_for('admin.hod_dashboard'))

@admin_bp.route('/approve-permission/<int:permission_id>', methods=['POST'])
def approve_permission(permission_id):
    """Final approval of a permission by HOD"""
    if 'username' not in session:
        flash("Please log in to access this page", "warning")
        return redirect(url_for('auth.login'))

    if session.get('role') != 'HOD':
        flash("Access denied. This action requires HOD privileges.", "danger")
        return redirect(url_for('auth.login'))

    try:
        Permission = get_permission_model()
        permission = Permission.query.get_or_404(permission_id)

        permission.status = 'Approved'
        permission.updated_at = datetime.now()

        # Save changes
        from app_modular import db
        db.session.commit()

        logger.info(f"Permission {permission_id} finally approved by HOD {session.get('name')}")
        flash("Permission approved successfully!", "success")

    except Exception as e:
        logger.exception(f"Approve permission error for ID {permission_id}")
        flash("Error approving permission. Please try again.", "danger")

    return redirect(url_for('admin.hod_dashboard'))

@admin_bp.route('/reject-permission/<int:permission_id>', methods=['POST'])
def reject_permission(permission_id):
    """Final rejection of a permission by HOD"""
    if 'username' not in session:
        flash("Please log in to access this page", "warning")
        return redirect(url_for('auth.login'))

    if session.get('role') != 'HOD':
        flash("Access denied. This action requires HOD privileges.", "danger")
        return redirect(url_for('auth.login'))

    try:
        Permission = get_permission_model()
        permission = Permission.query.get_or_404(permission_id)

        permission.status = 'Rejected'
        permission.updated_at = datetime.now()

        # Save changes
        from app_modular import db
        db.session.commit()

        logger.info(f"Permission {permission_id} finally rejected by HOD {session.get('name')}")
        flash("Permission rejected.", "info")

    except Exception as e:
        logger.exception(f"Reject permission error for ID {permission_id}")
        flash("Error rejecting permission. Please try again.", "danger")

    return redirect(url_for('admin.hod_dashboard'))

@admin_bp.route('/user-management')
def user_management():
    """User management page"""
    if 'username' not in session:
        flash("Please log in to access this page", "warning")
        return redirect(url_for('auth.login'))

    if session.get('role') != 'HOD':
        flash("Access denied. This page is for HOD only.", "danger")
        return redirect(url_for('auth.login'))

    try:
        User = get_user_model()
        users = User.query.order_by(User.created_at.desc()).all()

        return render_template('user_management.html', users=users)

    except Exception as e:
        logger.exception("User management error")
        flash("Error loading user management. Please try again.", "danger")
        return redirect(url_for('admin.hod_dashboard'))

@admin_bp.route('/edit-user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    """Edit user details"""
    if 'username' not in session:
        flash("Please log in to access this page", "warning")
        return redirect(url_for('auth.login'))

    if session.get('role') != 'HOD':
        flash("Access denied. This action requires HOD privileges.", "danger")
        return redirect(url_for('auth.login'))

    try:
        User = get_user_model()
        user = User.query.get_or_404(user_id)

        if request.method == 'POST':
            # Update user details
            user.name = request.form.get('name', user.name).strip()
            user.email = request.form.get('email', user.email).strip()
            user.department = request.form.get('department', user.department).strip()
            user.year = request.form.get('year', user.year)
            user.role = request.form.get('role', user.role.value)

            # Save changes
            from app_modular import db
            user.updated_at = datetime.now()
            db.session.commit()

            logger.info(f"User {user_id} updated by HOD {session.get('name')}")
            flash("User updated successfully!", "success")
            return redirect(url_for('admin.user_management'))

        return render_template('edit_user.html', user=user)

    except Exception as e:
        logger.exception(f"Edit user error for ID {user_id}")
        flash("Error updating user. Please try again.", "danger")
        return redirect(url_for('admin.user_management'))

@admin_bp.route('/reports')
def reports():
    """System-wide reports"""
    if 'username' not in session:
        flash("Please log in to access this page", "warning")
        return redirect(url_for('auth.login'))

    if session.get('role') != 'HOD':
        flash("Access denied. This page is for HOD only.", "danger")
        return redirect(url_for('auth.login'))

    try:
        User = get_user_model()
        Request = get_request_model()
        Permission = get_permission_model()

        # System statistics
        total_users = User.query.count()
        total_students = User.query.filter_by(role='Student').count()
        total_mentors = User.query.filter_by(role='Mentor').count()
        total_advisors = User.query.filter_by(role='Advisor').count()

        total_requests = Request.query.count()
        approved_requests = Request.query.filter_by(status='Approved').count()
        pending_requests = Request.query.filter_by(status='Pending').count()

        total_permissions = Permission.query.count()
        approved_permissions = Permission.query.filter_by(status='Approved').count()

        return render_template('reports.html',
                             total_users=total_users,
                             total_students=total_students,
                             total_mentors=total_mentors,
                             total_advisors=total_advisors,
                             total_requests=total_requests,
                             approved_requests=approved_requests,
                             pending_requests=pending_requests,
                             total_permissions=total_permissions,
                             approved_permissions=approved_permissions)

    except Exception as e:
        logger.exception("Reports error")
        flash("Error loading reports. Please try again.", "danger")
        return redirect(url_for('admin.hod_dashboard'))
