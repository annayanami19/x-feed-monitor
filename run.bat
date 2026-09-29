@echo off
REM ============================================================
REM  X Feed Monitor - Launcher utama
REM  Dobel-klik file ini untuk menjalankan aplikasi.
REM
REM  Skrip ini akan:
REM    1. memeriksa Python tersedia
REM    2. membuat virtual environment (.venv) bila belum ada
REM    3. memasang dependency bila belum / berubah
REM    4. menjalankan aplikasi tanpa jendela hitam
REM ============================================================

setlocal
title X Feed Monitor
cd /d "%~dp0"

set "VENV=.venv"
set "PY=%VENV%\Scripts\python.exe"
set "PYW=%VENV%\Scripts\pythonw.exe"
set "MARKER=%VENV%\.deps-hash"

REM ------------------------------------------------------------
REM 1. Python tersedia dan benar-benar bisa dijalankan?
REM    (Pemeriksaan "where python" saja tidak cukup: alias rusak
REM     dari Microsoft Store juga terdeteksi oleh "where".)
REM ------------------------------------------------------------
where python >nul 2>nul
if errorlevel 1 goto :tanpa_python

python -c "import sys" >nul 2>nul
if errorlevel 1 goto :python_rusak

REM ------------------------------------------------------------
REM 2. Virtual environment
REM ------------------------------------------------------------
if not exist "%PY%" (
    echo.
    echo   Membuat virtual environment ^(sekali saja^)...
    echo.
    python -m venv "%VENV%"
    if errorlevel 1 goto :gagal_venv
)

REM ------------------------------------------------------------
REM 3. Dependency
REM    Dibandingkan lewat hash requirements.txt supaya pemasangan
REM    hanya terjadi saat daftar dependency benar-benar berubah.
REM
REM    Hash dihitung pakai Python (bukan certutil): output certutil
REM    berbeda-beda antar versi Windows dan bisa memuat spasi, sehingga
REM    pembandingannya tidak dapat diandalkan.
REM ------------------------------------------------------------
set "HASH_BARU="
for /f "usebackq delims=" %%H in (`python -c "import hashlib,pathlib;print(hashlib.md5(pathlib.Path('requirements.txt').read_bytes()).hexdigest())" 2^>nul`) do set "HASH_BARU=%%H"

set "HASH_LAMA="
if exist "%MARKER%" set /p HASH_LAMA=<"%MARKER%"

REM Pemasangan dilewati HANYA bila kedua hash terisi dan sama.
REM Kalau perhitungan hash gagal (HASH_BARU kosong), dependency tetap
REM dipasang ulang — lebih baik sedikit lambat daripada melewatkan
REM komponen yang dibutuhkan.
if not "%HASH_BARU%"=="" if "%HASH_BARU%"=="%HASH_LAMA%" goto :jalankan

echo.
echo   Menyiapkan komponen yang dibutuhkan...
echo   ^(pertama kali bisa 2-5 menit, mohon tunggu^)
echo.

"%PY%" -m pip install --upgrade pip --quiet --disable-pip-version-check
"%PY%" -m pip install -r requirements.txt --disable-pip-version-check
if errorlevel 1 goto :gagal_pip

> "%MARKER%" echo %HASH_BARU%

REM ------------------------------------------------------------
REM 4. Jalankan
REM ------------------------------------------------------------
:jalankan
if exist "%PYW%" (
    start "" "%PYW%" app.py
) else (
    start "" "%PY%" app.py
)
exit /b 0

REM ============================================================
REM  Penanganan masalah
REM ============================================================
:tanpa_python
echo.
echo   [MASALAH] Python tidak ditemukan di komputer ini.
echo.
echo   Langkah perbaikan:
echo     1. Unduh Python 3.10 atau lebih baru dari:
echo        https://www.python.org/downloads/
echo     2. Saat memasang, CENTANG kotak
echo        "Add python.exe to PATH".
echo     3. Jalankan ulang file ini.
echo.
pause
exit /b 1

:python_rusak
echo.
echo   [MASALAH] Python terdeteksi tapi tidak bisa dijalankan.
echo.
echo   Ini biasanya karena "App execution alias" bawaan Windows
echo   yang menunjuk ke Microsoft Store.
echo.
echo   Langkah perbaikan:
echo     1. Buka Settings -^> Apps -^> Advanced app settings
echo        -^> App execution aliases
echo     2. MATIKAN alias "python.exe" dan "python3.exe".
echo     3. Pasang Python asli dari https://www.python.org/downloads/
echo        lalu jalankan ulang file ini.
echo.
pause
exit /b 1

:gagal_venv
echo.
echo   [MASALAH] Gagal membuat virtual environment.
echo.
echo   Coba hapus folder ".venv" di folder ini, lalu jalankan ulang.
echo   Kalau masih gagal, pastikan antivirus tidak memblokir
echo   pembuatan folder di lokasi ini.
echo.
pause
exit /b 1

:gagal_pip
echo.
echo   [MASALAH] Gagal memasang komponen.
echo.
echo   Kemungkinan penyebab:
echo     - Tidak ada koneksi internet
echo     - Koneksi terputus di tengah proses
echo     - Proxy / firewall kantor memblokir pypi.org
echo.
echo   Coba jalankan ulang file ini. Kalau tetap gagal,
echo   jalankan run-debug.bat untuk melihat pesan lengkapnya.
echo.
pause
exit /b 1
