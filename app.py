import os
import logging

from flask import (
    Flask, render_template, request, redirect, url_for, 
    flash, session, jsonify, send_from_directory
)
from werkzeug.utils import secure_filename

from config import Config
from models import db, Ticket, generate_reference_number, init_db
from notifications import send_ticket_notifications, send_status_update_notification

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask App
app = Flask(__name__)
app.config.from_object(Config)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize Database
init_db(app)

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

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
        flash(f'Ticket with reference {ref} was not found.', 'error')
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
    logger.info(f"Created ticket {ref_num} for {name} ({email}, {phone})")

    # Dispatch notification (non-blocking errors)
    try:
        send_ticket_notifications(ticket)
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
    """Admin login handler."""
    if not app.config['ADMIN_AUTH_ENABLED']:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == app.config['ADMIN_PASSWORD']:
            session['admin_logged_in'] = True
            flash('Logged in successfully.', 'success')
            return redirect(url_for('dashboard'))
        else:
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

# ==================== FILE SERVING ====================

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded attachments securely."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

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
    app.run(host='0.0.0.0', port=5000, debug=True)

