"""Jendela utama: toolbar, panel filter, feed, statusbar, dan semua wiring.

Tanggung jawab file ini:
  * merakit tampilan
  * menghubungkan sinyal worker <-> UI
  * menyimpan preferensi filter & tema

Logika jaringan ada di poller.py, logika data di db.py, tampilan kartu di
feed_view.py — file ini hanya menyatukan.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QKeySequence
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .. import config as cfg
from .. import __app_name__, __version__
from ..db import RiwayatDB
from ..filters import KriteriaFilter, RENTANG_PILIHAN, batas_waktu, saring
from ..ikon import ikon_aplikasi
from ..models import Account, Post, waktu_sekarang
from ..notifier import Notifier
from ..poller import HasilAkun, PollerWorker
from ..thumbnails import PemuatThumbnail
from .accounts_dialog import DialogAkun
from .feed_view import TampilanFeed, buka_di_browser
from .post_detail import PanelDetail
from .settings_dialog import DialogPengaturan
from .theme import ambil_palet, qss
from .widgets import pemisah_horizontal, waktu_relatif

#: Jumlah postingan maksimum yang ditampilkan di feed sekaligus.
BATAS_TAMPIL = 1000


class JendelaUtama(QMainWindow):
    """Jendela utama aplikasi."""

    def __init__(self) -> None:
        super().__init__()

        # --- state ---
        self.config = cfg.muat()
        self.akun: list[Account] = cfg.ambil_akun(self.config)
        self.kriteria = KriteriaFilter.dari_dict(self.config.get("filter"))
        self.db = RiwayatDB()
        self.pemuat_thumbnail = PemuatThumbnail(self)
        self.notifier = Notifier(self)
        self.worker: PollerWorker | None = None

        # Akun yang dicentang di panel filter.
        #
        # Kalau kriteria tersimpan berarti "semua akun", himpunan ini harus
        # diisi SEMUA id akun — bukan dibiarkan kosong. Kalau kosong, melepas
        # centang satu akun akan menghasilkan himpunan kosong yang berarti
        # "tidak ada akun dipilih", bukan "semua kecuali satu".
        self._akun_terpilih_manual: set[str] = (
            {a.id for a in self.akun} if self.kriteria.semua_akun
            else set(self.kriteria.akun_ids)
        )

        # --- pembersihan riwayat saat start ---
        self._bersihkan_riwayat_awal()

        # --- tampilan ---
        self.setWindowTitle(f"{__app_name__} v{__version__}")
        # Ikon dari assets/icon.ico — berisi 7 ukuran sekaligus, sehingga
        # Windows bisa memakai ukuran yang tepat di judul jendela, taskbar,
        # Alt+Tab, dan shortcut.
        self.setWindowIcon(ikon_aplikasi())
        self.resize(1360, 880)
        self.setMinimumSize(940, 600)

        self._bangun_toolbar()
        self._bangun_tengah()
        self._bangun_statusbar()

        # --- tema ---
        self.terapkan_tema(self.config.get("tema", "dark"))

        # --- timer (dibuat SEBELUM worker) ---
        # Worker bisa memancarkan sinyal kapan saja setelah dijalankan, dan
        # handler-nya menyentuh timer-timer ini. Karena itu timer harus sudah
        # ada lebih dulu.

        # Timer debounce pembacaan ulang feed: satu siklus polling memancarkan
        # hasil per akun; timer ini menggabungkannya jadi satu pembacaan DB.
        self._timer_feed = QTimer(self)
        self._timer_feed.setSingleShot(True)
        self._timer_feed.setInterval(400)
        self._timer_feed.timeout.connect(self.muat_ulang_feed)

        # Timer auto-poll
        self.timer_poll = QTimer(self)
        self.timer_poll.timeout.connect(self.mulai_refresh)
        self._atur_timer()

        # --- worker polling ---
        self._jalankan_worker()

        # --- muat data awal dari DB ---
        self._segarkan_daftar_akun()
        self.muat_ulang_feed()

        # Tulis config sejak awal, supaya file-nya sudah ada (dan lokasinya
        # jelas) walau pengguna belum sempat mengubah apa pun.
        cfg.simpan(self.config)

        # --- notifikasi ---
        self.notifier.aktif = bool(self.config.get("notifikasi_aktif", True))
        self.notifier.diklik.connect(self._pada_notifikasi_diklik)
        self.notifier.tampilkan()

        # --- refresh pertama ---
        QTimer.singleShot(600, self.mulai_refresh)

    # ==================================================================
    # Ikon
    # ==================================================================
    # Perakitan UI
    # ==================================================================
    def _bangun_toolbar(self) -> None:
        bar = QToolBar("Utama")
        bar.setMovable(False)
        self.addToolBar(bar)

        # --- Refresh ---
        self.aksi_refresh = QAction("Refresh", self)
        self.aksi_refresh.setShortcut(QKeySequence("F5"))
        self.aksi_refresh.setToolTip("Ambil postingan terbaru sekarang (F5)")
        self.aksi_refresh.triggered.connect(self.mulai_refresh)
        bar.addAction(self.aksi_refresh)

        # --- status auto-poll ---
        self.label_auto = QLabel()
        bar.addWidget(self.label_auto)

        bar.addSeparator()

        # --- rentang waktu ---
        bar.addWidget(QLabel("Periode:"))
        self.combo_rentang = QComboBox()
        for label, hari in RENTANG_PILIHAN:
            self.combo_rentang.addItem(label, hari)
        self.combo_rentang.setToolTip("Batasi feed ke rentang waktu tertentu")
        self.combo_rentang.currentIndexChanged.connect(self._pada_rentang_berubah)
        bar.addWidget(self.combo_rentang)

        bar.addSeparator()

        # --- aksi akun ---
        aksi_akun = QAction("Akun", self)
        aksi_akun.setToolTip("Kelola akun yang dipantau")
        aksi_akun.triggered.connect(self.buka_dialog_akun)
        bar.addAction(aksi_akun)

        aksi_pengaturan = QAction("Pengaturan", self)
        aksi_pengaturan.setToolTip("Interval, riwayat, notifikasi")
        aksi_pengaturan.triggered.connect(self.buka_dialog_pengaturan)
        bar.addAction(aksi_pengaturan)

        # --- spacer: dorong tombol berikutnya ke kanan ---
        kosong = QWidget()
        kosong.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        bar.addWidget(kosong)

        # --- tema ---
        self.tombol_tema = QPushButton()
        self.tombol_tema.setObjectName("ikon")
        self.tombol_tema.setToolTip("Ganti tema terang/gelap")
        self.tombol_tema.clicked.connect(self.toggle_tema)
        bar.addWidget(self.tombol_tema)

    def _bangun_tengah(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._bangun_panel_filter())
        splitter.addWidget(self._bangun_area_feed())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([int(self.config.get("lebar_panel_filter", 260)), 1100])
        self.splitter = splitter
        self.setCentralWidget(splitter)

    def _bangun_panel_filter(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panelFilter")
        panel.setMinimumWidth(210)
        panel.setMaximumWidth(420)

        tata = QVBoxLayout(panel)
        tata.setContentsMargins(12, 12, 12, 12)
        tata.setSpacing(9)

        # --- pencarian ---
        judul_cari = QLabel("PENCARIAN")
        judul_cari.setObjectName("judulPanel")
        tata.addWidget(judul_cari)

        self.input_cari = QLineEdit()
        self.input_cari.setPlaceholderText("Cari kata / hashtag…")
        self.input_cari.setClearButtonEnabled(True)
        self.input_cari.setText(self.kriteria.keyword)
        # debounce: jangan saring tiap ketukan tombol
        self._timer_cari = QTimer(self)
        self._timer_cari.setSingleShot(True)
        self._timer_cari.setInterval(300)
        self._timer_cari.timeout.connect(self._pada_cari)
        self.input_cari.textChanged.connect(lambda _: self._timer_cari.start())
        tata.addWidget(self.input_cari)

        tata.addWidget(pemisah_horizontal())

        # --- daftar akun ---
        baris_judul = QHBoxLayout()
        judul_akun = QLabel("AKUN")
        judul_akun.setObjectName("judulPanel")
        baris_judul.addWidget(judul_akun)
        baris_judul.addStretch(1)

        tombol_semua = QPushButton("Semua")
        tombol_semua.setObjectName("ikon")
        tombol_semua.setToolTip("Pilih semua akun")
        tombol_semua.clicked.connect(lambda: self._pilih_semua_akun(True))
        baris_judul.addWidget(tombol_semua)

        tombol_none = QPushButton("Kosong")
        tombol_none.setObjectName("ikon")
        tombol_none.setToolTip("Kosongkan pilihan akun")
        tombol_none.clicked.connect(lambda: self._pilih_semua_akun(False))
        baris_judul.addWidget(tombol_none)
        tata.addLayout(baris_judul)

        self.daftar_akun = QListWidget()
        self.daftar_akun.setObjectName("daftarAkun")
        self.daftar_akun.setToolTip("Centang akun yang ingin ditampilkan")
        self.daftar_akun.itemChanged.connect(self._pada_akun_dicentang)
        tata.addWidget(self.daftar_akun, 1)

        tata.addWidget(pemisah_horizontal())

        # --- opsi tambahan ---
        judul_opsi = QLabel("TAMPILAN")
        judul_opsi.setObjectName("judulPanel")
        tata.addWidget(judul_opsi)

        self.cek_retweet = QCheckBox("Sembunyikan retweet")
        self.cek_retweet.setChecked(self.kriteria.sembunyikan_retweet)
        self.cek_retweet.toggled.connect(self._pada_opsi_berubah)
        tata.addWidget(self.cek_retweet)

        self.cek_reply = QCheckBox("Sembunyikan reply")
        self.cek_reply.setChecked(self.kriteria.sembunyikan_reply)
        self.cek_reply.toggled.connect(self._pada_opsi_berubah)
        tata.addWidget(self.cek_reply)

        return panel

    def _bangun_area_feed(self) -> QWidget:
        wadah = QWidget()
        tata = QHBoxLayout(wadah)          # feed | panel detail (kanan)
        tata.setContentsMargins(0, 0, 0, 0)
        tata.setSpacing(0)

        self.feed = TampilanFeed(self.pemuat_thumbnail, self)
        self.feed.minta_buka.connect(self._pada_buka)
        self.feed.minta_detail.connect(self._pada_detail)
        tata.addWidget(self.feed, 1)

        # --- panel detail (tersembunyi sampai dipakai) ---
        self.panel_detail = PanelDetail(self)
        self.panel_detail.tutup.connect(self._tutup_detail)
        self.panel_detail.buka_browser.connect(self._pada_buka)
        self.panel_detail.hide()
        tata.addWidget(self.panel_detail)

        return wadah

    def _bangun_statusbar(self) -> None:
        bar = QStatusBar()
        self.setStatusBar(bar)

        self.label_status = QLabel("Siap")
        bar.addWidget(self.label_status, 1)

        self.label_progres = QLabel("")
        bar.addPermanentWidget(self.label_progres)

        self.label_total = QLabel("")
        bar.addPermanentWidget(self.label_total)

        # Versi di kanan statusbar — berguna saat melaporkan masalah, karena
        # langsung terlihat versi mana yang sedang dipakai.
        self.label_versi = QLabel(f"v{__version__}")
        self.label_versi.setToolTip(
            f"{__app_name__} v{__version__}\n\n"
            "Sertakan nomor versi ini saat melaporkan masalah."
        )
        self.label_versi.setStyleSheet("color: #5f6b78; padding-left: 8px;")
        bar.addPermanentWidget(self.label_versi)

    # ==================================================================
    # Worker
    # ==================================================================
    def _jalankan_worker(self) -> None:
        self.worker = PollerWorker()
        self.worker.atur_akun(self.akun)
        self.worker.atur_auth_utama(cfg.ambil_auth_utama(self.config))
        self.worker.atur_opsi(
            int(self.config.get("post_per_akun", 20)),
            float(self.config.get("jeda_antar_akun", 3)),
        )

        self.worker.siklus_mulai.connect(self._pada_siklus_mulai)
        self.worker.akun_mulai.connect(self._pada_akun_mulai)
        self.worker.akun_selesai.connect(self._pada_akun_selesai)
        self.worker.postingan_masuk.connect(self._pada_postingan_masuk)
        self.worker.siklus_selesai.connect(self._pada_siklus_selesai)
        self.worker.catatan.connect(self._pada_catatan)
        self.worker.profil_diperbarui.connect(self._pada_profil)

        self.worker.mulai()

    def _pada_siklus_mulai(self, jumlah: int) -> None:
        self.aksi_refresh.setEnabled(False)
        self.label_progres.setText(f"0/{jumlah}")
        self.label_status.setText(f"Mengambil postingan dari {jumlah} akun…")

    def _pada_akun_mulai(self, account_id: str, username: str) -> None:
        self.label_status.setText(f"Mengambil @{username}…")

    def _pada_akun_selesai(self, ringkas: HasilAkun) -> None:
        akun = cfg.cari_akun(self.akun, ringkas.account_id)
        if akun is None:
            return

        akun.last_fetch = waktu_sekarang()
        if ringkas.berhasil:
            akun.last_status = "ok"
            akun.last_error = None
        else:
            akun.last_status = "error"
            akun.last_error = f"{ringkas.pesan}. {ringkas.saran}"

        self._perbarui_status_akun()

    def _pada_postingan_masuk(self, posts: list[Post], ringkas: HasilAkun) -> None:
        """Simpan ke DB; notifikasi hanya untuk yang benar-benar baru."""
        baru = self.db.simpan_banyak(posts)
        self.db.perbarui_statistik(posts)

        if baru and self.notifier.aktif:
            nama_akun = {a.id: a.nama_tampil() for a in self.akun}
            # Hormati preferensi: hanya akun yang sedang tampil.
            dipilih = self.kriteria.akun_dipilih()
            if self.config.get("notifikasi_hanya_akun_terpilih") and dipilih:
                baru_notif = [p for p in baru if p.account_id in dipilih]
            else:
                baru_notif = baru
            if baru_notif:
                self.notifier.beritahu_banyak(baru_notif, nama_akun)

        if baru:
            self._jadwalkan_muat_ulang()

    def _jadwalkan_muat_ulang(self) -> None:
        """Tunda pembacaan ulang feed sebentar.

        Satu siklus polling memancarkan `postingan_masuk` sekali per akun.
        Tanpa penundaan, feed dibaca ulang 30 kali dalam satu siklus —
        pemborosan yang membuat UI tersendat. Timer ini menggabungkan
        semuanya menjadi satu pembacaan.
        """
        self._timer_feed.start()

    def _pada_siklus_selesai(self, hasil: list[HasilAkun]) -> None:
        self.aksi_refresh.setEnabled(True)
        self.label_progres.setText("")

        if not hasil:
            self.label_status.setText("Tidak ada akun aktif.")
        else:
            gagal = [h for h in hasil if not h.berhasil]
            total = sum(h.jumlah for h in hasil)
            if gagal:
                self.label_status.setText(
                    f"Selesai: {total} postingan · {len(gagal)} akun gagal"
                )
            else:
                self.label_status.setText(f"Selesai: {total} postingan dari {len(hasil)} akun")

        self.config["terakhir_refresh"] = waktu_sekarang()
        cfg.simpan(self.config)
        # Pastikan perubahan terakhir tetap ditampilkan walau debounce
        # belum sempat menyala.
        self._jadwalkan_muat_ulang()
        self._perbarui_total()

    def _pada_catatan(self, pesan: str) -> None:
        self.label_status.setText(pesan)

    def _pada_profil(self, account_id: str, profil: dict) -> None:
        akun = cfg.cari_akun(self.akun, account_id)
        if akun is None:
            return
        akun.user_id = profil.get("user_id") or akun.user_id
        akun.display_name = profil.get("display_name") or akun.display_name
        akun.avatar_url = profil.get("avatar_url") or akun.avatar_url
        cfg.simpan_akun(self.config, self.akun)

    # ==================================================================
    # Refresh & filter
    # ==================================================================
    def mulai_refresh(self) -> None:
        """Picu satu siklus pengambilan data."""
        if self.worker is None:
            return
        if not self.akun:
            self.label_status.setText("Belum ada akun. Klik 'Akun' untuk menambahkan.")
            return
        self.worker.atur_akun(self.akun)
        self.worker.atur_auth_utama(cfg.ambil_auth_utama(self.config))
        self.worker.minta_refresh()

    def muat_ulang_feed(self) -> None:
        """Baca ulang dari DB dengan filter aktif, lalu tampilkan."""
        posts = self.db.ambil(
            batas=BATAS_TAMPIL,
            akun_ids=self.kriteria.akun_dipilih() or None,
            keyword=self.kriteria.keyword.strip(),
            sembunyikan_retweet=self.kriteria.sembunyikan_retweet,
            sembunyikan_reply=self.kriteria.sembunyikan_reply,
            sejak=batas_waktu(self.kriteria.rentang_hari),
        )
        posts = saring(posts, self.kriteria)
        self.feed.ganti_posts(posts)
        self._perbarui_total()

    def _perbarui_total(self) -> None:
        jumlah_db = self.db.jumlah()
        tampil = len(self.feed.posts())
        akun_aktif = sum(1 for a in self.akun if a.enabled and a.siap_dipantau())

        bagian = [f"{akun_aktif} akun aktif", f"{tampil} dari {jumlah_db} postingan"]

        # Kalau kredensial utama belum diisi, akun tetap "aktif" tapi tidak
        # akan menghasilkan apa pun — beri tahu penyebabnya di sini daripada
        # membiarkan pengguna menebak.
        if not cfg.ambil_auth_utama(self.config).lengkap() and not any(
            a.punya_auth_sendiri() for a in self.akun
        ):
            bagian.append("auth belum diisi")

        terakhir = self.config.get("terakhir_refresh")
        if terakhir:
            bagian.append(f"terakhir {waktu_relatif(terakhir)} lalu")
        self.label_total.setText(" · ".join(bagian))

    # --- handler filter -------------------------------------------------
    def _pada_cari(self) -> None:
        self.kriteria.keyword = self.input_cari.text()
        self._simpan_filter()
        self.muat_ulang_feed()

    def _pada_opsi_berubah(self) -> None:
        self.kriteria.sembunyikan_retweet = self.cek_retweet.isChecked()
        self.kriteria.sembunyikan_reply = self.cek_reply.isChecked()
        self._simpan_filter()
        self.muat_ulang_feed()

    def _pada_rentang_berubah(self) -> None:
        hari = self.combo_rentang.currentData()
        self.kriteria.rentang_hari = int(hari or 0)
        self._simpan_filter()
        self.muat_ulang_feed()

    def _pada_akun_dicentang(self, item: QListWidgetItem) -> None:
        akun_id = item.data(Qt.ItemDataRole.UserRole)
        if not akun_id:
            return
        if item.checkState() == Qt.CheckState.Checked:
            self._akun_terpilih_manual.add(akun_id)
        else:
            self._akun_terpilih_manual.discard(akun_id)

        self._terapkan_pilihan_akun()
        self._simpan_filter()
        self.muat_ulang_feed()

    def _terapkan_pilihan_akun(self) -> None:
        """Sinkronkan centang akun -> KriteriaFilter.

        Semua tercentang (atau tidak ada akun sama sekali) berarti "tanpa
        batasan akun", sehingga akun baru otomatis ikut tampil tanpa perlu
        dicentang manual.
        """
        semua = {a.id for a in self.akun}
        if not semua or self._akun_terpilih_manual >= semua:
            self.kriteria.semua_akun = True
            self.kriteria.akun_ids = []
        else:
            self.kriteria.semua_akun = False
            self.kriteria.akun_ids = sorted(self._akun_terpilih_manual)

    def _pilih_semua_akun(self, dipilih: bool) -> None:
        self.daftar_akun.blockSignals(True)
        for i in range(self.daftar_akun.count()):
            item = self.daftar_akun.item(i)
            item.setCheckState(
                Qt.CheckState.Checked if dipilih else Qt.CheckState.Unchecked
            )
        self.daftar_akun.blockSignals(False)

        self._akun_terpilih_manual = {a.id for a in self.akun} if dipilih else set()
        self._terapkan_pilihan_akun()
        self._simpan_filter()
        self.muat_ulang_feed()

    def _simpan_filter(self) -> None:
        self.config["filter"] = self.kriteria.ke_dict()
        cfg.simpan(self.config)

    # ==================================================================
    # Panel akun
    # ==================================================================
    def _segarkan_daftar_akun(self) -> None:
        """Bangun ulang daftar akun di panel filter, pertahankan centang.

        Dipanggil saat jumlah akun berubah (tambah/hapus). Untuk pembaruan
        status rutin dipakai `_perbarui_status_akun()` yang jauh lebih murah.
        """
        self.daftar_akun.blockSignals(True)
        self.daftar_akun.clear()

        jumlah = self.db.jumlah_per_akun()

        for akun in self.akun:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, akun.id)
            item.setCheckState(
                Qt.CheckState.Checked
                if akun.id in self._akun_terpilih_manual
                else Qt.CheckState.Unchecked
            )
            self._isi_item_akun(item, akun, jumlah.get(akun.id, 0))
            self.daftar_akun.addItem(item)

        self.daftar_akun.blockSignals(False)

    def _perbarui_status_akun(self) -> None:
        """Perbarui teks + tooltip item akun tanpa membangun ulang daftar.

        Memanggil `_segarkan_daftar_akun()` setiap akun selesai akan membuat
        widget list di-reset terus-menerus (fokus & posisi scroll hilang).
        Fungsi ini hanya menyentuh teks item yang sudah ada.
        """
        jumlah = self.db.jumlah_per_akun()
        peta = {a.id: a for a in self.akun}

        self.daftar_akun.blockSignals(True)
        for i in range(self.daftar_akun.count()):
            item = self.daftar_akun.item(i)
            akun_id = item.data(Qt.ItemDataRole.UserRole)
            akun = peta.get(akun_id)
            if akun is not None:
                self._isi_item_akun(item, akun, jumlah.get(akun_id, 0))
        self.daftar_akun.blockSignals(False)

    def _isi_item_akun(self, item: QListWidgetItem, akun: Account, jumlah_post: int) -> None:
        """Isi teks, warna status, dan tooltip satu item akun."""
        if not akun.enabled:
            tanda, warna = "⏸", "#8b98a5"
        elif akun.last_status == "error":
            tanda, warna = "⚠", "#f4212e"
        elif akun.last_status == "ok":
            tanda, warna = "●", "#00ba7c"
        else:
            tanda, warna = "○", "#8b98a5"

        item.setText(f"{tanda} {akun.nama_tampil()}  ({jumlah_post})")
        item.setForeground(QColor(warna))

        tips = [f"@{akun.username}"]
        if akun.last_fetch:
            tips.append(f"Terakhir diambil: {waktu_relatif(akun.last_fetch)} lalu")
        if akun.last_error:
            tips.append(f"Error: {akun.last_error}")
        if not akun.enabled:
            tips.append("Dinonaktifkan")
        item.setToolTip("\n".join(tips))

    # ==================================================================
    # Aksi
    # ==================================================================
    def _pada_buka(self, post: Post) -> None:
        if not buka_di_browser(post.url):
            self.label_status.setText("Gagal membuka browser.")

    def _pada_detail(self, post: Post) -> None:
        self.panel_detail.tampilkan(post)
        if self.panel_detail.isHidden():
            self.panel_detail.show()

    def _tutup_detail(self) -> None:
        self.panel_detail.hide()

    def _pada_notifikasi_diklik(self, post: Post) -> None:
        """Klik notifikasi -> tampilkan detail postingan itu."""
        self.raise_()
        self.activateWindow()
        self._pada_detail(post)

    # ==================================================================
    # Dialog
    # ==================================================================
    def buka_dialog_akun(self) -> None:
        dialog = DialogAkun(self.akun, cfg.ambil_auth_utama(self.config), self)
        if not dialog.exec():
            return

        # Catat kredensial khusus lama SEBELUM ditimpa, untuk deteksi perubahan.
        auth_lama = {a.id: (a.auth_token, a.ct0) for a in self.akun}

        id_lama = {a.id for a in self.akun}
        self.akun = dialog.ambil_akun()
        cfg.simpan_akun(self.config, self.akun)

        # Akun yang kredensialnya berubah -> cookie di pool twscrape harus
        # ditulis ulang. Tanpa ini, twscrape terus memakai cookie lama dan
        # akun tersebut gagal terus walau kredensial barunya sudah benar.
        auth_berubah: set[str] = set()
        for akun in self.akun:
            lama = auth_lama.get(akun.id)
            if lama is None or lama != (akun.auth_token, akun.ct0):
                auth_berubah.add(akun.id)

        if self.worker is not None:
            self.worker.atur_akun(self.akun, paksa_cookie=auth_berubah)

        id_aktif = {a.id for a in self.akun}

        # Akun yang dihapus -> lepas dari pilihan.
        self._akun_terpilih_manual &= id_aktif

        # Akun baru: ikut tercentang bila sedang dalam mode "semua akun".
        if self.kriteria.semua_akun:
            self._akun_terpilih_manual = set(id_aktif)
        else:
            self._akun_terpilih_manual |= (id_aktif - id_lama)

        self._terapkan_pilihan_akun()
        self._segarkan_daftar_akun()
        self._simpan_filter()
        self.muat_ulang_feed()
        self.mulai_refresh()

    def buka_dialog_pengaturan(self) -> None:
        # Catat kredensial utama lama: kalau berubah, semua akun yang
        # memakainya harus menulis ulang cookie di pool twscrape.
        kred_lama = cfg.ambil_auth_utama(self.config)

        dialog = DialogPengaturan(self.config, self.db, self)
        if not dialog.exec():
            return

        dialog.terapkan(self.config)
        cfg.simpan(self.config)

        if self.worker is not None:
            self.worker.atur_opsi(
                int(self.config.get("post_per_akun", 20)),
                float(self.config.get("jeda_antar_akun", 3)),
            )
            # atur_auth_utama() menandai sendiri akun-akun yang perlu
            # penulisan ulang cookie (semua yang tidak punya kredensial sendiri).
            self.worker.atur_auth_utama(cfg.ambil_auth_utama(self.config))

        # Kredensial utama berganti -> sesi tersimpan di pool bersama sudah
        # tidak berlaku. Bersihkan supaya twscrape tidak memakai cookie basi.
        kred_baru = cfg.ambil_auth_utama(self.config)
        if kred_lama.sidik() != kred_baru.sidik():
            self._bersihkan_pool_bersama()

        self.notifier.aktif = bool(self.config.get("notifikasi_aktif", True))
        self._atur_timer()
        self.terapkan_tema(self.config.get("tema", "dark"))
        self.muat_ulang_feed()
        self._perbarui_total()

    def _bersihkan_pool_bersama(self) -> None:
        """Hapus sesi pool bersama setelah kredensial utama berubah."""
        import asyncio

        from ..twitter_client import hapus_pool_bersama

        try:
            asyncio.run(hapus_pool_bersama())
        except Exception:  # noqa: BLE001 - gagal hapus file bukan alasan membatalkan
            pass

    # ==================================================================
    # Tema
    # ==================================================================
    def terapkan_tema(self, nama: str) -> None:
        """Terapkan tema ke seluruh aplikasi + komponen yang menggambar sendiri."""
        from PyQt6.QtWidgets import QApplication

        palet = ambil_palet(nama)

        aplikasi = QApplication.instance()
        if aplikasi is not None:
            aplikasi.setStyleSheet(qss(nama))

        # Delegate menggambar kartu sendiri, jadi tidak ikut QSS — paletnya
        # harus diberikan langsung.
        self.feed.set_palet(palet)
        self.panel_detail.setStyleSheet("")

        self.tombol_tema.setText("🌙" if nama == "dark" else "☀")
        self.tombol_tema.setToolTip(
            "Ganti ke tema terang" if nama == "dark" else "Ganti ke tema gelap"
        )
        self.config["tema"] = nama

    def toggle_tema(self) -> None:
        baru = "light" if self.config.get("tema", "dark") == "dark" else "dark"
        self.terapkan_tema(baru)
        cfg.simpan(self.config)

    # ==================================================================
    # Timer & riwayat
    # ==================================================================
    def _atur_timer(self) -> None:
        menit = int(self.config.get("interval_menit", 5))
        if menit <= 0:
            self.timer_poll.stop()
            self.label_auto.setText("Auto: mati")
            self.label_auto.setToolTip("Polling otomatis dimatikan di Pengaturan")
        else:
            self.timer_poll.start(menit * 60 * 1000)
            self.label_auto.setText(f"Auto: {menit} mnt")
            self.label_auto.setToolTip(f"Memeriksa postingan baru setiap {menit} menit")

    def _bersihkan_riwayat_awal(self) -> None:
        """Jalankan retensi otomatis saat aplikasi dibuka."""
        if not self.config.get("bersihkan_otomatis", True):
            return
        hari = int(self.config.get("retensi_hari", 30))
        if hari <= 0:
            return
        dihapus = self.db.bersihkan(hari)
        if dihapus:
            self.db.vakum()

    # ==================================================================
    # Siklus hidup
    # ==================================================================
    def closeEvent(self, event) -> None:  # noqa: N802 - API Qt
        """Tutup = keluar total (sesuai pilihan pengguna)."""
        self.timer_poll.stop()

        if self.worker is not None:
            self.label_status.setText("Menghentikan…")
            self.worker.hentikan()

        self.pemuat_thumbnail.hentikan()
        self.notifier.sembunyikan()

        # simpan preferensi terakhir
        self.config["lebar_panel_filter"] = self.splitter.sizes()[0] if self.splitter.sizes() else 260
        self._simpan_filter()
        cfg.simpan(self.config)

        self.db.tutup()
        super().closeEvent(event)
