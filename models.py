import secrets
import string
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def generate_reference_number(length=8):
    """Generate a unique reference number like TKT-A8F2K9."""
    chars = string.ascii_uppercase + string.digits
    random_str = ''.join(secrets.choice(chars) for _ in range(length))
    return f"TKT-{random_str}"

class Ticket(db.Model):
    """Ticket model representing employee complaints/issues."""
    __tablename__ = 'tickets'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    reference_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    attachment_filename = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='open', index=True)
    admin_reply = db.Column(db.Text, nullable=True)
    whatsapp_sent = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        """Convert model to dictionary for JSON output."""
        return {
            'id': self.id,
            'reference_number': self.reference_number,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'description': self.description,
            'attachment_filename': self.attachment_filename,
            'status': self.status,
            'admin_reply': self.admin_reply,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f"<Ticket {self.reference_number} - {self.status}>"

def init_db(app):
    """Initialize database tables."""
    db.init_app(app)
    with app.app_context():
        db.create_all()
