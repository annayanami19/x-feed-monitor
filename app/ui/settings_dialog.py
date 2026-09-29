"""Dialog pengaturan: kredensial, polling, riwayat, tampilan, notifikasi."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import INTERVAL_PILIHAN, RETENSI_PILIHAN, ambil_auth_utama
from ..db import RiwayatDB
from ..models import Account, Kredensial
from ..twitter_client import uji_kredensial

#: Label ramah untuk pilihan interval (menit).
LABEL_INTERVAL: dict[int, str] = {
    0: "Mati (hanya manual)",
    1: "Setiap 1 menit",
    2: "Setiap 2 menit",
    5: "Setiap 5 menit (disarankan)",
    10: "Setiap 10 menit",
    15: "Setiap 15 menit",
    30: "Setiap 30 menit",
    60: "Setiap 1 jam",
}

#: Label ramah untuk pilihan retensi (hari).
LABEL_RETENSI: dict[int, str] = {
    0: "Simpan selamanya",
    7: "7 hari",
    14: "14 hari",
    30: "30 hari (disarankan)",
    90: "90 hari",
    180: "180 hari",
    365: "1 tahun",
}

PANDUAN_AUTH_HTML = """
<p style="margin:0 0 6px 0;">
Ambil <b>auth_token</b> dan <b>ct0</b> dari browser:
</p>
<ol style="margin:0; padding-left:18px;">
  <li>Buka <b>x.com</b> dan pastikan sudah login.</li>
  <li>Tekan <b>F12</b> → tab <b>Application</b> (Chrome/Edge)
      atau <b>Storage</b> (Firefox).</li>
  <li>Pilih <b>Cookies</b> → <b>https://x.com</b>.</li>
  <li>Salin nilai <b>auth_token</b> (±40 karakter)
      dan <b>ct0</b> (±160 karakter).</li>
</ol>
<p style="margin:6px 0 0 0; color:#e08a00;">
Kredensial ini milik akunmu sendiri — bukan akun yang dipantau.
Satu kredensial cukup untuk semua akun yang ingin dipantau.
</p>
"""


class _PekerjaUjiAuth(QThread):
    """Menguji kredensial di thread terpisah (jaringan bisa lambat)."""

    hasil = pyqtSignal(bool, str)

    def __init__(self, kredensial: Kredensial, parent=None) -> None:
        super().__init__(parent)
        self.kredensial = kredensial

    def run(self) -> None:  # noqa: D102
        import asyncio

        # Uji dengan akun contoh: endpoint UserByScreenName bisa dipanggil
        # untuk username apa pun, jadi cukup satu nama yang pasti ada.
        contoh = Account(username="x")
        try:
            berhasil, pesan = asyncio.run(uji_kredensial(contoh, self.kredensial))
        except Exception as e:  # noqa: BLE001 - apa pun errornya, laporkan
            berhasil, pesan = False, f"Gagal menguji: {e}"
        self.hasil.emit(berhasil, pesan)


class DialogPengaturan(QDialog):
    """Dialog pengaturan aplikasi."""

    def __init__(self, config: dict, db: RiwayatDB, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pengaturan")
        self.resize(600, 720)

        self.config = config
        self.db = db
        self._pekerja_uji: _PekerjaUjiAuth | None = None

        self._bangun()

    # ==================================================================
    def _bangun(self) -> None:
        luar = QVBoxLayout(self)
        luar.setContentsMargins(0, 0, 0, 0)
        luar.setSpacing(0)

        # Isi dibuat bisa di-scroll: dengan tambahan grup kredensial,
        # dialog bisa lebih tinggi dari layar laptop.
        gulir = QScrollArea()
        gulir.setWidgetResizable(True)
        isi = QWidget()
        tata = QVBoxLayout(isi)
        tata.setContentsMargins(16, 16, 16, 16)
        tata.setSpacing(14)

        tata.addWidget(self._grup_auth_utama())
        tata.addWidget(self._grup_polling())
        tata.addWidget(self._grup_riwayat())
        tata.addWidget(self._grup_tampilan())
        tata.addWidget(self._grup_notifikasi())
        tata.addStretch(1)

        gulir.setWidget(isi)
        luar.addWidget(gulir, 1)

        # ---------------- tombol ----------------
        baris = QHBoxLayout()
        baris.setContentsMargins(16, 10, 16, 14)
        tombol = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        tombol.button(QDialogButtonBox.StandardButton.Ok).setText("Simpan")
        tombol.button(QDialogButtonBox.StandardButton.Cancel).setText("Batal")
        tombol.accepted.connect(self._pada_ok)
        tombol.rejected.connect(self.reject)
        baris.addWidget(tombol)
        luar.addLayout(baris)

        self._perbarui_info_db()

    # ==================================================================
    # Kredensial
    # ==================================================================
    def _grup_auth_utama(self) -> QGroupBox:
        grup = QGroupBox("Auth Utama (wajib)")
        tata = QVBoxLayout(grup)
        tata.setSpacing(9)

        keterangan = QLabel(
            "Dipakai untuk semua akun yang dipantau. Cukup diisi sekali — "
            "akun yang butuh kredensial berbeda bisa diatur di dialog Akun."
        )
        keterangan.setWordWrap(True)
        keterangan.setStyleSheet("color: #8b98a5;")
        tata.addWidget(keterangan)

        kred = ambil_auth_utama(self.config)

        form = QFormLayout()
        form.setSpacing(9)

        self.input_auth = QLineEdit()
        self.input_auth.setPlaceholderText("nilai cookie auth_token")
        self.input_auth.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_auth.setText(kred.auth_token)
        form.addRow("auth_token", self._baris_rahasia(self.input_auth))

        self.input_ct0 = QLineEdit()
        self.input_ct0.setPlaceholderText("nilai cookie ct0")
        self.input_ct0.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_ct0.setText(kred.ct0)
        form.addRow("ct0", self._baris_rahasia(self.input_ct0))

        tata.addLayout(form)

        # --- baris uji ---
        baris_uji = QHBoxLayout()
        self.tombol_uji = QPushButton("Uji Auth")
        self.tombol_uji.setToolTip("Cek apakah kredensial ini bisa dipakai (perlu internet)")
        self.tombol_uji.clicked.connect(self._uji_auth)
        baris_uji.addWidget(self.tombol_uji)

        self.label_uji = QLabel("")
        self.label_uji.setWordWrap(True)
        baris_uji.addWidget(self.label_uji, 1)
        tata.addLayout(baris_uji)

        # --- panduan ---
        panduan = QLabel(PANDUAN_AUTH_HTML)
        panduan.setWordWrap(True)
        panduan.setTextFormat(panduan.textFormat().RichText)
        tata.addWidget(panduan)

        # --- peringatan keamanan ---
        peringatan = QLabel(
            "⚠ <b>auth_token setara password akun X-mu.</b> Nilainya disimpan "
            "tanpa enkripsi di <code>data/config.json</code> — jangan bagikan "
            "file itu ke siapa pun."
        )
        peringatan.setWordWrap(True)
        peringatan.setStyleSheet(
            "color: #f4212e; background: rgba(244,33,46,0.08);"
            "border: 1px solid rgba(244,33,46,0.35);"
            "border-radius: 6px; padding: 8px;"
        )
        tata.addWidget(peringatan)

        return grup

    def _baris_rahasia(self, edit: QLineEdit) -> QWidget:
        """Bungkus QLineEdit dengan tombol lihat/sembunyikan."""
        wadah = QWidget()
        tata = QHBoxLayout(wadah)
        tata.setContentsMargins(0, 0, 0, 0)
        tata.setSpacing(4)
        tata.addWidget(edit, 1)

        tombol = QPushButton("👁")
        tombol.setObjectName("ikon")
        tombol.setCheckable(True)
        tombol.setToolTip("Tampilkan / sembunyikan nilai")

        def alih(ditekan: bool) -> None:
            edit.setEchoMode(
                QLineEdit.EchoMode.Normal if ditekan else QLineEdit.EchoMode.Password
            )

        tombol.toggled.connect(alih)
        tata.addWidget(tombol)
        return wadah

    def _uji_auth(self) -> None:
        kred = self._kredensial_form()
        if not kred.lengkap():
            self.label_uji.setText("Isi auth_token dan ct0 terlebih dahulu.")
            self.label_uji.setStyleSheet("color: #e08a00;")
            return

        self.tombol_uji.setEnabled(False)
        self.label_uji.setText("Menguji…")
        self.label_uji.setStyleSheet("color: #8b98a5;")

        self._pekerja_uji = _PekerjaUjiAuth(kred, self)
        self._pekerja_uji.hasil.connect(self._pada_hasil_uji)
        self._pekerja_uji.finished.connect(self._pekerja_uji.deleteLater)
        self._pekerja_uji.start()

    def _pada_hasil_uji(self, berhasil: bool, pesan: str) -> None:
        self.tombol_uji.setEnabled(True)
        self.label_uji.setText(pesan)
        self.label_uji.setStyleSheet(
            "color: #00ba7c;" if berhasil else "color: #f4212e;"
        )

    def _kredensial_form(self) -> Kredensial:
        return Kredensial(
            auth_token=self.input_auth.text().strip(),
            ct0=self.input_ct0.text().strip(),
        )

    # ==================================================================
    # Polling
    # ==================================================================
    def _grup_polling(self) -> QGroupBox:
        grup = QGroupBox("Pengambilan data")
        form = QFormLayout(grup)
        form.setSpacing(9)

        self.combo_interval = QComboBox()
        for menit in INTERVAL_PILIHAN:
            self.combo_interval.addItem(LABEL_INTERVAL.get(menit, f"{menit} menit"), menit)
        indeks = self.combo_interval.findData(int(self.config.get("interval_menit", 5)))
        self.combo_interval.setCurrentIndex(max(0, indeks))
        self.combo_interval.setToolTip(
            "Makin sering polling, makin besar risiko akun dibatasi X."
        )
        form.addRow("Interval otomatis", self.combo_interval)

        self.spin_post = QSpinBox()
        self.spin_post.setRange(5, 100)
        self.spin_post.setSingleStep(5)
        self.spin_post.setValue(int(self.config.get("post_per_akun", 20)))
        self.spin_post.setToolTip(
            "Jumlah postingan terbaru yang ditarik dari tiap akun setiap siklus."
        )
        form.addRow("Postingan per akun", self.spin_post)

        self.spin_jeda = QSpinBox()
        self.spin_jeda.setRange(0, 30)
        self.spin_jeda.setSuffix(" detik")
        self.spin_jeda.setValue(int(self.config.get("jeda_antar_akun", 3)))
        self.spin_jeda.setToolTip(
            "Jeda antar akun saat mengambil data. Jangan dikurangi kecuali "
            "jumlah akun sedikit — request beruntun mudah terdeteksi sebagai bot."
        )
        form.addRow("Jeda antar akun", self.spin_jeda)

        return grup

    # ==================================================================
    # Riwayat
    # ==================================================================
    def _grup_riwayat(self) -> QGroupBox:
        grup = QGroupBox("Riwayat")
        form = QFormLayout(grup)
        form.setSpacing(9)

        self.combo_retensi = QComboBox()
        for hari in RETENSI_PILIHAN:
            self.combo_retensi.addItem(LABEL_RETENSI.get(hari, f"{hari} hari"), hari)
        indeks = self.combo_retensi.findData(int(self.config.get("retensi_hari", 30)))
        self.combo_retensi.setCurrentIndex(max(0, indeks))
        self.combo_retensi.setToolTip(
            "Postingan yang lebih tua dari batas ini dihapus otomatis dari database."
        )
        form.addRow("Simpan riwayat", self.combo_retensi)

        self.cek_bersih_otomatis = QCheckBox("Bersihkan otomatis saat aplikasi dibuka")
        self.cek_bersih_otomatis.setChecked(bool(self.config.get("bersihkan_otomatis", True)))
        form.addRow("", self.cek_bersih_otomatis)

        # info ukuran + tombol bersihkan
        baris_db = QHBoxLayout()
        self.label_db = QLabel()
        self.label_db.setStyleSheet("color: #8b98a5;")
        baris_db.addWidget(self.label_db, 1)

        self.tombol_bersihkan = QPushButton("Bersihkan sekarang")
        self.tombol_bersihkan.setObjectName("bahaya")
        self.tombol_bersihkan.setToolTip("Terapkan masa simpan di atas saat ini juga")
        self.tombol_bersihkan.clicked.connect(self._bersihkan_sekarang)
        baris_db.addWidget(self.tombol_bersihkan)

        self.tombol_kosongkan = QPushButton("Hapus semua")
        self.tombol_kosongkan.setObjectName("bahaya")
        self.tombol_kosongkan.setToolTip("Hapus SELURUH riwayat postingan")
        self.tombol_kosongkan.clicked.connect(self._kosongkan)
        baris_db.addWidget(self.tombol_kosongkan)

        form.addRow("", self._bungkus(baris_db))

        return grup

    # ==================================================================
    # Tampilan
    # ==================================================================
    def _grup_tampilan(self) -> QGroupBox:
        grup = QGroupBox("Tampilan")
        form = QFormLayout(grup)
        form.setSpacing(9)

        self.combo_tema = QComboBox()
        self.combo_tema.addItem("Gelap (dark)", "dark")
        self.combo_tema.addItem("Terang (light)", "light")
        indeks = self.combo_tema.findData(self.config.get("tema", "dark"))
        self.combo_tema.setCurrentIndex(max(0, indeks))
        form.addRow("Tema", self.combo_tema)

        return grup

    # ==================================================================
    # Notifikasi
    # ==================================================================
    def _grup_notifikasi(self) -> QGroupBox:
        grup = QGroupBox("Notifikasi")
        tata = QVBoxLayout(grup)
        tata.setSpacing(6)

        self.cek_notif = QCheckBox("Tampilkan notifikasi untuk postingan baru")
        self.cek_notif.setChecked(bool(self.config.get("notifikasi_aktif", True)))
        tata.addWidget(self.cek_notif)

        self.cek_notif_terpilih = QCheckBox("Hanya untuk akun yang sedang ditampilkan")
        self.cek_notif_terpilih.setChecked(
            bool(self.config.get("notifikasi_hanya_akun_terpilih", False))
        )
        self.cek_notif_terpilih.setToolTip(
            "Kalau dicentang, notifikasi hanya muncul untuk akun yang "
            "centangnya aktif di panel filter."
        )
        tata.addWidget(self.cek_notif_terpilih)

        catatan = QLabel(
            "Notifikasi memakai system tray Windows. Kalau tidak muncul, "
            "periksa Pengaturan → Sistem → Notifikasi."
        )
        catatan.setWordWrap(True)
        catatan.setStyleSheet("color: #8b98a5; font-size: 11px;")
        tata.addWidget(catatan)

        return grup

    # ==================================================================
    @staticmethod
    def _bungkus(tata: QHBoxLayout) -> QWidget:
        wadah = QWidget()
        wadah.setLayout(tata)
        return wadah

    # ==================================================================
    def _perbarui_info_db(self) -> None:
        jumlah = self.db.jumlah()
        ukuran = self.db.ukuran_mb()
        self.label_db.setText(f"{jumlah} postingan tersimpan · {ukuran} MB")

    def _bersihkan_sekarang(self) -> None:
        hari = int(self.combo_retensi.currentData() or 0)
        if hari <= 0:
            QMessageBox.information(
                self,
                "Tidak ada yang dihapus",
                "Masa simpan disetel ke 'Simpan selamanya', jadi tidak ada "
                "postingan yang dihapus.",
            )
            return

        jawab = QMessageBox.question(
            self,
            "Bersihkan riwayat",
            f"Hapus postingan yang lebih tua dari {hari} hari?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if jawab != QMessageBox.StandardButton.Yes:
            return

        dihapus = self.db.bersihkan(hari)
        self.db.vakum()
        self._perbarui_info_db()
        QMessageBox.information(
            self, "Selesai", f"{dihapus} postingan lama dihapus."
        )

    def _kosongkan(self) -> None:
        jawab = QMessageBox.warning(
            self,
            "Hapus semua riwayat",
            "Hapus SELURUH riwayat postingan?\n\n"
            "Tindakan ini tidak bisa dibatalkan. Postingan akan muncul lagi "
            "saat polling berikutnya, tapi riwayat lama tidak bisa dipulihkan.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if jawab != QMessageBox.StandardButton.Yes:
            return

        dihapus = self.db.hapus_semua()
        self.db.vakum()
        self._perbarui_info_db()
        QMessageBox.information(self, "Selesai", f"{dihapus} postingan dihapus.")

    # ==================================================================
    def _pada_ok(self) -> None:
        """Validasi ringan sebelum dialog ditutup."""
        kred = self._kredensial_form()
        if kred.auth_token and not kred.ct0:
            QMessageBox.warning(
                self, "Belum lengkap",
                "auth_token sudah diisi, tapi ct0 masih kosong.\n\n"
                "Keduanya harus diisi. Lihat panduan di grup Auth Utama.",
            )
            return
        if kred.ct0 and not kred.auth_token:
            QMessageBox.warning(
                self, "Belum lengkap",
                "ct0 sudah diisi, tapi auth_token masih kosong.\n\n"
                "Keduanya harus diisi. Lihat panduan di grup Auth Utama.",
            )
            return
        self.accept()

    def terapkan(self, config: dict) -> None:
        """Tulis pilihan dialog ke dict config (dipanggil setelah OK)."""
        config["auth_utama"] = self._kredensial_form().ke_dict()

        config["interval_menit"] = int(self.combo_interval.currentData() or 0)
        config["post_per_akun"] = int(self.spin_post.value())
        config["jeda_antar_akun"] = int(self.spin_jeda.value())

        config["retensi_hari"] = int(self.combo_retensi.currentData() or 0)
        config["bersihkan_otomatis"] = self.cek_bersih_otomatis.isChecked()

        config["tema"] = self.combo_tema.currentData()

        config["notifikasi_aktif"] = self.cek_notif.isChecked()
        config["notifikasi_hanya_akun_terpilih"] = self.cek_notif_terpilih.isChecked()

    # ==================================================================
    def closeEvent(self, event) -> None:  # noqa: N802 - API Qt
        """Pastikan thread uji tidak menggantung saat dialog ditutup."""
        if self._pekerja_uji is not None and self._pekerja_uji.isRunning():
            self._pekerja_uji.wait(3000)
        super().closeEvent(event)
