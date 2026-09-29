"""Isi postingan sebagai teks yang bisa diblok, di-copy, dan diklik tautannya.

MENGAPA MODUL TERSENDIRI
========================
Delegate menggambar kartu langsung ke kanvas, dan kanvas tidak punya konsep
"teks yang bisa diblok". Supaya isi postingan bisa di-select seperti di
browser, teksnya harus digambar lewat QTextDocument — bukan
`painter.drawText()`.

Modul ini membungkus semua kerumitan itu:

  * menyiapkan QTextDocument dengan tautan yang bisa diklik
  * menerjemahkan klik mouse jadi posisi karakter (hit test)
  * mengelola blok seleksi (drag) + salin ke clipboard
  * melaporkan tautan mana yang sedang disorot mouse

Pemakaian dari delegate:
    dok = DokumenTeks(palet)
    dok.siapkan(post.content, post.links, lebar, tinggi_maks, ukuran_font)
    dok.gambar(painter, x, y)
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from PyQt6.QtCore import QPointF, QSizeF, Qt
from PyQt6.QtGui import (
    QAbstractTextDocumentLayout,
    QColor,
    QFont,
    QPainter,
    QPalette,
    QTextCursor,
    QTextDocument,
)

from ..models import Link, _normalisasi_kunci_link
from .theme import Palet

#: Pola tautan yang dikenali di dalam teks.
#:
#: Mencakup `https://…`, `http://…`, dan `www.…`. Sengaja TIDAK mencakup
#: `t.co/xxxx` tanpa skema karena pola itu terlalu mudah salah cocok dengan
#: teks biasa.
POLA_URL = re.compile(
    r"(?:https?://|www\.)[^\s<>\"')\]]+",
    re.IGNORECASE,
)


def domain_dari(url: str) -> str:
    """Ambil nama domain dari sebuah URL, untuk ditampilkan di konfirmasi.

    Mengembalikan string kosong bila domain tidak bisa ditentukan — pemanggil
    yang memutuskan apa yang ditampilkan sebagai gantinya.
    """
    t = (url or "").strip()
    if not t:
        return ""
    # urlparse butuh skema; tambahkan bila belum ada.
    if "://" not in t:
        t = "https://" + t.lstrip("/")
    try:
        host = urlparse(t).hostname or ""
    except ValueError:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host.lower()


class DokumenTeks:
    """Satu dokumen teks untuk SATU postingan.

    Objek ini dipakai ulang (bukan dibuat ulang tiap paint) karena
    pembuatan QTextDocument relatif mahal dan `paint()` dipanggil sangat
    sering saat scrolling.
    """

    def __init__(self, palet: Palet) -> None:
        self.palet = palet
        self.doc = QTextDocument()
        self.doc.setDocumentMargin(0)
        self.doc.setUndoRedoEnabled(False)

        self._lebar = 0
        self._teks = ""
        self._sidik_konten = ""
        #: Seleksi aktif: (posisi_awal, posisi_akhir) dalam karakter.
        self.seleksi: tuple[int, int] | None = None
        #: Nomor baris kartu yang memiliki seleksi ini. Dipakai supaya
        #: seleksi tidak "menempel" ke kartu lain saat model di-refresh.
        self.baris_pemilik: int = -1
        #: Peta teks-tampil -> url asli, untuk menerjemahkan saat diklik.
        self._peta_link: dict[str, str] = {}

    # ==================================================================
    # Penyiapan
    # ==================================================================
    def siapkan(self, teks: str, links: list[Link], lebar: int,
                tinggi_maks: int, ukuran_font: float) -> None:
        """Bangun ulang dokumen bila isi/lebar berubah.

        Dibuat idempoten: pemanggilan berulang dengan parameter yang sama
        tidak melakukan apa-apa, sehingga aman dipanggil dari `paint()`.
        """
        sidik = f"{teks}\x00{lebar}\x00{tinggi_maks}\x00{ukuran_font}"
        if sidik == self._sidik_konten:
            return

        self._sidik_konten = sidik
        self._teks = teks or ""
        self._lebar = lebar
        self.seleksi = None
        self.baris_pemilik = -1

        font = QFont()
        font.setPointSizeF(ukuran_font)
        self.doc.setDefaultFont(font)

        self._peta_link = {}
        for link in links:
            if not link.url:
                continue
            for kunci in (link.teks, link.url):
                if kunci:
                    self._peta_link[_normalisasi_kunci_link(kunci)] = link.url

        self.doc.setHtml(self._ke_html(self._teks))
        self.doc.setTextWidth(lebar)

        # Batasi tinggi: sisanya dipotong dan diberi tanda "…".
        # setPageSize butuh QSizeF (bukan QSize) — QSize akan ditolak PyQt6.
        self.doc.setPageSize(QSizeF(float(lebar), float(tinggi_maks)))

    def _ke_html(self, teks: str) -> str:
        """Ubah teks biasa jadi HTML dengan tautan yang bisa diklik.

        X mengirim isi postingan sebagai teks polos (tautan dalam bentuk
        pendek), jadi di sini tautan dideteksi sendiri lalu dibungkus <a>.
        """
        p = self.palet
        bagian: list[str] = []

        posisi = 0
        for cocok in POLA_URL.finditer(teks):
            awal, akhir = cocok.span()
            url_mentah = cocok.group(0)

            # Teks sebelum tautan.
            bagian.append(self._esc(teks[posisi:awal]))

            url_asli = self._url_asli(url_mentah)
            tampil = self._esc(url_mentah)
            bagian.append(
                f'<a href="{self._esc_attr(url_asli)}" '
                f'style="color:{p.aksen}; text-decoration:none;">{tampil}</a>'
            )
            posisi = akhir

        bagian.append(self._esc(teks[posisi:]))

        # Isi dengan warna teks tema; jarak antar-baris sedikit dilonggarkan
        # supaya tidak terasa padat.
        return (
            f'<div style="color:{p.teks}; line-height:135%;">'
            + "".join(bagian)
            + "</div>"
        )

    def _url_asli(self, url_tampil: str) -> str:
        """Terjemahkan tautan yang tampil menjadi alamat sebenarnya.

        X menampilkan tautan dalam bentuk pendek (`t.co/xxxx`); alamat
        aslinya ada di peta. Kalau tidak ada padanannya, pakai apa adanya.
        """
        kunci = _normalisasi_kunci_link(url_tampil)
        asli = self._peta_link.get(kunci)
        if asli:
            return asli
        # Coba juga tanpa protokol pada kedua sisi.
        for k, v in self._peta_link.items():
            if k.endswith(kunci) or kunci.endswith(k):
                return v
        return url_tampil

    @staticmethod
    def _esc(teks: str) -> str:
        return (
            (teks or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    @staticmethod
    def _esc_attr(teks: str) -> str:
        return (
            (teks or "")
            .replace("&", "&amp;")
            .replace('"', "&quot;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    # ==================================================================
    # Ukuran
    # ==================================================================
    def tinggi_isi(self) -> int:
        """Tinggi dokumen yang sebenarnya dibutuhkan (tanpa batas potong)."""
        return int(self.doc.size().height())

    # ==================================================================
    # Menggambar
    # ==================================================================
    def gambar(self, painter: QPainter, x: int, y: int) -> None:
        """Gambar teks ke kanvas pada posisi (x, y).

        `x`/`y` sudah dalam koordinat viewport — `option.rect` yang diterima
        `paint()` dari Qt sudah memperhitungkan posisi scroll, jadi tidak ada
        koreksi tambahan yang diperlukan di sini.
        """
        painter.save()
        painter.translate(x, y)

        ctx = QAbstractTextDocumentLayout.PaintContext()
        # setColor butuh (peran, warna) — bukan QColor saja.
        # Peran yang dipakai dokumen untuk teks biasa adalah Text.
        ctx.palette.setColor(QPalette.ColorRole.Text, QColor(self.palet.teks))

        # Blok seleksi (bila ada) — QTextDocument tidak tahu soal seleksi
        # sendiri, jadi harus diberitahu lewat PaintContext.
        if self.seleksi is not None:
            awal, akhir = self.seleksi
            awal, akhir = min(awal, akhir), max(awal, akhir)
            if akhir > awal:
                pilihan = QAbstractTextDocumentLayout.Selection()
                pilihan.start = awal
                pilihan.length = akhir - awal
                pilihan.format.setBackground(QColor(self.palet.aksen))
                pilihan.format.setForeground(QColor(self.palet.aksen_teks))
                ctx.selections = [pilihan]

        self.doc.documentLayout().draw(painter, ctx)
        painter.restore()

    # ==================================================================
    # Interaksi
    # ==================================================================
    def posisi_pada(self, x: int, y: int) -> int:
        """Ubah koordinat lokal (relatif ke teks) jadi posisi karakter."""
        titik = QPointF(float(x), float(y))
        try:
            return int(self.doc.documentLayout().hitTest(
                titik, Qt.HitTestAccuracy.FuzzyHit
            ))
        except Exception:  # noqa: BLE001 - hit test tidak boleh menjatuhkan UI
            return 0

    def link_pada(self, x: int, y: int) -> str:
        """URL di posisi ini, atau string kosong bila bukan tautan."""
        try:
            return self.doc.documentLayout().anchorAt(QPointF(float(x), float(y))) or ""
        except Exception:  # noqa: BLE001
            return ""

    def teks_terpilih(self) -> str:
        """Isi yang sedang diblok (string kosong bila tidak ada)."""
        if self.seleksi is None:
            return ""
        awal, akhir = self.seleksi
        awal, akhir = min(awal, akhir), max(awal, akhir)
        if akhir <= awal:
            return ""
        kursor = QTextCursor(self.doc)
        kursor.setPosition(awal)
        kursor.setPosition(akhir, QTextCursor.MoveMode.KeepAnchor)
        return kursor.selectedText().replace("\u2029", "\n")

    def pilih_semua(self) -> None:
        self.seleksi = (0, len(self._teks))

    def bersihkan_seleksi(self) -> None:
        self.seleksi = None
        self.baris_pemilik = -1

    def ada_seleksi(self) -> bool:
        return bool(self.teks_terpilih())
