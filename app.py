import os
import logging

from flask import (
    Flask, render_template, request, redirect, url_for, 
    flash, session, jsonify, send_from_directory
)
from werkzeug.utils import secure_filename

from functools import wraps
import time
import hashlib
import hmac
import secrets as _secrets

from config import Config
from models import db, Ticket, generate_reference_number, init_db
from notifications import send_ticket_notifications, send_status_update_notification

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== RATE LIMITER ====================
_login_attempts = {}  # {ip_hash: [(timestamp, ...), ...]}
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW = 900  # 15 minutes

def _hash_ip(ip):
    return hashlib.sha256((ip or '').encode()).hexdigest()[:16]

def _is_rate_limited(ip):
    h = _hash_ip(ip)
    now = time.time()
    attempts = _login_attempts.get(h, [])
    attempts = [t for t in attempts if now - t < _RATE_LIMIT_WINDOW]
    _login_attempts[h] = attempts
    return len(attempts) >= _RATE_LIMIT_MAX

def _record_attempt(ip):
    h = _hash_ip(ip)
    _login_attempts.setdefault(h, []).append(time.time())

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)
app.config.from_object(Config)

# Ensure upload directory exists safely
try:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
except Exception as e:
    logger.warning(f"Could not create upload directory: {e}")

# Session security hardening
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
if os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RENDER'):
    app.config['SESSION_COOKIE_SECURE'] = True

# Security response headers
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    # Prevent caching of dynamic content to ensure logout and CSRF tokens work properly
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Handle reverse proxy headers (e.g., on Railway)
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Warn about weak default password
_admin_pw = app.config.get('ADMIN_PASSWORD', '')
if _admin_pw in ('admin123', 'password', 'admin', '123456', ''):
    logger.warning("⚠️  SECURITY WARNING: Admin password is weak or default. Set ADMIN_PASSWORD environment variable to a strong password!")

# Initialize Database safely
db.init_app(app)

_db_initialized = False

@app.before_request
def setup_database_once():
    global _db_initialized
    if not _db_initialized:
        try:
            db.create_all()
            _db_initialized = True
        except Exception as e:
            logger.error(f"Error creating DB tables: {e}")

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def validate_file_mime(file_storage):
    """Validate file's actual MIME type matches its extension (magic-byte check)."""
    if not file_storage or not file_storage.filename:
        return False
    ext = file_storage.filename.rsplit('.', 1)[1].lower() if '.' in file_storage.filename else ''
    expected_mime = app.config.get('ALLOWED_MIME_TYPES', {}).get(ext)
    if not expected_mime:
        return False
    header = file_storage.read(8192)
    file_storage.seek(0)
    magic_checks = {
        'image/png': header[:8] == b'\x89PNG\r\n\x1a\n',
        'image/jpeg': header[:3] == b'\xff\xd8\xff',
        'image/gif': header[:6] in (b'GIF87a', b'GIF89a'),
        'image/webp': header[:4] == b'RIFF' and header[8:12] == b'WEBP',
        'application/pdf': header[:5] == b'%PDF-',
    }
    if expected_mime in magic_checks:
        return magic_checks[expected_mime]
    return True

# Helper to check admin authentication status
def is_admin_authenticated():
    if not app.config['ADMIN_AUTH_ENABLED']:
        return True
    return session.get('admin_logged_in') is True

# Inject global variables to all templates
@app.context_processor
def inject_globals():
    return {
        'admin_auth_enabled': app.config['ADMIN_AUTH_ENABLED'],
        'is_admin': is_admin_authenticated()
    }

# ==================== CSRF PROTECTION ====================

@app.before_request
def ensure_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = _secrets.token_hex(32)

@app.context_processor
def inject_csrf():
    return {'csrf_token': session.get('_csrf_token', '')}

def validate_csrf():
    token = request.form.get('_csrf_token', '')
    if not token or token != session.get('_csrf_token', ''):
        from flask import abort
        abort(403)

# ==================== PUBLIC ROUTES ====================

@app.route('/')
@app.route('/new-ticket')
def new_ticket():
    """Public employee ticket submission form."""
    return render_template('index.html')

@app.route('/track', methods=['GET', 'POST'])
def track_ticket():
    """Public page allowing users to search and view ticket status & admin response."""
    searched_ref = None
    if request.method == 'POST':
        searched_ref = request.form.get('ref', '').strip().upper()
        if searched_ref:
            return redirect(url_for('track_ticket_view', ref=searched_ref))
    return render_template('public_ticket_view.html', ticket=None, searched_ref=searched_ref)

@app.route('/track/search', methods=['POST'])
def track_ticket_post():
    """Form submission target for tracking lookup."""
    ref = request.form.get('ref', '').strip().upper()
    if ref:
        return redirect(url_for('track_ticket_view', ref=ref))
    flash('Please enter a valid reference number.', 'error')
    return redirect(url_for('track_ticket'))

@app.route('/track/<ref>')
def track_ticket_view(ref):
    """View ticket status and support team reply by reference number."""
    ticket = Ticket.query.filter_by(reference_number=ref.strip().upper()).first()
    if not ticket:
        from markupsafe import escape
        flash(f'Ticket with reference {escape(ref)} was not found.', 'error')
        return render_template('public_ticket_view.html', ticket=None, searched_ref=ref)
    return render_template('public_ticket_view.html', ticket=ticket)

def clean_phone_number(phone_raw):
    """Normalize phone number to international format without +."""
    if not phone_raw:
        return ""
    clean = phone_raw.replace('+', '').replace(' ', '').replace('-', '').strip()
    if clean.startswith('01') and len(clean) == 11:
        clean = '20' + clean[1:]
    return clean

@app.route('/submit', methods=['POST'])
def submit_ticket():
    """Process ticket submission."""
    validate_csrf()
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone_raw = request.form.get('phone', '').strip()
    description = request.form.get('description', '').strip()
    
    phone = clean_phone_number(phone_raw)
    
    # Server-side validation
    if not name or not email or not description:
        flash('Please fill in all required fields.', 'error')
        return redirect(url_for('new_ticket'))
    
    # Handle File Upload
    attachment_filename = None
    if 'attachment' in request.files:
        file = request.files['attachment']
        if file and file.filename != '':
            if allowed_file(file.filename):
                if not validate_file_mime(file):
                    flash('File content does not match its extension. Upload rejected for security.', 'error')
                    return redirect(url_for('new_ticket'))
                filename = secure_filename(file.filename)
                unique_name = f"{generate_reference_number(6)}_{filename}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
                file.save(save_path)
                attachment_filename = unique_name
            else:
                flash('File type not allowed. Please upload an image or PDF.', 'error')
                return redirect(url_for('new_ticket'))

    # Generate unique reference number
    ref_num = generate_reference_number()
    while Ticket.query.filter_by(reference_number=ref_num).first() is not None:
        ref_num = generate_reference_number()

    # Save Ticket to DB
    ticket = Ticket(
        reference_number=ref_num,
        name=name,
        phone=phone,
        email=email,
        description=description,
        attachment_filename=attachment_filename
    )
    
    db.session.add(ticket)
    db.session.commit()
    session['last_submitted_ref'] = ref_num
    logger.info(f"Created ticket {ref_num} for {name} ({email}, {phone})")

    # Dispatch notification (non-blocking errors)
    try:
        res = send_ticket_notifications(ticket)
        if res and (res.get('whatsmeow_submitter') or res.get('whatsmeow_admin')):
            ticket.whatsapp_sent = True
            db.session.commit()
    except Exception as e:
        logger.error(f"Notification error: {e}")

    return redirect(url_for('confirmation', ref=ref_num))

@app.route('/confirmation/<ref>')
def confirmation(ref):
    """Accessible confirmation page displaying reference number."""
    ticket = Ticket.query.filter_by(reference_number=ref).first_or_404()
    return render_template('confirmation.html', ticket=ticket)

# ==================== ADMIN ROUTES ====================

@app.route('/admin')
@app.route('/dashboard')
def dashboard():
    """Admin dashboard listing all tickets."""
    if not is_admin_authenticated():
        return redirect(url_for('admin_login'))
        
    try:
        from notifications import retry_pending_whatsapp_notifications
        retry_pending_whatsapp_notifications()
    except Exception:
        pass

    status_filter = request.args.get('status', 'all')
    
    query = Ticket.query
    if status_filter in ['open', 'in_progress', 'resolved', 'closed']:
        query = query.filter_by(status=status_filter)
        
    tickets = query.order_by(Ticket.created_at.desc()).all()
    
    stats = {
        'total': Ticket.query.count(),
        'open': Ticket.query.filter_by(status='open').count(),
        'in_progress': Ticket.query.filter_by(status='in_progress').count(),
        'resolved': Ticket.query.filter_by(status='resolved').count(),
        'closed': Ticket.query.filter_by(status='closed').count()
    }
    
    return render_template('dashboard.html', tickets=tickets, stats=stats, current_filter=status_filter)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login handler with brute-force protection."""
    if not app.config['ADMIN_AUTH_ENABLED']:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        validate_csrf()
        client_ip = request.remote_addr
        if _is_rate_limited(client_ip):
            flash('Too many login attempts. Please try again in 15 minutes.', 'error')
            return render_template('login.html'), 429
        
        password = request.form.get('password', '')
        if hmac.compare_digest(password, app.config['ADMIN_PASSWORD']):
            session['admin_logged_in'] = True
            h = _hash_ip(client_ip)
            _login_attempts.pop(h, None)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('dashboard'))
        else:
            _record_attempt(client_ip)
            flash('Invalid admin password. Please try again.', 'error')
    
    return render_template('login.html')

@app.route('/admin/logout')
def admin_logout():
    """Admin logout handler."""
    session.pop('admin_logged_in', None)
    flash('Logged out successfully.', 'info')
    return redirect(url_for('new_ticket'))

@app.route('/admin/ticket/<int:ticket_id>')
def ticket_detail(ticket_id):
    """View details of a specific ticket."""
    if not is_admin_authenticated():
        return redirect(url_for('admin_login'))
        
    ticket = Ticket.query.get_or_404(ticket_id)
    return render_template('ticket_detail.html', ticket=ticket)

@app.route('/admin/ticket/<int:ticket_id>/status', methods=['POST'])
def update_status(ticket_id):
    """Update ticket status and admin reply via AJAX or POST form."""
    if not is_admin_authenticated():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
    validate_csrf()
        
    ticket = Ticket.query.get_or_404(ticket_id)
    new_status = request.form.get('status')
    admin_reply = request.form.get('admin_reply', '').strip()
    
    valid_statuses = ['open', 'in_progress', 'resolved', 'closed']
    if new_status in valid_statuses:
        ticket.status = new_status
        
    if admin_reply != '':
        ticket.admin_reply = admin_reply
        
    db.session.commit()
    logger.info(f"Ticket {ticket.reference_number} status updated to {new_status}")
    
    # Send status update & response notification to submitter
    try:
        send_status_update_notification(ticket)
    except Exception as e:
        logger.error(f"Status update notification error: {e}")
    
    status_labels = {
        'open': 'Open',
        'in_progress': 'In Progress',
        'resolved': 'Resolved',
        'closed': 'Closed'
    }
    
    message = f"Status updated to {status_labels.get(new_status, new_status)} and response saved."
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({
            'success': True, 
            'status': new_status,
            'status_label': status_labels.get(new_status, new_status),
            'admin_reply': ticket.admin_reply,
            'message': message
        })
        
    flash(message, 'success')
    return redirect(url_for('ticket_detail', ticket_id=ticket_id))

@app.route('/admin/ticket/<int:ticket_id>/delete', methods=['POST'])
def delete_ticket(ticket_id):
    """Delete ticket record and associated attachment file."""
    if not is_admin_authenticated():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    validate_csrf()

    ticket = Ticket.query.get_or_404(ticket_id)
    ref_num = ticket.reference_number
    
    # Remove physical file if exists
    if ticket.attachment_filename:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], ticket.attachment_filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Error removing attachment file: {e}")

    db.session.delete(ticket)
    db.session.commit()
    logger.info(f"Deleted ticket {ref_num}")
    
    flash(f"Ticket {ref_num} deleted successfully.", 'success')
    return redirect(url_for('dashboard'))

@app.route('/admin/ticket/<int:ticket_id>/delete-attachment', methods=['POST'])
def delete_attachment(ticket_id):
    """Delete attachment file of a ticket without deleting the ticket."""
    if not is_admin_authenticated():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    validate_csrf()

    ticket = Ticket.query.get_or_404(ticket_id)
    
    if ticket.attachment_filename:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], ticket.attachment_filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Error removing attachment file: {e}")
        ticket.attachment_filename = None
        db.session.commit()
        logger.info(f"Deleted attachment for ticket {ticket.reference_number}")
        flash("Attachment deleted successfully.", 'success')
    else:
        flash("No attachment found for this ticket.", 'info')

    return redirect(url_for('ticket_detail', ticket_id=ticket_id))

@app.route('/test-whatsapp')
def test_whatsapp_endpoint():
    """Live diagnostic endpoint to verify WhatsApp integration (admin only)."""
    if not is_admin_authenticated():
        from flask import abort
        abort(403)
    import requests
    from config import Config
    
    api_url = Config.WHATSMEOW_API_URL
    recipient = Config.WHATSMEOW_RECIPIENT_NUMBER or '201000000000'
    enabled = Config.WHATSMEOW_ENABLED
    
    diagnostic = {
        'WHATSMEOW_ENABLED': enabled,
        'WHATSMEOW_API_URL': api_url,
        'WHATSMEOW_RECIPIENT_NUMBER': Config.WHATSMEOW_RECIPIENT_NUMBER,
        'BASE_URL': os.environ.get('BASE_URL', 'http://localhost:5000')
    }
    
    if not api_url or api_url == 'http://localhost:3000':
        diagnostic['error'] = 'WHATSMEOW_API_URL is missing or using default localhost:3000 on Railway. Please set WHATSMEOW_API_URL in Railway Variables to your ngrok URL.'
        return jsonify(diagnostic), 400
        
    target_url = f"{api_url.rstrip('/')}/send-message"
    payload = {
        "phone": recipient,
        "receiver": recipient,
        "to": recipient,
        "message": "🧪 Test WhatsApp message from Railway diagnostic tool.",
        "text": "🧪 Test WhatsApp message from Railway diagnostic tool."
    }
    headers = {
        "ngrok-skip-browser-warning": "true",
        "User-Agent": "TicketSystem/1.0"
    }
    
    try:
        res = requests.post(target_url, json=payload, headers=headers, timeout=10)
        diagnostic['response_status'] = res.status_code
        diagnostic['response_text'] = res.text
        diagnostic['success'] = res.status_code in [200, 201]
        return jsonify(diagnostic), (200 if diagnostic['success'] else 500)
    except Exception as err:
        diagnostic['exception'] = str(err)
        diagnostic['success'] = False
        return jsonify(diagnostic), 500

# ==================== FILE SERVING ====================

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded attachments with IDOR protection."""
    if is_admin_authenticated():
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    
    ticket = Ticket.query.filter_by(attachment_filename=filename).first()
    if not ticket:
        from flask import abort
        abort(404)
    
    referer = request.headers.get('Referer', '')
    ref_num = ticket.reference_number
    if ref_num and (f'/confirmation/{ref_num}' in referer or 
                    f'/track/{ref_num}' in referer or
                    f'/admin/ticket/' in referer):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    
    if session.get('last_submitted_ref') == ref_num:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    
    from flask import abort
    abort(403)

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', 
                           error_code=404, 
                           error_title_en="Page Not Found", 
                           error_title_ar="الصفحة غير موجودة",
                           error_msg_en="The page you are looking for does not exist or has been moved.",
                           error_msg_ar="الصفحة التي تبحث عنها غير موجودة أو تم نقلها."), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', 
                           error_code=500, 
                           error_title_en="Internal Server Error", 
                           error_title_ar="خطأ داخلي في الخادم",
                           error_msg_en="Something went wrong on our end. Please try again later.",
                           error_msg_ar="حدث خطأ غير متوقع. يرجى المحاولة لاحقاً."), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
