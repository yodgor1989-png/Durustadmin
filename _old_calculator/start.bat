@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".env" (
    echo [!] .env fayli topilmadi.
    echo     .env.example dan nusxa oling va BOT_TOKEN ni yozing.
    pause
    exit /b 1
)

echo Kutubxonalar tekshirilmoqda...
python -m pip install -q -r requirements.txt

echo Bot ishga tushirilmoqda... (to^'xtatish uchun Ctrl+C)
python bot.py
pause
