"""Authentication routes."""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils_auth import hash_password, verify_password, login_user, logout_user, is_authenticated, get_current_user, generate_token
from utils_database import get_db
import re

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Username and password required', 'error')
            return render_template('auth/login.html')
        
        try:
            db = get_db()
            if not db:
                flash('Database connection failed', 'error')
                return render_template('auth/login.html')
            
            cursor = db.cursor()
            cursor.execute("""
                SELECT u.user_id, u.username, u.password_hash, r.role_name, r.role_id
                FROM users u
                JOIN roles r ON u.role_id = r.role_id
                WHERE u.username = :username AND u.user_status = 'ACTIVE'
            """, {'username': username})
            
            user = cursor.fetchone()
            cursor.close()
            
            if user and verify_password(user[2], password):
                login_user(user[0], user[1], user[4], user[3])
                flash(f'Welcome, {user[1]}!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid username or password', 'error')
        
        except Exception as e:
            print(f"Login error: {e}")
            flash('Login failed', 'error')
    
    if is_authenticated():
        return redirect(url_for('index'))
    
    return render_template('auth/login.html')


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """User registration."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        full_name = request.form.get('full_name', '').strip()
        
        # Validation
        if not all([username, email, password, full_name]):
            flash('All fields required', 'error')
            return render_template('auth/signup.html')
        
        if len(username) < 3:
            flash('Username must be at least 3 characters', 'error')
            return render_template('auth/signup.html')
        
        if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email):
            flash('Invalid email format', 'error')
            return render_template('auth/signup.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters', 'error')
            return render_template('auth/signup.html')
        
        if password != password_confirm:
            flash('Passwords do not match', 'error')
            return render_template('auth/signup.html')
        
        try:
            db = get_db()
            if not db:
                flash('Database connection failed', 'error')
                return render_template('auth/signup.html')
            
            cursor = db.cursor()
            
            # Check if user exists
            cursor.execute("SELECT user_id FROM users WHERE username = :username", {'username': username})
            if cursor.fetchone():
                flash('Username already exists', 'error')
                cursor.close()
                return render_template('auth/signup.html')
            
            # Insert new user (student role by default, role_id = 4)
            pwd_hash = hash_password(password)
            cursor.execute("""
                INSERT INTO users (user_id, role_id, department_id, full_name, username, email, password_hash, user_status)
                VALUES (users_seq.NEXTVAL, 4, 1, :name, :username, :email, :pwd, 'ACTIVE')
            """, {'name': full_name, 'username': username, 'email': email, 'pwd': pwd_hash})
            
            db.commit()
            cursor.close()
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))
        
        except Exception as e:
            print(f"Signup error: {e}")
            flash('Registration failed', 'error')
    
    if is_authenticated():
        return redirect(url_for('index'))
    
    return render_template('auth/signup.html')


@auth_bp.route('/logout')
def logout():
    """User logout."""
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile')
def profile():
    """View user profile."""
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))
    
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT u.user_id, u.full_name, u.email, u.phone, u.employee_id, 
                   d.dept_name, r.role_name
            FROM users u
            LEFT JOIN departments d ON u.department_id = d.dept_id
            JOIN roles r ON u.role_id = r.role_id
            WHERE u.user_id = :user_id
        """, {'user_id': user['user_id']})
        
        profile_data = cursor.fetchone()
        cursor.close()
        
        if profile_data:
            return render_template('auth/profile.html', 
                profile={
                    'user_id': profile_data[0],
                    'full_name': profile_data[1],
                    'email': profile_data[2],
                    'phone': profile_data[3],
                    'employee_id': profile_data[4],
                    'department': profile_data[5],
                    'role': profile_data[6]
                }
            )
    
    except Exception as e:
        print(f"Profile error: {e}")
        flash('Could not load profile', 'error')
    
    return render_template('auth/profile.html')
