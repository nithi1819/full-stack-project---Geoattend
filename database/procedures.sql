-- ============================================================
-- PL/SQL PROCEDURES AND FUNCTIONS
-- ============================================================

-- ============================================================
-- 1. Check for booking time conflicts
-- ============================================================
CREATE OR REPLACE PROCEDURE check_booking_conflict(
    p_room_id       IN NUMBER,
    p_booking_date  IN DATE,
    p_start_time    IN VARCHAR2,
    p_end_time      IN VARCHAR2,
    p_exclude_id    IN NUMBER DEFAULT NULL,
    p_has_conflict  OUT NUMBER,
    p_conflict_msg  OUT VARCHAR2
) AS
    v_count NUMBER;
BEGIN
    p_has_conflict := 0;
    p_conflict_msg := '';

    SELECT COUNT(*)
    INTO v_count
    FROM room_bookings
    WHERE room_id = p_room_id
      AND booking_date = p_booking_date
      AND status = 'APPROVED'
      AND (p_exclude_id IS NULL OR booking_id != p_exclude_id)
      AND (
          (start_time < p_end_time AND end_time > p_start_time)
      );

    IF v_count > 0 THEN
        p_has_conflict := 1;
        p_conflict_msg := 'Time conflict with an existing approved booking for this room on the selected date.';
    END IF;
END check_booking_conflict;
/

-- ============================================================
-- 2. Validate and mark attendance
-- ============================================================
CREATE OR REPLACE PROCEDURE mark_attendance(
    p_session_id    IN NUMBER,
    p_student_id    IN NUMBER,
    p_token_used    IN VARCHAR2,
    p_ip_address    IN VARCHAR2,
    p_status        OUT VARCHAR2,
    p_message       OUT VARCHAR2
) AS
    v_session_active  NUMBER;
    v_token_valid     VARCHAR2(255);
    v_qr_expiry       NUMBER;
    v_session_created TIMESTAMP;
    v_existing        NUMBER;
    v_already_marked  NUMBER;
    v_now             TIMESTAMP := CURRENT_TIMESTAMP;
BEGIN
    p_status := 'ERROR';
    p_message := '';

    -- Check session exists
    SELECT is_active, qr_token, qr_expiry_minutes, created_at
    INTO v_session_active, v_token_valid, v_qr_expiry, v_session_created
    FROM attendance_sessions
    WHERE session_id = p_session_id;

    -- Check session is active
    IF v_session_active != 1 THEN
        p_message := 'This attendance session is no longer active.';
        RETURN;
    END IF;

    -- Validate token
    IF v_token_valid != p_token_used THEN
        p_message := 'Invalid attendance token.';
        RETURN;
    END IF;

    -- Check expiry
    IF (CAST(v_now AS DATE) - CAST(v_session_created AS DATE)) * 24 * 60 > v_qr_expiry THEN
        p_message := 'This QR code has expired. Please ask your instructor for a new one.';
        RETURN;
    END IF;

    -- Check not already marked
    SELECT COUNT(*) INTO v_already_marked
    FROM attendance_records
    WHERE session_id = p_session_id AND student_id = p_student_id;

    IF v_already_marked > 0 THEN
        p_message := 'You have already marked attendance for this session.';
        RETURN;
    END IF;

    -- Determine status (PRESENT if within first 5 min, LATE otherwise)
    DECLARE
        v_diff_minutes NUMBER;
    BEGIN
        v_diff_minutes := (CAST(v_now AS DATE) - CAST(v_session_created AS DATE)) * 24 * 60;
        IF v_diff_minutes <= 5 THEN
            v_session_active := 1; -- reuse: 1=PRESENT
        ELSE
            v_session_active := 0; -- reuse: 0=LATE
        END IF;
    END;

    -- Insert attendance record
    INSERT INTO attendance_records (record_id, session_id, student_id, status, marked_at, qr_token_used, ip_address)
    VALUES (attendance_seq.NEXTVAL, p_session_id, p_student_id,
            CASE WHEN v_session_active = 1 THEN 'PRESENT' ELSE 'LATE' END,
            v_now, p_token_used, p_ip_address);

    p_status := 'SUCCESS';
    p_message := 'Attendance marked successfully.';
    COMMIT;
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        p_message := 'An error occurred: ' || SQLERRM;
END mark_attendance;
/

-- ============================================================
-- 3. Get attendance statistics for a student
-- ============================================================
CREATE OR REPLACE FUNCTION get_attendance_percentage(
    p_student_id IN NUMBER
) RETURN NUMBER AS
    v_total    NUMBER := 0;
    v_present  NUMBER := 0;
    v_late     NUMBER := 0;
BEGIN
    SELECT COUNT(*) INTO v_total
    FROM attendance_sessions s
    WHERE s.is_active = 0 OR s.closed_at IS NOT NULL;

    IF v_total = 0 THEN
        RETURN 0;
    END IF;

    SELECT COUNT(*) INTO v_present
    FROM attendance_records
    WHERE student_id = p_student_id AND status = 'PRESENT';

    SELECT COUNT(*) INTO v_late
    FROM attendance_records
    WHERE student_id = p_student_id AND status = 'LATE';

    RETURN ROUND(((v_present + v_late) / v_total) * 100, 1);
END get_attendance_percentage;
/

-- ============================================================
-- 4. Record complaint status change
-- ============================================================
CREATE OR REPLACE PROCEDURE update_complaint_status(
    p_complaint_id  IN NUMBER,
    p_new_status    IN VARCHAR2,
    p_changed_by    IN NUMBER,
    p_notes         IN VARCHAR2 DEFAULT NULL,
    p_message       OUT VARCHAR2
) AS
    v_old_status VARCHAR2(20);
    v_now        TIMESTAMP := CURRENT_TIMESTAMP;
BEGIN
    SELECT status INTO v_old_status
    FROM complaints WHERE complaint_id = p_complaint_id;

    -- Insert history record
    INSERT INTO complaint_status_history (history_id, complaint_id, old_status, new_status, changed_by, changed_at, notes)
    VALUES (history_seq.NEXTVAL, p_complaint_id, v_old_status, p_new_status, p_changed_by, v_now, p_notes);

    -- Update complaint
    UPDATE complaints
    SET status = p_new_status,
        updated_at = v_now
    WHERE complaint_id = p_complaint_id;

    -- If resolved or closed, set resolved_at
    IF p_new_status IN ('RESOLVED', 'CLOSED') AND v_old_status NOT IN ('RESOLVED', 'CLOSED') THEN
        UPDATE complaints SET resolved_at = v_now WHERE complaint_id = p_complaint_id;
    END IF;

    p_message := 'Status updated successfully.';
    COMMIT;
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        p_message := 'Error updating status: ' || SQLERRM;
END update_complaint_status;
/

-- ============================================================
-- 5. Write audit log entry
-- ============================================================
CREATE OR REPLACE PROCEDURE write_audit_log(
    p_user_id      IN NUMBER,
    p_action       IN VARCHAR2,
    p_entity_type  IN VARCHAR2,
    p_entity_id    IN NUMBER DEFAULT NULL,
    p_description  IN VARCHAR2 DEFAULT NULL,
    p_ip_address   IN VARCHAR2 DEFAULT NULL
) AS
BEGIN
    INSERT INTO audit_logs (log_id, user_id, action, entity_type, entity_id, created_at, description, ip_address)
    VALUES (audit_seq.NEXTVAL, p_user_id, p_action, p_entity_type, p_entity_id, CURRENT_TIMESTAMP, p_description, p_ip_address);
    COMMIT;
END write_audit_log;
/

-- ============================================================
-- 6. Check if a student is eligible for a session
-- ============================================================
CREATE OR REPLACE FUNCTION is_student_eligible(
    p_session_id IN NUMBER,
    p_student_id IN NUMBER
) RETURN NUMBER AS
    v_count NUMBER;
BEGIN
    -- Student must be an active student user
    SELECT COUNT(*) INTO v_count
    FROM users u
    JOIN students s ON u.user_id = s.user_id
    WHERE u.user_id = p_student_id AND u.user_status = 'ACTIVE';

    IF v_count = 0 THEN
        RETURN 0;
    END IF;

    RETURN 1;
END is_student_eligible;
/
