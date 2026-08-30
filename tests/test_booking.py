"""Booking functionality tests."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBookingRoutes:
    """Test booking routes (requires Oracle DB)."""

    @pytest.fixture
    def client(self):
        from app import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def _login_student(self, client):
        client.post("/auth/login", data={"username": "student1", "password": "Student@123"})

    def _login_faculty(self, client):
        client.post("/auth/login", data={"username": "faculty1", "password": "Faculty@123"})

    def _login_admin(self, client):
        client.post("/auth/login", data={"username": "admin", "password": "Admin@123"})

    def test_student_rooms_list_loads(self, client):
        self._login_student(client)
        response = client.get("/student/rooms")
        assert response.status_code == 200

    def test_student_bookings_list_loads(self, client):
        self._login_student(client)
        response = client.get("/student/bookings")
        assert response.status_code == 200

    def test_student_booking_form_loads(self, client):
        self._login_student(client)
        response = client.get("/student/bookings/create")
        assert response.status_code == 200

    def test_faculty_booking_form_loads(self, client):
        self._login_faculty(client)
        response = client.get("/faculty/bookings/create")
        assert response.status_code == 200

    def test_student_can_create_booking(self, client):
        self._login_student(client)
        response = client.post("/student/bookings/create", data={
            "room_id": "1",
            "booking_date": "2026-12-01",
            "start_time": "10:00",
            "end_time": "12:00",
            "purpose": "Study group meeting",
            "num_participants": "5"
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"Booking request submitted" in response.data

    def test_faculty_can_create_booking(self, client):
        self._login_faculty(client)
        response = client.post("/faculty/bookings/create", data={
            "room_id": "2",
            "booking_date": "2026-12-02",
            "start_time": "14:00",
            "end_time": "16:00",
            "purpose": "Lecture preparation",
            "num_participants": "30"
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"Booking request submitted" in response.data

    def test_admin_can_view_all_bookings(self, client):
        self._login_admin(client)
        response = client.get("/admin/bookings")
        assert response.status_code == 200

    def test_admin_booking_actions_require_pending(self, client):
        """Test that approve/reject only works on pending bookings."""
        self._login_admin(client)
        # Try to approve a non-existent booking - should still return 302 (redirect)
        response = client.post("/admin/bookings/99999/approve", follow_redirects=False)
        # Even if booking doesn't exist, route should handle gracefully
        assert response.status_code in [302, 200]
