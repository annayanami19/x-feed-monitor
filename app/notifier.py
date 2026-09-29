"""Notifikasi desktop.

Memakai QSystemTrayIcon bawaan Qt — tidak butuh dependency tambahan dan
tidak memunculkan entri di Action Center yang menumpuk.

PENTING: notifikasi HANYA dibuat untuk postingan yang benar-benar baru
(hasil `db.simpan_banyak`), bukan untuk setiap postingan yang ditarik.
Tanpa aturan itu, setiap siklus polling akan memunculkan notifikasi ulang
untuk postingan yang sama.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QSystemTrayIcon

from .models import Post

#: Maksimum notifikasi per siklus. Kalau akun baru di-import, jangan
#: memunculkan 30 notifikasi sekaligus.
MAKS_PER_SIKLUS = 3

#: Panjang potongan isi postingan di notifikasi.
PANJANG_CUPLIKAN = 110


def _cuplik(teks: str) -> str:
    """Rapikan isi postingan jadi satu baris pendek untuk notifikasi."""
    bersih = " ".join((teks or "").split())
    if len(bersih) <= PANJANG_CUPLIKAN:
        return bersih
    return bersih[: PANJANG_CUPLIKAN - 1].rstrip() + "…"


class Notifier(QObject):
    """Pembungkus QSystemTrayIcon untuk menampilkan notifikasi postingan baru."""

    #: Dipancarkan saat pengguna mengklik notifikasi (membawa Post terkait).
    diklik = pyqtSignal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.aktif = True

        self._tray = QSystemTrayIcon(parent)
        self._tray.setToolTip("X Feed Monitor")
        self._tray.setIcon(self._ikon_default())
        self._tray.messageClicked.connect(self._pada_klik)
        self._terakhir: Post | None = None

    # ------------------------------------------------------------------
    def _ikon_default(self) -> QIcon:
        """Ikon sederhana (kotak biru) — supaya tray tetap muncul tanpa aset."""
        pixmap = QPixmap(32, 32)
        pixmap.fill()
        return QIcon(pixmap)

    def pasang_ikon(self, ikon: QIcon) -> None:
        if not ikon.isNull():
            self._tray.setIcon(ikon)

    def tampilkan(self) -> None:
        """Tampilkan ikon di system tray (dipanggil sekali saat start)."""
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray.show()

    def sembunyikan(self) -> None:
        self._tray.hide()

    # ------------------------------------------------------------------
    def beritahu_banyak(self, posts: list[Post], nama_akun: dict[str, str] | None = None) -> int:
        """Tampilkan notifikasi untuk postingan BARU. Kembalikan jumlah terkirim.

        `nama_akun` memetakan account_id -> label tampilan akun.
        """
        if not self.aktif or not posts:
            return 0
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return 0

        nama_akun = nama_akun or {}
        terkirim = 0

        for post in posts[:MAKS_PER_SIKLUS]:
            label = nama_akun.get(post.account_id) or f"@{post.username}"
            judul = f"{label} · postingan baru"
            isi = _cuplik(post.content) or "(tanpa teks)"

            self._terakhir = post
            self._tray.showMessage(
                judul,
                isi,
                QSystemTrayIcon.MessageIcon.Information,
                8000,
            )
            terkirim += 1

        sisa = len(posts) - terkirim
        if sisa > 0:
            self._terakhir = None
            self._tray.showMessage(
                "X Feed Monitor",
                f"+{sisa} postingan baru lainnya",
                QSystemTrayIcon.MessageIcon.Information,
                6000,
            )

        return terkirim

    def _pada_klik(self) -> None:
        """Klik notifikasi -> beri tahu GUI untuk membuka postingan terkait."""
        if self._terakhir is not None:
            self.diklik.emit(self._terakhir)
            self._terakhir = None
