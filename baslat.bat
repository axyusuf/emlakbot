@echo off
chcp 65001 >nul
echo =============================================
echo    EmlakBot - WhatsApp + Mini CRM
echo =============================================
echo.

REM Bagimliliklari kur (ilk kurulumda gerekli)
REM py -m pip install -r requirements.txt

echo [1/2] FastAPI sunucusu baslatiliyor (port 8000)...
start "EmlakBot-Server" cmd /k "cd /d %~dp0 && py -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload"

REM 3 saniye bekle
timeout /t 3 /nobreak >nul

REM ngrok.exe ayni klasorde olmali (yoksa: py download_ngrok.py)
if exist "%~dp0ngrok.exe" (
    echo [2/2] ngrok tuneli baslatiliyor...
    echo.
    echo *** Webhook URL ngrok penceresinde gorunecek ***
    echo *** Meta panelinde aynı URL'i girin: https://&lt;domain&gt;/webhook ***
    echo.
    start "EmlakBot-ngrok" cmd /k "%~dp0ngrok.exe http --domain=unveiled-ploy-banner.ngrok-free.dev 8000"
) else (
    echo [UYARI] ngrok.exe bulunamadi. Indirmek icin: py download_ngrok.py
    echo Sunucu yerel olarak http://localhost:8000 adresinde calisiyor.
)

echo.
echo EmlakBot baslatildi!
echo Anasayfa: http://localhost:8000/
echo Dashboard: http://localhost:8000/app
echo.
pause
