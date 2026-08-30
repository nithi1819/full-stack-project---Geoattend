"""Authentication and password utilities."""

from werkzeug.security import generate_password_hash, check_password_hash
from flask import session, g
from utils_database import get_db
import os
import secrets
import string
from datetime import datetime, timedelta


def hash_password(password):
    """Hash a password using werkzeug."""
    return generate_password_hash(password, method='pbkdf2:sha256')


def verify_password(password_hash, password):
    """Verify a password against its hash."""
    return check_password_hash(password_hash, password)


def login_user(user_id, username, role_id, role_name):
    """Store user info in session after login."""
    session['user_id'] = user_id
    session['username'] = username
    session['role_id'] = role_id
    session['role_name'] = role_name
    session.permanent = True
    g.current_user = {
        'user_id': user_id,
        'username': username,
        'role_id': role_id,
        'role_name': role_name
    }


def logout_user():
    """Clear session on logout."""
    session.clear()
    g.pop('current_user', None)


def is_authenticated():
    """Check if user is logged in."""
    return 'user_id' in session and session.get('user_id') is not None


def get_current_user():
    """Get current user from session."""
    if not is_authenticated():
        return None
    
    return {
        'user_id': session.get('user_id'),
        'username': session.get('username'),
        'role_id': session.get('role_id'),
        'role_name': session.get('role_name')
    }


def generate_token(length=32):
    """Generate a random token."""
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


def get_dashboard_url(role_name):
    """Get the dashboard URL based on user role."""
    dashboards = {
        'Admin': '/admin/dashboard',
        'Faculty': '/faculty/dashboard',
        'Student': '/student/dashboard',
        'Representative': '/representative/dashboard',
    }
    return dashboards.get(role_name, '/')


def require_role(*allowed_roles):
    """Decorator to require specific roles."""
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not is_authenticated():
                return {'error': 'Not authenticated'}, 401
            
            user = get_current_user()
            if user and user['role_name'] in allowed_roles:
                return f(*args, **kwargs)
            
            return {'error': 'Forbidden'}, 403
        return decorated_function
    return decorator
