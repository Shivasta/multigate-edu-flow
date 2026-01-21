from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
import logging

# Initialize extensions
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

csrf = CSRFProtect()

# Initialize Rate Limiter
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    storage_options={},
    strategy="fixed-window"
)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger('mefportal')
