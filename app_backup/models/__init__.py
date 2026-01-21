"""Models package for MEF Portal"""

def register_models():
    """Register all models with SQLAlchemy in correct order"""
    try:
        # Import models in dependency order
        from .user import User, UserRole, StudentType
        from .request import Request, RequestStatus, LeaveType  
        from .permission import Permission, PermissionType, PermissionStatus
        
        return {
            'User': User,
            'Request': Request, 
            'Permission': Permission,
        }
    except Exception as e:
        print(f"Warning: Could not import all models: {e}")
        return {}

# Safe imports for backward compatibility
try:
    from .user import User
    from .request import Request
    from .permission import Permission
    __all__ = ['User', 'Request', 'Permission', 'register_models']
except ImportError as e:
    print(f"Models import warning: {e}")
    __all__ = ['register_models']