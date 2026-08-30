"""Admin routes module."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from utils_decorators import admin_required, login_required
from utils_database import get_db
from utils_auth import get_current_user, hash_password
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Admin dashboard with system statistics."""
    user = get_current_user()
    stats = {}
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get total users
        cursor.execute("SELECT COUNT(*) FROM users")
        stats['total_users'] = cursor.fetchone()[0]
        
        # Get user breakdown by role
        cursor.execute("""
            SELECT r.role_name, COUNT(*) as count
            FROM users u
            JOIN roles r ON u.role_id = r.role_id
            GROUP BY r.role_name
        """)
        stats['users_by_role'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Get total rooms
        cursor.execute("SELECT COUNT(*) FROM rooms WHERE room_status = 'ACTIVE'")
        stats['total_rooms'] = cursor.fetchone()[0]
        
        # Get total bookings
        cursor.execute("SELECT COUNT(*) FROM room_bookings WHERE booking_status IN ('APPROVED', 'PENDING')")
        stats['active_bookings'] = cursor.fetchone()[0]
        
        # Get pending complaints
        cursor.execute("SELECT COUNT(*) FROM complaints WHERE complaint_status = 'OPEN'")
        stats['pending_complaints'] = cursor.fetchone()[0]
        
        cursor.close()
    
    except Exception as e:
        print(f"Dashboard error: {e}")
        flash('Error loading dashboard', 'error')
    
    return render_template('admin/dashboard.html', stats=stats)


@admin_bp.route('/users')
@admin_required
def users_list():
    """List all users."""
    try:
        db = get_db()
        cursor = db.cursor()
        
        search = request.args.get('search', '').strip()
        role_filter = request.args.get('role', '').strip()
        
        query = """
            SELECT u.user_id, u.username, u.full_name, u.email, r.role_name, u.user_status
            FROM users u
            JOIN roles r ON u.role_id = r.role_id
            WHERE 1=1
        """
        params = {}
        
        if search:
            query += " AND (u.username LIKE :search OR u.full_name LIKE :search OR u.email LIKE :search)"
            params['search'] = f"%{search}%"
        
        if role_filter:
            query += " AND r.role_name = :role"
            params['role'] = role_filter
        
        query += " ORDER BY u.user_id DESC"
        
        cursor.execute(query, params)
        users = cursor.fetchall()
        
        cursor.close()
        
        return render_template('admin/users.html', users=users, search=search, role_filter=role_filter)
    
    except Exception as e:
        print(f"Users list error: {e}")
        flash('Error loading users', 'error')
        return render_template('admin/users.html', users=[])


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """Edit user details."""
    try:
        db = get_db()
        cursor = db.cursor()
        
        if request.method == 'POST':
            full_name = request.form.get('full_name', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            status = request.form.get('status', 'ACTIVE')
            
            cursor.execute("""
                UPDATE users
                SET full_name = :name, email = :email, phone = :phone, user_status = :status
                WHERE user_id = :user_id
            """, {'name': full_name, 'email': email, 'phone': phone, 'status': status, 'user_id': user_id})
            
            db.commit()
            cursor.close()
            
            flash('User updated successfully', 'success')
            return redirect(url_for('admin.users_list'))
        
        # GET: Show form
        cursor.execute("""
            SELECT u.user_id, u.full_name, u.email, u.phone, u.user_status, r.role_name
            FROM users u
            JOIN roles r ON u.role_id = r.role_id
            WHERE u.user_id = :user_id
        """, {'user_id': user_id})
        
        user = cursor.fetchone()
        cursor.close()
        
        if user:
            return render_template('admin/edit_user.html', user={
                'user_id': user[0],
                'full_name': user[1],
                'email': user[2],
                'phone': user[3],
                'status': user[4],
                'role': user[5]
            })
    
    except Exception as e:
        print(f"Edit user error: {e}")
        flash('Error editing user', 'error')
    
    return redirect(url_for('admin.users_list'))


@admin_bp.route('/complaints')
@admin_required
def complaints():
    """Manage facility complaints."""
    try:
        db = get_db()
        cursor = db.cursor()
        
        status_filter = request.args.get('status', '').strip()
        
        query = """
            SELECT c.complaint_id, c.complaint_title, c.complaint_category, c.complaint_status,
                   u.full_name, c.created_at, c.updated_at
            FROM complaints c
            JOIN users u ON c.user_id = u.user_id
            WHERE 1=1
        """
        params = {}
        
        if status_filter:
            query += " AND c.complaint_status = :status"
            params['status'] = status_filter
        
        query += " ORDER BY c.updated_at DESC"
        
        cursor.execute(query, params)
        complaints_list = cursor.fetchall()
        
        cursor.close()
        
        return render_template('admin/complaints.html', complaints=complaints_list, status_filter=status_filter)
    
    except Exception as e:
        print(f"Complaints error: {e}")
        flash('Error loading complaints', 'error')
        return render_template('admin/complaints.html', complaints=[])


@admin_bp.route('/rooms')
@admin_required
def rooms():
    """Manage facilities/rooms."""
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT room_id, room_name, room_capacity, room_type, room_status
            FROM rooms
            ORDER BY room_id
        """)
        rooms_list = cursor.fetchall()
        
        cursor.close()
        
        return render_template('admin/rooms.html', rooms=rooms_list)
    
    except Exception as e:
        print(f"Rooms error: {e}")
        flash('Error loading rooms', 'error')
        return render_template('admin/rooms.html', rooms=[])


@admin_bp.route('/reports/attendance')
@admin_required
def attendance_reports():
    """Generate attendance reports."""
    return render_template('admin/reports_attendance.html')


@admin_bp.route('/reports/bookings')
@admin_required
def booking_reports():
    """Generate booking reports."""
    return render_template('admin/reports_bookings.html')
