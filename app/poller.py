"""Worker polling: menjalankan pengambilan data X di thread terpisah.

MENGAPA THREAD TERPISAH
=======================
twscrape sepenuhnya `async`, sementara Qt punya event loop sendiri. Kalau
keduanya dijalankan di thread yang sama, UI akan membeku. Karena itu:

  * QThread ini memiliki event loop asyncio-nya SENDIRI (`asyncio.new_event_loop`)
  * Semua komunikasi ke GUI lewat Qt Signal (otomatis queued antar-thread,
    jadi aman — tidak ada widget yang disentuh dari thread ini)

ANTRIAN BERTAHAP
================
Request dijalankan berurutan dengan jeda antar akun (default 3 detik).
Mengirim 30 request serentak ke X terlihat seperti bot dan mengundang 403.
Jeda ini juga membuat progres bisa ditampilkan satu per satu di UI.
"""

from __future__ import annotations

import asyncio
import contextlib
import random
from dataclasses import dataclass

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from .models import Account, Kredensial
from .twitter_client import KlienAkun, jelaskan_error


@dataclass
class HasilAkun:
    """Ringkasan hasil pengambilan data satu akun."""

    account_id: str
    username: str
    jumlah: int = 0
    baru: int = 0
    berhasil: bool = True
    pesan: str = ""
    saran: str = ""


class PollerWorker(QObject):
    """Menjalankan siklus pengambilan data. Hidup di dalam QThread."""

    # --- sinyal ke GUI (semuanya aman dipanggil dari thread worker) ---
    siklus_mulai = pyqtSignal(int)                  # jumlah akun yang akan diproses
    akun_mulai = pyqtSignal(str, str)               # (account_id, username)
    akun_selesai = pyqtSignal(object)               # HasilAkun
    postingan_masuk = pyqtSignal(object, object)    # (list[Post], HasilAkun)
    siklus_selesai = pyqtSignal(object)             # list[HasilAkun]
    catatan = pyqtSignal(str)                       # pesan log untuk statusbar
    profil_diperbarui = pyqtSignal(str, object)     # (account_id, dict profil)

    def __init__(self) -> None:
        super().__init__()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: QThread | None = None
        self._akun: list[Account] = []
        self._auth_utama: Kredensial = Kredensial()
        self._batas = 20
        self._jeda = 3.0
        self._berjalan = False
        self._berhenti = False
        self._minta_refresh = False
        # Dibuat di dalam thread worker (lihat _utama) — asyncio.Event terikat
        # pada event loop-nya, jadi tidak boleh dibuat di thread GUI.
        self._event: asyncio.Event | None = None
        #: id akun yang cookie-nya wajib ditulis ulang sebelum dipakai.
        self._paksa_cookie: set[str] = set()

    # ------------------------------------------------------------------
    # Siklus hidup
    # ------------------------------------------------------------------
    def mulai(self) -> None:
        """Jalankan worker di QThread baru dengan event loop asyncio sendiri."""
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._thread.started.connect(self._jalan)
        self._thread.start()

    def hentikan(self, tunggu_ms: int = 1200) -> bool:
        """Minta worker berhenti. TIDAK memblokir lama.

        Mengembalikan True bila thread sudah benar-benar selesai.

        MENGAPA TIDAK MENUNGGU LAMA
        ===========================
        Worker bisa sedang berada di tengah request jaringan ke X, dan
        request yang sedang berjalan **tidak bisa dibatalkan** — Python
        harus menunggu socket-nya selesai atau timeout. Dengan 3 akun,
        totalnya bisa belasan detik.

        Kalau GUI menunggu selama itu di `closeEvent`, Windows menganggap
        jendela "Not Responding" dan menampilkan dialog yang terlihat
        seperti aplikasi crash. Karena itu:

          * tunggu sebentar saja (default 1,2 detik) supaya kasus normal
            (worker sedang idle) selesai rapi
          * kalau belum selesai, JANGAN menunggu lebih lama — kembalikan
            False dan biarkan pemanggil memutuskan
          * `tunggu_ms` menentukan berapa lama menunggu sebelum menyerah
        """
        self._berhenti = True
        self._minta_refresh = False

        # Sama seperti paksa_hentikan(): objek Qt bisa sudah dibersihkan
        # kalau thread selesai sendiri lebih dulu.
        try:
            if self._loop is not None and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._bangunkan)

            if self._thread is None:
                return True

            self._thread.quit()
            return bool(self._thread.wait(tunggu_ms))
        except RuntimeError:
            # Objek thread sudah dihapus -> thread sudah tidak berjalan.
            # Itu artinya worker memang sudah berhenti: kembalikan True.
            return True

    def paksa_hentikan(self, tunggu_ms: int = 800) -> None:
        """Hentikan paksa thread worker (dipakai saat menutup aplikasi).

        Dipanggil HANYA setelah `hentikan()` gagal — artinya worker masih
        tertahan di request jaringan. `terminate()` memang tidak rapi, tapi
        pada tahap ini aplikasi sedang ditutup, dan menggantung lebih buruk
        daripada penghentian yang tidak rapi.

        Aman karena:
          * database memakai WAL — penulisan yang belum selesai akan
            di-rollback otomatis oleh SQLite
          * config disimpan SEBELUM fungsi ini dipanggil
          * tidak ada data pengguna yang hilang: yang tertahan hanyalah
            request jaringan yang hasilnya belum tentu ada
        """
        if self._thread is None:
            return

        # Setiap akses ke objek Qt dibungkus: thread bisa sudah selesai
        # sendiri di antara pemeriksaan, sehingga `self._thread` sudah
        # tidak menunjuk objek yang sah.
        try:
            if self._thread.isRunning():
                self._thread.terminate()
                self._thread.wait(tunggu_ms)
        except RuntimeError:
            # "wrapped C/C++ object has been deleted" — thread sudah selesai
            # dan objeknya dibersihkan. Justru itu yang kita inginkan.
            pass

    # ------------------------------------------------------------------
    # Dipanggil dari GUI thread — aman karena hanya menyentuh flag
    # ------------------------------------------------------------------
    def atur_akun(self, akun: list[Account], paksa_cookie: set[str] | None = None) -> None:
        """Perbarui daftar akun yang dipantau (dibaca di siklus berikutnya).

        `paksa_cookie` berisi id akun yang kredensialnya baru berubah.
        Untuk akun-akun itu, cookie di pool twscrape ditulis ulang lebih dulu —
        tanpa ini, twscrape akan terus memakai cookie lama yang sudah tidak valid.
        """
        self._akun = list(akun)
        if paksa_cookie:
            self._paksa_cookie |= set(paksa_cookie)

    def atur_auth_utama(self, kredensial: Kredensial) -> None:
        """Perbarui kredensial utama yang dipakai akun tanpa kredensial sendiri.

        Semua akun tanpa kredensial sendiri ikut ditandai untuk penulisan
        ulang cookie, karena kredensial yang mereka pakai baru saja berubah.
        """
        if kredensial.sidik() == self._auth_utama.sidik():
            return
        self._auth_utama = Kredensial(kredensial.auth_token, kredensial.ct0)
        for akun in self._akun:
            if not akun.punya_auth_sendiri():
                self._paksa_cookie.add(akun.id)

    def atur_opsi(self, batas: int, jeda: float) -> None:
        self._batas = max(1, int(batas))
        self._jeda = max(0.0, float(jeda))

    def minta_refresh(self) -> None:
        """Minta siklus segera dijalankan (tombol Refresh / timer)."""
        self._minta_refresh = True
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._bangunkan)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _bangunkan(self) -> None:
        """Bangunkan event yang sedang ditunggu (dipanggil di thread worker).

        Aman dipanggil sebelum `_utama` sempat membuat event-nya: kalau
        belum ada, tidak terjadi apa-apa — flag `_minta_refresh` tetap
        terpasang dan akan terbaca dalam ≤1 detik.
        """
        if self._event is not None:
            self._event.set()

    def _jalan(self) -> None:
        """Titik masuk di thread worker: buat loop, jalankan, tutup rapi."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._utama())
        except Exception as e:  # noqa: BLE001 - worker tidak boleh mati diam
            self.catatan.emit(f"Worker berhenti: {e}")
        finally:
            with contextlib.suppress(Exception):
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            self._loop.close()
            self._loop = None

    async def _utama(self) -> None:
        """Loop utama: tunggu permintaan refresh, lalu jalankan siklus."""
        self._event = asyncio.Event()
        while not self._berhenti:
            # Tunggu sinyal refresh (dari timer GUI atau tombol).
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._event.wait(), timeout=1.0)
            self._event.clear()

            if self._berhenti:
                break
            if not self._minta_refresh:
                continue

            self._minta_refresh = False
            await self._siklus()

    async def _siklus(self) -> None:
        """Satu putaran penuh: ambil postingan dari semua akun aktif."""
        if self._berjalan:
            return
        self._berjalan = True

        # Kredensial diperiksa lebih dulu: tanpa itu, setiap akun akan gagal
        # satu per satu dengan pesan yang sama, dan pengguna tidak tahu
        # bahwa masalahnya cuma satu (kredensial belum diisi).
        if not self._auth_utama.lengkap() and not any(
            a.punya_auth_sendiri() for a in self._akun
        ):
            self._berjalan = False
            self.catatan.emit(
                "Kredensial belum diisi. Buka Pengaturan → Auth Utama, "
                "lalu tempel auth_token & ct0 dari browser."
            )
            self.siklus_selesai.emit([])
            return

        akun_aktif = [a for a in self._akun if a.enabled and a.siap_dipantau()]
        if not akun_aktif:
            self._berjalan = False
            self.catatan.emit("Belum ada akun. Klik 'Akun' untuk menambahkan.")
            self.siklus_selesai.emit([])
            return

        self.siklus_mulai.emit(len(akun_aktif))
        hasil: list[HasilAkun] = []

        for i, akun in enumerate(akun_aktif):
            if self._berhenti:
                break

            self.akun_mulai.emit(akun.id, akun.username)
            ringkas = await self._proses_akun(akun)
            hasil.append(ringkas)
            self.akun_selesai.emit(ringkas)

            # Jeda antar akun (kecuali akun terakhir) — anti-burst.
            # Dijalankan sebagai tidur bertahap supaya permintaan berhenti
            # bisa langsung dipatuhi tanpa menunggu jeda selesai.
            if i < len(akun_aktif) - 1 and self._jeda > 0 and not self._berhenti:
                # sedikit acak supaya polanya tidak persis seragam
                await self._tidur_bisa_dibatalkan(self._jeda * random.uniform(0.8, 1.2))

        self._berjalan = False
        self.siklus_selesai.emit(hasil)

    async def _tidur_bisa_dibatalkan(self, detik: float) -> None:
        """Tidur yang langsung berhenti bila `_berhenti` diset.

        Dipotong menjadi potongan 0,25 detik supaya shutdown terasa responsif
        walau jeda antar akun sedang berjalan.
        """
        sisa = float(detik)
        while sisa > 0 and not self._berhenti:
            langkah = min(0.25, sisa)
            await asyncio.sleep(langkah)
            sisa -= langkah

    async def _proses_akun(self, akun: Account) -> HasilAkun:
        """Ambil postingan satu akun. Tidak pernah melempar — selalu kembalikan ringkasan."""
        # Bekerja di SALINAN akun, bukan objek aslinya: objek asli juga
        # dibaca GUI thread, jadi memutasi `user_id`/`last_error` dari sini
        # akan jadi data race. Hasilnya dikirim balik lewat sinyal
        # `profil_diperbarui`, dan GUI yang menuliskannya ke objek asli.
        akun_kerja = Account.dari_dict(akun.ke_dict())

        # Kredensial utama ikut dikirim: akun tanpa kredensial sendiri
        # memakainya, dan pool yang dipilih mengikuti itu.
        klien = KlienAkun(akun_kerja, self._auth_utama)
        ringkas = HasilAkun(account_id=akun.id, username=akun.username)

        try:
            # Kredensial baru diubah pengguna? Tulis ulang cookie di pool
            # dulu, kalau tidak twscrape masih memakai cookie lama.
            if akun.id in self._paksa_cookie:
                self._paksa_cookie.discard(akun.id)
                await klien.segarkan_cookie()

            posts = await klien.ambil_postingan(self._batas)
            ringkas.jumlah = len(posts)

            # Kabari GUI bila profil baru didapat (nama/avatar untuk panel).
            if akun_kerja.user_id:
                self.profil_diperbarui.emit(akun.id, {
                    "user_id": akun_kerja.user_id,
                    "display_name": akun_kerja.display_name or "",
                    "avatar_url": akun_kerja.avatar_url or "",
                })

            if posts:
                self.postingan_masuk.emit(posts, ringkas)

        except Exception as e:  # noqa: BLE001 - satu akun gagal tidak boleh stop semua
            ringkas.berhasil = False
            ringkas.pesan, ringkas.saran = jelaskan_error(e)

        finally:
            await klien.tutup()

        return ringkas
