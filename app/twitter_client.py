"""Adapter twscrape — satu-satunya file yang tahu cara bicara dengan X.

MENGAPA FILE INI TERISOLASI
===========================
Library pihak ketiga untuk membaca X (twikit, twscrape, dsb.) rawan rusak
saat X mengubah frontend-nya. Dengan menaruh SEMUA ketergantungan pada
twscrape di file ini saja, mengganti mesin di belakangnya cukup mengubah
satu file — sisa aplikasi tidak perlu tahu.

CATATAN PRIVASI
===============
twscrape punya modul telemetry yang mengirim event ke PostHog
(app.posthog.com), termasuk hash machine-id perangkat. Kita mematikannya
di baris paling atas file ini, SEBELUM twscrape diimpor, lewat env var
TWS_TELEMETRY=0. Tidak ada data yang dikirim keluar selain request ke X.
"""

from __future__ import annotations

import os

# --- WAJIB di paling atas, sebelum twscrape diimpor ------------------------

# 1. Perbaiki sys.stdout/sys.stderr yang None.
#
#    run.bat memakai pythonw.exe (tanpa console), dan pythonw membuat
#    sys.stderr bernilai None. twscrape memanggil logger.add(sys.stderr) saat
#    diimpor, sehingga tanpa perbaikan ini impor GAGAL TOTAL dengan
#    "TypeError: Cannot log to objects of type 'NoneType'".
#    Lihat app/compat.py untuk penjelasan lengkapnya.
from .compat import pastikan_std_stream

pastikan_std_stream()

# 2. Mematikan telemetry twscrape (PostHog) + standar industri DO_NOT_TRACK.
os.environ.setdefault("TWS_TELEMETRY", "0")
os.environ.setdefault("DO_NOT_TRACK", "1")

# 3. Pakai backend curl_cffi (bukan httpx).
#
#    curl_cffi meniru TLS fingerprint browser sungguhan, sedangkan httpx
#    memakai fingerprint Python yang mudah dikenali. X memakai pemeriksaan
#    fingerprint untuk mendeteksi otomatis — memakai curl_cffi menurunkan
#    risiko 403 / "looks automated" secara signifikan.
#
#    Diterapkan lewat setdefault supaya pengguna yang punya alasan khusus
#    tetap bisa menimpanya dari luar (mis. TWS_HTTP_BACKEND=httpx).
os.environ.setdefault("TWS_HTTP_BACKEND", "curl")

import logging  # noqa: E402
from typing import Any  # noqa: E402

from .models import (  # noqa: E402
    Account,
    Kredensial,
    Link,
    Media,
    Post,
    cari_url_di_teks,
    waktu_sekarang,
)
from .paths import pastikan_folder, pool_untuk  # noqa: E402

# twscrape baru boleh diimpor setelah env var di atas diset.
from twscrape import API, AccountsPool, gather  # noqa: E402

# Matikan log twscrape yang terlalu berisik di console.
logging.getLogger("twscrape").setLevel(logging.WARNING)


#: Nama pool bersama untuk semua akun yang memakai kredensial utama.
#: Diawali garis bawah supaya tidak bentrok dengan id akun (hex).
ID_POOL_UTAMA: str = "_utama"

#: Id tetap untuk pool sementara saat menguji kredensial.
#: Dipaku supaya file pool-nya selalu sama dan bisa dibersihkan setelah uji —
#: kalau diacak, tiap klik "Uji" akan meninggalkan file sampah.
ID_POOL_UJI: str = "_uji"


# ---------------------------------------------------------------------------
# Klasifikasi error -> pesan Indonesia yang bisa ditindaklanjuti
# ---------------------------------------------------------------------------

#: Urutan penting: pola paling spesifik lebih dulu.
_POLA_ERROR: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (
        ("features cannot be null", "gqlfeaturesoutdated", "update required"),
        "twscrape perlu diperbarui (X menambah field baru)",
        "Jalankan update.bat, lalu coba lagi.",
    ),
    (
        ("query not found", "404", "not found"),
        "Query ID X sudah berubah",
        "Jalankan update.bat untuk menarik versi twscrape terbaru.",
    ),
    (
        ("rate limit", "ratelimit", "429", "too many requests"),
        "Kena rate-limit dari X",
        "Tunggu ±15 menit. Perpanjang interval polling di Pengaturan.",
    ),
    (
        ("could not authenticate", "unauthorized", "401", "bad authentication",
         "invalid token", "auth_invalid", "missing authentication cookies"),
        "Kredensial tidak valid atau kedaluwarsa",
        "Buka Pengaturan → Auth Utama, ambil ulang auth_token & ct0 dari browser.",
    ),
    (
        ("403", "forbidden", "suspend", "locked", "looks automated"),
        "Ditolak X (403) — akun dibatasi",
        "Coba akun lain, atau login ulang akun ini di browser.",
    ),
    (
        ("account not found", "user not found", "no user"),
        "Akun tidak ditemukan",
        "Periksa ejaan username-nya.",
    ),
    (
        ("protected", "not authorized to view"),
        "Akun ini private dan tidak bisa dibaca",
        "Akun yang dipakai untuk auth harus mem-follow akun private tersebut.",
    ),
    (
        ("timeout", "timed out", "connect", "network", "getaddrinfo",
         "ssl", "connection"),
        "Gangguan koneksi internet",
        "Periksa koneksi, lalu klik Refresh.",
    ),
)


def jelaskan_error(galat: BaseException | str) -> tuple[str, str]:
    """Ubah error mentah jadi (pesan singkat, saran tindakan).

    Selalu mengembalikan sesuatu — error tak dikenal pun tetap terbaca
    manusia, tidak menampilkan stack trace mentah ke pengguna.
    """
    teks = str(galat).strip() or galat.__class__.__name__
    rendah = teks.lower()

    for pola, pesan, saran in _POLA_ERROR:
        if any(p in rendah for p in pola):
            return pesan, saran

    # Tidak dikenal: potong supaya tidak memenuhi UI.
    ringkas = teks if len(teks) <= 200 else teks[:197] + "..."
    return ringkas, "Klik Refresh untuk mencoba lagi."


# ---------------------------------------------------------------------------
# Normalisasi Tweet -> Post
# ---------------------------------------------------------------------------

def _url_terbaik(video: Any) -> str:
    """Pilih varian video dengan bitrate tertinggi (kualitas terbaik)."""
    varian = getattr(video, "variants", None) or []
    terbaik, bitrate_terbaik = "", -1
    for v in varian:
        if not isinstance(getattr(v, "contentType", ""), str):
            continue
        if "mp4" not in (v.contentType or ""):
            continue
        bitrate = getattr(v, "bitrate", 0) or 0
        if bitrate > bitrate_terbaik:
            terbaik, bitrate_terbaik = getattr(v, "url", "") or "", bitrate
    if not terbaik and varian:
        terbaik = getattr(varian[-1], "url", "") or ""
    return terbaik


def _kumpulkan_media(tweet: Any) -> list[Media]:
    """Ambil foto/video/gif dari sebuah Tweet twscrape."""
    hasil: list[Media] = []
    media = getattr(tweet, "media", None)
    if media is None:
        return hasil

    for foto in getattr(media, "photos", None) or []:
        url = getattr(foto, "url", "") or ""
        if url:
            hasil.append(Media(url=url, tipe="photo"))

    for video in getattr(media, "videos", None) or []:
        thumb = getattr(video, "thumbnailUrl", "") or ""
        url_video = _url_terbaik(video)
        if thumb or url_video:
            hasil.append(Media(url=thumb or url_video, tipe="video",
                               video_url=url_video))

    for gif in getattr(media, "animated", None) or []:
        thumb = getattr(gif, "thumbnailUrl", "") or ""
        url_video = _url_terbaik(gif)
        if thumb or url_video:
            hasil.append(Media(url=thumb or url_video, tipe="animated",
                               video_url=url_video))

    return hasil


def _kumpulkan_links(tweet: Any, konten: str) -> list[Link]:
    """Ambil tautan dari sebuah Tweet twscrape.

    X menulis tautan di isi postingan dalam bentuk pendek (`t.co/xxxx`),
    sedangkan alamat sebenarnya ada di `tweet.links`. Keduanya disimpan
    supaya popup konfirmasi bisa menampilkan domain TUJUAN yang sebenarnya,
    bukan `t.co` yang menyembunyikan ke mana tautan itu membawa.

    Sebagian tautan (mis. ke media X sendiri) kadang tidak punya entri di
    `links` — untuk itu URL yang tertulis di teks tetap diambil apa adanya.
    """
    hasil: list[Link] = []
    sudah: set[str] = set()

    # 1) tautan yang sudah diperluas oleh twscrape
    for item in getattr(tweet, "links", None) or []:
        url = getattr(item, "url", "") or ""
        if not url:
            continue
        kunci = url.lower()
        if kunci in sudah:
            continue
        sudah.add(kunci)
        hasil.append(Link(
            url=str(url),
            teks=str(getattr(item, "text", "") or ""),
        ))

    # 2) tautan yang tertulis di isi postingan tapi belum tercakup di atas
    for url_teks in cari_url_di_teks(konten):
        # t.co selalu punya padanan di `links`; kalau tidak ada, berarti
        # memang tautan mentah yang ditulis pengguna — pakai apa adanya.
        if url_teks.lower() in sudah:
            continue
        sudah.add(url_teks.lower())
        hasil.append(Link(url=url_teks, teks=url_teks))

    return hasil


def _angka(nilai: Any) -> int:
    """Konversi aman ke int (twscrape kadang memberi None)."""
    try:
        return int(nilai or 0)
    except (TypeError, ValueError):
        return 0


def tweet_ke_post(tweet: Any, akun: Account) -> Post | None:
    """Normalisasi satu Tweet twscrape menjadi Post milik aplikasi.

    Mengembalikan None bila tweet tidak punya id (data rusak).
    """
    tweet_id = getattr(tweet, "id", None)
    if not tweet_id:
        return None

    # --- retweet: pakai isi tweet aslinya, tapi tetap tandai sebagai RT ---
    asli = getattr(tweet, "retweetedTweet", None)
    sumber = asli if asli is not None else tweet

    penulis = getattr(sumber, "user", None) or getattr(tweet, "user", None)
    username = getattr(penulis, "username", "") or akun.username
    nama = getattr(penulis, "displayname", "") or ""

    konten = (getattr(sumber, "rawContent", "")
              or getattr(sumber, "content", "")
              or "")

    tanggal = getattr(sumber, "date", None) or getattr(tweet, "date", None)
    try:
        created = tanggal.isoformat(timespec="seconds") if tanggal else waktu_sekarang()
    except (AttributeError, TypeError, ValueError):
        created = waktu_sekarang()

    url = getattr(sumber, "url", "") or f"https://x.com/{username}/status/{tweet_id}"

    masuk_balasan = getattr(tweet, "inReplyToTweetId", None)
    balasan_ke = getattr(sumber, "inReplyToTweetId", None)

    return Post(
        tweet_id=str(tweet_id),
        account_id=akun.id,
        username=str(username),
        display_name=str(nama),
        content=str(konten),
        created_at=created,
        url=str(url),
        like_count=_angka(getattr(sumber, "likeCount", 0)),
        retweet_count=_angka(getattr(sumber, "retweetCount", 0)),
        reply_count=_angka(getattr(sumber, "replyCount", 0)),
        view_count=(_angka(getattr(sumber, "viewCount", None))
                    if getattr(sumber, "viewCount", None) is not None else None),
        media=_kumpulkan_media(sumber),
        links=_kumpulkan_links(sumber, str(konten)),
        is_retweet=asli is not None,
        is_reply=bool(masuk_balasan or balasan_ke),
        lang=str(getattr(sumber, "lang", "") or ""),
    )


# ---------------------------------------------------------------------------
# Klien per akun
# ---------------------------------------------------------------------------

class KlienAkun:
    """Pembungkus twscrape untuk memantau SATU akun X.

    STRATEGI POOL
    =============
    twscrape memilih akun dari pool secara otomatis dan melacak rate-limit
    per akun per endpoint DI DALAM database pool-nya. Dari situ:

      * Akun yang memakai kredensial utama  -> ikut SATU pool bersama
        (`data/pools/_utama.db`). Karena 30 akun target sebenarnya memakai
        SATU akun X yang sama, limitnya harus dilacak bersama. Kalau tiap
        target diberi pool sendiri, aplikasi akan mengira punya 30 kuota
        padahal kenyataannya satu — dan menabrak limit X.

      * Akun yang punya kredensial sendiri   -> pool sendiri
        (`data/pools/<id>.db`). Kredensial berbeda berarti akun X berbeda,
        jadi limitnya memang terpisah.
    """

    def __init__(self, akun: Account, auth_utama: Kredensial | None = None) -> None:
        self.akun = akun
        self.auth_utama = auth_utama or Kredensial()
        self._api: API | None = None
        self._cookie_terpasang: str = ""

    # ------------------------------------------------------------------
    # Kredensial
    # ------------------------------------------------------------------
    def kredensial(self) -> Kredensial:
        """Kredensial yang benar-benar dipakai untuk akun ini.

        Kredensial khusus akun menang bila ada; kalau tidak, pakai yang utama.
        """
        if self.akun.punya_auth_sendiri():
            return self.akun.kredensial_sendiri()
        return self.auth_utama

    def id_pool(self) -> str:
        """Id pool yang dipakai: '_utama' untuk kredensial bersama."""
        if self.akun.punya_auth_sendiri():
            return self.akun.id
        return ID_POOL_UTAMA

    def _nama_pool_twscrape(self) -> str:
        """Nama akun di dalam pool twscrape.

        Nilainya hanya dipakai twscrape untuk memilih User-Agent secara
        deterministik (lihat `Account.make_client` di twscrape) — BUKAN
        untuk autentikasi. Jadi untuk pool bersama cukup satu nama tetap.
        """
        return self.akun.username if self.akun.punya_auth_sendiri() else "utama"

    # ------------------------------------------------------------------
    async def _siapkan(self) -> API:
        """Bangun API + daftarkan cookie ke pool yang tepat (idempoten)."""
        if self._api is not None:
            return self._api

        kredensial = self.kredensial()
        if not kredensial.lengkap():
            raise ValueError(
                "Kredensial belum diisi. Buka Pengaturan → Auth Utama, "
                "lalu tempel auth_token dan ct0 dari browser."
            )

        pastikan_folder()
        db_pool = pool_untuk(self.id_pool())

        pool = AccountsPool(
            db_file=str(db_pool),
            # Jangan menunggu lama saat akun terkunci/rate-limit — lebih baik
            # gagal cepat lalu UI melaporkan statusnya ke pengguna.
            raise_when_no_account=False,
            wait_timeout=8.0,
            wait_interval=1.0,
        )
        self._api = API(
            pool=pool,
            raise_when_no_account=False,
            wait_timeout=8.0,
            wait_interval=1.0,
        )
        await self._pasang_cookie()
        return self._api

    async def _pasang_cookie(self, paksa: bool = False) -> None:
        """Daftarkan/perbarui cookie di pool. Hanya menulis bila berubah.

        PENTING: twscrape menyimpan cookie DI DALAM database pool-nya. Kalau
        pengguna memperbarui kredensial, pool masih memegang cookie lama
        sampai baris ini ditulis ulang. Karena itu `segarkan_cookie()` wajib
        dipanggil setiap kali kredensial berubah — kalau tidak, akun akan
        terus gagal walau kredensial barunya benar.
        """
        assert self._api is not None
        cookie = self.kredensial().cookie_string()
        if not paksa and cookie == self._cookie_terpasang:
            return
        # add_account_cookies = INSERT ... ON CONFLICT DO UPDATE, jadi aman
        # dipanggil berulang; sekaligus menandai akun aktif dan menghapus
        # pesan error lama.
        await self._api.pool.add_account_cookies(self._nama_pool_twscrape(), cookie)
        self._cookie_terpasang = cookie

    async def segarkan_cookie(self) -> None:
        """Paksa tulis ulang cookie (dipakai setelah kredensial berubah).

        Juga membuang cache `user_id`: kalau kredensial diganti, data profil
        yang tersimpan bisa saja berasal dari konteks yang berbeda.
        """
        self.akun.user_id = None
        self.akun.display_name = None
        self.akun.avatar_url = None
        await self._siapkan()
        await self._pasang_cookie(paksa=True)

    async def tutup(self) -> None:
        """Lepaskan sumber daya. Pool twscrape berbasis file, tidak perlu
        penutupan eksplisit — cukup lupakan referensinya."""
        self._api = None

    # ------------------------------------------------------------------
    async def ambil_profil(self, paksa: bool = False) -> dict[str, Any]:
        """Ambil profil akun (id, nama, avatar). Hasilnya di-cache.

        Memakai cache `user_id` dari config supaya siklus polling rutin
        tidak membuang 1 request per akun hanya untuk menerjemahkan
        username -> id.
        """
        if self.akun.user_id and not paksa:
            return {
                "user_id": self.akun.user_id,
                "display_name": self.akun.display_name or "",
                "avatar_url": self.akun.avatar_url or "",
            }

        api = await self._siapkan()
        pengguna = await api.user_by_login(self.akun.username)
        if pengguna is None:
            raise ValueError(f"Akun @{self.akun.username} tidak ditemukan")

        return {
            "user_id": str(getattr(pengguna, "id", "")),
            "display_name": str(getattr(pengguna, "displayname", "") or ""),
            "avatar_url": str(getattr(pengguna, "profileImageUrl", "") or ""),
        }

    async def ambil_postingan(self, batas: int = 20) -> list[Post]:
        """Ambil postingan terbaru akun ini.

        Memakai endpoint UserTweets (postingan asli + retweet, TANPA reply).
        """
        api = await self._siapkan()

        profil = await self.ambil_profil()
        user_id = profil["user_id"]
        if not user_id:
            raise ValueError(f"ID akun @{self.akun.username} tidak diketahui")

        mentah = await gather(api.user_tweets(int(user_id), limit=int(batas)))

        hasil: list[Post] = []
        for tweet in mentah:
            post = tweet_ke_post(tweet, self.akun)
            if post is not None:
                hasil.append(post)
        return hasil

    # ------------------------------------------------------------------
    async def status(self) -> dict[str, Any]:
        """Status akun menurut twscrape — untuk panel status di UI."""
        api = await self._siapkan()
        try:
            info = await api.pool.accounts_info()
        except Exception as e:  # noqa: BLE001 - status tidak boleh menjatuhkan UI
            return {"logged_in": False, "active": False, "total_req": 0,
                    "error_msg": str(e), "last_used": None}

        # Nama akun di dalam pool bisa berbeda dari username target (pool
        # bersama memakai satu nama tetap), jadi cocokkan lewat keduanya.
        nama_pool = self._nama_pool_twscrape().lower()
        for item in info:
            nama_item = str(item.get("username", "")).lower()
            if nama_item in (nama_pool, self.akun.username.lower()):
                return dict(item)
        return {"logged_in": False, "active": False, "total_req": 0,
                "error_msg": None, "last_used": None}


# ---------------------------------------------------------------------------
# Utilitas sinkron (dipanggil dari dalam event loop worker)
# ---------------------------------------------------------------------------

async def uji_kredensial(akun: Account, kredensial: Kredensial) -> tuple[bool, str]:
    """Uji apakah sebuah kredensial bisa dipakai untuk membaca timeline.

    `akun` menentukan username yang dicek; `kredensial` menentukan kunci
    yang dipakai. Dipakai dua tempat:
      * tombol "Uji Auth" di Pengaturan (kredensial utama)
      * tombol "Uji Koneksi" di dialog Akun (kredensial khusus akun)

    Mengembalikan (berhasil, pesan siap tampil).
    """
    if not kredensial.lengkap():
        return False, "auth_token dan ct0 belum diisi."

    # Akun sementara untuk pengujian.
    #
    # PENTING: id-nya DIPAKU (bukan diacak seperti Account biasa), karena
    # id itulah yang menentukan nama file pool. Kalau diacak, tiap klik
    # "Uji" akan membuat file pool baru di data/pools/ yang tidak pernah
    # terpakai lagi — sampah yang menumpuk seiring pemakaian.
    target = Account(
        id=ID_POOL_UJI,
        username=akun.username,
        auth_token=kredensial.auth_token,
        ct0=kredensial.ct0,
    )
    klien = KlienAkun(target)
    try:
        profil = await klien.ambil_profil(paksa=True)
        nama = profil.get("display_name") or akun.username
        return True, f"Berhasil — @{akun.username} terbaca ({nama})"
    except Exception as e:  # noqa: BLE001 - apa pun errornya, laporkan ke UI
        pesan, saran = jelaskan_error(e)
        return False, f"{pesan}. {saran}"
    finally:
        await klien.tutup()
        # Pool uji selalu dibersihkan supaya tidak menumpuk di data/pools/.
        await _hapus_pool_id(ID_POOL_UJI)


async def _hapus_pool_id(account_id: str) -> None:
    """Hapus file pool untuk sebuah id (dipakai untuk membersihkan pool uji)."""
    import contextlib

    jalur = pool_untuk(account_id)
    for akhiran in ("", "-wal", "-shm"):
        with contextlib.suppress(OSError):
            (jalur.parent / (jalur.name + akhiran)).unlink(missing_ok=True)


async def hapus_pool(akun: Account) -> None:
    """Hapus database pool KHUSUS milik akun (saat akun dihapus dari app).

    Pool bersama (`_utama`) TIDAK dihapus: isinya dipakai akun-akun lain,
    dan menghapusnya akan membuang pelacakan rate-limit yang masih berlaku.
    """
    if not akun.punya_auth_sendiri():
        return
    await _hapus_pool_id(akun.id)


async def hapus_pool_bersama() -> None:
    """Hapus sesi pool BERSAMA (dipakai saat kredensial utama diganti).

    HANYA pool `_utama` yang dihapus. Pool milik akun dengan kredensial
    sendiri tidak boleh disentuh: kredensialnya tidak berubah, dan
    menghapusnya akan membuang pelacakan rate-limit yang masih berlaku.
    """
    await _hapus_pool_id(ID_POOL_UTAMA)
