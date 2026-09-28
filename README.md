# 🎫 Accessible Ticket Management System

A production-ready, lightweight custom web application built with **Flask**, **SQLAlchemy**, **Vanilla CSS/JS**, and strict **WCAG 2.1 AA Web Accessibility (a11y)** standards. Designed for seamless usage by both **sighted users** and **blind/visually impaired screen reader users**, with instant **bilingual support (English & Arabic with full RTL)**.

---

## 🌟 Key Features

1. **Accessibility & Screen Readers (WCAG 2.1 AA)**:
   - Native HTML5 semantics (`<header>`, `<nav>`, `<main>`, `<section>`, `<article>`).
   - Every form input explicitly associated with `<label for="...">`.
   - `aria-describedby` for help text and dynamic error messages.
   - Screen reader live region (`aria-live="polite"` / `role="status"`) for instant status updates and confirmations.
   - Accessible keyboard navigation (Tab, Shift+Tab, Enter, Space) with visible, high-contrast `:focus-visible` ring.
   - Skip to main content link (`.skip-link`).
   - Tables with proper `<th scope="col">` and understandable column hierarchies.

2. **Bilingual (English / Arabic RTL)**:
   - Default language is **English**.
   - One-click toggle button to switch to **Arabic** with `dir="rtl"` layout, Arabic typography (`Noto Sans Arabic`), and instant UI text translation.

3. **Public Ticket Submission Portal (`/` or `/new-ticket`)**:
   - Clean, accessible form with Full Name, Email, Description, and Screenshot/Attachment upload.
   - Generates a unique Ticket Reference Number (e.g. `TKT-A8F2K9`).
   - Accessible confirmation screen with copy reference button and polite screen reader announcements.

4. **Admin / Management Dashboard (`/admin` or `/dashboard`)**:
   - Optional session password protection (`ADMIN_AUTH_ENABLED=true/false`).
   - Real-time metric cards (Total, Open, In Progress, Resolved, Closed).
   - Filter tickets by status.
   - Detailed ticket view with attachment preview/download.
   - AJAX status update with screen reader live announcements (`"Status updated to Resolved"` / `"تم تحديث الحالة إلى تم الحل"`).

5. **Modular Instant Notifications**:
   - **WhatsApp Cloud API / Twilio** integration (Primary).
   - **Telegram Bot API** integration (Fallback).
   - **Generic Webhook** integration.
   - Notifications include Ticket Reference, Name, Email, and Issue Preview.

6. **Flexible Database & File Storage**:
   - SQLite for local development.
   - PostgreSQL (Neon / Supabase / Render) support via `DATABASE_URL`.
   - Local directory upload storage with configurable 16MB file limit.

---

## 📁 Project Structure

```
ticket-system/
├── app.py                  # Main Flask App & Routing logic
├── config.py               # Configuration Loader (.env reader)
├── models.py               # SQLAlchemy Ticket Data Model & DB init
├── notifications.py        # WhatsApp, Telegram & Webhook notification service
├── requirements.txt        # Python dependencies
├── Procfile                # Production deployment process file (Gunicorn)
├── render.yaml             # Render.com Blueprint configuration
├── .env.example            # Environment variables template
├── README.md               # Documentation & Setup Guide
├── uploads/                # Directory for user attachments
├── static/
│   ├── css/
│   │   └── style.css       # Premium WCAG 2.1 AA accessible CSS
│   └── js/
│       └── main.js         # Vanilla JS (a11y announcer, EN/AR switch, AJAX)
└── templates/
    ├── base.html           # Core HTML layout with a11y live region
    ├── index.html          # Public ticket submission form
    ├── confirmation.html   # Submission confirmation page
    ├── login.html          # Admin login portal
    ├── dashboard.html      # Management dashboard & ticket table
    └── ticket_detail.html  # Ticket detail & status update view
```

---

## 🚀 How to Run Locally

### 1. Prerequisites
- Python 3.9+
- `pip`

### 2. Setup Project
```bash
cd D:\.gemini\antigravity\scratch\ticket-system

# Create a virtual environment (optional but recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file from `.env.example`:
```bash
cp .env.example .env
```

Key environment options in `.env`:
```ini
ADMIN_AUTH_ENABLED=false
ADMIN_PASSWORD=admin123
DATABASE_URL=sqlite:///tickets.db

# WhatsApp Settings (Optional)
WHATSAPP_ENABLED=false
WHATSAPP_PHONE_NUMBER_ID=your_id
WHATSAPP_API_TOKEN=your_token
WHATSAPP_RECIPIENT_NUMBER=201234567890

# Telegram Settings (Optional)
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 4. Start Application
```bash
python app.py
```
Open your browser and navigate to **`http://localhost:5000`**.

---

## ☁️ Deployment Guide (Free PaaS)

### Deploying to Render.com
1. Push your repository to GitHub / GitLab.
2. Log in to [Render.com](https://render.com) and click **New > Web Service**.
3. Connect your repository.
4. Select Environment: **Python**.
5. Set Build Command: `pip install -r requirements.txt`
6. Set Start Command: `gunicorn app:app`
7. Add your Environment Variables (`SECRET_KEY`, `ADMIN_AUTH_ENABLED`, `ADMIN_PASSWORD`, `DATABASE_URL`).
8. Click **Create Web Service**.

### Deploying to Railway.app
1. Log in to [Railway.app](https://railway.app).
2. Click **New Project > Deploy from GitHub repo**.
3. Add a PostgreSQL database service (optional) and link `DATABASE_URL`.
4. Railway automatically reads the `Procfile` and deploys your service.

---

## ♿ Accessibility Compliance Summary

| WCAG 2.1 Standard | Implementation |
|-------------------|----------------|
| **1.3.1 Info & Relationships** | Semantic elements (`<main>`, `<header>`, `<nav>`), explicit `<label for>` pairing, `<th scope="col">`. |
| **1.4.3 Contrast (Minimum)** | Contrast ratio ≥ 4.5:1 on all text & icons against backgrounds. |
| **2.1.1 Keyboard** | All interactive controls accessible via Tab / Enter / Space. |
| **2.4.7 Focus Visible** | Strong `:focus-visible` outline ring (3px solid indigo/purple). |
| **4.1.3 Status Messages** | `aria-live="polite"` live announcer region for notifications and status updates without reloading. |
| **Multilingual (RTL)** | Automatic `lang="ar"` and `dir="rtl"` attribute switching with localized labels. |
