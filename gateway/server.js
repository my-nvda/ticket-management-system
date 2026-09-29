const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const express = require('express');
const qrcodeTerminal = require('qrcode-terminal');
const QRCode = require('qrcode');
const pino = require('pino');
const path = require('path');

const fs = require('fs');

const app = express();
app.use(express.json());

const PORT = 3000;
let sock = null;
let qrCodeData = null;
let isConnected = false;
let isResetting = false;

function resetCorruptedSession() {
    if (isResetting) return;
    isResetting = true;
    try {
        console.log('[AUTO-RECOVERY] Resetting corrupted Baileys Signal session keys...');
        if (sock && sock.ws) {
            try { sock.ws.close(); } catch(e){}
        }
        sock = null;
        isConnected = false;
        qrCodeData = null;
        const authDir = path.join(__dirname, 'auth_info_baileys');
        if (fs.existsSync(authDir)) {
            fs.rmSync(authDir, { recursive: true, force: true });
            console.log('[AUTO-RECOVERY] Purged corrupted auth_info_baileys directory.');
        }
        setTimeout(() => {
            isResetting = false;
            connectToWhatsApp();
        }, 2000);
    } catch(e) {
        console.log('[AUTO-RECOVERY ERROR]:', e.message);
        isResetting = false;
    }
}

// Process-level crash prevention & auto-recovery safeguards
process.on('uncaughtException', (err) => {
    const msg = err ? (err.message || String(err)) : '';
    console.log('[SAFEGUARD] Suppressed uncaught exception:', msg);
    if (msg.includes('Over 2000 messages into the future') || msg.includes('SessionError') || msg.includes('Failed to decrypt')) {
        resetCorruptedSession();
    }
});

process.on('unhandledRejection', (reason) => {
    const msg = reason ? (reason.message || String(reason)) : '';
    console.log('[SAFEGUARD] Suppressed unhandled rejection:', msg);
    if (msg.includes('Over 2000 messages into the future') || msg.includes('SessionError') || msg.includes('Failed to decrypt')) {
        resetCorruptedSession();
    }
});

const msgStore = new Map();

async function connectToWhatsApp() {
    const authDir = path.join(__dirname, 'auth_info_baileys');
    const { state, saveCreds } = await useMultiFileAuthState(authDir);

    sock = makeWASocket({
        auth: state,
        logger: pino({ level: 'silent' }),
        printQRInTerminal: false,
        getMessage: async (key) => {
            if (key && key.id && msgStore.has(key.id)) {
                return msgStore.get(key.id);
            }
            return { conversation: "Ticket Notification Message" };
        }
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;
        
        if (qr) {
            qrCodeData = qr;
            console.log('\n==================================================');
            console.log('📱 SCAN THIS QR CODE WITH YOUR WHATSAPP APP:');
            console.log('==================================================\n');
            qrcodeTerminal.generate(qr, { small: true });
            console.log('\n==================================================');
            console.log(`Or open in browser: http://localhost:${PORT}/qr`);
            console.log('==================================================\n');
        }

        if (connection === 'close') {
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            console.log('Connection closed. Reconnecting:', shouldReconnect);
            isConnected = false;
            if (shouldReconnect) {
                setTimeout(connectToWhatsApp, 3000);
            }
        } else if (connection === 'open') {
            console.log('\n==================================================');
            console.log('✅ WHATSAPP CONNECTED SUCCESSFULLY!');
            console.log('Ready to process ticket notifications.');
            console.log('==================================================\n');
            isConnected = true;
            qrCodeData = null;
        }
    });
}

// REST Endpoint to send message
app.post('/send-message', async (req, res) => {
    try {
        const phone = req.body.phone || req.body.receiver || req.body.to;
        const message = req.body.message || req.body.text;

        if (!phone || !message) {
            return res.status(400).json({ success: false, error: 'Missing phone or message parameter' });
        }

        if (!isConnected || !sock) {
            return res.status(503).json({ 
                success: false, 
                error: `WhatsApp is not connected yet. Please scan QR code first at http://localhost:${PORT}/qr` 
            });
        }

        let cleanPhone = phone.toString().replace(/[^0-9]/g, '');
        if (cleanPhone.startsWith('01') && cleanPhone.length === 11) {
            cleanPhone = '20' + cleanPhone.substring(1);
        }
        
        let jid = `${cleanPhone}@s.whatsapp.net`;
        try {
            const results = await sock.onWhatsApp(cleanPhone);
            if (results && results.length > 0 && results[0].exists) {
                jid = results[0].jid;
            }
        } catch (e) {
            console.log('[WARN] onWhatsApp lookup fallback:', e.message);
        }

        const sentMsg = await sock.sendMessage(jid, { text: message });
        if (sentMsg && sentMsg.key && sentMsg.key.id) {
            msgStore.set(sentMsg.key.id, { conversation: message });
        }
        console.log(`[SUCCESS] WhatsApp notification sent to ${cleanPhone} (JID: ${jid})`);
        return res.json({ success: true, message: 'Message sent successfully', jid: jid });
    } catch (err) {
        console.error('[ERROR] Failed to send WhatsApp message:', err);
        return res.status(500).json({ success: false, error: err.message });
    }
});

const fs = require('fs');

// QR Code Web Page Endpoint (Server-side rendering to Base64 Image)
app.get('/qr', async (req, res) => {
    if (isConnected) {
        return res.send(`
            <!DOCTYPE html>
            <html>
            <head><title>WhatsApp Gateway Connected</title></head>
            <body style="font-family: sans-serif; text-align: center; padding: 3rem; background: #0f172a; color: #f8fafc;">
                <h1 style="color: #4ade80;">✅ الواتساب متصل بالفعل! (WhatsApp Connected)</h1>
                <p style="font-size: 1.1rem; margin-top: 1rem;">الخدمة تعمل وتستمع حالياً على البورت ${PORT}. الإشعارات يتم إرسالها تلقائياً.</p>
                <div style="margin-top: 2rem;">
                    <p style="color: #94a3b8;">هل تريد إلغاء الاتصال ومسح كيو آر جديد (QR Code)؟</p>
                    <a href="/reset" style="display: inline-block; background: #ef4444; color: white; padding: 0.75rem 1.5rem; border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 0.5rem;">🔄 إعادة تعيين الـ QR Code / Reset Session</a>
                </div>
            </body>
            </html>
        `);
    }

    if (!qrCodeData) {
        return res.send(`
            <!DOCTYPE html>
            <html>
            <head><title>Generating QR Code...</title><meta http-equiv="refresh" content="3"></head>
            <body style="font-family: sans-serif; text-align: center; padding: 3rem; background: #0f172a; color: #f8fafc;">
                <h1>⏳ جارٍ تجهيز الـ QR Code...</h1>
                <p>يرجى الانتظار ثوانٍ معدودة. سيتم تحديث الصفحة تلقائياً خلال 3 ثوانٍ.</p>
                <p><a href="/reset" style="color: #cbd5e1; text-decoration: underline;">إعادة المحاولة مجدداً (Reset)</a></p>
            </body>
            </html>
        `);
    }

    try {
        const qrImageUrl = await QRCode.toDataURL(qrCodeData, { width: 320, margin: 2 });
        res.send(`
            <!DOCTYPE html>
            <html>
            <head>
                <title>Scan WhatsApp QR Code</title>
                <meta http-equiv="refresh" content="15">
            </head>
            <body style="font-family: sans-serif; text-align: center; padding: 2rem; background: #0f172a; color: #f8fafc;">
                <h1 style="margin-bottom: 0.5rem;">📱 امسح كود الـ QR لربط الواتساب</h1>
                <p style="color: #94a3b8;">افتح الواتساب ➔ الإعدادات ➔ الأجهزة المرتبطة ➔ ربط جهاز</p>
                <div style="background: white; display: inline-block; padding: 1.5rem; border-radius: 16px; margin: 1.5rem auto; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
                    <img src="${qrImageUrl}" alt="WhatsApp QR Code" style="display: block; width: 300px; height: 300px;">
                </div>
                <p style="font-size: 0.85rem; color: #64748b;">تتحدث الصفحة تلقائياً كل 15 ثانية لتحديث الكود.</p>
            </body>
            </html>
        `);
    } catch (err) {
        res.status(500).send("Error generating QR code image: " + err.message);
    }
});

// Reset Session Endpoint
app.get('/reset', async (req, res) => {
    try {
        if (sock && sock.ws) {
            try { sock.ws.close(); } catch(e){}
        }
        sock = null;
        isConnected = false;
        qrCodeData = null;
        const authDir = path.join(__dirname, 'auth_info_baileys');
        if (fs.existsSync(authDir)) {
            fs.rmSync(authDir, { recursive: true, force: true });
        }
        setTimeout(() => {
            connectToWhatsApp();
        }, 1000);
        return res.send(`
            <!DOCTYPE html>
            <html>
            <head><title>Resetting Session...</title><meta http-equiv="refresh" content="3;url=/qr"></head>
            <body style="font-family: sans-serif; text-align: center; padding: 3rem; background: #0f172a; color: #f8fafc;">
                <h1 style="color: #38bdf8;">🔄 تم إعادة تعيين الجلسة بنجاح!</h1>
                <p>جارٍ إنشاء كيو آر (QR Code) جديد... سيتم توجيهك خلال 3 ثوانٍ.</p>
            </body>
            </html>
        `);
    } catch(err) {
        return res.status(500).send("Error resetting session: " + err.message);
    }
});

// Status Endpoint
app.get('/status', (req, res) => {
    res.json({ connected: isConnected, qr_available: !!qrCodeData });
});

app.listen(PORT, () => {
    console.log(`WhatsApp QR Gateway listening on http://localhost:${PORT}`);
    connectToWhatsApp();
});
