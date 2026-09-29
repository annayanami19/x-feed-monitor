"""Dialog kelola akun: tambah (bisa banyak sekaligus) / ubah / hapus.

Dialog ini hanya mengurus **daftar akun yang dipantau**. Kredensial untuk
mengambil datanya diatur sekali di Pengaturan (lihat settings_dialog.py).

Setiap akun boleh punya kredensial sendiri sebagai pengecualian — misalnya
akun private yang hanya di-follow oleh akun X kedua. Secara bawaan, akun
memakai kredensial utama.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .. import config as cfg
from ..models import Account, Kredensial
from ..twitter_client import hapus_pool, uji_kredensial

#: Panduan pengambilan kredensial — ditampilkan di dalam dialog.
PANDUAN_HTML = """
<h3>Cara mengambil auth value</h3>
<ol>
  <li>Buka <b>x.com</b> di browser dan pastikan sudah <b>login</b>.</li>
  <li>Tekan <b>F12</b> untuk membuka DevTools.</li>
  <li>Buka tab <b>Application</b> (Chrome/Edge) atau <b>Storage</b> (Firefox).</li>
  <li>Pilih <b>Cookies</b> → <b>https://x.com</b>.</li>
  <li>Salin nilai dua cookie berikut:
    <ul>
      <li><b>auth_token</b> — nilainya panjang (±40 karakter)</li>
      <li><b>ct0</b> — nilainya ±160 karakter</li>
    </ul>
  </li>
  <li>Tempel keduanya di <b>Pengaturan → Auth Utama</b>.</li>
</ol>
<p>
Kredensial itu milik <b>akunmu sendiri</b>, bukan akun yang dipantau.
Satu kredensial cukup untuk memantau berapa pun akun, termasuk akun
private selama akunmu mem-follow-nya.
</p>
<p style="color:#e08a00;">
Hanya isi <b>auth khusus</b> di sini kalau akun tertentu butuh kredensial
BERBEDA dari yang utama.
</p>
"""


class _PekerjaUji(QThread):
    """Menguji kredensial satu akun di thread terpisah (jaringan bisa lambat)."""

    hasil = pyqtSignal(bool, str)

    def __init__(self, akun: Account, kredensial: Kredensial, parent=None) -> None:
        super().__init__(parent)
        self.akun = akun
        self.kredensial = kredensial

    def run(self) -> None:  # noqa: D102
        import asyncio

        try:
            berhasil, pesan = asyncio.run(uji_kredensial(self.akun, self.kredensial))
        except Exception as e:  # noqa: BLE001 - apa pun errornya, laporkan
            berhasil, pesan = False, f"Gagal menguji: {e}"
        self.hasil.emit(berhasil, pesan)


class DialogAkun(QDialog):
    """Kelola daftar akun yang dipantau."""

    def __init__(
        self,
        akun: list[Account],
        auth_utama: Kredensial | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Kelola Akun")
        self.resize(1020, 700)

        self.auth_utama = auth_utama or Kredensial()

        #: Salinan kerja — perubahan baru berlaku saat dialog ditutup dengan OK.
        self._akun: list[Account] = [
            Account.dari_dict(a.ke_dict()) for a in akun
        ]
        self._pekerja_uji: _PekerjaUji | None = None

        self._bangun()

    # ==================================================================
    def _bangun(self) -> None:
        tata = QVBoxLayout(self)
        tata.setContentsMargins(14, 14, 14, 14)
        tata.setSpacing(10)

        # --- peringatan kalau kredensial utama belum diisi ---
        if not self.auth_utama.lengkap():
            self.label_auth_utama = QLabel(
                "⚠ <b>Auth utama belum diisi.</b> Buka "
                "<b>Pengaturan → Auth Utama</b> dulu, supaya akun yang "
                "ditambahkan di sini bisa dipantau."
            )
            self.label_auth_utama.setWordWrap(True)
            self.label_auth_utama.setStyleSheet(
                "color: #e08a00; background: rgba(224,138,0,0.10);"
                "border: 1px solid rgba(224,138,0,0.4);"
                "border-radius: 6px; padding: 9px;"
            )
            tata.addWidget(self.label_auth_utama)

        isi = QHBoxLayout()
        isi.setSpacing(14)

        isi.addLayout(self._kolom_tabel(), 3)
        isi.addLayout(self._kolom_kanan(), 2)

        tata.addLayout(isi, 1)

        # ---------------- tombol dialog ----------------
        tombol = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        tombol.button(QDialogButtonBox.StandardButton.Ok).setText("Simpan & Tutup")
        tombol.button(QDialogButtonBox.StandardButton.Cancel).setText("Batal")
        tombol.accepted.connect(self.accept)
        tombol.rejected.connect(self.reject)
        tata.addWidget(tombol)

        self._segarkan_tabel()

    # ==================================================================
    # Kolom kiri: tabel akun
    # ==================================================================
    def _kolom_tabel(self) -> QVBoxLayout:
        kiri = QVBoxLayout()
        kiri.setSpacing(8)

        judul = QLabel("Akun yang dipantau")
        f = QFont()
        f.setBold(True)
        judul.setFont(f)
        kiri.addWidget(judul)

        self.tabel = QTableWidget(0, 4)
        self.tabel.setHorizontalHeaderLabels(["Username", "Nama", "Auth", "Status"])
        self.tabel.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabel.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabel.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabel.verticalHeader().setVisible(False)
        self.tabel.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.tabel.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.tabel.itemSelectionChanged.connect(self._pada_pilih_baris)
        self.tabel.doubleClicked.connect(lambda _: self._muat_ke_form())
        kiri.addWidget(self.tabel, 1)

        # tombol aksi baris
        baris_aksi = QHBoxLayout()

        self.tombol_hapus = QPushButton("Hapus")
        self.tombol_hapus.setObjectName("bahaya")
        self.tombol_hapus.setEnabled(False)
        self.tombol_hapus.clicked.connect(self._hapus_terpilih)
        baris_aksi.addWidget(self.tombol_hapus)

        self.tombol_ubah = QPushButton("Ubah")
        self.tombol_ubah.setEnabled(False)
        self.tombol_ubah.setToolTip("Ubah akun terpilih di panel kanan")
        self.tombol_ubah.clicked.connect(self._muat_ke_form)
        baris_aksi.addWidget(self.tombol_ubah)

        baris_aksi.addStretch(1)
        kiri.addLayout(baris_aksi)

        catatan = QLabel(
            "Akun yang dihapus tidak menghapus riwayat postingannya. "
            "Klik dua kali sebuah baris untuk mengubahnya."
        )
        catatan.setWordWrap(True)
        catatan.setStyleSheet("color: #8b98a5; font-size: 11px;")
        kiri.addWidget(catatan)

        return kiri

    # ==================================================================
    # Kolom kanan: tambah massal + ubah
    # ==================================================================
    def _kolom_kanan(self) -> QVBoxLayout:
        kanan = QVBoxLayout()
        kanan.setSpacing(10)

        kanan.addWidget(self._grup_tambah())
        kanan.addWidget(self._grup_ubah())

        # --- panduan ---
        panduan = QTextBrowser()
        panduan.setHtml(PANDUAN_HTML)
        panduan.setOpenExternalLinks(True)
        panduan.setMaximumHeight(190)
        kanan.addWidget(panduan)

        kanan.addStretch(1)
        return kanan

    # ------------------------------------------------------------------
    def _grup_tambah(self) -> QGroupBox:
        grup = QGroupBox("Tambah akun")
        tata = QVBoxLayout(grup)
        tata.setSpacing(8)

        keterangan = QLabel(
            "Tempel satu atau banyak username. Boleh dipisah baris baru, "
            "koma, atau spasi — dan boleh berupa URL profil."
        )
        keterangan.setWordWrap(True)
        keterangan.setStyleSheet("color: #8b98a5;")
        tata.addWidget(keterangan)

        self.input_massal = QLineEdit()
        self.input_massal.setPlaceholderText("elonmusk, @jack, https://x.com/billgates")
        self.input_massal.returnPressed.connect(self._tambah_massal)
        tata.addWidget(self.input_massal)

        baris = QHBoxLayout()
        self.tombol_tambah = QPushButton("Tambah")
        self.tombol_tambah.setObjectName("utama")
        self.tombol_tambah.clicked.connect(self._tambah_massal)
        baris.addWidget(self.tombol_tambah)

        self.label_hasil_tambah = QLabel("")
        self.label_hasil_tambah.setWordWrap(True)
        baris.addWidget(self.label_hasil_tambah, 1)
        tata.addLayout(baris)

        return grup

    # ------------------------------------------------------------------
    def _grup_ubah(self) -> QGroupBox:
        grup = QGroupBox("Ubah akun terpilih")
        tata = QVBoxLayout(grup)
        tata.setSpacing(8)

        self.label_ubah_info = QLabel("Pilih akun di tabel sebelah kiri.")
        self.label_ubah_info.setWordWrap(True)
        self.label_ubah_info.setStyleSheet("color: #8b98a5;")
        tata.addWidget(self.label_ubah_info)

        form = QFormLayout()
        form.setSpacing(8)

        self.input_username = QLineEdit()
        self.input_username.setPlaceholderText("mis. elonmusk")
        form.addRow("Username", self.input_username)

        self.input_label = QLineEdit()
        self.input_label.setPlaceholderText("opsional — nama untuk tampilan")
        form.addRow("Label", self.input_label)

        self.cek_aktif = QCheckBox("Aktif (ikut dipantau)")
        self.cek_aktif.setChecked(True)
        form.addRow("", self.cek_aktif)

        tata.addLayout(form)

        # --- auth khusus (opsional) ---
        self.cek_auth_khusus = QCheckBox("Pakai auth khusus untuk akun ini")
        self.cek_auth_khusus.setToolTip(
            "Hanya perlu diisi kalau akun ini butuh kredensial BERBEDA dari "
            "auth utama — misalnya akun private yang hanya di-follow oleh "
            "akun X kedua."
        )
        self.cek_auth_khusus.toggled.connect(self._pada_auth_khusus_toggled)
        tata.addWidget(self.cek_auth_khusus)

        self.panel_auth_khusus = QWidget()
        form_khusus = QFormLayout(self.panel_auth_khusus)
        form_khusus.setContentsMargins(16, 0, 0, 0)
        form_khusus.setSpacing(8)

        self.input_auth = QLineEdit()
        self.input_auth.setPlaceholderText("nilai cookie auth_token")
        self.input_auth.setEchoMode(QLineEdit.EchoMode.Password)
        form_khusus.addRow("auth_token", self._baris_rahasia(self.input_auth))

        self.input_ct0 = QLineEdit()
        self.input_ct0.setPlaceholderText("nilai cookie ct0")
        self.input_ct0.setEchoMode(QLineEdit.EchoMode.Password)
        form_khusus.addRow("ct0", self._baris_rahasia(self.input_ct0))

        self.panel_auth_khusus.setVisible(False)
        tata.addWidget(self.panel_auth_khusus)

        # --- tombol aksi ---
        baris = QHBoxLayout()

        self.tombol_simpan_akun = QPushButton("Simpan perubahan")
        self.tombol_simpan_akun.setObjectName("utama")
        self.tombol_simpan_akun.setEnabled(False)
        self.tombol_simpan_akun.clicked.connect(self._simpan_form)
        baris.addWidget(self.tombol_simpan_akun)

        self.tombol_uji = QPushButton("Uji Koneksi")
        self.tombol_uji.setToolTip(
            "Ambil profil akun ini untuk memastikan kredensialnya bekerja"
        )
        self.tombol_uji.setEnabled(False)
        self.tombol_uji.clicked.connect(self._uji)
        baris.addWidget(self.tombol_uji)

        baris.addStretch(1)
        tata.addLayout(baris)

        self.label_uji = QLabel("")
        self.label_uji.setWordWrap(True)
        tata.addWidget(self.label_uji)

        return grup

    # ------------------------------------------------------------------
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

    def _pada_auth_khusus_toggled(self, aktif: bool) -> None:
        self.panel_auth_khusus.setVisible(aktif)

    # ==================================================================
    # Tabel
    # ==================================================================
    def _segarkan_tabel(self, pilih_akun_id: str | None = None) -> None:
        self.tabel.setRowCount(0)

        for akun in self._akun:
            baris = self.tabel.rowCount()
            self.tabel.insertRow(baris)

            item_user = QTableWidgetItem(f"@{akun.username}")
            item_user.setData(Qt.ItemDataRole.UserRole, akun.id)
            self.tabel.setItem(baris, 0, item_user)

            self.tabel.setItem(baris, 1, QTableWidgetItem(akun.label or "—"))

            # --- kolom Auth ---
            if akun.punya_auth_sendiri():
                teks_auth, warna_auth = "Khusus", "#e08a00"
                tips_auth = "Memakai auth khusus, bukan auth utama"
            else:
                teks_auth, warna_auth = "Utama", "#1d9bf0"
                tips_auth = "Memakai auth utama dari Pengaturan"
            item_auth = QTableWidgetItem(teks_auth)
            item_auth.setForeground(QColor(warna_auth))
            item_auth.setToolTip(tips_auth)
            self.tabel.setItem(baris, 2, item_auth)

            # --- kolom Status ---
            if not akun.enabled:
                teks_status, warna = "Nonaktif", "#8b98a5"
            elif akun.last_status == "ok":
                teks_status, warna = "OK", "#00ba7c"
            elif akun.last_status == "error":
                teks_status, warna = "Error", "#f4212e"
            else:
                teks_status, warna = "Belum diambil", "#8b98a5"

            item_status = QTableWidgetItem(teks_status)
            item_status.setForeground(QColor(warna))
            if akun.last_error:
                item_status.setToolTip(akun.last_error)
            self.tabel.setItem(baris, 3, item_status)

        if pilih_akun_id:
            baris = self._baris_akun_id(pilih_akun_id)
            if baris >= 0:
                self.tabel.selectRow(baris)

        self._pada_pilih_baris()

    def _baris_akun_id(self, akun_id: str) -> int:
        """Nomor baris tabel untuk sebuah id akun (atau -1)."""
        for baris in range(self.tabel.rowCount()):
            item = self.tabel.item(baris, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == akun_id:
                return baris
        return -1

    def _akun_terpilih(self) -> Account | None:
        """Akun pada baris terpilih.

        Dicari lewat id di UserRole, bukan nomor baris: urutan tabel dan
        list `_akun` bisa berbeda (mis. setelah penghapusan), dan
        mencocokkan lewat indeks akan mengembalikan akun yang salah.
        """
        baris = self.tabel.currentRow()
        if baris < 0:
            return None
        item = self.tabel.item(baris, 0)
        if item is None:
            return None
        akun_id = item.data(Qt.ItemDataRole.UserRole)
        if not akun_id:
            return None
        return cfg.cari_akun(self._akun, akun_id)

    def _pada_pilih_baris(self) -> None:
        akun = self._akun_terpilih()
        ada = akun is not None
        self.tombol_hapus.setEnabled(ada)
        self.tombol_ubah.setEnabled(ada)
        self.tombol_simpan_akun.setEnabled(ada)
        self.tombol_uji.setEnabled(ada)

        if akun is None:
            self.label_ubah_info.setText("Pilih akun di tabel sebelah kiri.")
        else:
            asal = "auth khusus" if akun.punya_auth_sendiri() else "auth utama"
            self.label_ubah_info.setText(f"Mengubah <b>@{akun.username}</b> ({asal}).")

    # ==================================================================
    # Tambah massal
    # ==================================================================
    def _tambah_massal(self) -> None:
        teks = self.input_massal.text()
        daftar = cfg.pecah_username_massal(teks)

        if not daftar:
            self.label_hasil_tambah.setText("Belum ada username yang bisa dibaca.")
            self.label_hasil_tambah.setStyleSheet("color: #e08a00;")
            return

        ditambah: list[str] = []
        dilewati: list[str] = []

        for nama in daftar:
            if cfg.cari_akun_username(self._akun, nama) is not None:
                dilewati.append(nama)
                continue
            akun = Account(username=nama)
            self._akun.append(akun)
            ditambah.append(nama)

        self._segarkan_tabel()

        if ditambah and not dilewati:
            self.label_hasil_tambah.setText(f"{len(ditambah)} akun ditambahkan.")
            self.label_hasil_tambah.setStyleSheet("color: #00ba7c;")
        elif ditambah and dilewati:
            self.label_hasil_tambah.setText(
                f"{len(ditambah)} ditambahkan, {len(dilewati)} dilewati "
                f"(sudah ada): {', '.join('@' + d for d in dilewati[:4])}"
                + ("…" if len(dilewati) > 4 else "")
            )
            self.label_hasil_tambah.setStyleSheet("color: #e08a00;")
        else:
            self.label_hasil_tambah.setText(
                f"Semua sudah ada ({len(dilewati)} dilewati)."
            )
            self.label_hasil_tambah.setStyleSheet("color: #e08a00;")

        if ditambah:
            self.input_massal.clear()
            self.input_massal.setFocus()

    # ==================================================================
    # Ubah akun
    # ==================================================================
    def _muat_ke_form(self) -> None:
        akun = self._akun_terpilih()
        if akun is None:
            return

        self.input_username.setText(akun.username)
        self.input_label.setText(akun.label)
        self.cek_aktif.setChecked(akun.enabled)

        punya_khusus = akun.punya_auth_sendiri()
        self.cek_auth_khusus.setChecked(punya_khusus)
        self.input_auth.setText(akun.auth_token)
        self.input_ct0.setText(akun.ct0)
        self.panel_auth_khusus.setVisible(punya_khusus)

        self.label_uji.clear()
        self.input_username.setFocus()

    def _simpan_form(self) -> None:
        akun = self._akun_terpilih()
        if akun is None:
            return

        username = cfg.bersihkan_username(self.input_username.text())
        if not username:
            self._peringatan("Username wajib diisi.")
            return

        # --- cek duplikat (selain akun ini sendiri) ---
        lain = cfg.cari_akun_username(self._akun, username)
        if lain is not None and lain.id != akun.id:
            self._peringatan(
                f"@{username} sudah ada di daftar.\n\n"
                "Gunakan username yang berbeda, atau ubah akun yang sudah ada."
            )
            return

        # --- tentukan kredensial BARU lebih dulu (tanpa menyentuh akun) ---
        # Nilai lama harus dibaca SEBELUM ditimpa, kalau tidak perbandingan
        # "berubah atau tidak" di bawah selalu menghasilkan False dan pool
        # twscrape tidak pernah ditulis ulang.
        auth_lama = (akun.auth_token, akun.ct0)

        if self.cek_auth_khusus.isChecked():
            auth = self.input_auth.text().strip()
            ct0 = self.input_ct0.text().strip()
            if not auth or not ct0:
                self._peringatan(
                    "Auth khusus dicentang, tapi auth_token / ct0 masih kosong.\n\n"
                    "Isi keduanya, atau hilangkan centang untuk memakai auth utama."
                )
                return
            pesan_cek = self._periksa_bentuk_auth(auth)
            if pesan_cek:
                self._peringatan(pesan_cek)
                return
            auth_baru = (auth, ct0)
        else:
            # Beralih ke auth utama -> buang kredensial khusus.
            auth_baru = ("", "")

        username_berubah = akun.username != username
        auth_berubah = auth_lama != auth_baru

        # --- terapkan ---
        akun.username = username
        akun.label = self.input_label.text().strip()
        akun.enabled = self.cek_aktif.isChecked()
        akun.auth_token, akun.ct0 = auth_baru

        # Username berubah -> cache profil tidak berlaku lagi.
        if username_berubah:
            akun.user_id = None
            akun.display_name = None
            akun.avatar_url = None

        if username_berubah or auth_berubah:
            akun.last_status = "belum"
            akun.last_error = None

        self._segarkan_tabel(akun.id)
        self.label_uji.setText(
            f"@{akun.username} disimpan. Klik 'Uji Koneksi' untuk memastikan."
        )
        self.label_uji.setStyleSheet("color: #00ba7c;")

    @staticmethod
    def _periksa_bentuk_auth(auth: str) -> str | None:
        """Sanity check bentuk auth_token. Kembalikan pesan masalah, atau None."""
        if len(auth) < 20:
            return (
                f"Nilai auth_token terlihat terlalu pendek ({len(auth)} karakter).\n"
                "Nilai yang benar biasanya ±40 karakter."
            )
        if " " in auth or "=" in auth:
            return (
                "Nilai auth_token mengandung spasi atau tanda '='.\n"
                "Pastikan hanya menyalin NILAINYA saja, "
                "bukan 'auth_token=nilainya'."
            )
        return None

    def _hapus_terpilih(self) -> None:
        akun = self._akun_terpilih()
        if akun is None:
            return

        jawab = QMessageBox.question(
            self,
            "Hapus akun",
            f"Hapus @{akun.username} dari daftar?\n\n"
            "Postingan yang sudah tersimpan tetap ada di riwayat.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if jawab != QMessageBox.StandardButton.Yes:
            return

        # Hapus sesi tersimpan akun ini (kalau dia punya pool sendiri),
        # supaya tidak meninggalkan file yatim.
        if akun.punya_auth_sendiri():
            import asyncio

            try:
                asyncio.run(hapus_pool(akun))
            except Exception:  # noqa: BLE001 - gagal hapus file bukan alasan membatalkan
                pass

        self._akun.remove(akun)
        self._segarkan_tabel()

    # ==================================================================
    # Uji koneksi
    # ==================================================================
    def _uji(self) -> None:
        akun = self._akun_terpilih()
        if akun is None:
            self._peringatan("Pilih akun di tabel terlebih dahulu.")
            return

        # Uji nilai yang SEDANG di form (kalau akun ini sedang diubah),
        # supaya pengguna bisa memastikan sebelum menyimpan.
        if self.cek_auth_khusus.isChecked():
            kred = Kredensial(
                auth_token=self.input_auth.text().strip(),
                ct0=self.input_ct0.text().strip(),
            )
            if not kred.lengkap():
                self._peringatan(
                    "Auth khusus dicentang tapi belum lengkap.\n"
                    "Isi auth_token dan ct0 terlebih dahulu."
                )
                return
        else:
            kred = self.auth_utama
            if not kred.lengkap():
                self._peringatan(
                    "Auth utama belum diisi.\n\n"
                    "Buka Pengaturan → Auth Utama untuk mengisinya."
                )
                return

        username_form = cfg.bersihkan_username(self.input_username.text())
        target = Account(
            username=username_form or akun.username,
            auth_token=kred.auth_token,
            ct0=kred.ct0,
        )

        self.tombol_uji.setEnabled(False)
        self.label_uji.setText("Menguji koneksi… mohon tunggu.")
        self.label_uji.setStyleSheet("color: #8b98a5;")

        self._pekerja_uji = _PekerjaUji(target, kred, self)
        self._pekerja_uji.hasil.connect(self._pada_hasil_uji)
        self._pekerja_uji.finished.connect(self._pekerja_uji.deleteLater)
        self._pekerja_uji.start()

    def _pada_hasil_uji(self, berhasil: bool, pesan: str) -> None:
        self.tombol_uji.setEnabled(True)
        self.label_uji.setText(pesan)
        self.label_uji.setStyleSheet(
            "color: #00ba7c;" if berhasil else "color: #f4212e;"
        )

    # ==================================================================
    # Util
    # ==================================================================
    def _peringatan(self, pesan: str) -> None:
        QMessageBox.warning(self, "Belum bisa dilanjutkan", pesan)

    def ambil_akun(self) -> list[Account]:
        """Daftar akun final (dipanggil setelah dialog diterima)."""
        return self._akun

    def closeEvent(self, event) -> None:  # noqa: N802 - API Qt
        """Pastikan thread uji tidak menggantung saat dialog ditutup."""
        if self._pekerja_uji is not None and self._pekerja_uji.isRunning():
            self._pekerja_uji.wait(3000)
        super().closeEvent(event)
