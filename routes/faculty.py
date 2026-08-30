"""Faculty routes: dashboard, attendance sessions, QR codes, bookings, complaints."""

from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.database import get_db, fetch_one, fetch_all
from utils.auth import login_required, get_current_user
from utils.decorators import faculty_required
from utils.qr import generate_session_token, generate_qr_base64, build_attendance_url, get_public_base_url

faculty_bp = Blueprint("faculty", __name__, url_prefix="/faculty")


@faculty_bp.route("/rooms")
@faculty_required
def rooms_list():
    db = get_db()
    cursor = db.cursor()
    search = request.args.get("search", "").strip()
    type_filter = request.args.get("type", "")
    query = "SELECT * FROM rooms WHERE is_active=1"
    params = {}
    if search:
        query += " AND (UPPER(room_number) LIKE :search OR UPPER(building) LIKE :search)"
        params["search"] = f"%{search.upper()}%"
    if type_filter:
        query += " AND room_type = :room_type"
        params["room_type"] = type_filter
    rooms = fetch_all(cursor, query + " ORDER BY building, room_number", params)
    cursor.close()
    return render_template("faculty/rooms.html", rooms=rooms, search=search, type_filter=type_filter)


# ── DASHBOARD ───────────────────────────────────────────────
@faculty_bp.route("/dashboard")
@faculty_required
def dashboard():
    user = get_current_user()
    db = get_db()
    cursor = db.cursor()
    uid = user["user_id"]

    stats = {}
    stats["my_sessions"] = fetch_one(cursor, "SELECT COUNT(*) AS cnt FROM attendance_sessions WHERE created_by=:user_id", {"user_id": uid})["cnt"]
    stats["active_sessions"] = fetch_one(cursor, "SELECT COUNT(*) AS cnt FROM attendance_sessions WHERE created_by=:user_id AND is_active=1", {"user_id": uid})["cnt"]
    stats["today_sessions"] = fetch_one(cursor, "SELECT COUNT(*) AS cnt FROM attendance_sessions WHERE created_by=:user_id AND session_date=TRUNC(SYSDATE)", {"user_id": uid})["cnt"]
    stats["my_bookings"] = fetch_one(cursor, "SELECT COUNT(*) AS cnt FROM room_bookings WHERE requested_by=:user_id", {"user_id": uid})["cnt"]
    stats["my_complaints"] = fetch_one(cursor, "SELECT COUNT(*) AS cnt FROM complaints WHERE submitted_by=:user_id", {"user_id": uid})["cnt"]
    stats["pending_bookings"] = fetch_one(cursor, "SELECT COUNT(*) AS cnt FROM room_bookings WHERE requested_by=:user_id AND status='PENDING'", {"user_id": uid})["cnt"]

    # Total attendance across my sessions
    stats["total_attendance"] = fetch_one(cursor,
        """SELECT COUNT(*) AS cnt FROM attendance_records ar
           JOIN attendance_sessions s ON ar.session_id=s.session_id WHERE s.created_by=:user_id""", {"user_id": uid})["cnt"]

    recent_sessions = fetch_all(cursor,
        """SELECT s.*,
           (SELECT COUNT(*) FROM attendance_records WHERE session_id=s.session_id) AS marked_count
           FROM attendance_sessions s WHERE s.created_by=:user_id
           ORDER BY s.session_date DESC, s.start_time DESC FETCH FIRST 5 ROWS ONLY""",
        {"user_id": uid})

    cursor.close()
    return render_template("faculty/dashboard.html", stats=stats, recent_sessions=recent_sessions)


# ── SESSIONS ────────────────────────────────────────────────
@faculty_bp.route("/sessions")
@faculty_required
def sessions_list():
    user = get_current_user()
    db = get_db()
    cursor = db.cursor()
    sessions = fetch_all(cursor,
        """SELECT s.*,
           (SELECT COUNT(*) FROM attendance_records WHERE session_id=s.session_id) AS marked_count
           FROM attendance_sessions s WHERE s.created_by=:user_id
           ORDER BY s.session_date DESC, s.start_time DESC""",
        {"user_id": user["user_id"]})
    cursor.close()
    return render_template("faculty/sessions.html", sessions=sessions)


@faculty_bp.route("/sessions/create", methods=["GET", "POST"])
@faculty_required
def session_create():
    user = get_current_user()
    if request.method == "POST":
        db = get_db()
        cursor = db.cursor()
        class_name = request.form.get("class_name", "").strip()
        course_name = request.form.get("course_name", "").strip()
        session_date = request.form.get("session_date", "")
        start_time = request.form.get("start_time", "")
        end_time = request.form.get("end_time", "")
        qr_expiry = request.form.get("qr_expiry_minutes", "15")

        errors = []
        if not class_name:
            errors.append("Class name is required.")
        if not session_date:
            errors.append("Session date is required.")
        if not start_time or not end_time:
            errors.append("Start and end times are required.")
        if start_time and end_time and start_time >= end_time:
            errors.append("Start time must be before end time.")

        if errors:
            for e in errors:
                flash(e, "danger")
            cursor.close()
            return render_template("faculty/session_form.html", form=request.form)

        token = generate_session_token()
        cursor.execute(
            """INSERT INTO attendance_sessions
               (session_id,created_by,class_name,course_name,session_date,start_time,end_time,qr_token,qr_expiry_minutes,is_active)
               VALUES (sessions_seq.NEXTVAL,:user_id,:cls,:crs,TO_DATE(:dt,'YYYY-MM-DD'),:st,:et,:token,:exp,1)""",
            {"user_id": user["user_id"], "cls": class_name, "crs": course_name, "dt": session_date,
             "st": start_time, "et": end_time, "token": token, "exp": int(qr_expiry)},
        )
        cursor.execute("SELECT sessions_seq.CURRVAL FROM DUAL")
        session_id = cursor.fetchone()[0]
        db.commit()
        cursor.close()
        flash("Attendance session created. QR code generated.", "success")
        return redirect(url_for("faculty.session_qr", session_id=session_id))

    return render_template("faculty/session_form.html", form={})


@faculty_bp.route("/sessions/<int:session_id>/qr")
@faculty_required
def session_qr(session_id):
    user = get_current_user()
    db = get_db()
    cursor = db.cursor()
    session_info = fetch_one(cursor,
        "SELECT * FROM attendance_sessions WHERE session_id=:sid AND created_by=:user_id",
        {"sid": session_id, "user_id": user["user_id"]})
    if not session_info:
        flash("Session not found.", "danger")
        cursor.close()
        return redirect(url_for("faculty.sessions_list"))

    created_at = session_info["created_at"]
    current_time = datetime.now(created_at.tzinfo) if getattr(created_at, "tzinfo", None) else datetime.now()
    expires_at = created_at + timedelta(minutes=session_info["qr_expiry_minutes"])
    if session_info["is_active"] == 1 and current_time >= expires_at:
        cursor.execute(
            """UPDATE attendance_sessions
               SET is_active=0, closed_at=CURRENT_TIMESTAMP
               WHERE session_id=:session_id AND is_active=1""",
            {"session_id": session_id},
        )
        db.commit()
        session_info["is_active"] = 0

    # Generate QR code with the attendance URL
    from flask import request as req
    base_url = get_public_base_url(req)
    attendance_url = build_attendance_url(base_url, session_info["qr_token"])
    qr_base64 = generate_qr_base64(attendance_url)

    marked_count = fetch_one(cursor,
        "SELECT COUNT(*) AS cnt FROM attendance_records WHERE session_id=:sid", {"sid": session_id})["cnt"]

    cursor.close()
    return render_template("faculty/qr_display.html", session=session_info, qr_base64=qr_base64,
                           attendance_url=attendance_url, marked_count=marked_count,
                           expires_at_ms=int(expires_at.timestamp() * 1000))


@faculty_bp.route("/sessions/<int:session_id>/close", methods=["POST"])
@faculty_required
def session_close(session_id):
    user = get_current_user()
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE attendance_sessions SET is_active=0, closed_at=CURRENT_TIMESTAMP WHERE session_id=:sid AND created_by=:user_id",
        {"sid": session_id, "user_id": user["user_id"]})
    db.commit()
    cursor.close()
    flash("Session closed.", "success")
    return redirect(url_for("faculty.sessions_list"))


@faculty_bp.route("/sessions/<int:session_id>/records")
@faculty_required
def session_records(session_id):
    user = get_current_user()
    db = get_db()
    cursor = db.cursor()
    session_info = fetch_one(cursor,
        "SELECT * FROM attendance_sessions WHERE session_id=:sid AND created_by=:user_id",
        {"sid": session_id, "user_id": user["user_id"]})
    if not session_info:
        flash("Session not found.", "danger")
        cursor.close()
        return redirect(url_for("faculty.sessions_list"))

    records = fetch_all(cursor,
        """SELECT ar.*, u.full_name AS student_name, st.student_number
           FROM attendance_records ar
           JOIN users u ON ar.student_id=u.user_id
           JOIN students st ON u.user_id=st.user_id
           WHERE ar.session_id=:sid ORDER BY st.student_number""",
        {"sid": session_id})
    cursor.close()
    return render_template("faculty/attendance_records.html", session=session_info, records=records)


# ── BOOKINGS ────────────────────────────────────────────────
@faculty_bp.route("/bookings")
@faculty_required
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
    return render_template("faculty/bookings.html", bookings=bookings)


@faculty_bp.route("/bookings/create", methods=["GET", "POST"])
@faculty_required
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
            errors.append("Start and end times are required.")
        if start_time and end_time and start_time >= end_time:
            errors.append("Start time must be before end time.")
        if not purpose:
            errors.append("Purpose is required.")
        if not num_participants or int(num_participants) < 1:
            errors.append("Number of participants must be at least 1.")

        # Check room capacity
        if room_id and num_participants:
            room = fetch_one(cursor, "SELECT capacity FROM rooms WHERE room_id=:rid", {"rid": int(room_id)})
            if room and int(num_participants) > room["capacity"]:
                errors.append(f"Number of participants ({num_participants}) exceeds room capacity ({room['capacity']}).")

        # Check time conflict
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
            return render_template("faculty/booking_form.html", rooms=rooms, form=request.form)

        cursor.execute(
            """INSERT INTO room_bookings (booking_id,room_id,requested_by,booking_date,start_time,end_time,purpose,num_participants,status)
               VALUES (bookings_seq.NEXTVAL,:rid,:user_id,TO_DATE(:dt,'YYYY-MM-DD'),:st,:et,:purpose,:num,'PENDING')""",
            {"rid": int(room_id), "user_id": user["user_id"], "dt": booking_date,
             "st": start_time, "et": end_time, "purpose": purpose, "num": int(num_participants)})
        db.commit()
        cursor.close()
        flash("Booking request submitted.", "success")
        return redirect(url_for("faculty.bookings_list"))

    rooms = fetch_all(cursor, "SELECT * FROM rooms WHERE is_active=1 ORDER BY building, room_number")
    cursor.close()
    return render_template("faculty/booking_form.html", rooms=rooms, form=request.args)


@faculty_bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@faculty_required
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
    return redirect(url_for("faculty.bookings_list"))


# ── COMPLAINTS ──────────────────────────────────────────────
@faculty_bp.route("/complaints")
@faculty_required
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
    return render_template("faculty/complaints.html", complaints=complaints)


@faculty_bp.route("/complaints/create", methods=["GET", "POST"])
@faculty_required
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
            return render_template("faculty/complaint_form.html", rooms=rooms, form=request.form)

        rid = int(room_id) if room_id else None
        cursor.execute(
            """INSERT INTO complaints (complaint_id,submitted_by,room_id,category,title,description,priority,status)
               VALUES (complaints_seq.NEXTVAL,:user_id,:rid,:cat,:title,:description,:pri,'OPEN')""",
            {"user_id": user["user_id"], "rid": rid, "cat": category, "title": title, "description": description, "pri": priority})
        db.commit()
        cursor.close()
        flash("Complaint submitted.", "success")
        return redirect(url_for("faculty.complaints_list"))

    rooms = fetch_all(cursor, "SELECT * FROM rooms WHERE is_active=1 ORDER BY building, room_number")
    cursor.close()
    return render_template("faculty/complaint_form.html", rooms=rooms, form={})
