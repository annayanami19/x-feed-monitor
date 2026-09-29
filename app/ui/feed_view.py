"""Tampilan feed: model data + delegate yang menggambar kartu postingan.

MENGAPA DELEGATE, BUKAN TUMPUKAN WIDGET
=======================================
Alternatif yang lazim adalah membuat satu QWidget per postingan. Cara itu
mudah ditulis, tapi runtuh saat riwayat sudah ribuan baris: Qt harus
membuat dan menata ribuan widget sekaligus, dan scrolling jadi tersendat.

Delegate menggambar kartu langsung ke kanvas. Qt hanya memanggil `paint()`
untuk kartu yang SEDANG TERLIHAT, jadi biaya render konstan berapa pun
panjang riwayatnya.

KONSEKUENSINYA: teks tidak otomatis bisa di-select
==================================================
Kanvas tidak punya konsep "teks yang bisa diblok". Karena itu isi postingan
digambar lewat QTextDocument (bukan painter.drawText) supaya:

  * teks bisa diblok & di-copy seperti di browser
  * tautan bisa dikenali per-karakter dan diklik

QTextDocument dipakai HANYA untuk isi postingan; bagian lain (header, media,
statistik) tetap digambar manual karena lebih murah dan tidak perlu interaktif.
"""

from __future__ import annotations

import webbrowser

from PyQt6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QPoint,
    QRect,
    QSize,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QListView,
    QMenu,
    QMessageBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from ..models import Media, Post
from .teks_isi import DokumenTeks, domain_dari
from .theme import Palet, ambil_palet
from .widgets import angka_ringkas, waktu_lengkap, waktu_relatif

# --- peran data kustom ------------------------------------------------------
PERAN_POST = int(Qt.ItemDataRole.UserRole) + 1

# --- ukuran kartu -----------------------------------------------------------
PADDING = 14               # padding dalam kartu
JARAK_AVATAR = 10          # jarak avatar ke teks
UKURAN_AVATAR = 38
TINGGI_HEADER = 24         # tinggi dua baris teks header (nama + @handle)
TINGGI_MEDIA = 130         # tinggi satu baris thumbnail
JARAK_MEDIA = 4
TINGGI_STAT = 22
MAKS_MEDIA_TAMPIL = 4
MAKS_BARIS_TEKS = 8        # batas tinggi teks sebelum dipotong

#: Ukuran font isi postingan (pt). Dipakai untuk dokumen teks MAUPUN
#: perhitungan tinggi, supaya keduanya selalu cocok.
UKURAN_FONT_ISI = 10.2

#: Jarak vertikal antara blok header (avatar) dan isi postingan.
#:
#: HARUS lebih besar dari selisih tinggi avatar dengan tinggi teks header.
#: Sebelumnya bernilai 6 sementara avatar 38px dan header hanya 24px,
#: sehingga teks isi mulai 8px SEBELUM avatar selesai — dan terlihat
#: menempel/menabrak avatar.
JARAK_HEADER_ISI = 10

#: Jarak vertikal antara isi postingan dan blok media.
JARAK_ISI_MEDIA = 8


class ModelFeed(QAbstractListModel):
    """Model daftar postingan untuk QListView."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._posts: list[Post] = []

    # ------------------------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._posts)

    def data(self, index: QModelIndex, peran: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        baris = index.row()
        if baris < 0 or baris >= len(self._posts):
            return None

        post = self._posts[baris]

        if peran == PERAN_POST:
            return post
        if peran == Qt.ItemDataRole.ToolTipRole:
            return f"{post.content}\n\n{waktu_lengkap(post.created_at)}"
        if peran == Qt.ItemDataRole.DisplayRole:
            # Dipakai untuk pencarian/aksesibilitas.
            return f"@{post.username}: {post.content}"
        return None

    # ------------------------------------------------------------------
    def ganti_semua(self, posts: list[Post]) -> None:
        """Ganti seluruh isi model."""
        self.beginResetModel()
        self._posts = list(posts)
        self.endResetModel()

    def posts(self) -> list[Post]:
        return self._posts

    def post_pada(self, index: QModelIndex) -> Post | None:
        if not index.isValid():
            return None
        baris = index.row()
        if 0 <= baris < len(self._posts):
            return self._posts[baris]
        return None


class DelegateKartu(QStyledItemDelegate):
    """Menggambar satu postingan sebagai kartu."""

    def __init__(self, pemuat_thumbnail, parent=None) -> None:
        super().__init__(parent)
        self.pemuat = pemuat_thumbnail
        self.palet: Palet = ambil_palet("dark")
        # Lebar viewport terakhir yang diketahui. Dipakai sebagai cadangan
        # saat Qt memanggil sizeHint() sebelum option.rect terisi lebar
        # sebenarnya (terjadi pada layout awal) — tanpa ini tinggi kartu
        # bisa salah dan teks terpotong.
        self.lebar_viewport = 640

        # Dua dokumen terpisah, dan ini disengaja:
        #
        #   `dok`      -> dipakai saat MENGGAMBAR, dan menyimpan seleksi aktif
        #   `dok_ukur` -> dipakai saat MENGUKUR tinggi kartu (sizeHint)
        #
        # Kalau keduanya satu objek, memanggil sizeHint() akan menimpa
        # dokumen yang sedang menampung seleksi pengguna — dan blok teks
        # yang sedang diblok langsung hilang saat Qt mengukur ulang.
        self.dok = DokumenTeks(self.palet)
        self.dok_ukur = DokumenTeks(self.palet)

    def set_palet(self, palet: Palet) -> None:
        self.palet = palet
        for dok in (self.dok, self.dok_ukur):
            dok.palet = palet
            # Paksa dokumen dibangun ulang supaya warna teks & tautan ikut tema.
            dok._sidik_konten = ""  # noqa: SLF001 - sengaja: invalidasi cache

    def set_lebar_viewport(self, lebar: int) -> None:
        self.lebar_viewport = max(280, int(lebar))

    # ------------------------------------------------------------------
    # Ukuran
    # ------------------------------------------------------------------
    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        post: Post | None = index.data(PERAN_POST)
        if post is None:
            return QSize(300, 90)

        lebar = option.rect.width() if option.rect.width() > 0 else self.lebar_viewport
        lebar = max(280, lebar)
        return QSize(lebar, self._tinggi_kartu(post, lebar))

    def _lebar_teks(self, lebar_kartu: int) -> int:
        return max(120, lebar_kartu - (PADDING * 2))

    def _tinggi_teks(self, teks: str, lebar: int) -> int:
        """Tinggi blok isi postingan, dibatasi MAKS_BARIS_TEKS.

        Dihitung lewat dokumen teks yang sama dengan yang dipakai saat
        menggambar — kalau dihitung dengan cara berbeda, tinggi kartu bisa
        tidak cocok dengan isinya dan teks terpotong atau menyisakan ruang.
        """
        if not teks:
            return 0

        fm = QFontMetrics(self._font_teks())
        tinggi_maks = fm.height() * MAKS_BARIS_TEKS

        # Memakai dokumen TERPISAH dari yang dipakai menggambar: kalau sama,
        # pengukuran akan menimpa seleksi teks yang sedang aktif.
        self.dok_ukur.siapkan(teks, [], lebar, tinggi_maks, UKURAN_FONT_ISI)
        return min(self.dok_ukur.tinggi_isi(), tinggi_maks)

    def _tinggi_kartu(self, post: Post, lebar_kartu: int) -> int:
        # Header + jarak yang MEMPERHITUNGKAN tinggi avatar yang sebenarnya.
        # Sebelumnya memakai TINGGI_HEADER saja, sehingga isi postingan
        # mulai sebelum avatar selesai digambar (teks menabrak avatar).
        tinggi = PADDING + max(TINGGI_HEADER, UKURAN_AVATAR) + JARAK_HEADER_ISI

        # isi postingan
        tinggi += self._tinggi_teks(post.content, self._lebar_teks(lebar_kartu))

        # media
        if post.media:
            tinggi += JARAK_ISI_MEDIA + self._tinggi_blok_media(post.media, lebar_kartu)

        tinggi += 6 + TINGGI_STAT + PADDING
        return tinggi

    def _tinggi_blok_media(self, media: list[Media], lebar_kartu: int) -> int:
        n = min(len(media), MAKS_MEDIA_TAMPIL)
        if n == 0:
            return 0
        if n == 1:
            return TINGGI_MEDIA
        if n == 2:
            return TINGGI_MEDIA
        # 3-4 gambar: dua baris
        return TINGGI_MEDIA + JARAK_MEDIA + (TINGGI_MEDIA // 2)

    # ------------------------------------------------------------------
    # Gambar
    # ------------------------------------------------------------------
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:  # noqa: C901
        post: Post | None = index.data(PERAN_POST)
        if post is None:
            super().paint(painter, option, index)
            return

        p = self.palet
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        kartu = option.rect.adjusted(6, 3, -6, -3)

        # --- latar kartu ---
        terpilih = bool(option.state & QStyle.StateFlag.State_Selected)
        disorot = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if terpilih:
            warna_latar = QColor(p.kartu_pilih)
        elif disorot:
            warna_latar = QColor(p.kartu_hover)
        else:
            warna_latar = QColor(p.kartu)

        jalur = QPainterPath()
        jalur.addRoundedRect(
            float(kartu.x()), float(kartu.y()),
            float(kartu.width()), float(kartu.height()),
            12.0, 12.0,
        )
        painter.fillPath(jalur, warna_latar)

        # garis tepi tipis
        painter.setPen(QPen(QColor(p.garis), 1))
        painter.drawPath(jalur)

        # aksen kiri bila terpilih
        if terpilih:
            painter.fillRect(
                QRect(kartu.x(), kartu.y() + 8, 3, kartu.height() - 16),
                QColor(p.aksen),
            )

        # --- area kerja ---
        x = kartu.x() + PADDING
        y = kartu.y() + PADDING
        lebar = kartu.width() - (PADDING * 2)

        # --- header: avatar + nama + waktu ---
        y = self._gambar_header(painter, post, x, y, lebar)

        # --- isi postingan ---
        y = self._gambar_teks(painter, post, index, x, y, lebar)

        # --- media ---
        if post.media:
            y = self._gambar_media(painter, post.media, x, y, lebar)

        # --- statistik ---
        self._gambar_stat(painter, post, x, y + 6, lebar)

        painter.restore()

    # ------------------------------------------------------------------
    def _font_teks(self) -> QFont:
        f = QFont()
        f.setPointSizeF(UKURAN_FONT_ISI)
        return f

    def _font_nama(self) -> QFont:
        f = QFont()
        f.setPointSizeF(10.0)
        f.setBold(True)
        return f

    def _font_redup(self) -> QFont:
        f = QFont()
        f.setPointSizeF(9.0)
        return f

    def _gambar_header(self, painter: QPainter, post: Post,
                       x: int, y: int, lebar: int) -> int:
        """Gambar avatar + nama + username + waktu. Kembalikan y berikutnya."""
        p = self.palet

        # avatar bulat (inisial — avatar asli tidak diunduh agar hemat)
        lingkaran = QRect(x, y, UKURAN_AVATAR, UKURAN_AVATAR)
        painter.setBrush(QColor(p.aksen))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(lingkaran)

        inisial = (post.display_name or post.username or "?")[:1].upper()
        painter.setPen(QColor(p.aksen_teks))
        f_inisial = QFont()
        f_inisial.setPointSizeF(13.0)
        f_inisial.setBold(True)
        painter.setFont(f_inisial)
        painter.drawText(lingkaran, Qt.AlignmentFlag.AlignCenter, inisial)

        # teks header
        teks_x = x + UKURAN_AVATAR + JARAK_AVATAR
        teks_lebar = lebar - UKURAN_AVATAR - JARAK_AVATAR

        nama = post.display_name or post.username
        fm_waktu = QFontMetrics(self._font_redup())
        waktu = waktu_relatif(post.created_at)
        lebar_waktu = fm_waktu.horizontalAdvance(waktu) + 8

        painter.setFont(self._font_nama())
        fm_nama = QFontMetrics(self._font_nama())
        nama_tampil = fm_nama.elidedText(nama, Qt.TextElideMode.ElideRight,
                                         max(60, teks_lebar - lebar_waktu - 10))
        painter.setPen(QColor(p.teks))
        painter.drawText(
            QRect(teks_x, y, teks_lebar - lebar_waktu, TINGGI_HEADER // 2 + 4),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            nama_tampil,
        )

        # waktu di kanan atas
        painter.setFont(self._font_redup())
        painter.setPen(QColor(p.teks_redup))
        painter.drawText(
            QRect(teks_x + teks_lebar - lebar_waktu, y, lebar_waktu, TINGGI_HEADER // 2 + 4),
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            waktu,
        )

        # baris kedua: @username + badge
        baris2 = QRect(teks_x, y + 15, teks_lebar, 16)
        painter.setPen(QColor(p.teks_redup))
        painter.setFont(self._font_redup())
        fm2 = QFontMetrics(self._font_redup())

        kursor = baris2.x()
        handle = f"@{post.username}"
        lebar_handle = fm2.horizontalAdvance(handle)
        painter.drawText(
            QRect(kursor, baris2.y(), lebar_handle + 4, baris2.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            handle,
        )
        kursor += lebar_handle + 8

        # badge retweet / reply
        badge_aktif: list[tuple[str, str]] = []
        if post.is_retweet:
            badge_aktif.append(("RETWEET", p.retweet))
        if post.is_reply:
            badge_aktif.append(("REPLY", p.reply))

        for teks_badge, warna in badge_aktif:
            lebar_badge = fm2.horizontalAdvance(teks_badge) + 12
            if kursor + lebar_badge > baris2.right():
                break
            badge = QRect(kursor, baris2.y() + 1, lebar_badge, baris2.height() - 2)
            painter.setPen(QPen(QColor(warna), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            jalur = QPainterPath()
            jalur.addRoundedRect(float(badge.x()), float(badge.y()),
                                 float(badge.width()), float(badge.height()), 6.0, 6.0)
            painter.drawPath(jalur)
            painter.setPen(QColor(warna))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, teks_badge)
            painter.setPen(QColor(p.teks_redup))
            kursor += lebar_badge + 6

        # Jarak ke isi postingan: pakai nilai yang MEMPERHITUNGKAN tinggi
        # avatar. Sebelumnya memakai angka tetap yang lebih kecil dari
        # tinggi avatar, sehingga isi postingan menabrak avatar.
        return y + max(TINGGI_HEADER, UKURAN_AVATAR) + JARAK_HEADER_ISI

    def _gambar_teks(self, painter: QPainter, post: Post, index: QModelIndex,
                     x: int, y: int, lebar: int) -> int:
        """Gambar isi postingan lewat dokumen teks. Kembalikan y berikutnya.

        Memakai QTextDocument (bukan `painter.drawText`) supaya teks bisa
        diblok & di-copy, dan tautannya bisa diklik.

        Catatan koordinat: `option.rect` yang diterima `paint()` sudah dalam
        koordinat viewport (posisi scroll sudah diperhitungkan Qt), jadi
        dokumen digambar langsung di (x, y) tanpa koreksi tambahan.
        """
        if not post.content:
            return y

        p = self.palet
        fm = QFontMetrics(self._font_teks())
        tinggi_maks = fm.height() * MAKS_BARIS_TEKS

        dok = self.dok
        dok.siapkan(post.content, post.links, lebar, tinggi_maks, UKURAN_FONT_ISI)

        # Seleksi hanya berlaku untuk kartu yang memilikinya. Ini mencegah
        # blok biru "menempel" di kartu lain setelah model di-refresh.
        if dok.seleksi is not None and dok.baris_pemilik != index.row():
            dok.bersihkan_seleksi()

        dok.gambar(painter, x, y)

        tinggi = min(dok.tinggi_isi(), tinggi_maks)

        # tanda terpotong
        if dok.tinggi_isi() > tinggi_maks:
            painter.setPen(QColor(p.teks_samar))
            painter.drawText(
                QRect(x, y + tinggi - 2, lebar, fm.height()),
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom),
                "… klik dua kali untuk selengkapnya",
            )

        return y + tinggi

    def _gambar_media(self, painter: QPainter, media: list[Media],
                      x: int, y: int, lebar: int) -> int:
        """Gambar thumbnail. Kembalikan y berikutnya."""
        n = min(len(media), MAKS_MEDIA_TAMPIL)
        if n == 0:
            return y

        y += JARAK_ISI_MEDIA

        if n == 1:
            self._gambar_satu_media(painter, media[0], QRect(x, y, lebar, TINGGI_MEDIA))
            return y + TINGGI_MEDIA

        # 2-4 gambar: grid
        if n == 2:
            lebar_item = (lebar - JARAK_MEDIA) // 2
            for i in range(2):
                self._gambar_satu_media(
                    painter, media[i],
                    QRect(x + i * (lebar_item + JARAK_MEDIA), y, lebar_item, TINGGI_MEDIA),
                )
            return y + TINGGI_MEDIA

        # 3-4: baris atas 2 gambar, baris bawah sisanya
        lebar_item = (lebar - JARAK_MEDIA) // 2
        tinggi_atas = TINGGI_MEDIA
        tinggi_bawah = TINGGI_MEDIA // 2

        for i in range(min(2, n)):
            self._gambar_satu_media(
                painter, media[i],
                QRect(x + i * (lebar_item + JARAK_MEDIA), y, lebar_item, tinggi_atas),
            )

        sisa = n - 2
        if sisa > 0:
            y_bawah = y + tinggi_atas + JARAK_MEDIA
            lebar_bawah = (lebar - JARAK_MEDIA * (sisa - 1)) // sisa
            for i in range(sisa):
                self._gambar_satu_media(
                    painter, media[2 + i],
                    QRect(x + i * (lebar_bawah + JARAK_MEDIA), y_bawah,
                          lebar_bawah, tinggi_bawah),
                )
            return y_bawah + tinggi_bawah

        return y + tinggi_atas

    def _gambar_satu_media(self, painter: QPainter, item: Media, kotak: QRect) -> None:
        """Gambar satu thumbnail, atau placeholder bila belum termuat."""
        p = self.palet

        jalur = QPainterPath()
        jalur.addRoundedRect(float(kotak.x()), float(kotak.y()),
                             float(kotak.width()), float(kotak.height()), 8.0, 8.0)
        painter.save()
        painter.setClipPath(jalur)

        # placeholder
        painter.fillRect(kotak, QColor(p.latar_alt))

        pixmap: QPixmap | None = self.pemuat.minta(item.url)
        if pixmap is not None and not pixmap.isNull():
            disesuaikan = pixmap.scaled(
                kotak.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            # tengah
            ox = kotak.x() + (kotak.width() - disesuaikan.width()) // 2
            oy = kotak.y() + (kotak.height() - disesuaikan.height()) // 2
            painter.drawPixmap(ox, oy, disesuaikan)
        else:
            painter.setPen(QColor(p.teks_samar))
            painter.setFont(self._font_redup())
            painter.drawText(kotak, Qt.AlignmentFlag.AlignCenter, "memuat…")

        # badge tipe untuk video/gif
        if item.tipe in ("video", "animated"):
            label = "GIF" if item.tipe == "animated" else "▶"
            badge = QRect(kotak.x() + 6, kotak.y() + 6, 30, 20)
            painter.setBrush(QColor(0, 0, 0, 170))
            painter.setPen(Qt.PenStyle.NoPen)
            jalur_badge = QPainterPath()
            jalur_badge.addRoundedRect(float(badge.x()), float(badge.y()),
                                       float(badge.width()), float(badge.height()), 5.0, 5.0)
            painter.drawPath(jalur_badge)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, label)

        painter.restore()

        # tepi
        painter.setPen(QPen(QColor(p.garis), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(jalur)

    def _gambar_stat(self, painter: QPainter, post: Post,
                     x: int, y: int, lebar: int) -> None:
        """Gambar baris statistik (like, retweet, reply, view)."""
        p = self.palet
        painter.setFont(self._font_redup())
        painter.setPen(QColor(p.teks_redup))

        fm = QFontMetrics(self._font_redup())
        bagian = [
            f"♥ {angka_ringkas(post.like_count)}",
            f"↻ {angka_ringkas(post.retweet_count)}",
            f"💬 {angka_ringkas(post.reply_count)}",
        ]
        if post.view_count is not None:
            bagian.append(f"👁 {angka_ringkas(post.view_count)}")

        kursor = x
        for teks in bagian:
            lebar_teks = fm.horizontalAdvance(teks)
            if kursor + lebar_teks > x + lebar:
                break
            painter.drawText(
                QRect(kursor, y, lebar_teks + 4, TINGGI_STAT),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                teks,
            )
            kursor += lebar_teks + 18


class TampilanFeed(QListView):
    """Daftar postingan + menu klik-kanan.

    Menangani juga interaksi teks isi postingan:
      * klik-tahan-drag  -> memblok teks (seleksi)
      * Ctrl+C           -> menyalin blok yang dipilih
      * klik pada tautan -> konfirmasi, lalu buka browser
      * Escape           -> membatalkan blok
    """

    #: Dipancarkan saat pengguna memilih "Buka di browser".
    minta_buka = pyqtSignal(object)          # Post
    #: Dipancarkan saat pengguna memilih "Detail".
    minta_detail = pyqtSignal(object)        # Post
    #: Dipancarkan saat thumbnail baru selesai dimuat (perlu repaint).
    perlu_repaint = pyqtSignal()

    def __init__(self, pemuat_thumbnail, parent=None) -> None:
        super().__init__(parent)
        self.pemuat = pemuat_thumbnail
        self.palet: Palet = ambil_palet("dark")

        self._model = ModelFeed(self)
        self._delegate = DelegateKartu(pemuat_thumbnail, self)
        self.setModel(self._model)
        self.setItemDelegate(self._delegate)

        # --- perilaku tampilan ---
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setUniformItemSizes(False)
        self.setMouseTracking(True)          # supaya hover terdeteksi
        # Viewport-lah yang menerima event mouse, jadi tracking harus
        # diaktifkan di sana juga — tanpa ini efek hover kartu tidak muncul.
        self.viewport().setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setSpacing(0)
        self.setWordWrap(False)

        # --- status seleksi teks ---
        #: True saat pengguna sedang men-drag untuk memblok teks. Selama ini
        #: aktif, perilaku bawaan QListView (memilih baris) dinonaktifkan
        #: supaya tidak bertabrakan dengan seleksi teks.
        self._sedang_blok = False
        self._baris_blok = -1
        self._posisi_awal_blok = 0

        # --- sinyal ---
        self.customContextMenuRequested.connect(self._menu_konteks)
        self.doubleClicked.connect(self._pada_double_klik)
        self.pemuat.gambar_siap.connect(self._pada_thumbnail)

    # ==================================================================
    # Geometri teks (harus cocok dengan yang dipakai delegate)
    # ==================================================================
    def _geometri_teks(self, index: QModelIndex) -> tuple[int, int, int] | None:
        """(x, y, lebar) area isi postingan pada sebuah kartu.

        Dihitung dari rect kartu, bukan disimpan delegate, supaya kedua
        sisi selalu memakai angka yang sama.
        """
        rect = self.visualRect(index)
        if rect.isEmpty():
            return None

        kartu = rect.adjusted(6, 3, -6, -3)
        x = kartu.x() + PADDING
        y = kartu.y() + PADDING + max(TINGGI_HEADER, UKURAN_AVATAR) + JARAK_HEADER_ISI
        lebar = kartu.width() - (PADDING * 2)
        return x, y, lebar

    def _koordinat_teks(self, index: QModelIndex, pos: QPoint) -> tuple[int, int] | None:
        """Ubah posisi mouse (viewport) jadi koordinat lokal di dalam teks."""
        geo = self._geometri_teks(index)
        if geo is None:
            return None
        x, y, _ = geo
        return pos.x() - x, pos.y() - y

    def _dokumen_untuk(self, index: QModelIndex) -> bool:
        """Pastikan dokumen teks sudah dibangun untuk kartu ini."""
        post: Post | None = index.data(PERAN_POST)
        geo = self._geometri_teks(index)
        if post is None or geo is None:
            return False

        _, _, lebar = geo
        fm = QFontMetrics(self._delegate._font_teks())  # noqa: SLF001
        tinggi_maks = fm.height() * MAKS_BARIS_TEKS
        self._delegate.dok.siapkan(
            post.content, post.links, lebar, tinggi_maks, UKURAN_FONT_ISI
        )
        return True

    # ==================================================================
    # Seleksi teks
    # ==================================================================
    def mousePressEvent(self, event) -> None:  # noqa: N802 - API Qt
        """Mulai blok teks bila klik tepat di area isi postingan."""
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        index = self.indexAt(event.position().toPoint())
        if not index.isValid():
            self._bersihkan_blok()
            super().mousePressEvent(event)
            return

        # Klik pada tautan -> konfirmasi, JANGAN mulai blok.
        if self._coba_buka_tautan(index, event.position().toPoint()):
            return

        if not self._dokumen_untuk(index):
            super().mousePressEvent(event)
            return

        koord = self._koordinat_teks(index, event.position().toPoint())
        if koord is None:
            super().mousePressEvent(event)
            return

        x, y = koord
        dok = self._delegate.dok

        # Klik di luar area teks (mis. di media atau di bawah teks) ->
        # perilaku bawaan (memilih baris).
        if x < 0 or y < 0 or y > dok.tinggi_isi():
            self._bersihkan_blok()
            super().mousePressEvent(event)
            return

        # Mulai blok baru.
        self._bersihkan_blok()
        posisi = dok.posisi_pada(x, y)
        dok.seleksi = (posisi, posisi)
        dok.baris_pemilik = index.row()

        self._sedang_blok = True
        self._baris_blok = index.row()
        self._posisi_awal_blok = posisi

        # Jangan teruskan ke QListView: kita menangani sendiri, dan
        # meneruskannya akan membuat baris terpilih + teks ter-scroll.
        event.accept()
        self.viewport().update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - API Qt
        """Perluas blok saat mouse digeser, atau ubah kursor di atas tautan."""
        if self._sedang_blok:
            self._perluas_blok(event.position().toPoint())
            event.accept()
            return

        # Ubah kursor jadi "tangan" saat di atas tautan, supaya terlihat
        # bisa diklik.
        index = self.indexAt(event.position().toPoint())
        if index.isValid() and self._tautan_pada(index, event.position().toPoint()):
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - API Qt
        """Selesaikan blok."""
        if self._sedang_blok:
            self._sedang_blok = False
            event.accept()

            # Blok yang kosong (cuma klik, tanpa geser) -> bersihkan,
            # supaya tidak ada seleksi 0 karakter yang mengganggu.
            dok = self._delegate.dok
            if dok.seleksi is not None and not dok.ada_seleksi():
                dok.bersihkan_seleksi()
            self.viewport().update()
            return

        super().mouseReleaseEvent(event)

    def _perluas_blok(self, pos: QPoint) -> None:
        """Perluas seleksi sampai posisi mouse sekarang."""
        index = self.indexAt(pos)
        if not index.isValid():
            return

        dok = self._delegate.dok
        geo = self._geometri_teks(index)
        if geo is None:
            return

        # Blok boleh melewati batas kartu, tapi tetap dihitung pada dokumen
        # kartu tempat blok dimulai.
        x, y, lebar = geo
        lokal_x = pos.x() - x
        lokal_y = pos.y() - y

        # Batasi ke area teks supaya tidak "lari" ke kartu lain.
        lokal_y = max(0, min(lokal_y, dok.tinggi_isi()))
        lokal_x = max(0, min(lokal_x, lebar))

        posisi = dok.posisi_pada(lokal_x, lokal_y)
        if dok.seleksi is not None:
            dok.seleksi = (self._posisi_awal_blok, posisi)
        else:
            dok.seleksi = (self._posisi_awal_blok, posisi)
            dok.baris_pemilik = index.row()

        self.viewport().update()

    def _bersihkan_blok(self) -> None:
        dok = self._delegate.dok
        if dok.seleksi is not None:
            dok.bersihkan_seleksi()
            self.viewport().update()

    # ==================================================================
    # Tautan
    # ==================================================================
    def _tautan_pada(self, index: QModelIndex, pos: QPoint) -> str:
        """URL di posisi mouse, atau string kosong."""
        if not self._dokumen_untuk(index):
            return ""
        koord = self._koordinat_teks(index, pos)
        if koord is None:
            return ""
        x, y = koord
        if x < 0 or y < 0:
            return ""
        return self._delegate.dok.link_pada(x, y)

    def _coba_buka_tautan(self, index: QModelIndex, pos: QPoint) -> bool:
        """Bila posisi ini sebuah tautan: konfirmasi lalu buka. True bila ditangani."""
        url = self._tautan_pada(index, pos)
        if not url:
            return False

        self._konfirmasi_buka_tautan(url)
        return True

    def _konfirmasi_buka_tautan(self, url: str) -> None:
        """Tampilkan peringatan berisi domain tujuan sebelum membuka browser."""
        domain = domain_dari(url) or url

        pesan = QMessageBox(self)
        pesan.setWindowTitle("Buka tautan di browser?")
        pesan.setIcon(QMessageBox.Icon.Warning)
        pesan.setText("Tautan ini akan dibuka di browser default kamu.")
        pesan.setInformativeText(
            f"<b>Menuju ke:</b><br>{domain}<br><br>"
            f"<span style='color:#8b98a5; font-size:11px'>{url}</span>"
        )
        pesan.setTextFormat(Qt.TextFormat.RichText)

        tombol_buka = pesan.addButton("Buka browser", QMessageBox.ButtonRole.AcceptRole)
        pesan.addButton("Batal", QMessageBox.ButtonRole.RejectRole)
        pesan.setDefaultButton(pesan.buttons()[-1])   # default = Batal
        pesan.exec()

        if pesan.clickedButton() is tombol_buka:
            buka_di_browser(url)

    # ==================================================================
    def resizeEvent(self, event) -> None:  # noqa: N802 - API Qt
        """Teruskan lebar baru ke delegate supaya tinggi kartu dihitung ulang."""
        super().resizeEvent(event)
        lebar = self.viewport().width()
        if lebar != self._delegate.lebar_viewport:
            self._delegate.set_lebar_viewport(lebar)
            self.doItemsLayout()
            self.viewport().update()

    def set_palet(self, palet: Palet) -> None:
        self.palet = palet
        self._delegate.set_palet(palet)
        self.viewport().update()

    def ganti_posts(self, posts: list[Post]) -> None:
        """Ganti seluruh isi feed, pertahankan posisi scroll.

        Tanpa menjaga posisi scroll, setiap siklus polling akan melempar
        pengguna kembali ke atas — sangat mengganggu saat sedang membaca
        postingan lama sambil menunggu data baru masuk.
        """
        bar = self.verticalScrollBar()
        posisi_lama = bar.value()

        self._model.ganti_semua(posts)
        self.doItemsLayout()

        # Kembalikan posisi (dibatasi nilai maksimum yang baru).
        bar.setValue(min(posisi_lama, bar.maximum()))

    def posts(self) -> list[Post]:
        return self._model.posts()

    def post_terpilih(self) -> Post | None:
        return self._model.post_pada(self.currentIndex())

    def pilih_pertama(self) -> None:
        if self._model.rowCount() > 0:
            self.setCurrentIndex(self._model.index(0, 0))

    def _pada_thumbnail(self, url: str, pixmap) -> None:
        """Thumbnail selesai dimuat -> gambar ulang kartu yang memakainya.

        Hanya viewport yang digambar ulang, jadi biayanya kecil.
        """
        self.viewport().update()

    # ------------------------------------------------------------------
    def _pada_double_klik(self, index: QModelIndex) -> None:
        post = self._model.post_pada(index)
        if post is not None:
            self.minta_detail.emit(post)

    def _menu_konteks(self, pos: QPoint) -> None:
        index = self.indexAt(pos)
        if not index.isValid():
            return

        post = self._model.post_pada(index)
        if post is None:
            return

        p = self.palet
        menu = QMenu(self)
        menu.setStyleSheet(f"QMenu {{ background: {p.latar_alt}; color: {p.teks}; }}")

        aksi_buka = menu.addAction("Buka di browser")
        aksi_salin_link = menu.addAction("Copy link")
        aksi_salin_teks = menu.addAction("Copy teks postingan")
        menu.addSeparator()
        aksi_detail = menu.addAction("Lihat detail")

        dipilih = menu.exec(self.viewport().mapToGlobal(pos))
        if dipilih is None:
            return

        if dipilih == aksi_buka:
            self.minta_buka.emit(post)
        elif dipilih == aksi_salin_link:
            self._salin(post.url)
        elif dipilih == aksi_salin_teks:
            self._salin(post.content)
        elif dipilih == aksi_detail:
            self.minta_detail.emit(post)

    @staticmethod
    def _salin(teks: str) -> None:
        if teks:
            QGuiApplication.clipboard().setText(teks)

    # ------------------------------------------------------------------
    def keyPressEvent(self, event) -> None:  # noqa: N802 - API Qt
        """Ctrl+C = salin blok teks, Escape = batalkan blok, Enter = detail."""
        tombol = event.key()
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)

        # --- Ctrl+C: salin teks yang diblok ---
        #
        # Ini didahulukan sebelum perilaku bawaan (yang menyalin link),
        # supaya blok teks yang sedang aktif benar-benar tersalin.
        if tombol == Qt.Key.Key_C and ctrl:
            dok = self._delegate.dok
            if dok.seleksi is not None:
                teks = dok.teks_terpilih()
                if teks:
                    self._salin(teks)
                    return
            # Tidak ada blok aktif -> perilaku lama: salin link postingan.
            post = self.post_terpilih()
            if post is not None:
                self._salin(post.url)
                return

        # --- Ctrl+A: blok seluruh isi postingan yang sedang terpilih ---
        if tombol == Qt.Key.Key_A and ctrl:
            index = self.currentIndex()
            if index.isValid() and self._dokumen_untuk(index):
                dok = self._delegate.dok
                dok.pilih_semua()
                dok.baris_pemilik = index.row()
                self.viewport().update()
                return

        # --- Escape: batalkan blok ---
        if tombol == Qt.Key.Key_Escape:
            if self._delegate.dok.seleksi is not None:
                self._bersihkan_blok()
                return

        # --- Enter: buka detail ---
        if tombol in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            post = self.post_terpilih()
            if post is not None:
                self.minta_detail.emit(post)
                return

        super().keyPressEvent(event)


def buka_di_browser(url: str) -> bool:
    """Buka URL di browser default. Kembalikan True bila berhasil."""
    if not url:
        return False
    try:
        return webbrowser.open(url)
    except Exception:  # noqa: BLE001 - kegagalan browser bukan error fatal
        return False
