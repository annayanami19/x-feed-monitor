"""Pembuat ikon aplikasi.

MENJALANKAN
===========
    python tools/buat_ikon.py

Menghasilkan dua file di `assets/`:
    icon.ico  — ikon Windows multi-ukuran (untuk jendela, taskbar, shortcut)
    icon.png  — versi 256px (untuk dokumentasi & platform lain)

MENGAPA IKON DIBUAT DARI KODE
=============================
Ikon disimpan sebagai skrip, bukan file biner yang di-commit tanpa penjelasan.
Keuntungannya:

  * bisa dibuat ulang kapan saja (`python tools/buat_ikon.py`)
  * ukurannya bisa diubah cukup dengan mengubah satu angka
  * terlihat jelas desainnya tanpa perlu membuka editor gambar
  * tidak ada file biner gelap di repositori — yang di-commit hanya kode

File .ico & .png TETAP di-commit supaya aplikasi bisa dijalankan tanpa perlu
menjalankan skrip ini lebih dulu.

DESAIN
======
Ikon menggambarkan konsep aplikasi: **banyak sumber, satu aliran**.

  * Latar membulat dengan gradasi biru — warna aksen aplikasi
  * Tiga titik di kiri (menyala bergantian) = banyak akun yang dipantau
  * Dua garis mengalir ke kanan = postingan yang mengalir masuk
  * Satu titik besar di kanan = feed gabungan

Dibuat pada ukuran besar lalu diperkecil dengan LANCZOS, sehingga tepinya
tetap halus di ukuran kecil (16px sekalipun).
"""

from __future__ import annotations

import sys
from pathlib import Path

# --- path: tulis ke assets/ di root proyek --------------------------------
ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

# --- warna -----------------------------------------------------------------
# Mengikuti palet aplikasi (lihat app/ui/theme.py) supaya konsisten.
AKSEN_TERANG = (29, 155, 240)     # #1d9bf0 — biru utama
AKSEN_GELAP = (10, 90, 160)       # #0a5aa0 — biru lebih tua untuk gradasi
PUTIH = (255, 255, 255)
PUTIH_REDUP = (200, 225, 245)

#: Ukuran kanvas kerja. Digambar besar lalu diperkecil — cara ini
#: menghasilkan tepi yang jauh lebih halus dibanding menggambar langsung
#: di ukuran kecil.
UKURAN_KANVAS = 1024

#: Ukuran yang dimasukkan ke dalam file .ico.
#: Windows memakai ukuran berbeda tergantung tempatnya:
#:   16  — taskbar kecil, judul jendela
#:   32  — taskbar normal
#:   48  — desktop shortcut
#:   64  — ikon besar di Explorer
#:   128 — tampilan ekstra besar
#:   256 — ikon paling besar (Explorer "Extra large icons")
UKURAN_ICO = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def _gambar_ikon(ukuran: int):
    """Gambar ikon pada ukuran tertentu. Mengembalikan PIL.Image RGBA."""
    from PIL import Image, ImageDraw

    # Digambar di kanvas besar, diperkecil di akhir (supersampling).
    S = UKURAN_KANVAS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # --- latar membulat dengan gradasi vertikal ---
    #
    # PIL tidak punya gradasi bawaan, jadi digambar baris per baris lalu
    # dipotong dengan mask membulat.
    gradasi = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dg = ImageDraw.Draw(gradasi)
    for y in range(S):
        rasio = y / max(1, S - 1)
        r = int(AKSEN_TERANG[0] + (AKSEN_GELAP[0] - AKSEN_TERANG[0]) * rasio)
        g = int(AKSEN_TERANG[1] + (AKSEN_GELAP[1] - AKSEN_TERANG[1]) * rasio)
        b = int(AKSEN_TERANG[2] + (AKSEN_GELAP[2] - AKSEN_TERANG[2]) * rasio)
        dg.line([(0, y), (S, y)], fill=(r, g, b, 255))

    # Sudut membulat: radius 22% dari sisi, menyerupai ikon aplikasi modern.
    radius = int(S * 0.22)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [(0, 0), (S - 1, S - 1)], radius=radius, fill=255
    )
    img.paste(gradasi, (0, 0), mask)

    # --- tiga titik sumber (kiri) ---
    #
    # Ukuran berbeda-beda supaya terlihat seperti beberapa akun dengan
    # aktivitas berbeda — bukan tiga titik identik yang monoton.
    titik_sumber = [
        (S * 0.20, S * 0.32, S * 0.055),   # atas
        (S * 0.20, S * 0.50, S * 0.070),   # tengah (paling besar)
        (S * 0.20, S * 0.68, S * 0.055),   # bawah
    ]
    for cx, cy, r in titik_sumber:
        d.ellipse(
            [(cx - r, cy - r), (cx + r, cy + r)],
            fill=PUTIH + (255,),
        )

    # --- garis aliran (kiri -> kanan) ---
    #
    # Digambar sebagai garis tebal dengan ujung membulat.
    lebar_garis = int(S * 0.035)
    titik_akhir = (S * 0.62, S * 0.50)

    for _, cy, _ in titik_sumber:
        d.line(
            [(S * 0.28, cy), titik_akhir],
            fill=PUTIH_REDUP + (200,),
            width=lebar_garis,
            joint="curve",
        )

    # --- titik tujuan (kanan) = feed gabungan ---
    cx, cy, r = S * 0.72, S * 0.50, S * 0.155
    d.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=PUTIH + (255,))

    # Cincin dalam supaya titik tujuan tidak terlihat seperti bulatan polos.
    r2 = r * 0.55
    d.ellipse(
        [(cx - r2, cy - r2), (cx + r2, cy + r2)],
        fill=AKSEN_TERANG + (255,),
    )

    # --- perkecil ke ukuran yang diminta ---
    if ukuran != S:
        img = img.resize((ukuran, ukuran), Image.Resampling.LANCZOS)
    return img


def main() -> int:
    try:
        from PIL import Image
    except ImportError:
        print("[MASALAH] Pillow belum terpasang.")
        print("          Jalankan:  pip install Pillow")
        return 1

    ASSETS.mkdir(parents=True, exist_ok=True)

    print("Membuat ikon...")

    # --- gambar di ukuran besar dulu ---
    besar = _gambar_ikon(UKURAN_KANVAS)

    # --- PNG 256px (untuk dokumentasi / platform lain) ---
    png = besar.resize((256, 256), Image.Resampling.LANCZOS)
    jalur_png = ASSETS / "icon.png"
    png.save(jalur_png, "PNG", optimize=True)
    print(f"  OK  {jalur_png.relative_to(ROOT)}  (256x256)")

    # --- ICO multi-ukuran ---
    #
    # Setiap ukuran digambar ULANG dari kanvas besar (bukan hasil perkecilan
    # berantai), supaya ketajamannya maksimal di tiap ukuran.
    gambar_ico = []
    for lebar, tinggi in UKURAN_ICO:
        gambar_ico.append(
            besar.resize((lebar, tinggi), Image.Resampling.LANCZOS)
        )

    jalur_ico = ASSETS / "icon.ico"
    gambar_ico[-1].save(
        jalur_ico,
        format="ICO",
        sizes=UKURAN_ICO,
        append_images=gambar_ico[:-1],
    )
    ukuran_kb = jalur_ico.stat().st_size / 1024
    print(f"  OK  {jalur_ico.relative_to(ROOT)}  "
          f"({', '.join(f'{w}' for w, _ in UKURAN_ICO)} px, {ukuran_kb:.1f} KB)")

    print("\nSelesai. Ikon dipakai otomatis saat aplikasi dijalankan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
