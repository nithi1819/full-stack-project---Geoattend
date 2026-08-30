"""Authentication tests."""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPasswordHashing:
    """Test password hashing utilities."""

    def test_hash_password(self):
        from utils.auth import hash_password, verify_password
        pwd = "Test@1234"
        h = hash_password(pwd)
        assert h != pwd
        assert verify_password(pwd, h)

    def test_wrong_password(self):
        from utils.auth import hash_password, verify_password
        h = hash_password("Correct@1")
        assert not verify_password("Wrong@1", h)


class TestAuthRoutes:
    """Test authentication routes (requires running app and DB)."""

    @pytest.fixture
    def client(self):
        """Create test client (requires Oracle DB)."""
        from app import app
        app.config["TESTING"] = True
        app.config["SESSION_TYPE"] = "filesystem"
        with app.test_client() as client:
            yield client

    def test_login_page_loads(self, client):
        response = client.get("/auth/login")
        assert response.status_code == 200
        assert b"Sign In" in response.data

    def test_signup_page_loads(self, client):
        response = client.get("/auth/signup")
        assert response.status_code == 200
        assert b"Registration" in response.data or b"Sign Up" in response.data

    def test_login_redirect_when_not_authenticated(self, client):
        response = client.get("/admin/dashboard", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.headers.get("Location", "")

    def test_invalid_login(self, client):
        response = client.post("/auth/login", data={
            "username": "nonexistent",
            "password": "wrong"
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"Invalid username or password" in response.data

    def test_valid_admin_login(self, client):
        response = client.post("/auth/login", data={
            "username": "admin",
            "password": "Admin@123"
        }, follow_redirects=False)
        assert response.status_code == 302
        assert "/admin/dashboard" in response.headers.get("Location", "")

    def test_valid_faculty_login(self, client):
        response = client.post("/auth/login", data={
            "username": "faculty1",
            "password": "Faculty@123"
        }, follow_redirects=False)
        assert response.status_code == 302
        assert "/faculty/dashboard" in response.headers.get("Location", "")

    def test_valid_student_login(self, client):
        response = client.post("/auth/login", data={
            "username": "student1",
            "password": "Student@123"
        }, follow_redirects=False)
        assert response.status_code == 302
        assert "/student/dashboard" in response.headers.get("Location", "")

    def test_logout(self, client):
        # Login first
        client.post("/auth/login", data={
            "username": "admin",
            "password": "Admin@123"
        })
        response = client.get("/auth/logout", follow_redirects=False)
        assert response.status_code == 302
        # After logout, should redirect to login
        response = client.get("/admin/dashboard", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.headers.get("Location", "")


class TestRoleAuthorization:
    """Test role-based access control."""

    @pytest.fixture
    def client(self):
        from app import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def _login(self, client, username, password):
        client.post("/auth/login", data={
            "username": username,
            "password": password
        })

    def test_student_cannot_access_admin(self, client):
        self._login(client, "student1", "Student@123")
        response = client.get("/admin/dashboard", follow_redirects=False)
        assert response.status_code == 403

    def test_faculty_cannot_access_admin(self, client):
        self._login(client, "faculty1", "Faculty@123")
        response = client.get("/admin/dashboard", follow_redirects=False)
        assert response.status_code == 403

    def test_rep_cannot_access_admin(self, client):
        self._login(client, "rep1", "Rep@123")
        response = client.get("/admin/dashboard", follow_redirects=False)
        assert response.status_code == 403

    def test_student_can_access_student_dashboard(self, client):
        self._login(client, "student1", "Student@123")
        response = client.get("/student/dashboard", follow_redirects=False)
        assert response.status_code == 200

    def test_faculty_can_access_faculty_dashboard(self, client):
        self._login(client, "faculty1", "Faculty@123")
        response = client.get("/faculty/dashboard", follow_redirects=False)
        assert response.status_code == 200

    def test_admin_can_access_admin_dashboard(self, client):
        self._login(client, "admin", "Admin@123")
        response = client.get("/admin/dashboard", follow_redirects=False)
        assert response.status_code == 200
