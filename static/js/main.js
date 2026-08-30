/* ============================================================
   QR ATTENDANCE SYSTEM - Main JavaScript
   ============================================================ */

// ── Sidebar Toggle ──────────────────────────────────────
function toggleSidebar() {
    var sidebar = document.getElementById('sidebar');
    if (sidebar) {
        sidebar.classList.toggle('open');
    }
}

// Close sidebar when clicking outside on mobile
document.addEventListener('click', function(e) {
    var sidebar = document.getElementById('sidebar');
    var toggle = document.querySelector('.sidebar-toggle');
    if (sidebar && sidebar.classList.contains('open') &&
        !sidebar.contains(e.target) && !toggle.contains(e.target)) {
        sidebar.classList.remove('open');
    }
});

// ── Auto-dismiss Flash Messages ──────────────────────────
document.addEventListener('DOMContentLoaded', function() {
    var flashes = document.querySelectorAll('.flash');
    flashes.forEach(function(flash) {
        setTimeout(function() {
            flash.style.opacity = '0';
            flash.style.transform = 'translateY(-10px)';
            setTimeout(function() {
                flash.remove();
            }, 300);
        }, 5000);
    });
});

// ── Form Validation Helpers ──────────────────────────────
function validateEmail(email) {
    var re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

function validatePassword(password) {
    var errors = [];
    if (password.length < 8) errors.push('at least 8 characters');
    if (!/[A-Z]/.test(password)) errors.push('an uppercase letter');
    if (!/[a-z]/.test(password)) errors.push('a lowercase letter');
    if (!/[0-9]/.test(password)) errors.push('a number');
    if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) errors.push('a special character');
    return errors;
}

// Signup form validation
var signupForm = document.getElementById('signupForm');
if (signupForm) {
    signupForm.addEventListener('submit', function(e) {
        var password = document.getElementById('password').value;
        var confirm = document.getElementById('confirm_password').value;
        var errors = validatePassword(password);

        if (errors.length > 0) {
            e.preventDefault();
            alert('Password must contain ' + errors.join(', ') + '.');
            return;
        }
        if (password !== confirm) {
            e.preventDefault();
            alert('Passwords do not match.');
            return;
        }
    });
}

// Change password form validation
var changePwdForm = document.querySelector('form[action*="change-password"]');
if (changePwdForm) {
    changePwdForm.addEventListener('submit', function(e) {
        var newPwd = document.getElementById('new_password').value;
        var confirm = document.getElementById('confirm_password').value;
        var errors = validatePassword(newPwd);

        if (errors.length > 0) {
            e.preventDefault();
            alert('New password must contain ' + errors.join(', ') + '.');
            return;
        }
        if (newPwd !== confirm) {
            e.preventDefault();
            alert('Passwords do not match.');
            return;
        }
    });
}

// ── Confirm Before Delete/Deactivate ─────────────────────
document.querySelectorAll('[data-confirm]').forEach(function(el) {
    el.addEventListener('click', function(e) {
        if (!confirm(el.getAttribute('data-confirm') || 'Are you sure?')) {
            e.preventDefault();
        }
    });
});

// ── Print QR Code ────────────────────────────────────────
function printQR() {
    var qrImage = document.getElementById('qrImage');
    if (!qrImage) return;
    var printWindow = window.open('', '_blank');
    printWindow.document.write('<html><head><title>QR Code</title>');
    printWindow.document.write('<style>body{text-align:center;padding:2rem;} img{width:400px;height:400px;} h2{margin-bottom:1rem;}</style>');
    printWindow.document.write('</head><body>');
    printWindow.document.write('<h2>Scan for Attendance</h2>');
    printWindow.document.write('<img src="' + qrImage.src + '" />');
    printWindow.document.write('</body></html>');
    printWindow.document.close();
    printWindow.print();
}
