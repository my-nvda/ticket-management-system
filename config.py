import os
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

class Config:
    """Application configuration loader."""
    
    # Secret Key for Flask sessions
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default-dev-secret-key-change-in-prod')
    
    # Database Configuration (supports SQLite local & PostgreSQL remote)
    # Fix standard postgres:// URI format if provided by Neon/Supabase/Heroku/Render
    _db_url = os.environ.get('DATABASE_URL', 'sqlite:///tickets.db')
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Admin Auth Configuration
    ADMIN_AUTH_ENABLED = os.environ.get('ADMIN_AUTH_ENABLED', 'true').lower() in ['true', '1', 'yes']
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
    
    # Upload Configuration
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, os.environ.get('UPLOAD_FOLDER', 'uploads'))
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'txt'}
    
    # Notification Settings
    WHATSAPP_ENABLED = os.environ.get('WHATSAPP_ENABLED', 'false').lower() in ['true', '1', 'yes']
    WHATSAPP_API_URL = os.environ.get('WHATSAPP_API_URL', 'https://graph.facebook.com/v18.0')
    WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', '')
    WHATSAPP_API_TOKEN = os.environ.get('WHATSAPP_API_TOKEN', '')
    WHATSAPP_RECIPIENT_NUMBER = os.environ.get('WHATSAPP_RECIPIENT_NUMBER', '')
    
    TELEGRAM_ENABLED = os.environ.get('TELEGRAM_ENABLED', 'false').lower() in ['true', '1', 'yes']
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
    
    WEBHOOK_ENABLED = os.environ.get('WEBHOOK_ENABLED', 'false').lower() in ['true', '1', 'yes']
    WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')

    # WhatsMeow (Go QR Gateway) Settings
    WHATSMEOW_ENABLED = os.environ.get('WHATSMEOW_ENABLED', 'false').lower() in ['true', '1', 'yes']
    WHATSMEOW_API_URL = os.environ.get('WHATSMEOW_API_URL', 'http://localhost:3000')
    WHATSMEOW_RECIPIENT_NUMBER = os.environ.get('WHATSMEOW_RECIPIENT_NUMBER', '')

    @classmethod
    def get_active_notifications(cls):
        """Returns list of active notification channels."""
        channels = []
        if cls.WHATSMEOW_ENABLED and cls.WHATSMEOW_RECIPIENT_NUMBER:
            channels.append('WhatsMeow (QR Gateway)')
        if cls.WHATSAPP_ENABLED and cls.WHATSAPP_API_TOKEN:
            channels.append('WhatsApp Cloud API')
        if cls.TELEGRAM_ENABLED and cls.TELEGRAM_BOT_TOKEN:
            channels.append('Telegram')
        if cls.WEBHOOK_ENABLED and cls.WEBHOOK_URL:
            channels.append('Webhook')
        return channels
