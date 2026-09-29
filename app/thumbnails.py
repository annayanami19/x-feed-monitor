"""Pemuatan thumbnail dengan cache memori + cache disk.

Kenapa perlu cache:
  * Jaringan  -> tiap gambar hanya diunduh SEKALI, lalu dipakai ulang
  * Memori    -> QPixmap disimpan agar scroll tidak memicu unduh ulang
  * Disk      -> bertahan antar sesi aplikasi (folder data/cache/thumbs)

Unduhan berjalan di thread pool Qt, jadi UI tidak pernah membeku.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, QSize, QThreadPool, pyqtSignal

from .paths import THUMBS_DIR, pastikan_folder

#: Batas ukuran gambar yang disimpan di memori (bukan di disk).
BATAS_MEMORI = 400

#: Timeout unduhan (detik).
TIMEOUT = 15

#: Ukuran maksimum sisi panjang saat disimpan ke disk (hemat tempat).
SISI_MAKS = 640


def _nama_cache(url: str) -> str:
    """Nama file cache yang stabil untuk sebuah URL."""
    sidik = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return f"{sidik}.jpg"


def _jalur_cache(url: str) -> Path:
    return THUMBS_DIR / _nama_cache(url)


class _TugasUnduh(QRunnable):
    """Mengunduh satu gambar di thread pool."""

    def __init__(self, url: str, sinyal: "SinyalThumbnail") -> None:
        super().__init__()
        self.url = url
        self.sinyal = sinyal
        self.setAutoDelete(True)

    def run(self) -> None:  # noqa: D102 - dijalankan di thread pool
        try:
            jalur = _jalur_cache(self.url)
            if not jalur.exists():
                self._unduh_ke(jalur)
            if jalur.exists():
                self.sinyal.selesai.emit(self.url, str(jalur))
            else:
                self.sinyal.gagal.emit(self.url)
        except Exception:  # noqa: BLE001 - gambar gagal bukan error fatal
            self.sinyal.gagal.emit(self.url)

    def _unduh_ke(self, tujuan: Path) -> None:
        """Unduh gambar lalu simpan sebagai JPEG terkompresi.

        Memakai Pillow (sudah ikut twscrape) supaya gambar besar dikecilkan
        sebelum disimpan — cache tetap ringan.
        """
        import io
        import urllib.request

        permintaan = urllib.request.Request(
            self.url,
            headers={
                # X menolak permintaan tanpa User-Agent yang wajar.
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Referer": "https://x.com/",
            },
        )
        with urllib.request.urlopen(permintaan, timeout=TIMEOUT) as respons:
            mentah = respons.read()

        # Kecilkan bila Pillow tersedia; kalau tidak, simpan apa adanya.
        try:
            from PIL import Image

            gambar = Image.open(io.BytesIO(mentah))
            if gambar.mode not in ("RGB", "L"):
                gambar = gambar.convert("RGB")
            gambar.thumbnail((SISI_MAKS, SISI_MAKS))
            pastikan_folder()
            sementara = tujuan.with_suffix(".part")
            gambar.save(sementara, "JPEG", quality=82, optimize=True)
            os.replace(sementara, tujuan)
        except Exception:  # noqa: BLE001 - fallback: simpan byte mentah
            pastikan_folder()
            sementara = tujuan.with_suffix(".part")
            sementara.write_bytes(mentah)
            os.replace(sementara, tujuan)


class SinyalThumbnail(QObject):
    """Sinyal hasil unduhan (dipisah karena QRunnable bukan QObject)."""

    selesai = pyqtSignal(str, str)   # (url, path file lokal)
    gagal = pyqtSignal(str)          # (url)


class PemuatThumbnail(QObject):
    """Manajer unduhan + cache. Satu instance dipakai seluruh aplikasi."""

    #: Dipancarkan saat sebuah gambar siap dipakai (url, QPixmap).
    gambar_siap = pyqtSignal(str, object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._sinyal = SinyalThumbnail()
        self._sinyal.selesai.connect(self._pada_selesai)
        self._sinyal.gagal.connect(self._pada_gagal)

        self._pool = QThreadPool(self)
        # 4 unduhan paralel — cukup cepat, tidak membanjiri jaringan.
        self._pool.setMaxThreadCount(4)

        self._memori: dict[str, object] = {}       # url -> QPixmap
        self._sedang: set[str] = set()             # url yang sedang diunduh
        self._gagal: set[str] = set()              # url yang sudah gagal
        self._menunggu: dict[str, list[object]] = {}  # url -> callback

    # ------------------------------------------------------------------
    def minta(self, url: str, callback=None) -> object | None:
        """Minta gambar.

        Mengembalikan QPixmap segera bila sudah ada di memori (cache hit),
        atau None sambil mengunduh di latar belakang. `callback` akan
        dipanggil dengan (url, QPixmap|None) saat selesai.
        """
        if not url:
            return None

        # 1) cache memori
        if url in self._memori:
            return self._memori[url]

        # 2) sudah pernah gagal -> jangan coba lagi terus-menerus
        if url in self._gagal:
            if callback:
                callback(url, None)
            return None

        # 3) catat callback
        if callback:
            self._menunggu.setdefault(url, []).append(callback)

        # 4) mulai unduh bila belum
        if url not in self._sedang:
            self._sedang.add(url)
            self._pool.start(_TugasUnduh(url, self._sinyal))

        return None

    def siapkan_ukuran(self, ukuran: QSize) -> None:
        """Deklarasikan ukuran thumbnail (dipakai delegate untuk tata letak)."""
        self.ukuran = ukuran

    def bersihkan_memori(self) -> None:
        """Kosongkan cache memori (dipakai saat ganti tema / muat ulang besar)."""
        self._memori.clear()

    # ------------------------------------------------------------------
    def _pada_selesai(self, url: str, jalur: str) -> None:
        self._sedang.discard(url)

        from PyQt6.QtGui import QPixmap

        pixmap = QPixmap(jalur)
        if pixmap.isNull():
            self._pada_gagal(url)
            return

        # Simpan di memori (dengan batas sederhana).
        if len(self._memori) >= BATAS_MEMORI:
            # buang separuh entri terlama
            for kunci in list(self._memori)[: BATAS_MEMORI // 2]:
                self._memori.pop(kunci, None)
        self._memori[url] = pixmap

        self.gambar_siap.emit(url, pixmap)
        self._panggil_callback(url, pixmap)

    def _pada_gagal(self, url: str) -> None:
        self._sedang.discard(url)
        self._gagal.add(url)
        self._panggil_callback(url, None)

    def _panggil_callback(self, url: str, pixmap) -> None:
        for cb in self._menunggu.pop(url, []):
            try:
                cb(url, pixmap)
            except Exception:  # noqa: BLE001 - callback rusak tidak boleh menghentikan
                pass

    def hentikan(self) -> None:
        self._pool.clear()
        self._pool.waitForDone(3000)
