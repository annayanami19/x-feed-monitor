@echo off
REM ============================================================
REM  X Feed Monitor - Mode Debug
REM
REM  Menjalankan aplikasi DENGAN jendela hitam supaya pesan error
REM  terlihat langsung. Pakai file ini kalau aplikasi tidak mau
REM  terbuka, atau kalau ada masalah yang perlu ditelusuri.
REM
REM  Biarkan jendela ini terbuka selama aplikasi dipakai.
REM ============================================================

setlocal
title X Feed Monitor - Mode Debug
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"

echo.
echo   ============================================================
echo    X Feed Monitor - MODE DEBUG
echo   ============================================================
echo.
echo    Semua pesan (termasuk error) akan tampil di bawah ini.
echo    Biarkan jendela ini terbuka selama aplikasi berjalan.
echo.
echo   ------------------------------------------------------------
echo.

REM --- Pastikan environment sudah siap; kalau belum, arahkan ke run.bat
if not exist "%PY%" (
    echo   [INFO] Environment belum siap.
    echo          Jalankan run.bat terlebih dahulu ^(sekali saja^),
    echo          lalu kembali ke file ini.
    echo.
    pause
    exit /b 1
)

REM --- Jalankan dengan console
"%PY%" app.py

set "KODE=%ERRORLEVEL%"

echo.
echo   ------------------------------------------------------------
echo.
if not "%KODE%"=="0" (
    echo    Aplikasi berhenti dengan kode error: %KODE%
    echo.
    echo    Jejak lengkapnya juga tersimpan di file:
    echo      error.log
    echo.
    echo    Silakan kirimkan isi error.log beserta pesan di atas
    echo    saat melaporkan masalah.
) else (
    echo    Aplikasi ditutup dengan normal.
)
echo.
pause
exit /b %KODE%
