from flask_login import UserMixin
from app.database import get_db

class AuthUser(UserMixin):
    def __init__(self, user_row):
        # user_row should be a tuple from SELECT * FROM users
        # 0:id, 1:username, 2:name, 3:role, 4:password, 5:reg_num, 
        # 6:email, 7:dept, 8:year, 9:dob, 10:student_type, 11:mentor_email
        self.id = user_row[0]
        self.username = user_row[1]
        self.name = user_row[2]
        self.role = user_row[3]
        # self.password = user_row[4] # Don't store password in session user object usually
        self.register_number = user_row[5]
        self.email = user_row[6]
        self.department = user_row[7]
        self.year = user_row[8]
        self.dob = user_row[9]
        self.student_type = user_row[10] if len(user_row) > 10 else 'Day Scholar'
        
    def get_id(self):
        return str(self.id)

def load_user(user_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        if user:
            return AuthUser(user)
    except Exception:
        return None
    return None
