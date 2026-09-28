import logging
import os
import requests
from config import Config

logger = logging.getLogger(__name__)

BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000').rstrip('/')

def clean_phone_number(phone_raw):
    """Normalize phone number to international format without +."""
    if not phone_raw:
        return ""
    clean = str(phone_raw).replace('+', '').replace(' ', '').replace('-', '').strip()
    if clean.startswith('01') and len(clean) == 11:
        clean = '20' + clean[1:]
    return clean

def format_notification_text(ticket):
    """Format ticket notification content for admin alert."""
    preview = ticket.description[:180] + '...' if len(ticket.description) > 180 else ticket.description
    return (
        f"🎫 *New Ticket Submitted! / تذكرة جديدة*\n"
        f"------------------------\n"
        f"📌 *Ref:* `{ticket.reference_number}`\n"
        f"👤 *Name:* {ticket.name}\n"
        f"📞 *Phone:* {ticket.phone or 'N/A'}\n"
        f"✉️ *Email:* {ticket.email}\n"
        f"📝 *Issue:* {preview}\n"
        f"📎 *Attachment:* {'Yes' if ticket.attachment_filename else 'None'}\n"
        f"------------------------\n"
        f"🔗 *Admin Link:* {BASE_URL}/admin/ticket/{ticket.id}"
    )

def send_whatsapp_notification(ticket):
    """Send notification via WhatsApp Cloud API."""
    if not (Config.WHATSAPP_ENABLED and Config.WHATSAPP_API_TOKEN and Config.WHATSAPP_PHONE_NUMBER_ID and Config.WHATSAPP_RECIPIENT_NUMBER):
        return False
    
    url = f"{Config.WHATSAPP_API_URL}/{Config.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {Config.WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": Config.WHATSAPP_RECIPIENT_NUMBER,
        "type": "text",
        "text": {
            "body": format_notification_text(ticket)
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code in [200, 201]:
            logger.info("WhatsApp notification sent successfully.")
            return True
        else:
            logger.error(f"WhatsApp API error ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send WhatsApp notification: {e}")
        return False

def send_telegram_notification(ticket):
    """Send notification via Telegram Bot API."""
    if not (Config.TELEGRAM_ENABLED and Config.TELEGRAM_BOT_TOKEN and Config.TELEGRAM_CHAT_ID):
        return False
    
    url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": Config.TELEGRAM_CHAT_ID,
        "text": format_notification_text(ticket),
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("Telegram notification sent successfully.")
            return True
        else:
            logger.error(f"Telegram API error ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
        return False

def send_webhook_notification(ticket):
    """Send notification via generic webhook."""
    if not (Config.WEBHOOK_ENABLED and Config.WEBHOOK_URL):
        return False
    
    payload = ticket.to_dict()
    
    try:
        response = requests.post(Config.WEBHOOK_URL, json=payload, timeout=10)
        if response.status_code in [200, 201, 202, 204]:
            logger.info("Webhook notification sent successfully.")
            return True
        else:
            logger.error(f"Webhook error ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send Webhook notification: {e}")
        return False

def send_whatsmeow_notification(ticket):
    """Send admin alert notification via WhatsMeow Go QR-code gateway REST API."""
    if not (Config.WHATSMEOW_ENABLED and Config.WHATSMEOW_API_URL and Config.WHATSMEOW_RECIPIENT_NUMBER):
        return False
    
    recipient = clean_phone_number(Config.WHATSMEOW_RECIPIENT_NUMBER)
    text_content = format_notification_text(ticket)
    
    url = f"{Config.WHATSMEOW_API_URL.rstrip('/')}/send-message"
    payload = {
        "phone": recipient,
        "receiver": recipient,
        "to": recipient,
        "message": text_content,
        "text": text_content
    }
    
    headers = {
        "ngrok-skip-browser-warning": "true",
        "User-Agent": "TicketSystem/1.0"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code in [200, 201]:
            logger.info("WhatsMeow admin notification sent successfully.")
            return True
        else:
            logger.error(f"WhatsMeow API error ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send WhatsMeow notification: {e}")
        return False

def send_submitter_whatsmeow_confirmation(ticket):
    """Send automated instant confirmation message to the submitter's WhatsApp number."""
    if not (Config.WHATSMEOW_ENABLED and Config.WHATSMEOW_API_URL and ticket.phone):
        return False

    submitter_phone = clean_phone_number(ticket.phone)
    if not submitter_phone:
        return False

    track_url = f"{BASE_URL}/track/{ticket.reference_number}"
    text_content = (
        f"👋 *أهلاً {ticket.name}*\n"
        f"تم استلام تذكرتك بنجاح برقم مرجعي: `{ticket.reference_number}`\n\n"
        f"تذكرتك قيد المراجعة حالياً من قِبل فريق الدعم والإدارة.\n\n"
        f"🔗 *رابط متابعة التذكرة والردود:* \n"
        f"{track_url}\n\n"
        f"💡 *(ملاحظة: إذا كان الرابط غير أزرق، أضف الرقم لجهات اتصالك أو رد بأي رسالة لتفعيل الروابط).* "
    )

    url = f"{Config.WHATSMEOW_API_URL.rstrip('/')}/send-message"
    payload = {
        "phone": submitter_phone,
        "receiver": submitter_phone,
        "to": submitter_phone,
        "message": text_content,
        "text": text_content
    }

    headers = {
        "ngrok-skip-browser-warning": "true",
        "User-Agent": "TicketSystem/1.0"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code in [200, 201]:
            logger.info(f"Submitter WhatsApp confirmation sent to {submitter_phone}.")
            return True
        else:
            logger.error(f"WhatsMeow submitter API error ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send submitter WhatsApp confirmation: {e}")
        return False

def send_ticket_notifications(ticket):
    """
    Main dispatch function.
    1. Sends Admin Alert to Config.WHATSMEOW_RECIPIENT_NUMBER.
    2. Sends Automated Instant Confirmation to submitter's ticket.phone.
    """
    results = {}
    
    # 1. Admin Alert via WhatsMeow
    if Config.WHATSMEOW_ENABLED:
        results['whatsmeow_admin'] = send_whatsmeow_notification(ticket)
        # 2. Automated Submitter Instant Confirmation via WhatsMeow
        if ticket.phone:
            results['whatsmeow_submitter'] = send_submitter_whatsmeow_confirmation(ticket)
        
    # Try WhatsApp Cloud API
    if Config.WHATSAPP_ENABLED and not results.get('whatsmeow_admin', False):
        results['whatsapp'] = send_whatsapp_notification(ticket)
        
    # Try Telegram
    if Config.TELEGRAM_ENABLED:
        results['telegram'] = send_telegram_notification(ticket)
        
    # Try Webhook
    if Config.WEBHOOK_ENABLED:
        results['webhook'] = send_webhook_notification(ticket)
        
    return results

def send_status_update_notification(ticket):
    """Send notification directly to submitter's WhatsApp when support updates status or replies."""
    if not (Config.WHATSMEOW_ENABLED and Config.WHATSMEOW_API_URL):
        return False

    raw_recipient = ticket.phone if ticket.phone else Config.WHATSMEOW_RECIPIENT_NUMBER
    if not raw_recipient:
        return False

    recipient = clean_phone_number(raw_recipient)

    status_labels = {
        'open': 'Open / مفتوحة',
        'in_progress': 'In Progress / قيد المعالجة',
        'resolved': 'Resolved / تم الحل',
        'closed': 'Closed / مغلقة'
    }

    reply_preview = ticket.admin_reply if ticket.admin_reply else 'No reply text added.'
    track_url = f"{BASE_URL}/track/{ticket.reference_number}"

    update_text = (
        f"🔔 *تحديث على تذكرتك (Ticket Update)*\n"
        f"------------------------\n"
        f"📌 *Ref:* `{ticket.reference_number}`\n"
        f"📊 *الحالة:* {status_labels.get(ticket.status, ticket.status)}\n"
        f"💬 *رد الدعم:* {reply_preview}\n"
        f"------------------------\n"
        f"🔗 *رابط المتابعة المباشر:* \n"
        f"{track_url}"
    )

    url = f"{Config.WHATSMEOW_API_URL.rstrip('/')}/send-message"
    payload = {
        "phone": recipient,
        "receiver": recipient,
        "to": recipient,
        "message": update_text,
        "text": update_text
    }

    headers = {
        "ngrok-skip-browser-warning": "true",
        "User-Agent": "TicketSystem/1.0"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code in [200, 201]
    except Exception as e:
        logger.error(f"Failed to send status update notification: {e}")
        return False
