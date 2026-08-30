"""Faculty routes module."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from utils_decorators import faculty_required
from utils_database import get_db
from utils_auth import get_current_user
from utils_qr import generate_qr_code, generate_qr_data, generate_attendance_token
from datetime import datetime, timedelta

faculty_bp = Blueprint('faculty', __name__, url_prefix='/faculty')


@faculty_bp.route('/dashboard')
@faculty_required
def dashboard():
    """Faculty dashboard."""
    user = get_current_user()
    stats = {}
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get faculty attendance sessions
        cursor.execute("""
            SELECT COUNT(*) FROM attendance_sessions
            WHERE faculty_id = :user_id AND session_status = 'ACTIVE'
        """, {'user_id': user['user_id']})
        stats['active_sessions'] = cursor.fetchone()[0]
        
        # Get pending OD requests
        cursor.execute("""
            SELECT COUNT(*) FROM od_requests
            WHERE assigned_to = :user_id AND approval_status = 'PENDING'
        """, {'user_id': user['user_id']})
        stats['pending_od_requests'] = cursor.fetchone()[0]
        
        # Get room bookings
        cursor.execute("""
            SELECT COUNT(*) FROM room_bookings
            WHERE requested_by = :user_id AND booking_status IN ('APPROVED', 'PENDING')
        """, {'user_id': user['user_id']})
        stats['active_bookings'] = cursor.fetchone()[0]
        
        cursor.close()
    
    except Exception as e:
        print(f"Faculty dashboard error: {e}")
    
    return render_template('faculty/dashboard.html', stats=stats)


@faculty_bp.route('/attendance/create-session', methods=['GET', 'POST'])
@faculty_required
def create_attendance_session():
    """Create new attendance session with QR code."""
    user = get_current_user()
    
    if request.method == 'POST':
        session_name = request.form.get('session_name', '').strip()
        duration_minutes = request.form.get('duration_minutes', '30')
        
        if not session_name:
            flash('Session name required', 'error')
            return render_template('faculty/create_session.html')
        
        try:
            db = get_db()
            cursor = db.cursor()
            
            session_token = generate_attendance_token()
            session_start = datetime.now()
            session_end = session_start + timedelta(minutes=int(duration_minutes))
            
            cursor.execute("""
                INSERT INTO attendance_sessions
                (session_id, faculty_id, session_name, session_token, session_start, session_end, session_status)
                VALUES (attendance_sessions_seq.NEXTVAL, :faculty_id, :name, :token, :start, :end, 'ACTIVE')
            """, {
                'faculty_id': user['user_id'],
                'name': session_name,
                'token': session_token,
                'start': session_start,
                'end': session_end
            })
            
            db.commit()
            cursor.close()
            
            flash('Attendance session created successfully', 'success')
            return redirect(url_for('faculty.view_sessions'))
        
        except Exception as e:
            print(f"Session creation error: {e}")
            flash('Error creating session', 'error')
    
    return render_template('faculty/create_session.html')


@faculty_bp.route('/attendance/sessions')
@faculty_required
def view_sessions():
    """View attendance sessions."""
    user = get_current_user()
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT s.session_id, s.session_name, s.session_token, s.session_start, 
                   s.session_end, s.session_status, COUNT(ar.attendance_id) as attendance_count
            FROM attendance_sessions s
            LEFT JOIN attendance_records ar ON s.session_id = ar.session_id
            WHERE s.faculty_id = :user_id
            GROUP BY s.session_id, s.session_name, s.session_token, s.session_start, 
                     s.session_end, s.session_status
            ORDER BY s.session_start DESC
        """, {'user_id': user['user_id']})
        
        sessions = cursor.fetchall()
        cursor.close()
        
        return render_template('faculty/sessions.html', sessions=sessions)
    
    except Exception as e:
        print(f"Sessions view error: {e}")
        flash('Error loading sessions', 'error')
        return render_template('faculty/sessions.html', sessions=[])


@faculty_bp.route('/attendance/session/<int:session_id>')
@faculty_required
def session_details(session_id):
    """View session details and attendance records."""
    user = get_current_user()
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get session details
        cursor.execute("""
            SELECT s.session_id, s.session_name, s.session_token, s.session_start, 
                   s.session_end, s.session_status
            FROM attendance_sessions s
            WHERE s.session_id = :session_id AND s.faculty_id = :faculty_id
        """, {'session_id': session_id, 'faculty_id': user['user_id']})
        
        session = cursor.fetchone()
        
        if not session:
            flash('Session not found', 'error')
            return redirect(url_for('faculty.view_sessions'))
        
        # Generate QR code
        qr_data = generate_qr_data(session_id, session[2])
        qr_code = generate_qr_code(qr_data)
        
        # Get attendance records
        cursor.execute("""
            SELECT ar.attendance_id, st.student_number, u.full_name, ar.marked_at, ar.marking_method
            FROM attendance_records ar
            JOIN students st ON ar.student_id = st.user_id
            JOIN users u ON st.user_id = u.user_id
            WHERE ar.session_id = :session_id
            ORDER BY ar.marked_at DESC
        """, {'session_id': session_id})
        
        records = cursor.fetchall()
        cursor.close()
        
        return render_template('faculty/session_details.html', 
            session=session, 
            qr_code=qr_code,
            attendance_records=records
        )
    
    except Exception as e:
        print(f"Session details error: {e}")
        flash('Error loading session details', 'error')
        return redirect(url_for('faculty.view_sessions'))


@faculty_bp.route('/room-bookings')
@faculty_required
def room_bookings():
    """View faculty room bookings."""
    user = get_current_user()
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT rb.booking_id, r.room_name, rb.booking_date, rb.start_time, 
                   rb.end_time, rb.booking_status
            FROM room_bookings rb
            JOIN rooms r ON rb.room_id = r.room_id
            WHERE rb.requested_by = :user_id
            ORDER BY rb.booking_date DESC, rb.start_time DESC
        """, {'user_id': user['user_id']})
        
        bookings = cursor.fetchall()
        cursor.close()
        
        return render_template('faculty/room_bookings.html', bookings=bookings)
    
    except Exception as e:
        print(f"Room bookings error: {e}")
        flash('Error loading bookings', 'error')
        return render_template('faculty/room_bookings.html', bookings=[])
