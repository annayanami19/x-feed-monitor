"""Perbaikan kompatibilitas — WAJIB dijalankan sebelum mengimpor twscrape.

MASALAH YANG DIPERBAIKI
=======================
`run.bat` menjalankan aplikasi lewat **pythonw.exe** supaya tidak ada jendela
console hitam. Tapi pythonw.exe tidak punya handle console, sehingga
`sys.stdout` dan `sys.stderr` bernilai **None**.

twscrape memakai loguru dan menjalankan ini saat diimpor:

    logger.remove()
    logger.add(sys.stderr, filter=_filter)

Dengan `sys.stderr = None`, impor langsung gagal:

    TypeError: Cannot log to objects of type 'NoneType'

Akibatnya aplikasi **tidak bisa dibuka sama sekali** lewat run.bat, sementara
lewat run-debug.bat (python.exe, punya console) normal — gejala yang
membingungkan kalau penyebabnya tidak diketahui.

PERBAIKAN
=========
Sebelum twscrape diimpor, `sys.stdout`/`sys.stderr` yang None diganti dengan
handle file log sungguhan. Ini sekaligus berguna: pesan internal twscrape
(rate-limit, akun terkunci, kegagalan request) tersimpan dan bisa diperiksa
saat ada masalah — informasi yang kalau tidak, hilang begitu saja.

File log dipotong saat aplikasi dibuka bila sudah melewati batas ukuran,
supaya tidak tumbuh tanpa batas.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from .paths import LOG_PATH, pastikan_folder

#: Ukuran maksimum file log sebelum dipotong saat aplikasi dibuka.
BATAS_LOG: int = 2 * 1024 * 1024  # 2 MB

#: Handle file disimpan di sini supaya tidak di-garbage-collect selama
#: aplikasi berjalan (kalau tidak, tulisannya bisa hilang).
_handle: list = []


class _Pembuang(io.TextIOBase):
    """Aliran yang membuang semua tulisan.

    Dipakai sebagai cadangan terakhir kalau file log tidak bisa dibuka —
    yang penting library bisa diimpor, bukan pesannya tersimpan.
    """

    def write(self, teks: str) -> int:  # noqa: D102 - API io
        return len(teks)

    def flush(self) -> None:  # noqa: D102 - API io
        pass

    def isatty(self) -> bool:  # noqa: D102 - API io
        return False


def _buka_log():
    """Buka file log (mode append). Kembalikan None bila gagal."""
    try:
        pastikan_folder()
        # Potong bila sudah terlalu besar — dicek hanya saat aplikasi dibuka,
        # jadi biayanya tidak terasa saat berjalan.
        if LOG_PATH.exists() and LOG_PATH.stat().st_size > BATAS_LOG:
            LOG_PATH.write_text(
                "--- log dipotong karena melewati batas ukuran ---\n",
                encoding="utf-8",
            )
        return Path(LOG_PATH).open(
            "a", encoding="utf-8", errors="replace", buffering=1
        )
    except OSError:
        return None


def pastikan_std_stream() -> None:
    """Ganti sys.stdout/sys.stderr yang None dengan aliran yang valid.

    Idempoten: aman dipanggil berkali-kali. Kalau kedua stream sudah normal
    (mis. dijalankan lewat run-debug.bat), fungsi ini tidak melakukan apa pun.
    """
    if sys.stdout is not None and sys.stderr is not None:
        return

    aliran = _buka_log()
    if aliran is None:
        aliran = _Pembuang()
    _handle.append(aliran)

    if sys.stdout is None:
        sys.stdout = aliran
    if sys.stderr is None:
        sys.stderr = aliran
