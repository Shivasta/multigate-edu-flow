import os

# Database Configuration
DB_HOST = os.environ.get('MEF_DB_HOST', 'localhost')
DB_USER = os.environ.get('MEF_DB_USER', 'ram')
DB_PASSWORD = os.environ.get('MEF_DB_PASSWORD', 'ram123')
DB_NAME = os.environ.get('MEF_DB_NAME', 'mefportal')

# Alternative database configurations (fallback options)
DB_ALTERNATIVES = [
    {'host': 'localhost', 'user': 'root', 'password': '', 'database': 'mefportal'},
    {'host': 'localhost', 'user': 'root', 'password': 'root', 'database': 'mefportal'}
]

# Flask Configuration
SECRET_KEY = os.environ.get('MEF_SECRET_KEY', 'mef-portal-secret-key-2025-secure')
FLASK_DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
FLASK_HOST = os.environ.get('FLASK_HOST', '127.0.0.1')
FLASK_PORT = int(os.environ.get('FLASK_PORT', 5000))

# Security Configuration
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not FLASK_DEBUG  # True in production, False in debug

# Application Settings
APP_NAME = "MEF Portal"
COLLEGE_NAME = "Selvam College of Technology"
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

# Email Configuration (for future features like password reset)
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@mefportal.edu')

# Pagination Settings
REQUESTS_PER_PAGE = 10
STUDENTS_PER_PAGE = 20

# File Upload Settings
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
