"""Uji ketahanan penutupan jendela.

Menutup jendela pada berbagai waktu relatif terhadap siklus polling, untuk
memastikan tidak ada error yang muncul akibat race condition antara worker
(thread latar) dan proses pembongkaran jendela.

CARA PAKAI
==========
    python tools/uji_tutup.py

Setiap skenario dijalankan di **proses terpisah**. Ini disengaja:

Membuat lebih dari satu QApplication dalam satu proses Python tidak didukung
Qt — objek dari skenario sebelumnya bisa belum benar-benar dibersihkan, dan
error "wrapped C/C++ object has been deleted" yang muncul kemudian berasal
dari sisa objek itu, BUKAN dari aplikasi. Menjalankan tiap skenario di proses
sendiri memberi hasil yang bersih dan dapat dipercaya.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Waktu penutupan yang diuji (ms setelah refresh dipicu).
#: Nilai-nilai ini dipilih untuk menabrak momen berbeda dalam siklus polling:
#:   200  — sebelum worker benar-benar mulai
#:   600  — saat worker mulai menyiapkan koneksi
#:   1000 — saat request pertama berjalan
#:   1500 — saat menunggu balasan
#:   2500 — saat mungkin sudah menerima data
#:   4000 — saat jeda antar akun
WAKTU_UJI = [200, 600, 1000, 1500, 2500, 4000]

#: Batas waktu satu skenario (detik).
BATAS_DETIK = 45

#: Ambang "terlalu lambat" untuk penutupan jendela (detik).
BATAS_LAMBAT = 3.0

#: Kode skrip yang dijalankan di proses terpisah.
#: Menerima satu argumen: waktu penutupan dalam milidetik.
SKRIP = r'''
import os, sys, time, traceback
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, {root!r})

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from app.ikon import ikon_aplikasi
from app.paths import pastikan_folder
from app.ui.main_window import JendelaUtama

delay = int(sys.argv[1])

app = QApplication([])
app.setWindowIcon(ikon_aplikasi())
pastikan_folder()

errors = []
def tangkap(tipe, nilai, tb):
    errors.append(f"{{tipe.__name__}}: {{nilai}}")
sys.excepthook = tangkap

jendela = JendelaUtama()
jendela.show()
QTimer.singleShot(300, jendela.mulai_refresh)

waktu = {{"durasi": 0.0}}
def tutup():
    t0 = time.time()
    jendela.close()
    waktu["durasi"] = time.time() - t0

QTimer.singleShot(delay, tutup)
QTimer.singleShot(20000, app.quit)
app.exec()

# Hasil ditulis ke stdout dalam format yang mudah dibaca induk.
print("HASIL_DURASI={{:.3f}}".format(waktu["durasi"]))
print("HASIL_ERROR={{}}".format(len(errors)))
for e in errors:
    print("HASIL_PESAN={{}}".format(e))
'''


def jalankan_satu(delay_ms: int) -> tuple[float, list[str]]:
    """Jalankan satu skenario di proses terpisah."""
    kode = SKRIP.format(root=str(ROOT))
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        hasil = subprocess.run(
            [sys.executable, "-c", kode, str(delay_ms)],
            capture_output=True,
            text=True,
            timeout=BATAS_DETIK,
            env=env,
            cwd=str(ROOT),
        )
    except subprocess.TimeoutExpired:
        return 999.0, ["skenario melewati batas waktu"]

    durasi = 0.0
    errors: list[str] = []
    for baris in (hasil.stdout or "").splitlines():
        if baris.startswith("HASIL_DURASI="):
            try:
                durasi = float(baris.split("=", 1)[1])
            except ValueError:
                pass
        elif baris.startswith("HASIL_PESAN="):
            errors.append(baris.split("=", 1)[1])

    # Error yang lolos ke stderr juga dihitung (mis. crash keras).
    for baris in (hasil.stderr or "").splitlines():
        if "Error" in baris or "Traceback" in baris:
            if not any(k in baris for k in ("QFontDatabase", "Note that Qt")):
                errors.append(baris.strip())

    return durasi, errors


def main() -> int:
    print("=" * 62)
    print("  UJI KETAHANAN PENUTUPAN JENDELA")
    print("=" * 62)
    print(f"  {len(WAKTU_UJI)} skenario, masing-masing di proses terpisah")
    print()

    hasil: list[tuple[int, float, list[str]]] = []
    for delay in WAKTU_UJI:
        durasi, errors = jalankan_satu(delay)
        hasil.append((delay, durasi, errors))

        lambat = durasi >= BATAS_LAMBAT
        status = "OK " if (not errors and not lambat) else "GAGAL"
        print(f"  [{status}] tutup @{delay:4d}ms -> {durasi:.2f}s, {len(errors)} error")
        for e in errors:
            print(f"          {e}")

    print("=" * 62)

    gagal = [h for h in hasil if h[2] or h[1] >= BATAS_LAMBAT]
    if gagal:
        print(f"HASIL: {len(gagal)} dari {len(hasil)} skenario GAGAL")
        return 1

    paling_lambat = max(h[1] for h in hasil)
    print(f"HASIL: {len(hasil)}/{len(hasil)} skenario LULUS")
    print(f"Penutupan paling lambat: {paling_lambat:.2f} detik")
    return 0


if __name__ == "__main__":
    sys.exit(main())
