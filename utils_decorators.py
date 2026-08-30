"""Role-based access control decorators."""

from functools import wraps
from flask import redirect, url_for, render_template
from utils_auth import is_authenticated, get_current_user


def admin_required(f):
    """Decorator to require admin role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for('auth.login'))
        
        user = get_current_user()
        if user and user['role_name'] == 'Admin':
            return f(*args, **kwargs)
        
        return render_template('errors/403.html'), 403
    
    return decorated_function


def faculty_required(f):
    """Decorator to require faculty role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for('auth.login'))
        
        user = get_current_user()
        if user and user['role_name'] in ['Faculty', 'Admin']:
            return f(*args, **kwargs)
        
        return render_template('errors/403.html'), 403
    
    return decorated_function


def student_required(f):
    """Decorator to require student role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for('auth.login'))
        
        user = get_current_user()
        if user and user['role_name'] in ['Student', 'Admin']:
            return f(*args, **kwargs)
        
        return render_template('errors/403.html'), 403
    
    return decorated_function


def representative_required(f):
    """Decorator to require representative role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for('auth.login'))
        
        user = get_current_user()
        if user and user['role_name'] in ['Representative', 'Admin']:
            return f(*args, **kwargs)
        
        return render_template('errors/403.html'), 403
    
    return decorated_function


def login_required(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for('auth.login'))
        
        return f(*args, **kwargs)
    
    return decorated_function
