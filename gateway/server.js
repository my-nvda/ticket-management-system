const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const express = require('express');
const qrcodeTerminal = require('qrcode-terminal');
const QRCode = require('qrcode');
const pino = require('pino');
const path = require('path');

const app = express();
app.use(express.json());

const PORT = 3000;
let sock = null;
let qrCodeData = null;
let isConnected = false;

async function connectToWhatsApp() {
    const authDir = path.join(__dirname, 'auth_info_baileys');
    const { state, saveCreds } = await useMultiFileAuthState(authDir);

    sock = makeWASocket({
        auth: state,
        logger: pino({ level: 'silent' }),
        printQRInTerminal: false
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

        const cleanPhone = phone.toString().replace(/[^0-9]/g, '');
        
        let jid = `${cleanPhone}@s.whatsapp.net`;
        try {
            const results = await sock.onWhatsApp(cleanPhone);
            if (results && results.length > 0 && results[0].exists) {
                jid = results[0].jid;
            }
        } catch (e) {
            console.log('[WARN] onWhatsApp lookup fallback:', e.message);
        }

        await sock.sendMessage(jid, { text: message });
        console.log(`[SUCCESS] WhatsApp notification sent to ${cleanPhone} (JID: ${jid})`);
        return res.json({ success: true, message: 'Message sent successfully', jid: jid });
    } catch (err) {
        console.error('[ERROR] Failed to send WhatsApp message:', err);
        return res.status(500).json({ success: false, error: err.message });
    }
});

// QR Code Web Page Endpoint (Server-side rendering to Base64 Image)
app.get('/qr', async (req, res) => {
    if (isConnected) {
        return res.send(`
            <!DOCTYPE html>
            <html>
            <head><title>WhatsApp Gateway Connected</title></head>
            <body style="font-family: sans-serif; text-align: center; padding: 3rem; background: #0f172a; color: #f8fafc;">
                <h1 style="color: #4ade80;">✅ WhatsApp is Connected!</h1>
                <p>Gateway is active and listening on port ${PORT}. Ticket notifications will be sent automatically.</p>
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
                <h1>⏳ Generating QR Code...</h1>
                <p>Please wait a moment while the gateway initializes. Page will refresh in 3 seconds.</p>
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
                <h1 style="margin-bottom: 0.5rem;">📱 Scan QR Code to Connect WhatsApp</h1>
                <p style="color: #94a3b8;">Open WhatsApp on your phone ➔ Settings ➔ Linked Devices ➔ Link a Device</p>
                <div style="background: white; display: inline-block; padding: 1.5rem; border-radius: 16px; margin: 1.5rem auto; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
                    <img src="${qrImageUrl}" alt="WhatsApp QR Code" style="display: block; width: 300px; height: 300px;">
                </div>
                <p style="font-size: 0.85rem; color: #64748b;">Page refreshes automatically every 15 seconds to fetch fresh QR tokens.</p>
            </body>
            </html>
        `);
    } catch (err) {
        res.status(500).send("Error generating QR code image: " + err.message);
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
