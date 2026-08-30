"""QR Attendance, Room Booking & Facility Complaints Management System - Main Application."""

import os
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, request, session, g
from config import Config
from utils.database import get_db, fetch_one, fetch_all, close_db
from utils.auth import hash_password, is_authenticated, get_current_user

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = app.config["SECRET_KEY"]
app.permanent_session_lifetime = timedelta(seconds=Config.PERMANENT_SESSION_LIFETIME)

# ── Template Filters ────────────────────────────────────────
@app.template_filter("datetime_format")
def datetime_format(value, fmt="%Y-%m-%d %H:%M"):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.strftime(fmt)

@app.template_filter("date_format")
def date_format(value, fmt="%Y-%m-%d"):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.strftime(fmt)

@app.template_filter("time_format")
def time_format(value):
    if value is None:
        return ""
    return str(value)

@app.template_filter("status_badge")
def status_badge(status):
    colors = {
        "ACTIVE": "success", "INACTIVE": "danger", "SUSPENDED": "warning",
        "PENDING": "warning", "APPROVED": "success", "REJECTED": "danger",
        "CANCELLED": "secondary", "COMPLETED": "info",
        "PRESENT": "success", "LATE": "warning", "ABSENT": "danger",
        "OPEN": "info", "ASSIGNED": "primary", "IN_PROGRESS": "warning",
        "RESOLVED": "success", "CLOSED": "secondary",
        "LOW": "info", "MEDIUM": "warning", "HIGH": "danger", "URGENT": "danger",
    }
    return colors.get(status, "secondary")

# ── Context Processor ───────────────────────────────────────
@app.context_processor
def inject_user():
    user = None
    if is_authenticated():
        user = get_current_user()
    return dict(current_user=user)

# ── Request Hooks ───────────────────────────────────────────
@app.before_request
def before_request():
    session.permanent = True

@app.teardown_appcontext
def teardown_db(exception):
    db = g.pop("db", None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass

# ── Register Blueprints ─────────────────────────────────────
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.faculty import faculty_bp
from routes.representative import representative_bp
from routes.student import student_bp

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(faculty_bp)
app.register_blueprint(representative_bp)
app.register_blueprint(student_bp)

# ── Error Handlers ──────────────────────────────────────────
@app.errorhandler(403)
def forbidden(e):
    return render_template("errors/403.html"), 403

@app.errorhandler(404)
def not_found(e):
    return render_template("errors/404.html"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template("errors/500.html"), 500

# ── Root Route ──────────────────────────────────────────────
@app.route("/")
def index():
    if is_authenticated():
        user = get_current_user()
        if user:
            from utils.auth import get_dashboard_url
            return render_template("index.html", redirect_url=get_dashboard_url(user["role_name"]))
    return render_template("index.html")

# ── Database Initialization ─────────────────────────────────
def init_database():
    """Initialize database tables and seed demo data if needed."""
    try:
        db = get_db()
        cursor = db.cursor()

        # Check if ALL core tables exist (not just ROLES) so a partially-applied
        # schema from a previous failed run is detected and retried.
        required_tables = (
            "ROLES", "DEPARTMENTS", "USERS", "STUDENTS", "FACULTY",
            "REPRESENTATIVES", "ROOMS", "ROOM_BOOKINGS", "ATTENDANCE_SESSIONS",
            "ATTENDANCE_RECORDS", "COMPLAINTS", "COMPLAINT_STATUS_HISTORY", "AUDIT_LOGS",
        )
        placeholders = ",".join(f"'{t}'" for t in required_tables)
        cursor.execute(f"SELECT COUNT(*) FROM user_tables WHERE table_name IN ({placeholders})")
        count = cursor.fetchone()[0]

        if count < len(required_tables):
            print("[INIT] Tables not found. Running schema scripts...")
            base_dir = os.path.dirname(os.path.abspath(__file__))

            for sql_file in ["database/schema.sql", "database/procedures.sql", "database/triggers.sql", "database/seed.sql"]:
                filepath = os.path.join(base_dir, sql_file)
                if os.path.exists(filepath):
                    print(f"  Running {sql_file}...")
                    _run_sql_file(cursor, filepath)
                    db.commit()

            cursor.execute(f"SELECT COUNT(*) FROM user_tables WHERE table_name IN ({placeholders})")
            count = cursor.fetchone()[0]
            if count < len(required_tables):
                raise RuntimeError(
                    f"Database schema is incomplete: found {count} of "
                    f"{len(required_tables)} required tables."
                )

        # Recompile objects left invalid by an earlier failed initialization.
        cursor.execute(
            "SELECT COUNT(*) FROM user_objects "
            "WHERE status = 'INVALID' "
            "AND object_name IN ("
            "'CHECK_BOOKING_CONFLICT', 'MARK_ATTENDANCE', "
            "'GET_ATTENDANCE_PERCENTAGE', 'UPDATE_COMPLAINT_STATUS', "
            "'WRITE_AUDIT_LOG', 'IS_STUDENT_ELIGIBLE', "
            "'TRG_USERS_UPDATED_AT', 'TRG_COMPLAINTS_UPDATED_AT', "
            "'TRG_COMPLAINT_STATUS_INSERT', 'TRG_AUDIT_USER_INSERT', "
            "'TRG_AUDIT_BOOKING_STATUS', 'TRG_AUDIT_SESSION_INSERT')"
        )
        invalid_objects = cursor.fetchone()[0]
        if invalid_objects:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            for sql_file in ["database/procedures.sql", "database/triggers.sql"]:
                filepath = os.path.join(base_dir, sql_file)
                if os.path.exists(filepath):
                    print(f"[INIT] Recompiling invalid objects from {sql_file}...")
                    _run_sql_file(cursor, filepath)
                    db.commit()

            cursor.execute(
                "SELECT COUNT(*) FROM user_objects "
                "WHERE status = 'INVALID' "
                "AND object_name IN ("
                "'CHECK_BOOKING_CONFLICT', 'MARK_ATTENDANCE', "
                "'GET_ATTENDANCE_PERCENTAGE', 'UPDATE_COMPLAINT_STATUS', "
                "'WRITE_AUDIT_LOG', 'IS_STUDENT_ELIGIBLE', "
                "'TRG_USERS_UPDATED_AT', 'TRG_COMPLAINTS_UPDATED_AT', "
                "'TRG_COMPLAINT_STATUS_INSERT', 'TRG_AUDIT_USER_INSERT', "
                "'TRG_AUDIT_BOOKING_STATUS', 'TRG_AUDIT_SESSION_INSERT')"
            )
            if cursor.fetchone()[0]:
                raise RuntimeError("Oracle schema contains invalid triggers or stored procedures.")

        # Seed demo users (always check)
        _seed_demo_users(db)

        cursor.close()
        print("[INIT] Database ready.")
        return True

    except Exception as e:
        print(f"[INIT] Database initialization failed: {e}")
        print("[INIT] Make sure Oracle Database is running and .env is configured correctly.")
        return False


@app.before_request
def ensure_database_initialized():
    """Initialize the schema when the app is launched through Flask's CLI."""
    if app.extensions.get("database_initialized"):
        return

    if not init_database():
        raise RuntimeError(
            "Database initialization failed. Verify Oracle is running, the "
            "configured user has CREATE privileges, and ORACLE_DSN is correct."
        )

    app.extensions["database_initialized"] = True


def _run_sql_file(cursor, filepath):
    """Execute a SQL file, handling PL/SQL blocks properly."""
    with open(filepath, "r") as f:
        content = f.read()

    # Remove comment-only lines and empty statements
    statements = []
    current = ""
    in_plsql = False

    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("--"):
            continue

        upper = stripped.upper()

        # Detect PL/SQL block start
        if any(kw in upper for kw in ["CREATE OR REPLACE PROCEDURE", "CREATE OR REPLACE FUNCTION",
                                       "CREATE OR REPLACE TRIGGER", "CREATE OR REPLACE PACKAGE",
                                       "BEGIN", "DECLARE"]):
            in_plsql = True

        if stripped == "/":
            # "/" is a SQL*Plus script delimiter, not part of the SQL sent
            # through the Python Oracle driver.
            if in_plsql:
                statements.append(current.strip())
                current = ""
                in_plsql = False
            continue

        current += line + "\n"

        if stripped.endswith(";") and not in_plsql:
            statements.append(current.strip()[:-1].rstrip())
            current = ""

    if current.strip() and current.strip() != "/":
        statements.append(current.strip())

    for stmt in statements:
        stmt_clean = stmt.strip()
        if stmt_clean == "/":
            continue
        if not stmt_clean.startswith(("BEGIN", "DECLARE", "CREATE OR REPLACE")):
            stmt_clean = stmt_clean.rstrip(";").rstrip()
        if not stmt_clean or stmt_clean == "/":
            continue
        try:
            cursor.execute(stmt_clean)
        except Exception as e:
            # Ignore "already exists" errors
            if "ORA-00955" in str(e) or "ORA-01430" in str(e):
                pass
            else:
                print(f"  Warning: {str(e)[:120]}")


def _seed_demo_users(db):
    """Insert demo users with hashed passwords if they don't exist."""
    cursor = db.cursor()

    # Check if admin exists
    existing = fetch_one(cursor, "SELECT user_id FROM users WHERE username = 'admin'")
    if existing:
        cursor.close()
        return

    print("[INIT] Seeding demo users...")

    demo_users = [
        {
            "username": "admin", "password": "Admin@123",
            "full_name": "System Administrator", "email": "admin@college.edu",
            "role_id": 1, "dept_id": 1, "phone": "555-0100", "eid": "ADM001",
        },
        {
            "username": "faculty1", "password": "Faculty@123",
            "full_name": "Dr. Sarah Johnson", "email": "sarah.johnson@college.edu",
            "role_id": 2, "dept_id": 1, "phone": "555-0201", "eid": "FAC001",
        },
        {
            "username": "faculty2", "password": "Faculty@123",
            "full_name": "Prof. Michael Chen", "email": "michael.chen@college.edu",
            "role_id": 2, "dept_id": 2, "phone": "555-0202", "eid": "FAC002",
        },
        {
            "username": "rep1", "password": "Rep@123",
            "full_name": "Emily Williams", "email": "emily.w@college.edu",
            "role_id": 3, "dept_id": 1, "phone": "555-0301", "eid": None,
        },
        {
            "username": "student1", "password": "Student@123",
            "full_name": "James Anderson", "email": "james.a@college.edu",
            "role_id": 4, "dept_id": 1, "phone": "555-0401", "eid": None,
        },
        {
            "username": "student2", "password": "Student@123",
            "full_name": "Maria Garcia", "email": "maria.g@college.edu",
            "role_id": 4, "dept_id": 3, "phone": "555-0402", "eid": None,
        },
        {
            "username": "student3", "password": "Student@123",
            "full_name": "David Kim", "email": "david.k@college.edu",
            "role_id": 4, "dept_id": 2, "phone": "555-0403", "eid": None,
        },
    ]

    for u in demo_users:
        pwd_hash = hash_password(u["password"])
        cursor.execute(
            """INSERT INTO users (user_id,role_id,department_id,full_name,username,email,password_hash,phone,employee_id,user_status)
               VALUES (users_seq.NEXTVAL,:role_id,:dept,:name,:uname,:email,:pwd,:phone,:eid,'ACTIVE')""",
            {"role_id": u["role_id"], "dept": u["dept_id"], "name": u["full_name"],
             "uname": u["username"], "email": u["email"], "pwd": pwd_hash,
             "phone": u["phone"], "eid": u["eid"]},
        )
        cursor.execute("SELECT users_seq.CURRVAL FROM DUAL")
        uid = cursor.fetchone()[0]

        # Create role-specific records
        if u["role_id"] == 4:  # Student
            snum = f"STU{uid:04d}"
            cursor.execute(
                """INSERT INTO students (user_id,student_number,enrollment_year,program,year_level)
                   VALUES (:user_id,:snum,2024,'Computer Science',2)""",
                {"user_id": uid, "snum": snum},
            )
        elif u["role_id"] == 2:  # Faculty
            fnum = f"FAC{uid:04d}"
            designation = "Associate Professor" if "Sarah" in u["full_name"] else "Lecturer"
            spec = "Artificial Intelligence" if "Sarah" in u["full_name"] else "Data Structures"
            cursor.execute(
                """INSERT INTO faculty (user_id,faculty_number,designation,specialization)
                   VALUES (:user_id,:fnum,:des,:spec)""",
                {"user_id": uid, "fnum": fnum, "des": designation, "spec": spec},
            )
        elif u["role_id"] == 3:  # Representative
            cursor.execute(
                """INSERT INTO representatives (user_id,assigned_class,year_level)
                   VALUES (:user_id,'CS-301 Year 2',2)""",
                {"user_id": uid},
            )

    db.commit()
    cursor.close()
    print("[INIT] Demo users created successfully.")


# ── Run ─────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  QR Attendance, Room Booking & Facility Complaints")
    print("  Management System")
    print("=" * 60)
    print()
    print("[STARTUP] Initializing database...")
    with app.app_context():
        if init_database():
            app.extensions["database_initialized"] = True
    print()
    print("[STARTUP] Starting Flask application...")
    print("[STARTUP] Open http://127.0.0.1:5000 in your browser")
    print("[STARTUP] For phone QR scanning, use http://<computer-ip>:5000")
    print("[STARTUP] Press Ctrl+C to stop")
    print()
    app.run(debug=True, host="0.0.0.0", port=5000)
