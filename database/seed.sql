-- ============================================================
-- SEED DATA - Reference Data
-- (Users with hashed passwords are seeded via Python)
-- ============================================================

-- ROLES
INSERT INTO roles (role_id, role_name, description) VALUES (1, 'ADMIN', 'System Administrator');
INSERT INTO roles (role_id, role_name, description) VALUES (2, 'FACULTY', 'Faculty Member');
INSERT INTO roles (role_id, role_name, description) VALUES (3, 'REPRESENTATIVE', 'Class Representative');
INSERT INTO roles (role_id, role_name, description) VALUES (4, 'STUDENT', 'Student');

-- DEPARTMENTS
INSERT INTO departments (department_id, department_name, code) VALUES (1, 'Computer Science', 'CS');
INSERT INTO departments (department_id, department_name, code) VALUES (2, 'Electrical Engineering', 'EE');
INSERT INTO departments (department_id, department_name, code) VALUES (3, 'Mathematics', 'MATH');
INSERT INTO departments (department_id, department_name, code) VALUES (4, 'Physics', 'PHY');
INSERT INTO departments (department_id, department_name, code) VALUES (5, 'Business Administration', 'BA');
INSERT INTO departments (department_id, department_name, code) VALUES (6, 'Mechanical Engineering', 'ME');
INSERT INTO departments (department_id, department_name, code) VALUES (7, 'Civil Engineering', 'CE');

-- ROOMS
INSERT INTO rooms (room_id, room_number, building, floor, room_type, capacity, facilities, is_active) VALUES
(rooms_seq.NEXTVAL, 'CS-101', 'Science Building', 1, 'Classroom', 60, 'Projector, Whiteboard, Speakers', 1);
INSERT INTO rooms (room_id, room_number, building, floor, room_type, capacity, facilities, is_active) VALUES
(rooms_seq.NEXTVAL, 'CS-201', 'Science Building', 2, 'Classroom', 45, 'Projector, Whiteboard', 1);
INSERT INTO rooms (room_id, room_number, building, floor, room_type, capacity, facilities, is_active) VALUES
(rooms_seq.NEXTVAL, 'CS-301', 'Science Building', 3, 'Lab', 40, '40 Workstations, Projector, Printer', 1);
INSERT INTO rooms (room_id, room_number, building, floor, room_type, capacity, facilities, is_active) VALUES
(rooms_seq.NEXTVAL, 'SH-101', 'Main Hall', 1, 'Seminar Hall', 150, 'Stage, Microphone, Projector, AC', 1);
INSERT INTO rooms (room_id, room_number, building, floor, room_type, capacity, facilities, is_active) VALUES
(rooms_seq.NEXTVAL, 'CR-101', 'Admin Building', 1, 'Conference Room', 20, 'Projector, Whiteboard, Video Conference', 1);
INSERT INTO rooms (room_id, room_number, building, floor, room_type, capacity, facilities, is_active) VALUES
(rooms_seq.NEXTVAL, 'AUD-001', 'Main Hall', 0, 'Auditorium', 500, 'Stage, Sound System, Projector, AC, Recording', 1);
INSERT INTO rooms (room_id, room_number, building, floor, room_type, capacity, facilities, is_active) VALUES
(rooms_seq.NEXTVAL, 'EE-101', 'Engineering Building', 1, 'Lab', 35, '35 Workstations, Oscilloscopes, Projector', 1);
INSERT INTO rooms (room_id, room_number, building, floor, room_type, capacity, facilities, is_active) VALUES
(rooms_seq.NEXTVAL, 'BA-201', 'Business Building', 2, 'Classroom', 50, 'Projector, Whiteboard, AC', 1);
INSERT INTO rooms (room_id, room_number, building, floor, room_type, capacity, facilities, is_active) VALUES
(rooms_seq.NEXTVAL, 'CR-202', 'Admin Building', 2, 'Conference Room', 12, 'TV Screen, Whiteboard, Phone', 1);
INSERT INTO rooms (room_id, room_number, building, floor, room_type, capacity, facilities, is_active) VALUES
(rooms_seq.NEXTVAL, 'CS-102', 'Science Building', 1, 'Classroom', 55, 'Projector, Whiteboard, Speakers', 1);

COMMIT;
