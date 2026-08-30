# QR Attendance, Room Booking & Facility Complaints Management System

A complete full-stack web application for managing QR-based attendance, room booking, and facility complaints in a college environment.

## Tech Stack

- **Backend:** Python 3.11+, Flask
- **Database:** Oracle Database XE (via `oracledb`)
- **Frontend:** HTML5, CSS3, Vanilla JavaScript, Jinja2 Templates
- **Auth:** Flask sessions + Werkzeug password hashing

## Features

- **4 Roles:** Admin, Faculty, Representative, Student
- **QR Attendance:** Faculty generates QR codes; students scan or enter tokens to mark attendance
- **Room Booking:** Book rooms with conflict detection; admin approval workflow
- **Facility Complaints:** Submit, assign, track, and resolve complaints
- **Audit Logs:** Track all important system actions
- **Dashboards:** Role-specific dashboards with real statistics
- **Search & Filter:** Full search, filter, and sort across all management pages

## Demo Accounts

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `Admin@123` |
| Faculty | `faculty1` | `Faculty@123` |
| Representative | `rep1` | `Rep@123` |
| Student | `student1` | `Student@123` |

## Prerequisites

1. **Python 3.11+** - Download from [python.org](https://www.python.org/downloads/)
2. **Oracle Database XE** - Download from [Oracle](https://www.oracle.com/database/technologies/xe-downloads.html)
3. **Oracle Instant Client** (optional, for thick mode) - [Download](https://www.oracle.com/database/technologies/instant-client.html)
4. **VSCode** - [Download](https://code.visualstudio.com/)

## Setup Instructions (Windows + VSCode)

### 1. Clone/Extract Project

```
# Open the project folder in VSCode
File > Open Folder > select the project directory
```

### 2. Create Python Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Oracle Database

Make sure Oracle Database XE is running. The default connection is:
- Host: `localhost`
- Port: `1521`
- Service: `XEPDB1`

#### Create a Database User (optional but recommended)

Open Oracle SQL*Plus or SQL Developer and run:

```sql
CREATE USER qr_attendance IDENTIFIED BY qr_attendance123;
GRANT CONNECT, RESOURCE TO qr_attendance;
ALTER USER qr_attendance QUOTA UNLIMITED ON USERS;
```

### 5. Create `.env` File

Create a `.env` file in the project root:

```
ORACLE_USER=qr_attendance
ORACLE_PASSWORD=qr_attendance123
ORACLE_DSN=localhost:1521/XEPDB1
SECRET_KEY=your-random-secret-key-here-change-this
```

### 6. Run the Application

```bash
python app.py
```

The application will:
1. Connect to Oracle Database
2. Create all tables, procedures, triggers, and seed data (first run only)
3. Create demo user accounts with hashed passwords
4. Start the Flask development server

### Phone QR scanning

QR links must use the computer's LAN address; `127.0.0.1` only works on the
computer running Flask. Find the computer's IPv4 address with `ipconfig`, then
set this in `.env`, for example:

```
PUBLIC_BASE_URL=http://192.168.1.20:5000
```

Run Flask with `python app.py`, keep the phone and computer on the same Wi-Fi
network, and allow Python through Windows Firewall if the phone cannot connect.

### 7. Open in Browser

Navigate to: **http://127.0.0.1:5000**

## Project Structure

```
qr_attendance/
├── app.py                    # Main Flask application
├── config.py                 # Configuration management
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variable template
├── README.md                 # This file
│
├── database/                 # Oracle SQL scripts
│   ├── schema.sql           # Tables, sequences, constraints, indexes, views
│   ├── procedures.sql       # PL/SQL stored procedures and functions
│   ├── triggers.sql         # Database triggers
│   ├── seed.sql             # Reference data (roles, departments, rooms)
│   └── setup.sql            # Master setup script
│
├── routes/                   # Flask Blueprints
│   ├── auth.py              # Login, signup, logout, profile
│   ├── admin.py             # Admin management pages
│   ├── faculty.py           # Faculty attendance & bookings
│   ├── representative.py    # Representative view-only access
│   └── student.py           # Student scan, attendance, bookings
│
├── utils/                    # Utility modules
│   ├── database.py          # Oracle DB connection & query helpers
│   ├── auth.py              # Password hashing, session management
│   ├── decorators.py        # Role-based access control decorators
│   └── qr.py                # QR code generation
│
├── templates/                # Jinja2 HTML templates
│   ├── base.html            # Main layout with sidebar
│   ├── login.html           # Login page
│   ├── signup.html          # Registration page
│   ├── profile.html         # User profile
│   ├── change_password.html # Password change
│   ├── index.html           # Landing page
│   ├── admin/               # Admin pages (12 templates)
│   ├── faculty/             # Faculty pages (8 templates)
│   ├── representative/      # Representative pages (6 templates)
│   ├── student/             # Student pages (8 templates)
│   └── errors/              # Error pages (403, 404, 500)
│
├── static/
│   ├── css/style.css        # Complete stylesheet
│   ├── js/main.js           # Client-side JavaScript
│   └── images/              # Image assets
│
└── tests/                    # Test files
    ├── test_auth.py         # Authentication tests
    ├── test_admin.py        # Admin functionality tests
    ├── test_attendance.py   # Attendance tests
    └── test_booking.py      # Booking tests
```

## Role Permissions

### Admin (100% access)
- Full user management (CRUD)
- Room management
- Approve/reject/cancel all bookings
- View/edit all attendance records
- Manage all complaints (assign, status, delete)
- View reports and audit logs

### Faculty (~75% access)
- Create attendance sessions with QR codes
- View attendance for their sessions
- Book rooms
- Submit complaints
- Cannot manage users or system settings

### Representative (~45% access)
- View attendance sessions (read-only)
- Book rooms
- Submit complaints
- Cannot create sessions or manage users

### Student (~20% access)
- Scan QR codes / enter tokens for attendance
- View their attendance history
- View available rooms and book rooms
- Submit complaints
- Cannot create sessions or manage bookings system-wide

## Running Tests

```bash
python -m pytest tests/ -v
```

## Common Troubleshooting

### "Connection refused" / Oracle not connecting
- Ensure Oracle Database XE is running: `services.msc` > look for OracleServiceXE and OracleXETNSListener
- Verify the DSN in `.env` matches your Oracle configuration
- Default for Oracle XE 21c+: `localhost:1521/XEPDB1`
- Default for Oracle XE 18c: `localhost:1521/XE`

### "ORA-12541: TNS: no listener"
- Start the Oracle listener: `lsnrctl start`
- Or via Services in Windows

### "ModuleNotFoundError: No module named 'oracledb'"
- Make sure virtual environment is activated: `venv\Scripts\activate`
- Reinstall: `pip install -r requirements.txt`

### Tables already exist error
- This is normal on restarts. The app handles it gracefully.

### Port 5000 already in use
- Change the port in `app.py` line at the bottom: `app.run(port=5001)`
