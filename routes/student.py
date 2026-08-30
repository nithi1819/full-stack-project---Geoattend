"""Student routes: dashboard, scan QR, attendance, bookings, complaints."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.database import get_db, fetch_one, fetch_all
from utils.auth import login_required, get_current_user
from utils.decorators import student_required

student_bp = Blueprint("student", __name__, url_prefix="/student")


# ── DASHBOARD ───────────────────────────────────────────────
@student_bp.route("/dashboard")
@student_required
def dashboard():
    user = get_current_user()
    db = get_db()
    cursor = db.cursor()
    uid = user["user_id"]

    stats = {}
    # Attendance stats
    total_sessions = fetch_one(cursor,
        "SELECT COUNT(*) AS cnt FROM attendance_sessions WHERE is_active=0 OR closed_at IS NOT NULL")["cnt"]
    my_present = fetch_one(cursor,
        "SELECT COUNT(*) AS cnt FROM attendance_records WHERE student_id=:user_id AND status='PRESENT'", {"user_id": uid})["cnt"]
    my_late = fetch_one(cursor,
        "SELECT COUNT(*) AS cnt FROM attendance_records WHERE student_id=:user_id AND status='LATE'", {"user_id": uid})["cnt"]
    my_absent = total_sessions - my_present - my_late
    if total_sessions > 0:
        stats["attendance_pct"] = round(((my_present + my_late) / total_sessions) * 100, 1)
    else:
        stats["attendance_pct"] = 0
    stats["total_sessions"] = total_sessions
    stats["present"] = my_present
    stats["late"] = my_late
    stats["absent"] = max(0, my_absent)

    stats["my_bookings"] = fetch_one(cursor,
        "SELECT COUNT(*) AS cnt FROM room_bookings WHERE requested_by=:user_id", {"user_id": uid})["cnt"]
    stats["my_complaints"] = fetch_one(cursor,
        "SELECT COUNT(*) AS cnt FROM complaints WHERE submitted_by=:user_id", {"user_id": uid})["cnt"]

    # Active sessions available to scan
    active_sessions = fetch_all(cursor,
        """SELECT s.*, u.full_name AS created_by_name
           FROM attendance_sessions s JOIN users u ON s.created_by=u.user_id
           WHERE s.is_active=1
           ORDER BY s.session_date DESC""")

    # My recent attendance
    recent_attendance = fetch_all(cursor,
        """SELECT ar.*, s.class_name, s.course_name, s.session_date
           FROM attendance_records ar JOIN attendance_sessions s ON ar.session_id=s.session_id
           WHERE ar.student_id=:user_id ORDER BY s.session_date DESC FETCH FIRST 5 ROWS ONLY""",
        {"user_id": uid})

    # Available rooms
    available_rooms = fetch_all(cursor,
        "SELECT * FROM rooms WHERE is_active=1 ORDER BY building, room_number")

    cursor.close()
    return render_template("student/dashboard.html", stats=stats, active_sessions=active_sessions,
                           recent_attendance=recent_attendance, available_rooms=available_rooms)


# ── SCAN QR / MARK ATTENDANCE ───────────────────────────────
@student_bp.route("/scan")
@login_required
def scan_qr():
    """Show scan page. Accepts ?token= from QR code URL."""
    token = request.args.get("token", "")
    return render_template("student/scan_qr.html", token=token)


@student_bp.route("/attendance/mark", methods=["POST"])
@login_required
def mark_attendance():
    user = get_current_user()
    if user["role_name"] != "STUDENT":
        flash("Only student accounts can mark attendance.", "warning")
        return redirect(url_for("student.scan_qr"))
    token = request.form.get("token", "").strip()
    if not token:
        flash("Please enter a valid attendance token.", "danger")
        return redirect(url_for("student.scan_qr"))

    db = get_db()
    cursor = db.cursor()

    # Find session by token
    session_info = fetch_one(cursor,
        "SELECT * FROM attendance_sessions WHERE qr_token=:token", {"token": token})
    if not session_info:
        flash("Invalid attendance token. Please check and try again.", "danger")
        cursor.close()
        return redirect(url_for("student.scan_qr"))

    if session_info["is_active"] != 1:
        flash("This attendance session is no longer active.", "warning")
        cursor.close()
        return redirect(url_for("student.scan_qr"))

    # Check expiry using Python (more reliable than PL/SQL for timestamp math)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    created = session_info["created_at"]
    if hasattr(created, 'tzinfo') and created.tzinfo is None:
        # Oracle TIMESTAMP without time zone - assume local
        import datetime as dt_module
        now_local = datetime.now()
        diff_minutes = (now_local - created).total_seconds() / 60
    else:
        diff_minutes = (now - created).total_seconds() / 60

    if diff_minutes >= session_info["qr_expiry_minutes"]:
        cursor.execute(
            """UPDATE attendance_sessions
               SET is_active=0, closed_at=CURRENT_TIMESTAMP
               WHERE session_id=:session_id AND is_active=1""",
            {"session_id": session_info["session_id"]},
        )
        db.commit()
        flash("This QR code has expired. Please ask your instructor for a new one.", "warning")
        cursor.close()
        return redirect(url_for("student.scan_qr"))

    # Check if already marked
    existing = fetch_one(cursor,
        "SELECT record_id FROM attendance_records WHERE session_id=:sid AND student_id=:sid2",
        {"sid": session_info["session_id"], "sid2": user["user_id"]})
    if existing:
        flash("You have already marked attendance for this session.", "info")
        cursor.close()
        return redirect(url_for("student.attendance_history"))

    # Attendance is late after the scheduled start time plus a five-minute grace period.
    session_date = session_info["session_date"]
    if hasattr(session_date, "date"):
        session_day = session_date.date()
    else:
        session_day = session_date
    session_start = datetime.strptime(session_info["start_time"], "%H:%M").time()
    scheduled_start = datetime.combine(session_day, session_start)
    now_local = datetime.now()
    minutes_from_start = (now_local - scheduled_start).total_seconds() / 60
    if minutes_from_start <= 5:
        status = "PRESENT"
    else:
        status = "LATE"

    # Get IP
    ip = request.remote_addr or "unknown"

    cursor.execute(
        """INSERT INTO attendance_records (record_id,session_id,student_id,status,marked_at,qr_token_used,ip_address)
           VALUES (attendance_seq.NEXTVAL,:sid,:user_id,:st,CURRENT_TIMESTAMP,:tk,:ip)""",
        {"sid": session_info["session_id"], "user_id": user["user_id"],
         "st": status, "tk": token, "ip": ip})
    db.commit()
    cursor.close()
    flash(f"Attendance marked successfully! Status: {status}", "success")
    return redirect(url_for("student.attendance_history"))


# ── ATTENDANCE HISTORY ──────────────────────────────────────
@student_bp.route("/attendance")
@student_required
def attendance_history():
    user = get_current_user()
    db = get_db()
    cursor = db.cursor()
    uid = user["user_id"]

    records = fetch_all(cursor,
        """SELECT ar.*, s.class_name, s.course_name, s.session_date, s.start_time, s.end_time,
           u.full_name AS faculty_name
           FROM attendance_records ar
           JOIN attendance_sessions s ON ar.session_id=s.session_id
           JOIN users u ON s.created_by=u.user_id
           WHERE ar.student_id=:user_id ORDER BY s.session_date DESC""",
        {"user_id": uid})

    # Stats
    total_sessions = fetch_one(cursor,
        "SELECT COUNT(*) AS cnt FROM attendance_sessions WHERE is_active=0 OR closed_at IS NOT NULL")["cnt"]
    present = fetch_one(cursor,
        "SELECT COUNT(*) AS cnt FROM attendance_records WHERE student_id=:user_id AND status='PRESENT'", {"user_id": uid})["cnt"]
    late = fetch_one(cursor,
        "SELECT COUNT(*) AS cnt FROM attendance_records WHERE student_id=:user_id AND status='LATE'", {"user_id": uid})["cnt"]
    absent = max(0, total_sessions - present - late)
    pct = round(((present + late) / total_sessions) * 100, 1) if total_sessions > 0 else 0

    cursor.close()
    return render_template("student/attendance.html", records=records, total_sessions=total_sessions,
                           present=present, late=late, absent=absent, pct=pct)


# ── ROOMS ───────────────────────────────────────────────────
@student_bp.route("/rooms")
@student_required
def rooms_list():
    db = get_db()
    cursor = db.cursor()
    search = request.args.get("search", "").strip()
    type_filter = request.args.get("type", "")

    query = "SELECT * FROM rooms WHERE is_active=1"
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
    return render_template("student/rooms.html", rooms=rooms, search=search, type_filter=type_filter)


# ── BOOKINGS ────────────────────────────────────────────────
@student_bp.route("/bookings")
@student_required
def bookings_list():
    user = get_current_user()
    db = get_db()
    cursor = db.cursor()
    bookings = fetch_all(cursor,
        """SELECT rb.*, rm.room_number, rm.building, a.full_name AS approved_by_name
           FROM room_bookings rb JOIN rooms rm ON rb.room_id=rm.room_id
           LEFT JOIN users a ON rb.approved_by=a.user_id
           WHERE rb.requested_by=:user_id ORDER BY rb.created_at DESC""",
        {"user_id": user["user_id"]})
    cursor.close()
    return render_template("student/bookings.html", bookings=bookings)


@student_bp.route("/bookings/create", methods=["GET", "POST"])
@student_required
def booking_create():
    user = get_current_user()
    db = get_db()
    cursor = db.cursor()

    if request.method == "POST":
        room_id = request.form.get("room_id")
        booking_date = request.form.get("booking_date", "")
        start_time = request.form.get("start_time", "")
        end_time = request.form.get("end_time", "")
        purpose = request.form.get("purpose", "").strip()
        num_participants = request.form.get("num_participants", "1")

        errors = []
        if not room_id:
            errors.append("Please select a room.")
        if not booking_date:
            errors.append("Booking date is required.")
        if not start_time or not end_time:
            errors.append("Times are required.")
        if start_time and end_time and start_time >= end_time:
            errors.append("Start time must be before end time.")
        if not purpose:
            errors.append("Purpose is required.")

        if not errors and room_id and booking_date and start_time and end_time:
            conflict = fetch_one(cursor,
                """SELECT COUNT(*) AS cnt FROM room_bookings
                   WHERE room_id=:rid AND booking_date=TO_DATE(:dt,'YYYY-MM-DD')
                   AND status='APPROVED' AND start_time < :et AND end_time > :st""",
                {"rid": int(room_id), "dt": booking_date, "et": end_time, "st": start_time})
            if conflict and conflict["cnt"] > 0:
                errors.append("Time conflict with an existing approved booking.")

        if errors:
            for e in errors:
                flash(e, "danger")
            rooms = fetch_all(cursor, "SELECT * FROM rooms WHERE is_active=1 ORDER BY building, room_number")
            cursor.close()
            return render_template("student/booking_form.html", rooms=rooms, form=request.form)

        cursor.execute(
            """INSERT INTO room_bookings (booking_id,room_id,requested_by,booking_date,start_time,end_time,purpose,num_participants,status)
               VALUES (bookings_seq.NEXTVAL,:rid,:user_id,TO_DATE(:dt,'YYYY-MM-DD'),:st,:et,:purpose,:num,'PENDING')""",
            {"rid": int(room_id), "user_id": user["user_id"], "dt": booking_date,
             "st": start_time, "et": end_time, "purpose": purpose, "num": int(num_participants)})
        db.commit()
        cursor.close()
        flash("Booking request submitted.", "success")
        return redirect(url_for("student.bookings_list"))

    rooms = fetch_all(cursor, "SELECT * FROM rooms WHERE is_active=1 ORDER BY building, room_number")
    cursor.close()
    return render_template("student/booking_form.html", rooms=rooms, form=request.args)


@student_bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@student_required
def booking_cancel(booking_id):
    user = get_current_user()
    db = get_db()
    cursor = db.cursor()
    booking = fetch_one(cursor,
        "SELECT * FROM room_bookings WHERE booking_id=:bid AND requested_by=:user_id AND status IN ('PENDING','APPROVED')",
        {"bid": booking_id, "user_id": user["user_id"]})
    if booking:
        cursor.execute("UPDATE room_bookings SET status='CANCELLED' WHERE booking_id=:bid", {"bid": booking_id})
        db.commit()
        flash("Booking cancelled.", "success")
    else:
        flash("Cannot cancel this booking.", "danger")
    cursor.close()
    return redirect(url_for("student.bookings_list"))


# ── COMPLAINTS ──────────────────────────────────────────────
@student_bp.route("/complaints")
@student_required
def complaints_list():
    user = get_current_user()
    db = get_db()
    cursor = db.cursor()
    complaints = fetch_all(cursor,
        """SELECT c.*, rm.room_number, a.full_name AS assigned_to_name
           FROM complaints c LEFT JOIN rooms rm ON c.room_id=rm.room_id
           LEFT JOIN users a ON c.assigned_to=a.user_id
           WHERE c.submitted_by=:user_id ORDER BY c.created_at DESC""",
        {"user_id": user["user_id"]})
    cursor.close()
    return render_template("student/complaints.html", complaints=complaints)


@student_bp.route("/complaints/create", methods=["GET", "POST"])
@student_required
def complaint_create():
    user = get_current_user()
    db = get_db()
    cursor = db.cursor()

    if request.method == "POST":
        room_id = request.form.get("room_id")
        category = request.form.get("category", "")
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        priority = request.form.get("priority", "MEDIUM")

        errors = []
        if not title:
            errors.append("Title is required.")
        if not description:
            errors.append("Description is required.")
        if not category:
            errors.append("Category is required.")
        elif category not in {"Electrical", "Plumbing", "Furniture", "Air Conditioning",
                              "Internet", "Cleaning", "Equipment", "Other"}:
            errors.append("Please select a valid complaint category.")
        if priority not in {"LOW", "MEDIUM", "HIGH", "URGENT"}:
            errors.append("Please select a valid complaint priority.")

        if errors:
            for e in errors:
                flash(e, "danger")
            rooms = fetch_all(cursor, "SELECT * FROM rooms WHERE is_active=1 ORDER BY building, room_number")
            cursor.close()
            return render_template("student/complaint_form.html", rooms=rooms, form=request.form)

        rid = int(room_id) if room_id else None
        cursor.execute(
            """INSERT INTO complaints (complaint_id,submitted_by,room_id,category,title,description,priority,status)
               VALUES (complaints_seq.NEXTVAL,:user_id,:rid,:cat,:title,:description,:pri,'OPEN')""",
            {"user_id": user["user_id"], "rid": rid, "cat": category, "title": title, "description": description, "pri": priority})
        db.commit()
        cursor.close()
        flash("Complaint submitted.", "success")
        return redirect(url_for("student.complaints_list"))

    rooms = fetch_all(cursor, "SELECT * FROM rooms WHERE is_active=1 ORDER BY building, room_number")
    cursor.close()
    return render_template("student/complaint_form.html", rooms=rooms, form={})
