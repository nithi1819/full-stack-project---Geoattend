"""QR code generation utilities."""

import qrcode
from io import BytesIO
import base64
from datetime import datetime, timedelta
import secrets
import string


def generate_qr_code(data):
    """Generate QR code from data and return as base64 PNG."""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to BytesIO
        buf = BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        
        # Encode to base64
        img_base64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/png;base64,{img_base64}"
    
    except Exception as e:
        print(f"QR generation error: {e}")
        return None


def generate_attendance_token(length=8):
    """Generate random attendance token for manual entry."""
    characters = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


def generate_qr_data(session_id, session_token=None):
    """Generate QR data string for attendance session."""
    if session_token is None:
        session_token = generate_attendance_token()
    
    timestamp = datetime.now().isoformat()
    return f"ATTEND|{session_id}|{session_token}|{timestamp}"


def parse_qr_data(qr_string):
    """Parse QR data string back to components."""
    try:
        parts = qr_string.split('|')
        if len(parts) >= 4 and parts[0] == 'ATTEND':
            return {
                'type': parts[0],
                'session_id': parts[1],
                'token': parts[2],
                'timestamp': parts[3]
            }
    except Exception as e:
        print(f"QR parsing error: {e}")
    
    return None


def is_qr_expired(qr_timestamp_str, expiry_minutes=30):
    """Check if QR code is expired."""
    try:
        qr_time = datetime.fromisoformat(qr_timestamp_str)
        expiry_time = qr_time + timedelta(minutes=expiry_minutes)
        return datetime.now() > expiry_time
    except Exception as e:
        print(f"QR expiry check error: {e}")
        return True
