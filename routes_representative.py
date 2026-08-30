"""Representative routes module."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils_decorators import representative_required
from utils_database import get_db
from utils_auth import get_current_user

representative_bp = Blueprint('representative', __name__, url_prefix='/representative')


@representative_bp.route('/dashboard')
@representative_required
def dashboard():
    """Representative dashboard."""
    user = get_current_user()
    stats = {}
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get assigned class attendance percentage
        cursor.execute("""
            SELECT COUNT(DISTINCT s.session_id) as total_sessions,
                   COUNT(DISTINCT ar.attendance_id) as total_attendance
            FROM attendance_sessions s
            LEFT JOIN attendance_records ar ON s.session_id = ar.session_id
            WHERE s.session_status = 'CLOSED'
        """)
        
        result = cursor.fetchone()
        if result and result[0] > 0:
            stats['class_attendance_percentage'] = (result[1] / result[0]) * 100 if result[0] > 0 else 0
        else:
            stats['class_attendance_percentage'] = 0
        
        # Get class size
        cursor.execute("""
            SELECT COUNT(*) FROM students
        """)
        stats['class_size'] = cursor.fetchone()[0]
        
        # Get pending complaints for the class
        cursor.execute("""
            SELECT COUNT(*) FROM complaints
            WHERE complaint_status = 'OPEN'
        """)
        stats['pending_complaints'] = cursor.fetchone()[0]
        
        cursor.close()
    
    except Exception as e:
        print(f"Representative dashboard error: {e}")
    
    return render_template('representative/dashboard.html', stats=stats)


@representative_bp.route('/class-attendance')
@representative_required
def class_attendance():
    """View class attendance overview."""
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get attendance summary for each student
        cursor.execute("""
            SELECT u.user_id, u.full_name, s.student_number,
                   COUNT(DISTINCT ats.session_id) as total_sessions,
                   COUNT(DISTINCT ar.attendance_id) as attended_sessions,
                   ROUND(COUNT(DISTINCT ar.attendance_id) * 100.0 / 
                         NULLIF(COUNT(DISTINCT ats.session_id), 0), 2) as attendance_percentage
            FROM users u
            JOIN students s ON u.user_id = s.user_id
            LEFT JOIN attendance_sessions ats ON ats.session_status = 'CLOSED'
            LEFT JOIN attendance_records ar ON ats.session_id = ar.session_id AND ar.student_id = u.user_id
            GROUP BY u.user_id, u.full_name, s.student_number
            ORDER BY attendance_percentage ASC
        """)
        
        students = cursor.fetchall()
        cursor.close()
        
        return render_template('representative/class_attendance.html', students=students)
    
    except Exception as e:
        print(f"Class attendance error: {e}")
        flash('Error loading class attendance', 'error')
        return render_template('representative/class_attendance.html', students=[])


@representative_bp.route('/room-bookings')
@representative_required
def room_bookings():
    """View room bookings for class."""
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT rb.booking_id, r.room_name, u.full_name, rb.booking_date, 
                   rb.start_time, rb.end_time, rb.booking_status
            FROM room_bookings rb
            JOIN rooms r ON rb.room_id = r.room_id
            JOIN users u ON rb.requested_by = u.user_id
            ORDER BY rb.booking_date DESC
        """)
        
        bookings = cursor.fetchall()
        cursor.close()
        
        return render_template('representative/room_bookings.html', bookings=bookings)
    
    except Exception as e:
        print(f"Room bookings error: {e}")
        flash('Error loading room bookings', 'error')
        return render_template('representative/room_bookings.html', bookings=[])


@representative_bp.route('/complaints')
@representative_required
def complaints():
    """View complaints for class."""
    try:
        db = get_db()
        cursor = db.cursor()
        
        status = request.args.get('status', '').strip()
        
        query = """
            SELECT c.complaint_id, c.complaint_title, c.complaint_category, 
                   c.complaint_status, u.full_name, c.created_at
            FROM complaints c
            JOIN users u ON c.user_id = u.user_id
            WHERE 1=1
        """
        params = {}
        
        if status:
            query += " AND c.complaint_status = :status"
            params['status'] = status
        
        query += " ORDER BY c.created_at DESC"
        
        cursor.execute(query, params)
        complaints_list = cursor.fetchall()
        cursor.close()
        
        return render_template('representative/complaints.html', 
                             complaints=complaints_list, status=status)
    
    except Exception as e:
        print(f"Complaints error: {e}")
        flash('Error loading complaints', 'error')
        return render_template('representative/complaints.html', complaints=[])


@representative_bp.route('/complaint/<int:complaint_id>')
@representative_required
def complaint_detail(complaint_id):
    """View complaint details."""
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT c.complaint_id, c.complaint_title, c.complaint_description, 
                   c.complaint_category, c.complaint_location, c.complaint_status,
                   u.full_name, c.created_at, c.updated_at
            FROM complaints c
            JOIN users u ON c.user_id = u.user_id
            WHERE c.complaint_id = :complaint_id
        """, {'complaint_id': complaint_id})
        
        complaint = cursor.fetchone()
        cursor.close()
        
        if complaint:
            return render_template('representative/complaint_detail.html', complaint=complaint)
        else:
            flash('Complaint not found', 'error')
    
    except Exception as e:
        print(f"Complaint detail error: {e}")
        flash('Error loading complaint', 'error')
    
    return redirect(url_for('representative.complaints'))


@representative_bp.route('/od-requests')
@representative_required
def od_requests():
    """View On-Duty requests (bulk OD for groups)."""
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT od.od_id, od.od_title, od.od_type, od.approval_status, 
                   od.created_at, COUNT(DISTINCT ods.student_id) as student_count
            FROM od_requests od
            LEFT JOIN od_students ods ON od.od_id = ods.od_id
            GROUP BY od.od_id, od.od_title, od.od_type, od.approval_status, od.created_at
            ORDER BY od.created_at DESC
        """)
        
        od_list = cursor.fetchall()
        cursor.close()
        
        return render_template('representative/od_requests.html', od_requests=od_list)
    
    except Exception as e:
        print(f"OD requests error: {e}")
        flash('Error loading OD requests', 'error')
        return render_template('representative/od_requests.html', od_requests=[])


@representative_bp.route('/submit-od', methods=['GET', 'POST'])
@representative_required
def submit_od():
    """Submit bulk On-Duty request for class/group."""
    if request.method == 'POST':
        od_title = request.form.get('od_title', '').strip()
        od_type = request.form.get('od_type', '').strip()
        od_reason = request.form.get('od_reason', '').strip()
        od_date_start = request.form.get('od_date_start')
        od_date_end = request.form.get('od_date_end')
        
        if not all([od_title, od_type, od_date_start]):
            flash('Required fields missing', 'error')
            return render_template('representative/submit_od.html')
        
        try:
            db = get_db()
            cursor = db.cursor()
            
            # Insert OD request
            cursor.execute("""
                INSERT INTO od_requests
                (od_id, od_title, od_type, od_reason, od_date_start, od_date_end, approval_status)
                VALUES (od_requests_seq.NEXTVAL, :title, :type, :reason, :start, :end, 'PENDING')
            """, {
                'title': od_title,
                'type': od_type,
                'reason': od_reason,
                'start': od_date_start,
                'end': od_date_end
            })
            
            db.commit()
            cursor.close()
            
            flash('OD request submitted!', 'success')
            return redirect(url_for('representative.od_requests'))
        
        except Exception as e:
            print(f"OD submission error: {e}")
            flash('Error submitting OD request', 'error')
    
    return render_template('representative/submit_od.html')
