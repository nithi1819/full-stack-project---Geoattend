# QUICK REFERENCE GUIDE - Campus Connect

##  5-MINUTE QUICK START

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Ensure .env configured with correct DSN
# ORACLE_DSN=localhost:1521/XEPDB1 (NOT localhost/XEPDB1)

# 4. Run application
python app.py

# 5. Open browser
# http://127.0.0.1:5000
```

---

##  LOGIN CREDENTIALS

```
Admin:     admin / Admin@123
Faculty:   faculty1 / Faculty@123
Student:   student1 / Student@123
Rep:       rep1 / Rep@123
```

---

##  FILE PLACEMENT

```
Copy these files to project root:

 app_complete.py           → rename to → app.py
 config.py
 requirements.txt
 .env

Create utils/ directory:
 utils_database.py         → utils/database.py
 utils_auth.py            → utils/auth.py
 utils_decorators.py      → utils/decorators.py
 utils_qr.py              → utils/qr.py

Create routes/ directory:
 routes_auth.py           → routes/auth.py
 routes_admin.py          → routes/admin.py
 routes_faculty.py        → routes/faculty.py
 routes_student.py        → routes/student.py
 routes_representative.py → routes/representative.py

Create database/ directory:
 database_schema.sql      → database/schema.sql
```

---

##  CRITICAL CONFIGURATION

### Oracle DSN Format (MUST INCLUDE PORT)
```
 CORRECT:   localhost:1521/XEPDB1
 WRONG:     localhost/XEPDB1
 WRONG:     localhost:1521XEPDB1
```

### Environment Variables
```env
ORACLE_USER=system
ORACLE_PASSWORD=oracle123
ORACLE_DSN=localhost:1521/XEPDB1
SECRET_KEY=qr-attendance-secret-key-2026
FLASK_DEBUG=True
```

---

##  COMMON ERRORS & FIXES

| Error | Cause | Fix |
|-------|-------|-----|
| Connection refused | Oracle not running | Start: `lsnrctl start` |
| ORA-00955 | Tables exist already | Normal, app handles it |
| ModuleNotFoundError | Missing package | `pip install -r requirements.txt` |
| Port 5000 in use | Another process | `app.run(port=5001)` |
| DSN connection failed | Wrong DSN format | Add port: `localhost:1521/...` |

---

##  DATABASE SCHEMA

### Core Tables
- **ROLES** - Admin, Faculty, Student, Rep, Maintenance, Security
- **USERS** - All users with hashed passwords
- **STUDENTS** - Student records
- **FACULTY** - Faculty records
- **REPRESENTATIVES** - Rep records

### Features
- **ATTENDANCE_SESSIONS** - QR sessions created by faculty
- **ATTENDANCE_RECORDS** - Student scan records with device binding
- **ROOMS** - Facility/lab/classroom data
- **ROOM_BOOKINGS** - Booking requests with approval workflow
- **COMPLAINTS** - Facility complaints with status tracking
- **OD_REQUESTS** - On-duty requests for bulk groups
- **AUDIT_LOGS** - Complete audit trail

---

##  SECURITY FEATURES

-  Password hashing (pbkdf2:sha256)
-  SQL injection prevention (parameterized queries)
-  Session timeouts (30 minutes default)
-  Device binding (one device = one scan per session)
-  RBAC decorators (@admin_required, @faculty_required, etc.)
-  Audit logging of all actions
-  ORM/parameterized queries for all database access

---

##  FEATURES CHECKLIST

### Attendance System
- [x] Faculty creates QR sessions
- [x] Students scan QR to mark attendance
- [x] Device binding (prevent proxy attendance)
- [x] QR expiry after 30 minutes
- [x] Manual token entry option
- [x] Attendance percentage tracking
- [x] Defaulter alerts

### Room Booking
- [x] Real-time availability
- [x] Conflict detection
- [x] Approval workflow
- [x] Status tracking
- [x] Usage analytics

### Complaints
- [x] Submit facility complaints
- [x] Categorization
- [x] Priority levels
- [x] Assignment to maintenance
- [x] Status tracking with history

### On-Duty (OD)
- [x] Individual OD requests
- [x] Bulk OD for groups/teams
- [x] Teacher approval with remarks
- [x] Admin final approval
- [x] OD quota tracking

---

##  ROUTE STRUCTURE

### Authentication (`/auth`)
```
POST   /auth/login           - Login page
POST   /auth/signup          - Registration
GET    /auth/logout          - Logout
GET    /auth/profile         - User profile
```

### Admin (`/admin`)
```
GET    /admin/dashboard      - System statistics
GET    /admin/users          - User list
POST   /admin/users/<id>/edit- Edit user
GET    /admin/complaints     - Manage complaints
GET    /admin/rooms          - Manage rooms
GET    /admin/reports/*      - Generate reports
```

### Faculty (`/faculty`)
```
GET    /faculty/dashboard    - Faculty dashboard
POST   /faculty/attendance/create-session - Create QR
GET    /faculty/attendance/sessions - View sessions
GET    /faculty/attendance/session/<id> - QR + records
GET    /faculty/room-bookings - View bookings
```

### Student (`/student`)
```
GET    /student/dashboard    - Stats dashboard
GET    /student/attendance   - Attendance history
POST   /student/attendance/scan - QR scanner
POST   /student/room-booking - Book room
GET    /student/bookings     - View bookings
POST   /student/complaints   - Submit complaint
GET    /student/complaints/<id> - Complaint detail
```

### Representative (`/representative`)
```
GET    /representative/dashboard - Class stats
GET    /representative/class-attendance - Class attendance
GET    /representative/room-bookings - Class bookings
GET    /representative/complaints - Class complaints
POST   /representative/submit-od - Submit OD request
```

---

##  TESTING SCENARIOS

### Test 1: Complete Attendance Flow
1. Login as `faculty1`
2. Create attendance session → Get QR code
3. Logout, login as `student1`
4. Scan QR code (or enter token)
5. Verify attendance marked
6. Check attendance history

### Test 2: Room Booking Flow
1. Login as `student1`
2. Select room, date, time
3. Submit booking request
4. Logout, login as `admin`
5. Approve booking
6. Verify status changed

### Test 3: Complaint Flow
1. Login as `student1`
2. Submit complaint (AC broken, etc.)
3. Logout, login as `admin`
4. Assign to maintenance
5. Change status to "Resolved"
6. Verify history updated

### Test 4: Device Binding
1. Login as `faculty1`, create session
2. Login as `student1` (Browser 1), scan QR
3. In same Browser 1, try scanning again → Should fail
4. In different Browser 2, scan same QR → Should fail (same device)
5. Verify device binding works

---

##  CONFIGURATION OPTIONS

### Flask Configuration
```python
# In config.py or .env
SECRET_KEY              # Session encryption key
FLASK_DEBUG=True/False  # Debug mode
FLASK_ENV=development   # Environment
SESSION_TYPE            # filesystem (default)
PERMANENT_SESSION_LIFETIME # 1800 (30 minutes)
```

### QR Settings
```python
# In utils_qr.py
QR_EXPIRY_MINUTES = 30  # QR validity
QR_BOX_SIZE = 10        # QR size
QR_BORDER = 4           # QR border
```

### Database
```env
ORACLE_USER=system
ORACLE_PASSWORD=oracle123
ORACLE_DSN=localhost:1521/XEPDB1
```

---

##  PERFORMANCE TIPS

1. **Database Indexes** - Already created on:
   - users(username, email, role_id)
   - students(student_number)
   - attendance_records(session_id, student_id)
   - room_bookings(room_id, status, date)
   - complaints(user_id, status)

2. **Query Optimization** - Use parameterized queries (prevents SQL injection + better caching)

3. **Caching** - Implement Flask-Caching for:
   - Student lists
   - Available rooms
   - Attendance summaries

4. **Connection Pooling** - Oracle connection reused across requests

---

##  DEPLOYMENT PRODUCTION CHECKLIST

```
PRE-DEPLOYMENT
- [ ] Change SECRET_KEY to 32-char random string
- [ ] Update all demo passwords
- [ ] Set FLASK_DEBUG=False
- [ ] Set FLASK_ENV=production
- [ ] Configure HTTPS/SSL
- [ ] Set session storage to database
- [ ] Configure database backups
- [ ] Enable CORS if needed
- [ ] Set up logging to file
- [ ] Configure email for notifications

PRODUCTION ENV EXAMPLE
ORACLE_DSN=prod-db.example.com:1521/PROD_DB
ORACLE_USER=prod_user
ORACLE_PASSWORD=<strong-password>
SECRET_KEY=<32-char-random-key>
FLASK_DEBUG=False
FLASK_ENV=production
```

---

##  USEFUL COMMANDS

```bash
# Activate virtual environment
venv\Scripts\activate

# Install packages
pip install -r requirements.txt

# Run application
python app.py

# Run with specific port
python -c "from app import app; app.run(port=5001)"

# Test database connection
python -c "from utils_database import get_db; print(get_db())"

# Generate QR code
python -c "from utils_qr import generate_qr_code; print(generate_qr_code('test'))"

# Check Oracle connection
lsnrctl status
lsnrctl start
```

---

##  SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────┐
│           Flask Application                  │
│  (app.py - 320 lines)                       │
└────────────────┬────────────────────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
    ↓            ↓            ↓
┌─────────┐ ┌────────┐ ┌──────────┐
│ Routes  │ │ Utils  │ │Templates │
│  (725L) │ │ (295L) │ │(Jinja2)  │
└────┬────┘ └───┬────┘ └──────────┘
     │          │
     └─────┬────┘
           ↓
    ┌──────────────────┐
    │  Oracle Database │
    │  (16 tables)     │
    └──────────────────┘
```

---

##  VERIFICATION

Run these commands to verify setup:

```bash
# Test Python
python --version              # Should be 3.8+

# Test virtual environment
pip list                      # Should show Flask, oracledb, etc.

# Test imports
python -c "import flask; print(flask.__version__)"
python -c "import oracledb; print(oracledb.__version__)"

# Test database
python -c "from utils_database import get_db; db = get_db(); print(' DB OK' if db else ' DB Failed')"

# Start app
python app.py
# Should say: Starting Flask application...
# Access: http://127.0.0.1:5000
```

---

##  PRO TIPS

1. **Device ID for QR** - Use `request.headers.get('User-Agent')` to get device fingerprint
2. **Offline Sync** - Cache QR scans locally, sync when online
3. **Face Recognition** - Add OpenCV integration for secondary verification
4. **Push Notifications** - Integrate Firebase Cloud Messaging
5. **Analytics** - Use Tableau/Power BI for dashboards
6. **Mobile App** - Use React Native or Flutter for native mobile

---

##  SUPPORT MATRIX

| Issue | Check | Solution |
|-------|-------|----------|
| App won't start | Check .env | Verify ORACLE_DSN format with port |
| DB connection fails | Check Oracle | `lsnrctl status` / `lsnrctl start` |
| Import error | Check files | Verify routes/ and utils/ directories |
| Port in use | Check port | Change in app.py: `app.run(port=5001)` |
| Template not found | Check templates/ | Create missing HTML files |

---

##  QUICK CONTACTS

- **Oracle Issues:** https://docs.oracle.com/
- **Flask Docs:** https://flask.palletsprojects.com/
- **oracledb Docs:** https://python-oracledb.readthedocs.io/
- **Python:** https://www.python.org/

---

**Status:  READY TO DEPLOY**

Last Updated: 2026-08-30  
Version: 1.0  
Author: Development Team
