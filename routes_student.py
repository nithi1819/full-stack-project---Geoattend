"""Student routes module."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from utils_decorators import student_required, login_required
from utils_database import get_db
from utils_auth import get_current_user
from utils_qr import parse_qr_data, is_qr_expired
from datetime import datetime

student_bp = Blueprint('student', __name__, url_prefix='/student')


@student_bp.route('/dashboard')
@student_required
def dashboard():
    """Student dashboard."""
    user = get_current_user()
    stats = {}
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get student attendance percentage
        cursor.execute("""
            SELECT COUNT(*) as total_sessions,
                   SUM(CASE WHEN ar.attendance_id IS NOT NULL THEN 1 ELSE 0 END) as attended
            FROM attendance_sessions s
            LEFT JOIN attendance_records ar ON s.session_id = ar.session_id AND ar.student_id = :user_id
            WHERE s.session_status = 'CLOSED'
        """, {'user_id': user['user_id']})
        
        result = cursor.fetchone()
        if result and result[0] > 0:
            stats['attendance_percentage'] = (result[1] / result[0]) * 100
        else:
            stats['attendance_percentage'] = 0
        
        # Get pending complaints
        cursor.execute("""
            SELECT COUNT(*) FROM complaints
            WHERE user_id = :user_id AND complaint_status = 'OPEN'
        """, {'user_id': user['user_id']})
        stats['pending_complaints'] = cursor.fetchone()[0]
        
        # Get active room bookings
        cursor.execute("""
            SELECT COUNT(*) FROM room_bookings
            WHERE requested_by = :user_id AND booking_status = 'APPROVED'
        """, {'user_id': user['user_id']})
        stats['active_bookings'] = cursor.fetchone()[0]
        
        cursor.close()
    
    except Exception as e:
        print(f"Student dashboard error: {e}")
    
    return render_template('student/dashboard.html', stats=stats)


@student_bp.route('/attendance')
@student_required
def attendance_history():
    """View attendance history."""
    user = get_current_user()
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT s.session_id, s.session_name, s.session_start, 
                   CASE WHEN ar.attendance_id IS NOT NULL THEN 'Present' ELSE 'Absent' END as status
            FROM attendance_sessions s
            LEFT JOIN attendance_records ar ON s.session_id = ar.session_id AND ar.student_id = :user_id
            WHERE s.session_status = 'CLOSED'
            ORDER BY s.session_start DESC
        """, {'user_id': user['user_id']})
        
        records = cursor.fetchall()
        cursor.close()
        
        return render_template('student/attendance.html', attendance_records=records)
    
    except Exception as e:
        print(f"Attendance history error: {e}")
        flash('Error loading attendance', 'error')
        return render_template('student/attendance.html', attendance_records=[])


@student_bp.route('/attendance/scan', methods=['GET', 'POST'])
@student_required
def scan_attendance():
    """Scan QR code for attendance marking."""
    user = get_current_user()
    
    if request.method == 'POST':
        qr_data = request.form.get('qr_data', '').strip()
        device_id = request.form.get('device_id', '').strip()
        
        if not qr_data:
            flash('QR code data required', 'error')
            return render_template('student/scan_attendance.html')
        
        try:
            # Parse QR data
            parsed = parse_qr_data(qr_data)
            
            if not parsed:
                flash('Invalid QR code format', 'error')
                return render_template('student/scan_attendance.html')
            
            # Check if QR expired
            if is_qr_expired(parsed['timestamp']):
                flash('QR code has expired', 'error')
                return render_template('student/scan_attendance.html')
            
            session_id = int(parsed['session_id'])
            
            db = get_db()
            cursor = db.cursor()
            
            # Check if already marked present
            cursor.execute("""
                SELECT attendance_id FROM attendance_records
                WHERE session_id = :session_id AND student_id = :student_id
            """, {'session_id': session_id, 'student_id': user['user_id']})
            
            if cursor.fetchone():
                flash('You are already marked present for this session', 'info')
                cursor.close()
                return render_template('student/scan_attendance.html')
            
            # Check device binding (one device can only scan once)
            cursor.execute("""
                SELECT ar.attendance_id FROM attendance_records ar
                WHERE ar.device_id = :device_id AND ar.session_id = :session_id
            """, {'device_id': device_id, 'session_id': session_id})
            
            if cursor.fetchone():
                flash('This device has already been used to mark attendance in this session', 'error')
                cursor.close()
                return render_template('student/scan_attendance.html')
            
            # Mark attendance
            cursor.execute("""
                INSERT INTO attendance_records
                (attendance_id, session_id, student_id, device_id, marked_at, marking_method)
                VALUES (attendance_records_seq.NEXTVAL, :session_id, :student_id, :device_id, SYSDATE, 'QR_SCAN')
            """, {
                'session_id': session_id,
                'student_id': user['user_id'],
                'device_id': device_id
            })
            
            db.commit()
            cursor.close()
            
            flash('Attendance marked successfully!', 'success')
            return redirect(url_for('student.attendance_history'))
        
        except Exception as e:
            print(f"Scan error: {e}")
            flash('Error marking attendance', 'error')
    
    return render_template('student/scan_attendance.html')


@student_bp.route('/room-booking')
@student_required
def book_room():
    """Book a room."""
    user = get_current_user()
    
    if request.method == 'POST':
        room_id = request.form.get('room_id')
        booking_date = request.form.get('booking_date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        
        if not all([room_id, booking_date, start_time, end_time]):
            flash('All fields required', 'error')
            return render_template('student/book_room.html')
        
        try:
            db = get_db()
            cursor = db.cursor()
            
            # Check for booking conflicts
            cursor.execute("""
                SELECT booking_id FROM room_bookings
                WHERE room_id = :room_id AND booking_date = :date
                AND booking_status IN ('APPROVED', 'PENDING')
                AND (
                    (start_time < :end_time AND end_time > :start_time)
                )
            """, {
                'room_id': room_id,
                'date': booking_date,
                'start_time': start_time,
                'end_time': end_time
            })
            
            if cursor.fetchone():
                flash('Room is not available for the selected time slot', 'error')
                cursor.close()
                return render_template('student/book_room.html')
            
            # Create booking
            cursor.execute("""
                INSERT INTO room_bookings
                (booking_id, room_id, requested_by, booking_date, start_time, end_time, booking_status)
                VALUES (room_bookings_seq.NEXTVAL, :room_id, :user_id, :date, :start, :end, 'PENDING')
            """, {
                'room_id': room_id,
                'user_id': user['user_id'],
                'date': booking_date,
                'start': start_time,
                'end': end_time
            })
            
            db.commit()
            cursor.close()
            
            flash('Room booking request submitted!', 'success')
            return redirect(url_for('student.view_bookings'))
        
        except Exception as e:
            print(f"Booking error: {e}")
            flash('Error creating booking', 'error')
    
    # Get available rooms
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT room_id, room_name, room_capacity, room_type
            FROM rooms
            WHERE room_status = 'ACTIVE'
            ORDER BY room_name
        """)
        
        rooms = cursor.fetchall()
        cursor.close()
        
        return render_template('student/book_room.html', rooms=rooms)
    
    except Exception as e:
        print(f"Room list error: {e}")
        return render_template('student/book_room.html', rooms=[])


@student_bp.route('/bookings')
@student_required
def view_bookings():
    """View student bookings."""
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
            ORDER BY rb.booking_date DESC
        """, {'user_id': user['user_id']})
        
        bookings = cursor.fetchall()
        cursor.close()
        
        return render_template('student/bookings.html', bookings=bookings)
    
    except Exception as e:
        print(f"Bookings view error: {e}")
        flash('Error loading bookings', 'error')
        return render_template('student/bookings.html', bookings=[])


@student_bp.route('/complaints', methods=['GET', 'POST'])
@student_required
def complaints():
    """Submit facility complaints."""
    user = get_current_user()
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()
        location = request.form.get('location', '').strip()
        
        if not all([title, description, category]):
            flash('Title, description, and category required', 'error')
            return render_template('student/complaints.html', complaint_form=True)
        
        try:
            db = get_db()
            cursor = db.cursor()
            
            cursor.execute("""
                INSERT INTO complaints
                (complaint_id, user_id, complaint_title, complaint_description, complaint_category,
                 complaint_location, complaint_status, created_at)
                VALUES (complaints_seq.NEXTVAL, :user_id, :title, :desc, :cat, :loc, 'OPEN', SYSDATE)
            """, {
                'user_id': user['user_id'],
                'title': title,
                'desc': description,
                'cat': category,
                'loc': location
            })
            
            db.commit()
            cursor.close()
            
            flash('Complaint submitted successfully!', 'success')
            return redirect(url_for('student.view_complaints'))
        
        except Exception as e:
            print(f"Complaint submission error: {e}")
            flash('Error submitting complaint', 'error')
    
    # GET: Show complaints list
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT c.complaint_id, c.complaint_title, c.complaint_category, c.complaint_status, c.created_at
            FROM complaints c
            WHERE c.user_id = :user_id
            ORDER BY c.created_at DESC
        """, {'user_id': user['user_id']})
        
        user_complaints = cursor.fetchall()
        cursor.close()
        
        return render_template('student/complaints.html', complaints=user_complaints, complaint_form=True)
    
    except Exception as e:
        print(f"Complaints view error: {e}")
        return render_template('student/complaints.html', complaints=[], complaint_form=True)


@student_bp.route('/complaints/<int:complaint_id>')
@student_required
def complaint_detail(complaint_id):
    """View complaint details."""
    user = get_current_user()
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT c.complaint_id, c.complaint_title, c.complaint_description, c.complaint_category,
                   c.complaint_location, c.complaint_status, c.created_at, c.updated_at
            FROM complaints c
            WHERE c.complaint_id = :complaint_id AND c.user_id = :user_id
        """, {'complaint_id': complaint_id, 'user_id': user['user_id']})
        
        complaint = cursor.fetchone()
        
        if complaint:
            return render_template('student/complaint_detail.html', complaint=complaint)
        else:
            flash('Complaint not found', 'error')
    
    except Exception as e:
        print(f"Complaint detail error: {e}")
        flash('Error loading complaint', 'error')
    
    return redirect(url_for('student.complaints'))
