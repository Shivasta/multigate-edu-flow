import re
import datetime

def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one digit"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    return True, ""

def validate_date_range(from_date_str, to_date_str):
    try:
        from_dt = datetime.datetime.strptime(from_date_str, "%Y-%m-%d").date()
        to_dt = datetime.datetime.strptime(to_date_str, "%Y-%m-%d").date()
        if to_dt < from_dt:
            return False, "To date must be the same or after From date"
        return True, ""
    except Exception:
        return False, "Invalid date format"

def validate_enum(value, allowed_values, field_name):
    if value not in allowed_values:
        return False, f"Invalid {field_name}"
    return True, ""

def normalize_department_name(department_value):
    try:
        text = str(department_value or "").strip().lower()
        return re.sub(r'^(iv[\s-]*|IV[\s-]*|v[\s-]*|V[\s-]*)', '', text)
    except Exception:
        return ""
