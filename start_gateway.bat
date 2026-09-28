@echo off
title WhatsApp QR Gateway
echo ===================================================
echo   WhatsApp QR Gateway (Multi-Device Protocol)
echo ===================================================
echo.
cd /d "%~dp0gateway"
node server.js
pause
