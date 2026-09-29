"""Pemuat ikon aplikasi.

Ikon dimuat dari `assets/icon.ico` yang dibuat oleh `tools/buat_ikon.py`.

MENGAPA DARI FILE, BUKAN DIGAMBAR SAAT RUNTIME
==============================================
Versi sebelumnya menggambar ikon langsung dengan QPainter saat aplikasi
dijalankan. Cara itu membuat ikon hanya muncul di **jendela** aplikasi.

Untuk muncul di **taskbar**, **Alt+Tab**, **shortcut**, dan **Explorer**,
Windows memerlukan berkas `.ico` yang berisi banyak ukuran — Windows memilih
ukuran yang sesuai untuk tiap tempat (16px di judul jendela, 32px di taskbar,
256px di Explorer).

FALLBACK
========
Kalau `assets/icon.ico` tidak ada (mis. folder aset terhapus), ikon dibuat
sederhana secara programatik supaya aplikasi tetap punya ikon dan tidak crash.
Jalankan `python tools/buat_ikon.py` untuk membuat ulang berkasnya.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap

from .paths import ICON_ICO, ICON_PNG

#: Warna aksen untuk ikon cadangan — disamakan dengan tema aplikasi.
_AKSEN = QColor("#1d9bf0")

#: Cache — ikon dimuat sekali lalu dipakai ulang di seluruh aplikasi.
_ikon: QIcon | None = None


def _ikon_cadangan() -> QIcon:
    """Ikon sederhana yang digambar saat berkas ikon tidak tersedia."""
    ukuran = 64
    pixmap = QPixmap(ukuran, ukuran)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Latar membulat
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_AKSEN)
    radius = ukuran * 0.22
    painter.drawRoundedRect(0, 0, ukuran, ukuran, radius, radius)

    # Huruf X di tengah
    painter.setPen(QColor("#ffffff"))
    font = painter.font()
    font.setPointSizeF(ukuran * 0.5)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "X")
    painter.end()

    return QIcon(pixmap)


def ikon_aplikasi() -> QIcon:
    """Ikon aplikasi. Dimuat dari berkas, dengan cadangan programatik.

    Hasilnya di-cache: memuat berkas ikon berulang kali tidak ada gunanya,
    dan fungsi ini dipanggil dari beberapa tempat (jendela utama, tray,
    dialog).
    """
    global _ikon
    if _ikon is not None:
        return _ikon

    # --- coba berkas .ico (paling lengkap: berisi 7 ukuran) ---
    if ICON_ICO.exists():
        ikon = QIcon(str(ICON_ICO))
        if not ikon.isNull():
            _ikon = ikon
            return _ikon

    # --- coba berkas .png ---
    if ICON_PNG.exists():
        ikon = QIcon(str(ICON_PNG))
        if not ikon.isNull():
            _ikon = ikon
            return _ikon

    # --- cadangan: gambar sendiri ---
    _ikon = _ikon_cadangan()
    return _ikon


def ikon_tersedia() -> bool:
    """True bila berkas ikon asli ada (bukan cadangan).

    Dipakai untuk memberi peringatan saat berkas ikon hilang.
    """
    return ICON_ICO.exists() or ICON_PNG.exists()
