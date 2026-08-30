-- ============================================================
-- TRIGGERS
-- ============================================================

-- ============================================================
-- 1. Auto-update USERS.updated_at on row update
-- ============================================================
CREATE OR REPLACE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
BEGIN
    :NEW.updated_at := CURRENT_TIMESTAMP;
END;
/

-- ============================================================
-- 2. Auto-update COMPLAINTS.updated_at on row update
-- ============================================================
CREATE OR REPLACE TRIGGER trg_complaints_updated_at
BEFORE UPDATE ON complaints
FOR EACH ROW
BEGIN
    :NEW.updated_at := CURRENT_TIMESTAMP;
END;
/

-- ============================================================
-- 3. Auto-record complaint status history on INSERT
-- ============================================================
CREATE OR REPLACE TRIGGER trg_complaint_status_insert
AFTER INSERT ON complaints
FOR EACH ROW
BEGIN
    INSERT INTO complaint_status_history (history_id, complaint_id, old_status, new_status, changed_by, changed_at, notes)
    VALUES (history_seq.NEXTVAL, :NEW.complaint_id, NULL, :NEW.status, :NEW.submitted_by, CURRENT_TIMESTAMP, 'Complaint created');
END;
/

-- ============================================================
-- 4. (removed) Auto-record complaint status history on status UPDATE
-- ============================================================
-- NOTE: This trigger used to duplicate the history row that routes/admin.py
-- already inserts manually in complaint_assign() and complaint_status().
-- Having both meant every status change wrote TWO rows to
-- complaint_status_history: one from the app (with the correct actor and
-- notes) and one from this trigger (with an inaccurate changed_by, since it
-- guessed NVL(assigned_to, submitted_by) instead of the admin who actually
-- made the change). The trigger has been removed so only the app's insert
-- (which has the right user and notes) fires. Trigger #3 above is kept
-- because complaint creation has no equivalent manual insert.

-- ============================================================
-- 5. Audit log on user creation
-- ============================================================
CREATE OR REPLACE TRIGGER trg_audit_user_insert
AFTER INSERT ON users
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (log_id, user_id, action, entity_type, entity_id, created_at, description)
    VALUES (audit_seq.NEXTVAL, :NEW.user_id, 'CREATE', 'USER', :NEW.user_id, CURRENT_TIMESTAMP,
            'User created: ' || :NEW.username || ' (' || :NEW.full_name || ')');
END;
/

-- ============================================================
-- 6. Audit log on room booking status change
-- ============================================================
CREATE OR REPLACE TRIGGER trg_audit_booking_status
AFTER UPDATE OF status ON room_bookings
FOR EACH ROW
BEGIN
    IF :OLD.status != :NEW.status THEN
        INSERT INTO audit_logs (log_id, user_id, action, entity_type, entity_id, created_at, description)
        VALUES (audit_seq.NEXTVAL, :NEW.approved_by, 'UPDATE_STATUS', 'BOOKING', :NEW.booking_id, CURRENT_TIMESTAMP,
                'Booking ' || :NEW.booking_id || ' status changed from ' || :OLD.status || ' to ' || :NEW.status);
    END IF;
END;
/

-- ============================================================
-- 7. Audit log on attendance session creation
-- ============================================================
CREATE OR REPLACE TRIGGER trg_audit_session_insert
AFTER INSERT ON attendance_sessions
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (log_id, user_id, action, entity_type, entity_id, created_at, description)
    VALUES (audit_seq.NEXTVAL, :NEW.created_by, 'CREATE', 'ATTENDANCE_SESSION', :NEW.session_id, CURRENT_TIMESTAMP,
            'Attendance session created for ' || :NEW.class_name || ' on ' || TO_CHAR(:NEW.session_date, 'YYYY-MM-DD'));
END;
/
