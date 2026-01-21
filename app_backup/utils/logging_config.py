# Logging configuration for MEF Portal

import logging
import logging.handlers
import os
from datetime import datetime
from flask import has_request_context, request, session


class RequestFormatter(logging.Formatter):
    """Custom formatter that includes request context"""
    
    def format(self, record):
        # Add request context if available
        if has_request_context():
            record.url = request.url
            record.remote_addr = request.environ.get('REMOTE_ADDR', 'N/A')
            record.user = session.get('username', 'Anonymous')
        else:
            record.url = 'N/A'
            record.remote_addr = 'N/A'
            record.user = 'System'
        
        return super().format(record)


def setup_logging(app):
    """Set up comprehensive logging for the application"""
    
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(app.root_path, '..', 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Configure logging level
    log_level = logging.DEBUG if app.debug else logging.INFO
    
    # Create formatters
    detailed_formatter = RequestFormatter(
        '[%(asctime)s] %(levelname)s in %(module)s (%(user)s @ %(remote_addr)s): %(message)s'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handlers
    
    # 1. General application log
    app_handler = logging.handlers.RotatingFileHandler(
        os.path.join(logs_dir, 'mef_portal.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=10
    )
    app_handler.setFormatter(detailed_formatter)
    app_handler.setLevel(log_level)
    
    # 2. Error log
    error_handler = logging.handlers.RotatingFileHandler(
        os.path.join(logs_dir, 'errors.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    error_handler.setFormatter(detailed_formatter)
    error_handler.setLevel(logging.ERROR)
    
    # 3. Security log (authentication, authorization events)
    security_handler = logging.handlers.RotatingFileHandler(
        os.path.join(logs_dir, 'security.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=10
    )
    security_handler.setFormatter(detailed_formatter)
    security_handler.setLevel(logging.INFO)
    
    # Console handler for development
    if app.debug:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(simple_formatter)
        console_handler.setLevel(logging.DEBUG)
        app.logger.addHandler(console_handler)
    
    # Add handlers to app logger
    app.logger.addHandler(app_handler)
    app.logger.addHandler(error_handler)
    app.logger.setLevel(log_level)
    
    # Set up separate loggers for different components
    
    # Security logger
    security_logger = logging.getLogger('mef_portal.security')
    security_logger.addHandler(security_handler)
    security_logger.setLevel(logging.INFO)
    
    # Database logger
    db_logger = logging.getLogger('mef_portal.database')
    db_handler = logging.handlers.RotatingFileHandler(
        os.path.join(logs_dir, 'database.log'),
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5
    )
    db_handler.setFormatter(simple_formatter)
    db_logger.addHandler(db_handler)
    db_logger.setLevel(logging.INFO)
    
    # Request logger
    request_logger = logging.getLogger('mef_portal.requests')
    request_handler = logging.handlers.RotatingFileHandler(
        os.path.join(logs_dir, 'requests.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    request_handler.setFormatter(detailed_formatter)
    request_logger.addHandler(request_handler)
    request_logger.setLevel(logging.INFO)
    
    # Prevent duplicate logs
    app.logger.propagate = False
    security_logger.propagate = False
    db_logger.propagate = False
    request_logger.propagate = False
    
    app.logger.info("Logging system initialized")
    
    return {
        'app': app.logger,
        'security': security_logger,
        'database': db_logger,
        'requests': request_logger
    }


def log_request_info():
    """Log incoming request information"""
    request_logger = logging.getLogger('mef_portal.requests')
    request_logger.info(f"{request.method} {request.url}")


def log_user_action(action, details=None, user_id=None):
    """Log user actions for audit trail"""
    security_logger = logging.getLogger('mef_portal.security')
    user = session.get('username', 'Anonymous') if not user_id else user_id
    message = f"User '{user}' performed action: {action}"
    if details:
        message += f" - Details: {details}"
    security_logger.info(message)


def log_database_operation(operation, table=None, record_id=None, details=None):
    """Log database operations"""
    db_logger = logging.getLogger('mef_portal.database')
    message = f"Database {operation}"
    if table:
        message += f" on table '{table}'"
    if record_id:
        message += f" (ID: {record_id})"
    if details:
        message += f" - {details}"
    db_logger.info(message)


def log_security_event(event_type, details, severity='INFO'):
    """Log security-related events"""
    security_logger = logging.getLogger('mef_portal.security')
    level = getattr(logging, severity.upper(), logging.INFO)
    security_logger.log(level, f"SECURITY [{event_type}]: {details}")


# Convenience functions for common logging needs

def log_login_attempt(username, success=True, ip_address=None):
    """Log login attempts"""
    status = "SUCCESS" if success else "FAILED"
    details = f"Login attempt for user '{username}': {status}"
    if ip_address:
        details += f" from IP {ip_address}"
    log_security_event("LOGIN_ATTEMPT", details, "WARNING" if not success else "INFO")


def log_permission_request(user_id, request_type, details=None):
    """Log permission/leave requests"""
    log_user_action(f"Submitted {request_type} request", details, user_id)


def log_approval_action(approver_id, request_id, action, comments=None):
    """Log approval/rejection actions"""
    details = f"Request ID {request_id} - Action: {action}"
    if comments:
        details += f" - Comments: {comments}"
    log_user_action("Request approval action", details, approver_id)


def log_error(error, context=None):
    """Log application errors with context"""
    logger = logging.getLogger('mef_portal')
    error_msg = f"Error occurred: {str(error)}"
    if context:
        error_msg += f" - Context: {context}"
    logger.error(error_msg, exc_info=True)