@echo off
title WhatsApp QR Gateway
echo ===================================================
echo   WhatsApp QR Gateway (Keep-Alive Auto-Restart)
echo ===================================================
echo.
cd /d "%~dp0gateway"

:loop
echo [%time%] Starting WhatsApp Gateway Service...
node server.js
echo.
echo [WARNING] Gateway process stopped or disconnected. Reconnecting in 3 seconds...
timeout /t 3
goto loop
