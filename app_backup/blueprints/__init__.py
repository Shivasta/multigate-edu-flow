"""Blueprints package for MEF Portal"""

from .auth import auth_bp
from .student import student_bp
from .mentor import mentor_bp  
from .admin import admin_bp

__all__ = ['auth_bp', 'student_bp', 'mentor_bp', 'admin_bp']