@echo off
chcp 65001 >nul
title EmlakBot - Kurulum ve Baslatma
cd /d %~dp0

echo =====================================================
echo    EmlakBot - Tek Tikla Kurulum ve Baslatma
echo =====================================================
echo.

REM --- Python var mi? ---
py --version >nul 2>&1
if errorlevel 1 (
    echo [HATA] Python kurulu degil veya 'py' komutu bulunamadi.
    echo.
    echo Lutfen Python 3.10 veya ustunu kurun:
    echo   https://www.python.org/downloads/
    echo.
    echo Kurarken "Add Python to PATH" kutucugunu MUTLAKA isaretleyin.
    echo Kurduktan sonra bu dosyayi tekrar calistirin.
    echo.
    pause
    exit /b 1
)

echo [1/4] Python tespit edildi:
py --version
echo.

REM --- Bagimliliklar kurulu mu? ---
echo [2/4] Bagimliliklar kontrol ediliyor...
py -c "import fastapi, uvicorn, bcrypt, openpyxl, itsdangerous, openai, httpx, dotenv, jinja2" >nul 2>&1
if errorlevel 1 (
    echo     Eksik bagimliliklar var. Kuruluyor (birkac dakika surebilir)...
    py -m pip install --upgrade pip >nul 2>&1
    py -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [HATA] Bagimliliklar kurulamadi. Internet baglantisini ve pip'i kontrol edin.
        pause
        exit /b 1
    )
    echo     Bagimliliklar kuruldu.
) else (
    echo     Tum bagimliliklar zaten kurulu.
)
echo.

REM --- Demo verisi yukle ---
echo [3/4] Demo verisi yukleniyor...
py seed_demo.py
echo.

REM --- Sunucu baslat ---
echo [4/4] FastAPI sunucusu baslatiliyor (port 8000)...
start "EmlakBot-Server" cmd /k "cd /d %~dp0 && py -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload"

REM Sunucunun ayaga kalkmasini bekle
timeout /t 4 /nobreak >nul

REM Tarayiciyi ac
echo.
echo Tarayici aciliyor: http://localhost:8000/
start http://localhost:8000/

REM (Opsiyonel) ngrok varsa baslat
if exist "%~dp0ngrok.exe" (
    echo.
    echo ngrok bulundu, tunel baslatiliyor...
    start "EmlakBot-ngrok" cmd /k "%~dp0ngrok.exe http 8000"
) else (
    echo.
    echo Not: ngrok.exe yok. WhatsApp baglamak icin: py download_ngrok.py
)

echo.
echo =====================================================
echo  EmlakBot calisiyor!
echo.
echo  Anasayfa: http://localhost:8000/
echo  Login   : http://localhost:8000/login
echo            E-posta: demo@emlakbot.test
echo            Sifre  : demo1234
echo.
echo  Durdurmak icin acilan "EmlakBot-Server" penceresinde Ctrl+C
echo =====================================================
echo.
pause
