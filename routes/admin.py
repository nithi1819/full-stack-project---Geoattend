"""Admin routes: user management, rooms, bookings, attendance, complaints, reports, audit logs."""

import re
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from utils.database import get_db, fetch_one, fetch_all, execute_insert, row_to_dict, rows_to_dicts
from utils.auth import hash_password, login_required, get_current_user
from utils.decorators import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ── DASHBOARD ───────────────────────────────────────────────
@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    db = get_db()
    cursor = db.cursor()

    stats = {}
    stats["total_users"] = fetch_one(cursor, "SELECT COUNT(*) AS cnt FROM users WHERE user_status='ACTIVE'")["cnt"]
    stats["total_students"] = fetch_one(cursor, "SELECT COUNT(*) AS cnt FROM users u JOIN roles r ON u.role_id=r.role_id WHERE r.role_name='STUDENT' AND u.user_status='ACTIVE'")["cnt"]
    stats["total_faculty"] = fetch_one(cursor, "SELECT COUNT(*) AS cnt FROM users u JOIN roles r ON u.role_id=r.role_id WHERE r.role_name='FACULTY' AND u.user_status='ACTIVE'")["cnt"]
    stats["total_reps"] = fetch_one(cursor, "SELECT COUNT(*) AS cnt FROM users u JOIN roles r ON u.role_id=r.role_id WHERE r.role_name='REPRESENTATIVE' AND u.user_status='ACTIVE'")["cnt"]
    stats["total_rooms"] = fetch_one(cursor, "SELECT COUNT(*) AS cnt FROM rooms WHERE is_active=1")["cnt"]
    stats["todays_bookings"] = fetch_one(cursor, "SELECT COUNT(*) AS cnt FROM room_bookings WHERE booking_date=TRUNC(SYSDATE)")["cnt"]
    stats["pending_bookings"] = fetch_one(cursor, "SELECT COUNT(*) AS cnt FROM room_bookings WHERE status='PENDING'")["cnt"]
    stats["active_sessions"] = fetch_one(cursor, "SELECT COUNT(*) AS cnt FROM attendance_sessions WHERE is_active=1")["cnt"]
    stats["todays_attendance"] = fetch_one(cursor, "SELECT COUNT(*) AS cnt FROM attendance_records ar JOIN attendance_sessions s ON ar.session_id=s.session_id WHERE s.session_date=TRUNC(SYSDATE)")["cnt"]
    stats["open_complaints"] = fetch_one(cursor, "SELECT COUNT(*) AS cnt FROM complaints WHERE status IN ('OPEN','ASSIGNED','IN_PROGRESS')")["cnt"]
    stats["urgent_complaints"] = fetch_one(cursor, "SELECT COUNT(*) AS cnt FROM complaints WHERE priority='URGENT' AND status NOT IN ('RESOLVED','CLOSED','REJECTED')")["cnt"]
    stats["resolved_complaints"] = fetch_one(cursor, "SELECT COUNT(*) AS cnt FROM complaints WHERE status='RESOLVED'")["cnt"]

    recent_bookings = fetch_all(cursor,
        """SELECT rb.*, rm.room_number, rm.building, u.full_name AS requested_by_name
           FROM room_bookings rb JOIN rooms rm ON rb.room_id=rm.room_id JOIN users u ON rb.requested_by=u.user_id
           ORDER BY rb.created_at DESC FETCH FIRST 5 ROWS ONLY""")

    recent_complaints = fetch_all(cursor,
        """SELECT c.*, u.full_name AS submitted_by_name, rm.room_number
           FROM complaints c JOIN users u ON c.submitted_by=u.user_id LEFT JOIN rooms rm ON c.room_id=rm.room_id
           ORDER BY c.created_at DESC FETCH FIRST 5 ROWS ONLY""")

    cursor.close()
    return render_template("admin/dashboard.html", stats=stats, recent_bookings=recent_bookings, recent_complaints=recent_complaints)


# ── USER MANAGEMENT ─────────────────────────────────────────
@admin_bp.route("/users")
@admin_required
def users_list():
    db = get_db()
    cursor = db.cursor()
    search = request.args.get("search", "").strip()
    role_filter = request.args.get("role", "")
    status_filter = request.args.get("status", "")

    query = """SELECT u.*, r.role_name, d.department_name
               FROM users u JOIN roles r ON u.role_id=r.role_id
               LEFT JOIN departments d ON u.department_id=d.department_id WHERE 1=1"""
    params = {}

    if search:
        query += " AND (UPPER(u.full_name) LIKE :search OR UPPER(u.username) LIKE :search OR UPPER(u.email) LIKE :search)"
        params["search"] = f"%{search.upper()}%"
    if role_filter:
        query += " AND r.role_name = :role_id"
        params["role_id"] = role_filter
    if status_filter:
        query += " AND u.user_status = :status"
        params["status"] = status_filter

    query += " ORDER BY u.created_at DESC"
    users = fetch_all(cursor, query, params)
    roles = fetch_all(cursor, "SELECT * FROM roles ORDER BY role_id")
    cursor.close()
    return render_template("admin/users.html", users=users, roles=roles,
                           search=search, role_filter=role_filter, status_filter=status_filter)


@admin_bp.route("/users/create", methods=["GET", "POST"])
@admin_required
def user_create():
    db = get_db()
    cursor = db.cursor()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "Admin@123")
        role_id = request.form.get("role_id")
        department_id = request.form.get("department_id")
        phone = request.form.get("phone", "").strip()
        employee_id = request.form.get("employee_id", "").strip()
        student_number = request.form.get("student_number", "").strip()

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not email:
            errors.append("Email is required.")
        if not username:
            errors.append("Username is required.")
        if not role_id:
            errors.append("Role is required.")

        role = fetch_one(cursor, "SELECT role_name FROM roles WHERE role_id=:role_id", {"role_id": int(role_id)}) if role_id else None
        role_name = role["role_name"] if role else ""
        if role_name == "STUDENT" and not student_number:
            errors.append("Student ID is required for student accounts.")
        elif role_name != "STUDENT" and not employee_id:
            errors.append("Employee/Staff ID is required for this role.")

        if not errors:
            dup = fetch_one(cursor, "SELECT user_id FROM users WHERE username=:u", {"u": username})
            if dup:
                errors.append("Username already exists.")
            dup = fetch_one(cursor, "SELECT user_id FROM users WHERE email=:e", {"e": email})
            if dup:
                errors.append("Email already exists.")

        if errors:
            for e in errors:
                flash(e, "danger")
            roles = fetch_all(cursor, "SELECT * FROM roles ORDER BY role_id")
            depts = fetch_all(cursor, "SELECT * FROM departments ORDER BY department_name")
            cursor.close()
            return render_template("admin/user_form.html", user=None, roles=roles, departments=depts, form=request.form)

        dept_id = int(department_id) if department_id else None
        cursor.execute(
            """INSERT INTO users (user_id,role_id,department_id,full_name,username,email,password_hash,phone,employee_id,user_status)
              VALUES (users_seq.NEXTVAL,:role_id,:dept,:name,:uname,:email,:pwd,:phone,:eid,'ACTIVE')""",
            {"role_id": int(role_id), "dept": dept_id, "name": full_name, "uname": username,
             "email": email, "pwd": hash_password(password), "phone": phone,
             "eid": employee_id if role_name != "STUDENT" else None},
        )
        cursor.execute("SELECT users_seq.CURRVAL FROM DUAL")
        new_id = cursor.fetchone()[0]

        if role_name == "STUDENT":
            snum = student_number
            cursor.execute(
                """INSERT INTO students (user_id,student_number,enrollment_year,program,year_level)
                   VALUES (:user_id,:snum,2025,'General',1)""",
                {"user_id": new_id, "snum": snum},
            )
        elif role_name == "FACULTY":
            fnum = request.form.get("faculty_number", f"FAC{new_id}").strip()
            cursor.execute(
                """INSERT INTO faculty (user_id,faculty_number,designation,specialization)
                   VALUES (:user_id,:fnum,'Lecturer','General')""",
                {"user_id": new_id, "fnum": fnum},
            )
        elif role_name == "REPRESENTATIVE":
            cursor.execute(
                """INSERT INTO representatives (user_id,assigned_class,year_level)
                   VALUES (:user_id,'General',1)""",
                {"user_id": new_id},
            )

        db.commit()
        cursor.close()
        flash(f"User '{full_name}' created successfully.", "success")
        return redirect(url_for("admin.users_list"))

    roles = fetch_all(cursor, "SELECT * FROM roles ORDER BY role_id")
    depts = fetch_all(cursor, "SELECT * FROM departments ORDER BY department_name")
    cursor.close()
    return render_template("admin/user_form.html", user=None, roles=roles, departments=depts, form={})


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def user_edit(user_id):
    db = get_db()
    cursor = db.cursor()
    user = fetch_one(cursor, "SELECT * FROM users WHERE user_id=:user_id", {"user_id": user_id})
    if not user:
        flash("User not found.", "danger")
        cursor.close()
        return redirect(url_for("admin.users_list"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        role_id = request.form.get("role_id")
        department_id = request.form.get("department_id")
        phone = request.form.get("phone", "").strip()
        employee_id = request.form.get("employee_id", "").strip()
        status = request.form.get("user_status", "ACTIVE")

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not email:
            errors.append("Email is required.")

        if not errors:
            dup = fetch_one(cursor, "SELECT user_id FROM users WHERE email=:e AND user_id!=:user_id", {"e": email, "user_id": user_id})
            if dup:
                errors.append("Email already exists.")

        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            dept_id = int(department_id) if department_id else None
            cursor.execute(
                """UPDATE users SET full_name=:name, email=:email, role_id=:role_id, department_id=:dept,
                   phone=:phone, employee_id=:eid, user_status=:status WHERE user_id=:user_id""",
                {"name": full_name, "email": email, "role_id": int(role_id), "dept": dept_id,
                 "phone": phone, "eid": employee_id, "status": status, "user_id": user_id},
            )
            db.commit()
            flash("User updated successfully.", "success")
            cursor.close()
            return redirect(url_for("admin.users_list"))

    roles = fetch_all(cursor, "SELECT * FROM roles ORDER BY role_id")
    depts = fetch_all(cursor, "SELECT * FROM departments ORDER BY department_name")
    cursor.close()
    return render_template("admin/user_form.html", user=user, roles=roles, departments=depts, form=user)


@admin_bp.route("/users/<int:user_id>/deactivate", methods=["POST"])
@admin_required
def user_deactivate(user_id):
    db = get_db()
    cursor = db.cursor()
    current = get_current_user()
    if current["user_id"] == user_id:
        flash("You cannot deactivate your own account.", "danger")
        cursor.close()
        return redirect(url_for("admin.users_list"))

    cursor.execute("UPDATE users SET user_status='INACTIVE' WHERE user_id=:user_id", {"user_id": user_id})
    db.commit()
    cursor.close()
    flash("User deactivated.", "success")
    return redirect(url_for("admin.users_list"))


@admin_bp.route("/users/<int:user_id>/activate", methods=["POST"])
@admin_required
def user_activate(user_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE users SET user_status='ACTIVE' WHERE user_id=:user_id", {"user_id": user_id})
    db.commit()
    cursor.close()
    flash("User activated.", "success")
    return redirect(url_for("admin.users_list"))


@admin_bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@admin_required
def user_reset_password(user_id):
    db = get_db()
    cursor = db.cursor()
    new_pwd = hash_password("Reset@123")
    cursor.execute("UPDATE users SET password_hash=:pwd WHERE user_id=:user_id", {"pwd": new_pwd, "user_id": user_id})
    db.commit()
    cursor.close()
    flash("Password reset to 'Reset@123'. User should change it on next login.", "success")
    return redirect(url_for("admin.users_list"))


# ── ROOM MANAGEMENT ─────────────────────────────────────────
@admin_bp.route("/rooms")
@admin_required
def rooms_list():
    db = get_db()
    cursor = db.cursor()
    search = request.args.get("search", "").strip()
    type_filter = request.args.get("type", "")

    query = "SELECT * FROM rooms WHERE 1=1"
    params = {}
    if search:
        query += " AND (UPPER(room_number) LIKE :s OR UPPER(building) LIKE :s)"
        params["s"] = f"%{search.upper()}%"
    if type_filter:
        query += " AND room_type = :t"
        params["t"] = type_filter
    query += " ORDER BY building, room_number"
    rooms = fetch_all(cursor, query, params)
    cursor.close()
    return render_template("admin/rooms.html", rooms=rooms, search=search, type_filter=type_filter)


@admin_bp.route("/rooms/create", methods=["GET", "POST"])
@admin_required
def room_create():
    if request.method == "POST":
        db = get_db()
        cursor = db.cursor()
        room_number = request.form.get("room_number", "").strip()
        building = request.form.get("building", "").strip()
        floor = request.form.get("floor", "0")
        room_type = request.form.get("room_type", "")
        capacity = request.form.get("capacity", "30")
        facilities = request.form.get("facilities", "").strip()

        errors = []
        if not room_number:
            errors.append("Room number is required.")
        if not building:
            errors.append("Building is required.")
        if not room_type:
            errors.append("Room type is required.")

        if not errors:
            dup = fetch_one(cursor, "SELECT room_id FROM rooms WHERE room_number=:r", {"r": room_number})
            if dup:
                errors.append("Room number already exists.")

        if errors:
            for e in errors:
                flash(e, "danger")
            cursor.close()
            return render_template("admin/room_form.html", room=None, form=request.form)

        cursor.execute(
            """INSERT INTO rooms (room_id,room_number,building,floor,room_type,capacity,facilities,is_active)
               VALUES (rooms_seq.NEXTVAL,:rnum,:bldg,:fl,:rtype,:cap,:fac,1)""",
            {"rnum": room_number, "bldg": building, "fl": int(floor), "rtype": room_type,
             "cap": int(capacity), "fac": facilities},
        )
        db.commit()
        cursor.close()
        flash(f"Room '{room_number}' created.", "success")
        return redirect(url_for("admin.rooms_list"))

    return render_template("admin/room_form.html", room=None, form={})


@admin_bp.route("/rooms/<int:room_id>/edit", methods=["GET", "POST"])
@admin_required
def room_edit(room_id):
    db = get_db()
    cursor = db.cursor()
    room = fetch_one(cursor, "SELECT * FROM rooms WHERE room_id=:rid", {"rid": room_id})
    if not room:
        flash("Room not found.", "danger")
        cursor.close()
        return redirect(url_for("admin.rooms_list"))

    if request.method == "POST":
        room_number = request.form.get("room_number", "").strip()
        building = request.form.get("building", "").strip()
        floor = request.form.get("floor", "0")
        room_type = request.form.get("room_type", "")
        capacity = request.form.get("capacity", "30")
        facilities = request.form.get("facilities", "").strip()
        is_active = 1 if request.form.get("is_active") else 0

        dup = fetch_one(cursor, "SELECT room_id FROM rooms WHERE room_number=:r AND room_id!=:rid", {"r": room_number, "rid": room_id})
        if dup:
            flash("Room number already exists.", "danger")
            cursor.close()
            return render_template("admin/room_form.html", room=room, form=request.form)

        cursor.execute(
            """UPDATE rooms SET room_number=:rnum, building=:bldg, floor=:fl, room_type=:rtype,
               capacity=:cap, facilities=:fac, is_active=:active WHERE room_id=:rid""",
            {"rnum": room_number, "bldg": building, "fl": int(floor), "rtype": room_type,
             "cap": int(capacity), "fac": facilities, "active": is_active, "rid": room_id},
        )
        db.commit()
        cursor.close()
        flash("Room updated.", "success")
        return redirect(url_for("admin.rooms_list"))

    cursor.close()
    return render_template("admin/room_form.html", room=room, form=room)


@admin_bp.route("/rooms/<int:room_id>/deactivate", methods=["POST"])
@admin_required
def room_deactivate(room_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE rooms SET is_active=0 WHERE room_id=:rid", {"rid": room_id})
    db.commit()
    cursor.close()
    flash("Room deactivated.", "success")
    return redirect(url_for("admin.rooms_list"))


@admin_bp.route("/rooms/<int:room_id>/activate", methods=["POST"])
@admin_required
def room_activate(room_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE rooms SET is_active=1 WHERE room_id=:rid", {"rid": room_id})
    db.commit()
    cursor.close()
    flash("Room activated.", "success")
    return redirect(url_for("admin.rooms_list"))


# ── BOOKING MANAGEMENT ──────────────────────────────────────
@admin_bp.route("/bookings")
@admin_required
def bookings_list():
    db = get_db()
    cursor = db.cursor()
    status_filter = request.args.get("status", "")
    date_filter = request.args.get("date", "")

    query = """SELECT rb.*, rm.room_number, rm.building, rm.room_type, u.full_name AS requested_by_name,
               a.full_name AS approved_by_name
               FROM room_bookings rb
               JOIN rooms rm ON rb.room_id=rm.room_id
               JOIN users u ON rb.requested_by=u.user_id
               LEFT JOIN users a ON rb.approved_by=a.user_id WHERE 1=1"""
    params = {}
    if status_filter:
        query += " AND rb.status = :status"
        params["status"] = status_filter
    if date_filter:
        query += " AND rb.booking_date = TO_DATE(:date, 'YYYY-MM-DD')"
        params["date"] = date_filter
    query += " ORDER BY rb.created_at DESC"
    bookings = fetch_all(cursor, query, params)
    cursor.close()
    return render_template("admin/bookings.html", bookings=bookings, status_filter=status_filter, date_filter=date_filter)


@admin_bp.route("/bookings/<int:booking_id>/approve", methods=["POST"])
@admin_required
def booking_approve(booking_id):
    db = get_db()
    cursor = db.cursor()
    user = get_current_user()
    cursor.execute(
        "UPDATE room_bookings SET status='APPROVED', approved_by=:user_id, approval_date=CURRENT_TIMESTAMP WHERE booking_id=:bid AND status='PENDING'",
        {"user_id": user["user_id"], "bid": booking_id},
    )
    db.commit()
    cursor.close()
    flash("Booking approved.", "success")
    return redirect(url_for("admin.bookings_list"))


@admin_bp.route("/bookings/<int:booking_id>/reject", methods=["POST"])
@admin_required
def booking_reject(booking_id):
    db = get_db()
    cursor = db.cursor()
    user = get_current_user()
    notes = request.form.get("notes", "")
    cursor.execute(
        "UPDATE room_bookings SET status='REJECTED', approved_by=:user_id, approval_date=CURRENT_TIMESTAMP, notes=:notes WHERE booking_id=:bid AND status='PENDING'",
        {"user_id": user["user_id"], "bid": booking_id, "notes": notes},
    )
    db.commit()
    cursor.close()
    flash("Booking rejected.", "success")
    return redirect(url_for("admin.bookings_list"))


@admin_bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@admin_required
def booking_cancel(booking_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE room_bookings SET status='CANCELLED' WHERE booking_id=:bid", {"bid": booking_id})
    db.commit()
    cursor.close()
    flash("Booking cancelled.", "success")
    return redirect(url_for("admin.bookings_list"))


# ── ATTENDANCE MANAGEMENT ───────────────────────────────────
@admin_bp.route("/attendance")
@admin_required
def attendance_sessions():
    db = get_db()
    cursor = db.cursor()
    sessions = fetch_all(cursor,
        """SELECT s.*, u.full_name AS created_by_name,
           (SELECT COUNT(*) FROM attendance_records WHERE session_id=s.session_id) AS marked_count
           FROM attendance_sessions s JOIN users u ON s.created_by=u.user_id
           ORDER BY s.session_date DESC, s.start_time DESC""")
    cursor.close()
    return render_template("admin/attendance.html", sessions=sessions)


@admin_bp.route("/attendance/<int:session_id>/records")
@admin_required
def attendance_records(session_id):
    db = get_db()
    cursor = db.cursor()
    session_info = fetch_one(cursor,
        """SELECT s.*, u.full_name AS created_by_name
           FROM attendance_sessions s JOIN users u ON s.created_by=u.user_id
           WHERE s.session_id=:sid""",
        {"sid": session_id})
    records = fetch_all(cursor,
        """SELECT ar.*, u.full_name AS student_name, st.student_number
           FROM attendance_records ar
           JOIN users u ON ar.student_id=u.user_id
           JOIN students st ON u.user_id=st.user_id
           WHERE ar.session_id=:sid ORDER BY st.student_number""",
        {"sid": session_id})

    # Get all students for adding absent records
    all_students = fetch_all(cursor,
        """SELECT u.user_id, u.full_name, st.student_number
           FROM users u JOIN students st ON u.user_id=st.user_id
           WHERE u.user_status='ACTIVE' ORDER BY st.student_number""")
    cursor.close()
    return render_template("admin/attendance_records.html", session=session_info, records=records, all_students=all_students)


@admin_bp.route("/attendance/records/<int:record_id>/edit", methods=["POST"])
@admin_required
def attendance_record_edit(record_id):
    db = get_db()
    cursor = db.cursor()
    new_status = request.form.get("status", "")
    if new_status in ("PRESENT", "LATE", "ABSENT"):
        cursor.execute("UPDATE attendance_records SET status=:s WHERE record_id=:rid", {"s": new_status, "rid": record_id})
        db.commit()
        flash("Attendance record updated.", "success")
    else:
        flash("Invalid status.", "danger")
    record = fetch_one(cursor, "SELECT session_id FROM attendance_records WHERE record_id=:rid", {"rid": record_id})
    cursor.close()
    if record:
        return redirect(url_for("admin.attendance_records", session_id=record["session_id"]))
    return redirect(url_for("admin.attendance_sessions"))


# ── COMPLAINT MANAGEMENT ────────────────────────────────────
@admin_bp.route("/complaints")
@admin_required
def complaints_list():
    db = get_db()
    cursor = db.cursor()
    status_filter = request.args.get("status", "")
    priority_filter = request.args.get("priority", "")
    category_filter = request.args.get("category", "")

    query = """SELECT c.*, u.full_name AS submitted_by_name, rm.room_number, rm.building,
               a.full_name AS assigned_to_name
               FROM complaints c JOIN users u ON c.submitted_by=u.user_id
               LEFT JOIN rooms rm ON c.room_id=rm.room_id
               LEFT JOIN users a ON c.assigned_to=a.user_id WHERE 1=1"""
    params = {}
    if status_filter:
        query += " AND c.status = :status"
        params["status"] = status_filter
    if priority_filter:
        query += " AND c.priority = :priority"
        params["priority"] = priority_filter
    if category_filter:
        query += " AND c.category = :category"
        params["category"] = category_filter
    query += " ORDER BY CASE c.priority WHEN 'URGENT' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END, c.created_at DESC"
    complaints = fetch_all(cursor, query, params)
    staff = fetch_all(cursor,
        "SELECT user_id, full_name FROM users WHERE role_id IN (1,2) AND user_status='ACTIVE' ORDER BY full_name")
    cursor.close()
    return render_template("admin/complaints.html", complaints=complaints, staff=staff,
                           status_filter=status_filter, priority_filter=priority_filter, category_filter=category_filter)


@admin_bp.route("/complaints/<int:complaint_id>")
@admin_required
def complaint_detail(complaint_id):
    db = get_db()
    cursor = db.cursor()
    complaint = fetch_one(cursor,
        """SELECT c.*, u.full_name AS submitted_by_name, rm.room_number, rm.building,
           a.full_name AS assigned_to_name
           FROM complaints c JOIN users u ON c.submitted_by=u.user_id
           LEFT JOIN rooms rm ON c.room_id=rm.room_id
           LEFT JOIN users a ON c.assigned_to=a.user_id
           WHERE c.complaint_id=:cid""",
        {"cid": complaint_id})
    if not complaint:
        flash("Complaint not found.", "danger")
        cursor.close()
        return redirect(url_for("admin.complaints_list"))

    history = fetch_all(cursor,
        """SELECT h.*, u.full_name AS changed_by_name
           FROM complaint_status_history h JOIN users u ON h.changed_by=u.user_id
           WHERE h.complaint_id=:cid ORDER BY h.changed_at""",
        {"cid": complaint_id})
    staff = fetch_all(cursor,
        "SELECT user_id, full_name FROM users WHERE role_id IN (1,2) AND user_status='ACTIVE' ORDER BY full_name")
    cursor.close()
    return render_template("admin/complaint_detail.html", complaint=complaint, history=history, staff=staff)


@admin_bp.route("/complaints/<int:complaint_id>/assign", methods=["POST"])
@admin_required
def complaint_assign(complaint_id):
    db = get_db()
    cursor = db.cursor()
    assign_to = request.form.get("assigned_to")
    user = get_current_user()
    if assign_to:
        cursor.execute(
            "UPDATE complaints SET assigned_to=:user_id, status='ASSIGNED' WHERE complaint_id=:cid AND status='OPEN'",
            {"user_id": int(assign_to), "cid": complaint_id})
        cursor.execute(
            "INSERT INTO complaint_status_history (history_id,complaint_id,old_status,new_status,changed_by,notes) VALUES (history_seq.NEXTVAL,:cid,'OPEN','ASSIGNED',:user_id,'Assigned by admin')",
            {"cid": complaint_id, "user_id": user["user_id"]})
        db.commit()
        flash("Complaint assigned.", "success")
    cursor.close()
    return redirect(url_for("admin.complaint_detail", complaint_id=complaint_id))


@admin_bp.route("/complaints/<int:complaint_id>/status", methods=["POST"])
@admin_required
def complaint_status(complaint_id):
    db = get_db()
    cursor = db.cursor()
    new_status = request.form.get("status", "")
    resolution_notes = request.form.get("resolution_notes", "").strip()
    user = get_current_user()

    valid_statuses = ["OPEN", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED", "REJECTED"]
    if new_status not in valid_statuses:
        flash("Invalid status.", "danger")
        cursor.close()
        return redirect(url_for("admin.complaint_detail", complaint_id=complaint_id))

    old = fetch_one(cursor, "SELECT status FROM complaints WHERE complaint_id=:cid", {"cid": complaint_id})
    old_status = old["status"] if old else ""

    cursor.execute("UPDATE complaints SET status=:s WHERE complaint_id=:cid", {"s": new_status, "cid": complaint_id})
    if resolution_notes:
        cursor.execute("UPDATE complaints SET resolution_notes=:rn WHERE complaint_id=:cid", {"rn": resolution_notes, "cid": complaint_id})
    if new_status in ("RESOLVED", "CLOSED"):
        cursor.execute("UPDATE complaints SET resolved_at=CURRENT_TIMESTAMP WHERE complaint_id=:cid", {"cid": complaint_id})

    cursor.execute(
        "INSERT INTO complaint_status_history (history_id,complaint_id,old_status,new_status,changed_by,notes) VALUES (history_seq.NEXTVAL,:cid,:old,:new,:user_id,:notes)",
        {"cid": complaint_id, "old": old_status, "new": new_status, "user_id": user["user_id"],
         "notes": resolution_notes or None})
    db.commit()
    cursor.close()
    flash("Complaint status updated.", "success")
    return redirect(url_for("admin.complaint_detail", complaint_id=complaint_id))


@admin_bp.route("/complaints/<int:complaint_id>/delete", methods=["POST"])
@admin_required
def complaint_delete(complaint_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM complaints WHERE complaint_id=:cid", {"cid": complaint_id})
    db.commit()
    cursor.close()
    flash("Complaint deleted.", "success")
    return redirect(url_for("admin.complaints_list"))


# ── REPORTS ─────────────────────────────────────────────────
@admin_bp.route("/reports")
@admin_required
def reports():
    db = get_db()
    cursor = db.cursor()

    # Attendance report
    attendance_summary = fetch_all(cursor,
        """SELECT u.full_name, st.student_number,
           COUNT(CASE WHEN ar.status='PRESENT' THEN 1 END) AS present_count,
           COUNT(CASE WHEN ar.status='LATE' THEN 1 END) AS late_count,
           COUNT(CASE WHEN ar.status='ABSENT' THEN 1 END) AS absent_count,
           COUNT(ar.record_id) AS total_marked,
           (SELECT COUNT(*) FROM attendance_sessions WHERE is_active=0 OR closed_at IS NOT NULL) AS total_sessions
           FROM users u JOIN students st ON u.user_id=st.user_id
           LEFT JOIN attendance_records ar ON u.user_id=ar.student_id
           WHERE u.user_status='ACTIVE'
           GROUP BY u.full_name, st.student_number
           ORDER BY st.student_number""")

    # Booking report
    booking_summary = fetch_all(cursor,
        """SELECT rm.room_number, rm.building, rm.room_type,
           COUNT(*) AS total_bookings,
           COUNT(CASE WHEN rb.status='APPROVED' THEN 1 END) AS approved,
           COUNT(CASE WHEN rb.status='REJECTED' THEN 1 END) AS rejected,
           COUNT(CASE WHEN rb.status='PENDING' THEN 1 END) AS pending
           FROM room_bookings rb JOIN rooms rm ON rb.room_id=rm.room_id
           GROUP BY rm.room_number, rm.building, rm.room_type
           ORDER BY total_bookings DESC""")

    # Complaint report
    complaint_summary = fetch_all(cursor,
        """SELECT c.category, c.priority,
           COUNT(*) AS total,
           COUNT(CASE WHEN c.status='RESOLVED' THEN 1 END) AS resolved,
           COUNT(CASE WHEN c.status IN ('OPEN','ASSIGNED','IN_PROGRESS') THEN 1 END) AS open_count
           FROM complaints c
           GROUP BY c.category, c.priority
           ORDER BY c.category, c.priority""")

    cursor.close()
    return render_template("admin/reports.html", attendance_summary=attendance_summary,
                           booking_summary=booking_summary, complaint_summary=complaint_summary)


# ── AUDIT LOGS ──────────────────────────────────────────────
@admin_bp.route("/audit-logs")
@admin_required
def audit_logs():
    db = get_db()
    cursor = db.cursor()
    page = int(request.args.get("page", 1))
    per_page = 50
    offset = (page - 1) * per_page
    search = request.args.get("search", "").strip()
    entity_filter = request.args.get("entity", "")

    query = """SELECT al.*, u.full_name AS user_name
               FROM audit_logs al LEFT JOIN users u ON al.user_id=u.user_id WHERE 1=1"""
    params = {}
    if search:
        query += " AND (UPPER(al.description) LIKE :s OR UPPER(al.action) LIKE :s)"
        params["s"] = f"%{search.upper()}%"
    if entity_filter:
        query += " AND al.entity_type = :entity"
        params["entity"] = entity_filter

    count_q = query.replace("al.*, u.full_name AS user_name", "COUNT(*) AS cnt").replace("FROM audit_logs al LEFT JOIN users u ON al.user_id=u.user_id", "FROM audit_logs al LEFT JOIN users u ON al.user_id=u.user_id")
    total = fetch_one(cursor, count_q, params)["cnt"]

    query += " ORDER BY al.created_at DESC OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY"
    params["offset"] = offset
    params["limit"] = per_page
    logs = fetch_all(cursor, query, params)
    total_pages = (total + per_page - 1) // per_page
    cursor.close()
    return render_template("admin/audit_logs.html", logs=logs, page=page, total_pages=total_pages,
                           search=search, entity_filter=entity_filter)
