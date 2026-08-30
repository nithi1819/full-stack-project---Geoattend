"""Role-based access control decorators."""

from functools import wraps
from flask import session, redirect, url_for, flash, abort
from utils.auth import get_current_user, is_authenticated


def admin_required(f):
    """Restrict to ADMIN role only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for("auth.login"))
        user = get_current_user()
        if not user or user["role_name"] != "ADMIN":
            abort(403)
        return f(*args, **kwargs)
    return decorated


def faculty_required(f):
    """Restrict to FACULTY role only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for("auth.login"))
        user = get_current_user()
        if not user or user["role_name"] != "FACULTY":
            abort(403)
        return f(*args, **kwargs)
    return decorated


def representative_required(f):
    """Restrict to REPRESENTATIVE role only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for("auth.login"))
        user = get_current_user()
        if not user or user["role_name"] != "REPRESENTATIVE":
            abort(403)
        return f(*args, **kwargs)
    return decorated


def student_required(f):
    """Restrict to STUDENT role only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for("auth.login"))
        user = get_current_user()
        if not user or user["role_name"] != "STUDENT":
            abort(403)
        return f(*args, **kwargs)
    return decorated


def admin_or_faculty_required(f):
    """Restrict to ADMIN or FACULTY roles."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for("auth.login"))
        user = get_current_user()
        if not user or user["role_name"] not in ("ADMIN", "FACULTY"):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def admin_faculty_rep_required(f):
    """Restrict to ADMIN, FACULTY, or REPRESENTATIVE roles."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for("auth.login"))
        user = get_current_user()
        if not user or user["role_name"] not in ("ADMIN", "FACULTY", "REPRESENTATIVE"):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def non_admin_required(f):
    """Restrict to any role except ADMIN (for room booking, etc)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for("auth.login"))
        user = get_current_user()
        if not user or user["role_name"] == "ADMIN":
            abort(403)
        return f(*args, **kwargs)
    return decorated
