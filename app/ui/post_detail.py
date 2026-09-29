"""Panel detail: menampilkan satu postingan lengkap di sisi kanan.

Panel (bukan dialog) supaya pengguna bisa tetap melihat feed sambil membaca
detail, dan bisa berpindah postingan tanpa membuka-tutup jendela.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..models import Media, Post
from .widgets import BarisInfo, waktu_lengkap, waktu_relatif

LEBAR_PANEL = 380


class PanelDetail(QFrame):
    """Panel detail postingan yang bisa dibuka/tutup."""

    tutup = pyqtSignal()
    buka_browser = pyqtSignal(object)     # Post

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panelFilter")   # pakai gaya panel yang sama
        self.setMinimumWidth(320)
        self.setMaximumWidth(560)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.resize(LEBAR_PANEL, self.height())

        self.post: Post | None = None
        self._bangun()

    # ==================================================================
    def _bangun(self) -> None:
        tata = QVBoxLayout(self)
        tata.setContentsMargins(14, 12, 14, 12)
        tata.setSpacing(10)

        # ---------------- header ----------------
        baris_header = QHBoxLayout()

        self.label_judul = QLabel("Detail postingan")
        from PyQt6.QtGui import QFont

        f = QFont()
        f.setBold(True)
        f.setPointSize(11)
        self.label_judul.setFont(f)
        baris_header.addWidget(self.label_judul, 1)

        tombol_tutup = QPushButton("✕")
        tombol_tutup.setObjectName("ikon")
        tombol_tutup.setToolTip("Tutup panel detail")
        tombol_tutup.clicked.connect(self.tutup.emit)
        baris_header.addWidget(tombol_tutup)

        tata.addLayout(baris_header)

        # ---------------- isi yang bisa di-scroll ----------------
        gulir = QScrollArea()
        gulir.setWidgetResizable(True)
        gulir.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        isi = QWidget()
        tata_isi = QVBoxLayout(isi)
        tata_isi.setContentsMargins(0, 0, 6, 0)
        tata_isi.setSpacing(10)

        # penulis
        self.label_penulis = QLabel()
        self.label_penulis.setWordWrap(True)
        tata_isi.addWidget(self.label_penulis)

        self.label_waktu = QLabel()
        self.label_waktu.setStyleSheet("color: #8b98a5;")
        tata_isi.addWidget(self.label_waktu)

        # isi postingan (QTextBrowser supaya bisa scroll sendiri + selectable)
        self.teks = QTextBrowser()
        self.teks.setOpenExternalLinks(True)
        self.teks.setMinimumHeight(160)
        tata_isi.addWidget(self.teks)

        # media
        self.label_media = QLabel()
        self.label_media.setWordWrap(True)
        tata_isi.addWidget(self.label_media)

        # statistik
        self.baris_like = BarisInfo("Suka")
        self.baris_rt = BarisInfo("Retweet")
        self.baris_reply = BarisInfo("Balasan")
        self.baris_view = BarisInfo("Dilihat")
        for b in (self.baris_like, self.baris_rt, self.baris_reply, self.baris_view):
            tata_isi.addWidget(b)

        self.baris_id = BarisInfo("ID")
        self.baris_url = BarisInfo("URL")
        tata_isi.addWidget(self.baris_id)
        tata_isi.addWidget(self.baris_url)

        tata_isi.addStretch(1)
        gulir.setWidget(isi)
        tata.addWidget(gulir, 1)

        # ---------------- tombol aksi ----------------
        baris_aksi = QHBoxLayout()

        self.tombol_buka = QPushButton("Buka di browser")
        self.tombol_buka.setObjectName("utama")
        self.tombol_buka.clicked.connect(self._buka)
        baris_aksi.addWidget(self.tombol_buka)

        self.tombol_salin_link = QPushButton("Copy link")
        self.tombol_salin_link.clicked.connect(lambda: self._salin(self.post.url if self.post else ""))
        baris_aksi.addWidget(self.tombol_salin_link)

        tata.addLayout(baris_aksi)

        self.tombol_salin_teks = QPushButton("Copy teks postingan")
        self.tombol_salin_teks.clicked.connect(
            lambda: self._salin(self.post.content if self.post else "")
        )
        tata.addWidget(self.tombol_salin_teks)

    # ==================================================================
    def tampilkan(self, post: Post) -> None:
        """Isi panel dengan sebuah postingan."""
        self.post = post

        # --- penulis ---
        nama = post.display_name or post.username
        self.label_penulis.setText(
            f"<b>{self._esc(nama)}</b><br>"
            f"<span style='color:#8b98a5'>@{self._esc(post.username)}</span>"
        )

        # --- waktu ---
        self.label_waktu.setText(
            f"{waktu_lengkap(post.created_at)}  ({waktu_relatif(post.created_at)} lalu)"
        )

        # --- isi ---
        self.teks.setPlainText(post.content or "(tanpa teks)")

        # --- media ---
        self.label_media.setText(self._ringkas_media(post.media))

        # --- statistik ---
        self.baris_like.set_nilai(f"{post.like_count:,}".replace(",", "."))
        self.baris_rt.set_nilai(f"{post.retweet_count:,}".replace(",", "."))
        self.baris_reply.set_nilai(f"{post.reply_count:,}".replace(",", "."))
        self.baris_view.set_nilai(
            f"{post.view_count:,}".replace(",", ".") if post.view_count is not None else "—"
        )

        self.baris_id.set_nilai(post.tweet_id)
        self.baris_url.set_nilai(post.url)

    def _ringkas_media(self, media: list[Media]) -> str:
        if not media:
            return ""

        jumlah = len(media)
        jenis: dict[str, int] = {}
        for m in media:
            jenis[m.tipe] = jenis.get(m.tipe, 0) + 1

        bagian = []
        if jenis.get("photo"):
            bagian.append(f"{jenis['photo']} gambar")
        if jenis.get("video"):
            bagian.append(f"{jenis['video']} video")
        if jenis.get("animated"):
            bagian.append(f"{jenis['animated']} GIF")

        keterangan = " · ".join(bagian) or f"{jumlah} media"
        return (
            f"<span style='color:#1d9bf0'>📎 {keterangan}</span><br>"
            "<span style='color:#8b98a5; font-size:11px'>"
            "Thumbnail terlihat di kartu feed — klik untuk membukanya di browser."
            "</span>"
        )

    @staticmethod
    def _esc(teks: str) -> str:
        return (
            (teks or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    # ==================================================================
    def _buka(self) -> None:
        if self.post is not None:
            self.buka_browser.emit(self.post)

    @staticmethod
    def _salin(teks: str) -> None:
        if teks:
            QGuiApplication.clipboard().setText(teks)
