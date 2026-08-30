-- ============================================================
-- QR ATTENDANCE, ROOM BOOKING & FACILITY COMPLAINTS SYSTEM
-- Database Schema - Oracle SQL
-- ============================================================

-- Drop existing objects (safe re-runs)
BEGIN
  FOR c IN (SELECT table_name FROM user_tables WHERE table_name IN
    ('AUDIT_LOGS','COMPLAINT_STATUS_HISTORY','COMPLAINTS','ATTENDANCE_RECORDS',
     'ATTENDANCE_SESSIONS','ROOM_BOOKINGS','ROOMS','REPRESENTATIVES',
     'FACULTY','STUDENTS','USERS','DEPARTMENTS','ROLES')) LOOP
    EXECUTE IMMEDIATE 'DROP TABLE ' || c.table_name || ' CASCADE CONSTRAINTS';
  END LOOP;
END;
/

BEGIN
  FOR s IN (SELECT sequence_name FROM user_sequences) LOOP
    EXECUTE IMMEDIATE 'DROP SEQUENCE ' || s.sequence_name;
  END LOOP;
END;
/

-- ============================================================
-- SEQUENCES
-- ============================================================
CREATE SEQUENCE departments_seq START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE users_seq START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE rooms_seq START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE bookings_seq START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE sessions_seq START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE attendance_seq START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE complaints_seq START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE history_seq START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE audit_seq START WITH 1 INCREMENT BY 1 NOCACHE;

-- ============================================================
-- TABLES
-- ============================================================

-- ROLES
CREATE TABLE roles (
    role_id     NUMBER PRIMARY KEY,
    role_name   VARCHAR2(50) NOT NULL UNIQUE,
    description VARCHAR2(200)
);

-- DEPARTMENTS
CREATE TABLE departments (
    department_id   NUMBER PRIMARY KEY,
    department_name VARCHAR2(100) NOT NULL,
    code            VARCHAR2(20) NOT NULL UNIQUE
);

-- USERS
CREATE TABLE users (
    user_id       NUMBER PRIMARY KEY,
    role_id       NUMBER NOT NULL,
    department_id NUMBER,
    full_name     VARCHAR2(150) NOT NULL,
    username      VARCHAR2(50) NOT NULL UNIQUE,
    email         VARCHAR2(150) NOT NULL UNIQUE,
    password_hash VARCHAR2(255) NOT NULL,
    phone         VARCHAR2(20),
    employee_id   VARCHAR2(50),
    user_status   VARCHAR2(20) DEFAULT 'ACTIVE'
                  CHECK (user_status IN ('ACTIVE','INACTIVE','SUSPENDED')),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_users_role    FOREIGN KEY (role_id) REFERENCES roles(role_id),
    CONSTRAINT fk_users_dept    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

-- STUDENTS (extends users)
CREATE TABLE students (
    user_id         NUMBER PRIMARY KEY,
    student_number  VARCHAR2(50) NOT NULL UNIQUE,
    enrollment_year NUMBER(4),
    program         VARCHAR2(100),
    year_level      NUMBER(1),
    CONSTRAINT fk_students_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- FACULTY (extends users)
CREATE TABLE faculty (
    user_id        NUMBER PRIMARY KEY,
    faculty_number VARCHAR2(50) NOT NULL UNIQUE,
    designation    VARCHAR2(100),
    specialization VARCHAR2(200),
    CONSTRAINT fk_faculty_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- REPRESENTATIVES (extends users)
CREATE TABLE representatives (
    user_id        NUMBER PRIMARY KEY,
    assigned_class VARCHAR2(100),
    year_level     NUMBER(1),
    CONSTRAINT fk_rep_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ROOMS
CREATE TABLE rooms (
    room_id     NUMBER PRIMARY KEY,
    room_number VARCHAR2(20) NOT NULL UNIQUE,
    building    VARCHAR2(100) NOT NULL,
    floor       NUMBER(2),
    room_type   VARCHAR2(50) NOT NULL
                CHECK (room_type IN ('Classroom','Seminar Hall','Lab','Conference Room','Auditorium')),
    capacity    NUMBER(5) NOT NULL,
    facilities  VARCHAR2(500),
    is_active   NUMBER(1) DEFAULT 1 CHECK (is_active IN (0,1)),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROOM BOOKINGS
CREATE TABLE room_bookings (
    booking_id      NUMBER PRIMARY KEY,
    room_id         NUMBER NOT NULL,
    requested_by    NUMBER NOT NULL,
    booking_date    DATE NOT NULL,
    start_time      VARCHAR2(5) NOT NULL,
    end_time        VARCHAR2(5) NOT NULL,
    purpose         VARCHAR2(500) NOT NULL,
    num_participants NUMBER(5) NOT NULL,
    status          VARCHAR2(20) DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING','APPROVED','REJECTED','CANCELLED','COMPLETED')),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_by     NUMBER,
    approval_date   TIMESTAMP,
    notes           VARCHAR2(500),
    CONSTRAINT fk_booking_room     FOREIGN KEY (room_id) REFERENCES rooms(room_id),
    CONSTRAINT fk_booking_user     FOREIGN KEY (requested_by) REFERENCES users(user_id),
    CONSTRAINT fk_booking_approver FOREIGN KEY (approved_by) REFERENCES users(user_id),
    CONSTRAINT chk_booking_times   CHECK (start_time < end_time),
    CONSTRAINT chk_booking_participants CHECK (num_participants > 0)
);

-- ATTENDANCE SESSIONS
CREATE TABLE attendance_sessions (
    session_id        NUMBER PRIMARY KEY,
    created_by        NUMBER NOT NULL,
    class_name        VARCHAR2(100) NOT NULL,
    course_name       VARCHAR2(100),
    session_date      DATE NOT NULL,
    start_time        VARCHAR2(5) NOT NULL,
    end_time          VARCHAR2(5) NOT NULL,
    qr_token          VARCHAR2(255) NOT NULL UNIQUE,
    qr_expiry_minutes NUMBER(3) DEFAULT 15,
    is_active         NUMBER(1) DEFAULT 1 CHECK (is_active IN (0,1)),
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at         TIMESTAMP,
    CONSTRAINT fk_session_faculty FOREIGN KEY (created_by) REFERENCES users(user_id),
    CONSTRAINT chk_session_times  CHECK (start_time < end_time)
);

-- ATTENDANCE RECORDS
CREATE TABLE attendance_records (
    record_id      NUMBER PRIMARY KEY,
    session_id     NUMBER NOT NULL,
    student_id     NUMBER NOT NULL,
    status         VARCHAR2(20) NOT NULL CHECK (status IN ('PRESENT','LATE','ABSENT')),
    marked_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    qr_token_used  VARCHAR2(255),
    ip_address     VARCHAR2(45),
    CONSTRAINT fk_record_session FOREIGN KEY (session_id) REFERENCES attendance_sessions(session_id),
    CONSTRAINT fk_record_student FOREIGN KEY (student_id) REFERENCES users(user_id),
    CONSTRAINT uq_attendance     UNIQUE (session_id, student_id)
);

-- COMPLAINTS
CREATE TABLE complaints (
    complaint_id     NUMBER PRIMARY KEY,
    submitted_by     NUMBER NOT NULL,
    room_id          NUMBER,
    category         VARCHAR2(50) NOT NULL
                     CHECK (category IN ('Electrical','Plumbing','Furniture','Air Conditioning',
                                         'Internet','Cleaning','Equipment','Other')),
    title            VARCHAR2(200) NOT NULL,
    description      CLOB NOT NULL,
    priority         VARCHAR2(20) DEFAULT 'MEDIUM'
                     CHECK (priority IN ('LOW','MEDIUM','HIGH','URGENT')),
    status           VARCHAR2(20) DEFAULT 'OPEN'
                     CHECK (status IN ('OPEN','ASSIGNED','IN_PROGRESS','RESOLVED','CLOSED','REJECTED')),
    assigned_to      NUMBER,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolution_notes CLOB,
    resolved_at      TIMESTAMP,
    CONSTRAINT fk_complaint_user   FOREIGN KEY (submitted_by) REFERENCES users(user_id),
    CONSTRAINT fk_complaint_room   FOREIGN KEY (room_id) REFERENCES rooms(room_id),
    CONSTRAINT fk_complaint_assign FOREIGN KEY (assigned_to) REFERENCES users(user_id)
);

-- COMPLAINT STATUS HISTORY
CREATE TABLE complaint_status_history (
    history_id    NUMBER PRIMARY KEY,
    complaint_id  NUMBER NOT NULL,
    old_status    VARCHAR2(20),
    new_status    VARCHAR2(20) NOT NULL,
    changed_by    NUMBER NOT NULL,
    changed_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes         VARCHAR2(500),
    CONSTRAINT fk_history_complaint FOREIGN KEY (complaint_id) REFERENCES complaints(complaint_id) ON DELETE CASCADE,
    CONSTRAINT fk_history_user      FOREIGN KEY (changed_by) REFERENCES users(user_id)
);

-- AUDIT LOGS
CREATE TABLE audit_logs (
    log_id       NUMBER PRIMARY KEY,
    user_id      NUMBER,
    action       VARCHAR2(100) NOT NULL,
    entity_type  VARCHAR2(50) NOT NULL,
    entity_id    NUMBER,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description  VARCHAR2(1000),
    ip_address   VARCHAR2(45),
    CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX idx_users_role       ON users(role_id);
CREATE INDEX idx_users_dept       ON users(department_id);
CREATE INDEX idx_users_status     ON users(user_status);
CREATE INDEX idx_users_username   ON users(username);
CREATE INDEX idx_bookings_room    ON room_bookings(room_id);
CREATE INDEX idx_bookings_user    ON room_bookings(requested_by);
CREATE INDEX idx_bookings_date    ON room_bookings(booking_date);
CREATE INDEX idx_bookings_status  ON room_bookings(status);
CREATE INDEX idx_sessions_faculty ON attendance_sessions(created_by);
CREATE INDEX idx_sessions_date    ON attendance_sessions(session_date);
CREATE INDEX idx_sessions_active  ON attendance_sessions(is_active);
CREATE INDEX idx_records_session  ON attendance_records(session_id);
CREATE INDEX idx_records_student  ON attendance_records(student_id);
CREATE INDEX idx_complaints_user  ON complaints(submitted_by);
CREATE INDEX idx_complaints_room  ON complaints(room_id);
CREATE INDEX idx_complaints_status ON complaints(status);
CREATE INDEX idx_complaints_priority ON complaints(priority);
CREATE INDEX idx_audit_user       ON audit_logs(user_id);
CREATE INDEX idx_audit_entity     ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_date       ON audit_logs(created_at);
CREATE INDEX idx_history_complaint ON complaint_status_history(complaint_id);

-- ============================================================
-- USEFUL VIEWS
-- ============================================================

-- Active users with role names
CREATE OR REPLACE VIEW v_active_users AS
SELECT u.user_id, u.full_name, u.username, u.email, u.phone,
       u.employee_id, u.user_status, u.created_at,
       r.role_name, d.department_name, d.code AS dept_code
FROM users u
JOIN roles r ON u.role_id = r.role_id
LEFT JOIN departments d ON u.department_id = d.department_id
WHERE u.user_status = 'ACTIVE';

-- Attendance summary per student
CREATE OR REPLACE VIEW v_student_attendance AS
SELECT ar.student_id,
       u.full_name AS student_name,
       s.student_number,
       ar.session_id,
       att.class_name,
       att.course_name,
       att.session_date,
       ar.status AS attendance_status,
       ar.marked_at
FROM attendance_records ar
JOIN users u ON ar.student_id = u.user_id
JOIN students s ON u.user_id = s.user_id
JOIN attendance_sessions att ON ar.session_id = att.session_id;

-- Booking details
CREATE OR REPLACE VIEW v_booking_details AS
SELECT rb.booking_id, rb.booking_date, rb.start_time, rb.end_time,
       rb.purpose, rb.num_participants, rb.status, rb.created_at,
       rm.room_number, rm.building, rm.room_type, rm.capacity,
       u.full_name AS requested_by_name,
       a.full_name AS approved_by_name,
       rb.approval_date
FROM room_bookings rb
JOIN rooms rm ON rb.room_id = rm.room_id
JOIN users u ON rb.requested_by = u.user_id
LEFT JOIN users a ON rb.approved_by = a.user_id;

-- Complaint details
CREATE OR REPLACE VIEW v_complaint_details AS
SELECT c.complaint_id, c.title, c.description, c.category, c.priority,
       c.status, c.created_at, c.updated_at, c.resolution_notes, c.resolved_at,
       u.full_name AS submitted_by_name,
       r.room_number, r.building,
       a.full_name AS assigned_to_name
FROM complaints c
JOIN users u ON c.submitted_by = u.user_id
LEFT JOIN rooms r ON c.room_id = r.room_id
LEFT JOIN users a ON c.assigned_to = a.user_id;
