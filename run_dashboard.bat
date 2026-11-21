@echo off
title Panel Kontrol MikroTik - MIS Integral
cd /d "%~dp0"

echo ====================================================
echo   PANEL KONTROL MIKROTIK - MIS INTEGRAL TERNATE
echo   Membuka Dashboard di Browser...
echo ====================================================

start http://localhost:5000
python app.py
pause
