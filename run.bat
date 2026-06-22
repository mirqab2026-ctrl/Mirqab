@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Mirqab - نظام مرقاب الذكي

REM ====== بيانات الدخول ======
REM تُقرأ من ملف credentials.local.bat (غير مرفوع للمستودع لأسباب أمنية).
REM للإعداد: انسخ credentials.example.bat إلى credentials.local.bat وغيّر القيم.
if exist "credentials.local.bat" (
    call credentials.local.bat
) else (
    echo [تحذير] لم يُعثر على credentials.local.bat — سيُستخدم admin/admin افتراضياً.
    echo         انسخ credentials.example.bat الى credentials.local.bat وغيّر كلمة المرور.
    set GATE_USERNAME=admin
    set GATE_PASSWORD=admin
)

echo ============================================
echo    Mirqab  |  نظام مرقاب الذكي
echo ============================================
echo  تشغيل الواجهة...
echo.
python -m streamlit run frontend\app.py
pause
