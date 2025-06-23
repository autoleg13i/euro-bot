@echo off
SETLOCAL

echo 🔄 Активую віртуальне середовище...
call venv\Scripts\activate

echo 📦 Перевіряю, чи встановлено бібліотеки...
pip show aiohttp >nul 2>&1
IF ERRORLEVEL 1 (
    echo 🧰 Встановлюю залежності...
    python -m pip install --upgrade pip
    pip install python-telegram-bot aiohttp python-dotenv apscheduler
) ELSE (
    echo ✅ Усі необхідні бібліотеки вже встановлені.
)

echo 🚀 Запускаю бота...
python euro_bot_renew.py

pause