"""Admin functionality tests."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAdminManagement:
    """Test admin CRUD operations."""

    @pytest.fixture
    def client(self):
        from app import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def _login_admin(self, client):
        client.post("/auth/login", data={"username": "admin", "password": "Admin@123"})

    def test_admin_dashboard_loads(self, client):
        self._login_admin(client)
        response = client.get("/admin/dashboard")
        assert response.status_code == 200
        assert b"Total Users" in response.data

    def test_users_list_loads(self, client):
        self._login_admin(client)
        response = client.get("/admin/users")
        assert response.status_code == 200
        assert b"admin" in response.data

    def test_rooms_list_loads(self, client):
        self._login_admin(client)
        response = client.get("/admin/rooms")
        assert response.status_code == 200

    def test_bookings_list_loads(self, client):
        self._login_admin(client)
        response = client.get("/admin/bookings")
        assert response.status_code == 200

    def test_attendance_list_loads(self, client):
        self._login_admin(client)
        response = client.get("/admin/attendance")
        assert response.status_code == 200

    def test_complaints_list_loads(self, client):
        self._login_admin(client)
        response = client.get("/admin/complaints")
        assert response.status_code == 200

    def test_reports_loads(self, client):
        self._login_admin(client)
        response = client.get("/admin/reports")
        assert response.status_code == 200

    def test_audit_logs_loads(self, client):
        self._login_admin(client)
        response = client.get("/admin/audit-logs")
        assert response.status_code == 200

    def test_create_user_form_loads(self, client):
        self._login_admin(client)
        response = client.get("/admin/users/create")
        assert response.status_code == 200

    def test_create_room_form_loads(self, client):
        self._login_admin(client)
        response = client.get("/admin/rooms/create")
        assert response.status_code == 200


class TestComplaintManagement:
    """Test complaint assignment and status updates."""

    @pytest.fixture
    def client(self):
        from app import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def _login_admin(self, client):
        client.post("/auth/login", data={"username": "admin", "password": "Admin@123"})

    def _login_student(self, client):
        client.post("/auth/login", data={"username": "student1", "password": "Student@123"})

    def test_student_can_create_complaint(self, client):
        self._login_student(client)
        response = client.post("/student/complaints/create", data={
            "room_id": "1",
            "category": "Electrical",
            "title": "Broken lights in CS-101",
            "description": "The lights in the classroom are flickering.",
            "priority": "HIGH"
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"Complaint submitted" in response.data

    def test_admin_can_view_complaints(self, client):
        self._login_admin(client)
        response = client.get("/admin/complaints")
        assert response.status_code == 200
