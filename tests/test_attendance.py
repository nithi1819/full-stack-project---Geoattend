"""Attendance functionality tests."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestQRGeneration:
    """Test QR code generation utilities."""

    def test_generate_session_token(self):
        from utils.qr import generate_session_token
        token1 = generate_session_token()
        token2 = generate_session_token()
        assert token1 != token2
        assert len(token1) > 20

    def test_generate_qr_base64(self):
        from utils.qr import generate_qr_base64
        qr = generate_qr_base64("https://example.com/test?token=abc123")
        assert isinstance(qr, str)
        assert len(qr) > 100  # Base64 encoded image should be substantial

    def test_build_attendance_url(self):
        from utils.qr import build_attendance_url
        url = build_attendance_url("http://localhost:5000", "test-token-123")
        assert url == "http://localhost:5000/student/scan?token=test-token-123"


class TestAttendanceRoutes:
    """Test attendance routes (requires Oracle DB)."""

    @pytest.fixture
    def client(self):
        from app import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def _login_faculty(self, client):
        client.post("/auth/login", data={"username": "faculty1", "password": "Faculty@123"})

    def _login_student(self, client):
        client.post("/auth/login", data={"username": "student1", "password": "Student@123"})

    def test_faculty_can_create_session(self, client):
        self._login_faculty(client)
        response = client.post("/faculty/sessions/create", data={
            "class_name": "CS-301",
            "course_name": "Data Structures",
            "session_date": "2026-01-15",
            "start_time": "09:00",
            "end_time": "11:00",
            "qr_expiry_minutes": "15"
        }, follow_redirects=False)
        assert response.status_code == 302

    def test_student_cannot_create_session(self, client):
        self._login_student(client)
        response = client.post("/faculty/sessions/create", data={
            "class_name": "CS-301",
            "course_name": "Test",
            "session_date": "2026-01-15",
            "start_time": "09:00",
            "end_time": "11:00",
            "qr_expiry_minutes": "15"
        }, follow_redirects=False)
        assert response.status_code == 403

    def test_student_scan_page_loads(self, client):
        self._login_student(client)
        response = client.get("/student/scan")
        assert response.status_code == 200

    def test_mark_attendance_invalid_token(self, client):
        self._login_student(client)
        response = client.post("/student/attendance/mark", data={
            "token": "invalid-token-12345"
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"Invalid attendance token" in response.data

    def test_student_attendance_history_loads(self, client):
        self._login_student(client)
        response = client.get("/student/attendance")
        assert response.status_code == 200

    def test_faculty_sessions_list_loads(self, client):
        self._login_faculty(client)
        response = client.get("/faculty/sessions")
        assert response.status_code == 200
