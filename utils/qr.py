"""QR code generation and token utilities."""

import secrets
import io
import base64
import os
import socket
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer


def generate_session_token():
    """Generate a cryptographically secure random token for attendance sessions."""
    return secrets.token_urlsafe(32)


def generate_qr_base64(data, size=10, border=4):
    """Generate a QR code image as a base64-encoded PNG string.

    Args:
        data: The string data to encode in the QR code (typically a URL with token).
        size: Box size in pixels.
        border: Border size in modules.

    Returns:
        Base64-encoded PNG string for embedding in HTML img src.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def generate_qr_bytes(data, size=10, border=4):
    """Generate a QR code and return raw PNG bytes."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


def build_attendance_url(base_url, token):
    """Build the full attendance URL containing the QR token."""
    base_url = base_url.rstrip("/")
    return f"{base_url}/student/scan?token={token}"


def get_public_base_url(request):
    """Return a URL that another device on the local network can open."""
    configured_url = os.getenv("PUBLIC_BASE_URL", "").strip()
    if configured_url:
        return configured_url.rstrip("/")

    host = request.host.split(":", 1)[0]
    if host in {"127.0.0.1", "localhost", "::1"}:
        try:
            host = socket.gethostbyname(socket.gethostname())
        except socket.gaierror:
            host = request.host

    port = request.environ.get("SERVER_PORT")
    if not port or port == "80" and request.scheme == "http":
        port = "5000"
    return f"{request.scheme}://{host}:{port}"
