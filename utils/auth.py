"""Authentication helpers: password hashing, session management."""

from werkzeug.security import generate_password_hash, check_password_hash
from flask import session, redirect, url_for, flash, g
from functools import wraps
from utils.database import get_db, fetch_one


def hash_password(password):
    """Hash a password using werkzeug (pbkdf2:sha256)."""
    return generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)


def verify_password(password, password_hash):
    """Verify a password against its hash."""
    return check_password_hash(password_hash, password)


def login_user(user):
    """Store user info in session after successful login."""
    session["user_id"] = user["user_id"]
    session["username"] = user["username"]
    session["full_name"] = user["full_name"]
    session["role_id"] = user["role_id"]
    session["role_name"] = user["role_name"]
    session.permanent = True


def logout_user():
    """Clear the session."""
    session.clear()


def get_current_user():
    """Get the currently logged-in user from session and DB."""
    if "user_id" not in session:
        return None
    if "user" in g:
        return g.user
    db = get_db()
    cursor = db.cursor()
    user = fetch_one(
        cursor,
        """SELECT u.*, r.role_name
           FROM users u
           JOIN roles r ON u.role_id = r.role_id
           WHERE u.user_id = :user_id AND u.user_status = 'ACTIVE'""",
        {"user_id": session["user_id"]},
    )
    cursor.close()
    if user is None:
        logout_user()
        return None
    g.user = user
    return user


def is_authenticated():
    """Check if a user is logged in."""
    return "user_id" in session


def login_required(f):
    """Decorator: redirect to login if not authenticated."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login"))
        user = get_current_user()
        if user is None:
            flash("Session expired. Please log in again.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*allowed_roles):
    """Decorator: restrict access to specific roles."""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if user["role_name"] not in allowed_roles:
                flash("You do not have permission to access this page.", "danger")
                return redirect(url_for("auth.dashboard_redirect"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_dashboard_url(role_name):
    """Return the dashboard URL for a given role."""
    dashboards = {
        "ADMIN": "admin.dashboard",
        "FACULTY": "faculty.dashboard",
        "REPRESENTATIVE": "representative.dashboard",
        "STUDENT": "student.dashboard",
    }
    return url_for(dashboards.get(role_name, "auth.login"))
