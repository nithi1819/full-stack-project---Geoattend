"""Authentication routes: login, signup, logout, profile, change password."""

import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from utils.database import get_db, fetch_one, fetch_all, execute_insert
from utils.auth import (
    hash_password, verify_password, login_user, logout_user,
    get_current_user, is_authenticated, login_required, get_dashboard_url,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ── LOGIN ──────────────────────────────────────────────────
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if is_authenticated():
        user = get_current_user()
        if user:
            return redirect(get_dashboard_url(user["role_name"]))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please enter both username and password.", "danger")
            return render_template("login.html")

        db = get_db()
        cursor = db.cursor()
        user = fetch_one(
            cursor,
            """SELECT u.*, r.role_name
               FROM users u
               JOIN roles r ON u.role_id = r.role_id
               WHERE u.username = :username""",
            {"username": username},
        )
        cursor.close()

        if user is None:
            flash("Invalid username or password.", "danger")
            return render_template("login.html")

        if user["user_status"] != "ACTIVE":
            flash("Your account has been deactivated. Please contact the administrator.", "danger")
            return render_template("login.html")

        if not verify_password(password, user["password_hash"]):
            flash("Invalid username or password.", "danger")
            return render_template("login.html")

        login_user(user)
        flash(f"Welcome back, {user['full_name']}!", "success")
        return redirect(get_dashboard_url(user["role_name"]))

    return render_template("login.html")


# ── SIGNUP ─────────────────────────────────────────────────
@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if is_authenticated():
        return redirect(url_for("auth.dashboard_redirect"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        department_id = request.form.get("department_id")
        phone = request.form.get("phone", "").strip()
        student_number = request.form.get("student_number", "").strip()
        enrollment_year = request.form.get("enrollment_year", "").strip()
        program = request.form.get("program", "").strip()
        year_level = request.form.get("year_level", "").strip()

        # Validation
        errors = []
        if not full_name or len(full_name) < 2:
            errors.append("Full name must be at least 2 characters.")
        if not email or not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors.append("Please enter a valid email address.")
        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters.")
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            errors.append("Username can only contain letters, numbers, and underscores.")
        if not password or len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter.")
        if not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter.")
        if not re.search(r'[0-9]', password):
            errors.append("Password must contain at least one number.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character.")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        if not student_number:
            errors.append("Student number is required.")
        if not program:
            errors.append("Program is required.")

        if errors:
            for e in errors:
                flash(e, "danger")
            db = get_db()
            cursor = db.cursor()
            departments = fetch_all(cursor, "SELECT * FROM departments ORDER BY department_name")
            cursor.close()
            return render_template("signup.html", departments=departments, form=request.form)

        db = get_db()
        cursor = db.cursor()

        # Check duplicates
        existing = fetch_one(cursor, "SELECT user_id FROM users WHERE username = :u", {"u": username})
        if existing:
            flash("Username already taken.", "danger")
            departments = fetch_all(cursor, "SELECT * FROM departments ORDER BY department_name")
            cursor.close()
            return render_template("signup.html", departments=departments, form=request.form)

        existing = fetch_one(cursor, "SELECT user_id FROM users WHERE email = :e", {"e": email})
        if existing:
            flash("Email already registered.", "danger")
            departments = fetch_all(cursor, "SELECT * FROM departments ORDER BY department_name")
            cursor.close()
            return render_template("signup.html", departments=departments, form=request.form)

        existing = fetch_one(cursor, "SELECT user_id FROM students WHERE student_number = :s", {"s": student_number})
        if existing:
            flash("Student number already registered.", "danger")
            departments = fetch_all(cursor, "SELECT * FROM departments ORDER BY department_name")
            cursor.close()
            return render_template("signup.html", departments=departments, form=request.form)

        # Create user (always STUDENT role for public signup)
        password_h = hash_password(password)
        dept_id = int(department_id) if department_id else None

        cursor.execute(
            """INSERT INTO users (user_id, role_id, department_id, full_name, username, email, password_hash, phone, user_status)
               VALUES (users_seq.NEXTVAL, 4, :dept, :name, :username, :email, :pwd, :phone, 'ACTIVE')""",
            {"dept": dept_id, "name": full_name, "username": username, "email": email, "pwd": password_h, "phone": phone},
        )

        # Get the new user_id
        cursor.execute("SELECT users_seq.CURRVAL FROM DUAL")
        user_id = cursor.fetchone()[0]

        # Create student record
        cursor.execute(
            """INSERT INTO students (user_id, student_number, enrollment_year, program, year_level)
               VALUES (:user_id, :snum, :eyear, :prog, :ylevel)""",
            {"user_id": user_id, "snum": student_number, "eyear": int(enrollment_year) if enrollment_year else 2025,
             "prog": program, "ylevel": int(year_level) if year_level else 1},
        )

        db.commit()
        cursor.close()
        flash("Account created successfully! Please sign in.", "success")
        return redirect(url_for("auth.login"))

    # GET request
    db = get_db()
    cursor = db.cursor()
    departments = fetch_all(cursor, "SELECT * FROM departments ORDER BY department_name")
    cursor.close()
    return render_template("signup.html", departments=departments)


# ── LOGOUT ──────────────────────────────────────────────────
@auth_bp.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


# ── DASHBOARD REDIRECT ──────────────────────────────────────
@auth_bp.route("/")
@login_required
def dashboard_redirect():
    user = get_current_user()
    return redirect(get_dashboard_url(user["role_name"]))


# ── PROFILE ─────────────────────────────────────────────────
@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = get_current_user()
    db = get_db()
    cursor = db.cursor()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()

        errors = []
        if not full_name or len(full_name) < 2:
            errors.append("Full name must be at least 2 characters.")
        if not email or not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors.append("Please enter a valid email address.")

        # Check email uniqueness
        if not errors:
            existing = fetch_one(
                cursor,
                "SELECT user_id FROM users WHERE email = :e AND user_id != :user_id",
                {"e": email, "user_id": user["user_id"]},
            )
            if existing:
                errors.append("Email already registered.")

        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            cursor.execute(
                "UPDATE users SET full_name = :name, email = :email, phone = :phone WHERE user_id = :user_id",
                {"name": full_name, "email": email, "phone": phone, "user_id": user["user_id"]},
            )
            db.commit()
            session["full_name"] = full_name
            flash("Profile updated successfully.", "success")

        cursor.close()
        return redirect(url_for("auth.profile"))

    # Get extended profile info
    extra = None
    if user["role_name"] == "STUDENT":
        extra = fetch_one(cursor, "SELECT * FROM students WHERE user_id = :user_id", {"user_id": user["user_id"]})
    elif user["role_name"] == "FACULTY":
        extra = fetch_one(cursor, "SELECT * FROM faculty WHERE user_id = :user_id", {"user_id": user["user_id"]})
    elif user["role_name"] == "REPRESENTATIVE":
        extra = fetch_one(cursor, "SELECT * FROM representatives WHERE user_id = :user_id", {"user_id": user["user_id"]})

    departments = fetch_all(cursor, "SELECT * FROM departments ORDER BY department_name")
    cursor.close()
    return render_template("profile.html", user=user, extra=extra, departments=departments)


# ── CHANGE PASSWORD ─────────────────────────────────────────
@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    user = get_current_user()

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = []
        if not verify_password(current_password, user["password_hash"]):
            errors.append("Current password is incorrect.")
        if not new_password or len(new_password) < 8:
            errors.append("New password must be at least 8 characters.")
        if not re.search(r'[A-Z]', new_password):
            errors.append("New password must contain at least one uppercase letter.")
        if not re.search(r'[a-z]', new_password):
            errors.append("New password must contain at least one lowercase letter.")
        if not re.search(r'[0-9]', new_password):
            errors.append("New password must contain at least one number.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_password):
            errors.append("New password must contain at least one special character.")
        if new_password != confirm_password:
            errors.append("New passwords do not match.")

        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                "UPDATE users SET password_hash = :pwd WHERE user_id = :user_id",
                {"pwd": hash_password(new_password), "user_id": user["user_id"]},
            )
            db.commit()
            cursor.close()
            flash("Password changed successfully.", "success")
            return redirect(url_for("auth.profile"))

    return render_template("change_password.html")

