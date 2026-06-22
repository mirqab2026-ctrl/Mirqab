@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Mirqab - تثبيت المتطلبات
echo تثبيت متطلبات النظام... قد يستغرق بضع دقائق
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo تنزيل نماذج الوجه (buffalo_s) — مرة واحدة فقط...
python scripts\setup_face_models.py
echo.
echo تم. شغّل النظام عبر run.bat
pause
