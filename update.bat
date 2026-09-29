@echo off
REM ============================================================
REM  X Feed Monitor - Perbarui mesin pengambil data
REM
REM  Jalankan file ini KALAU muncul pesan seperti:
REM    - "Query ID X sudah berubah"
REM    - "twscrape perlu diperbarui"
REM    - postingan berhenti muncul padahal akun normal
REM
REM  Penyebabnya: X mengganti endpoint internalnya, sehingga
REM  library twscrape perlu versi terbaru.
REM ============================================================

setlocal
title X Feed Monitor - Update
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"

echo.
echo   ============================================================
echo    Memperbarui mesin pengambil data (twscrape)
echo   ============================================================
echo.

if not exist "%PY%" (
    echo   [MASALAH] Environment belum siap.
    echo.
    echo   Jalankan run.bat terlebih dahulu ^(sekali saja^),
    echo   lalu jalankan file ini lagi.
    echo.
    pause
    exit /b 1
)

echo   Versi terpasang saat ini:
"%PY%" -m pip show twscrape 2>nul | findstr /b /c:"Version:"
echo.
echo   Mengunduh versi terbaru...
echo.

"%PY%" -m pip install --upgrade "twscrape[curl]" --disable-pip-version-check
if errorlevel 1 goto :gagal

echo.
echo   Versi setelah pembaruan:
"%PY%" -m pip show twscrape 2>nul | findstr /b /c:"Version:"

REM --- paksa pemasangan ulang dependency lain juga (kalau requirements berubah)
echo.
echo   Memeriksa komponen lain...
"%PY%" -m pip install -r requirements.txt --upgrade --quiet --disable-pip-version-check

echo.
echo   ============================================================
echo    Selesai. Silakan jalankan run.bat lagi.
echo   ============================================================
echo.
pause
exit /b 0

:gagal
echo.
echo   [MASALAH] Gagal memperbarui.
echo.
echo   Kemungkinan penyebab:
echo     - Tidak ada koneksi internet
echo     - Proxy / firewall memblokir pypi.org
echo.
echo   Periksa koneksi lalu coba lagi.
echo.
pause
exit /b 1
