"""Baca/tulis config.json — pengaturan aplikasi + daftar akun.

CATATAN KEAMANAN
================
File ini memuat `auth_token` dalam bentuk PLAINTEXT (pilihan sadar pemilik
aplikasi demi kesederhanaan). Karena itu:

  * `data/` WAJIB ada di .gitignore  -> sudah, lihat .gitignore
  * Jangan pernah mengirim isi file ini ke mana pun
  * Siapa pun yang bisa membaca file ini bisa mengakses akun X terkait

Semua penulisan memakai EOL tetap (\\n) supaya file tidak berubah-ubah
bentuknya antar-platform.
"""

from __future__ import annotations

import json
import shutil
from typing import Any

from .models import Account, Kredensial
from .paths import CONFIG_PATH, DATA_DIR, pastikan_folder

# ---------------------------------------------------------------------------
# Nilai default
# ---------------------------------------------------------------------------

#: Interval polling otomatis (menit). 0 = matikan auto-poll.
INTERVAL_PILIHAN: tuple[int, ...] = (0, 1, 2, 5, 10, 15, 30, 60)

#: Pilihan masa simpan riwayat (hari). 0 = simpan selamanya.
RETENSI_PILIHAN: tuple[int, ...] = (0, 7, 14, 30, 90, 180, 365)

#: Versi skema config. Dinaikkan ke 2 saat kredensial dipindahkan dari
#: masing-masing akun menjadi satu kredensial utama.
VERSI_CONFIG: int = 2

DEFAULT: dict[str, Any] = {
    # --- kredensial ---
    # Dipakai untuk SEMUA akun yang tidak punya kredensial sendiri.
    "auth_utama": {
        "auth_token": "",
        "ct0": "",
    },

    # --- polling ---
    "interval_menit": 5,            # auto-poll tiap 5 menit (0 = mati)
    "post_per_akun": 20,            # jumlah postingan terbaru yang ditarik/akun
    "jeda_antar_akun": 3,           # detik jeda antar akun (hindari burst)

    # --- riwayat ---
    "retensi_hari": 30,             # 0 = simpan selamanya
    "bersihkan_otomatis": True,     # jalankan pembersihan tiap app dibuka

    # --- tampilan ---
    "tema": "dark",                 # dark | light
    "bahasa": "id",
    "lebar_panel_filter": 260,

    # --- notifikasi ---
    "notifikasi_aktif": True,
    "notifikasi_hanya_akun_terpilih": False,

    # --- filter (disimpan supaya tidak perlu diatur ulang) ---
    "filter": {
        "semua_akun": True,
        "akun_ids": [],
        "keyword": "",
        "sembunyikan_retweet": True,
        "sembunyikan_reply": True,
        "rentang_hari": 0,          # 0 = semua waktu
    },

    # --- akun ---
    "akun": [],

    # --- meta ---
    "versi_config": VERSI_CONFIG,
}


# ---------------------------------------------------------------------------
# Baca / tulis
# ---------------------------------------------------------------------------

def _gabung_default(data: dict[str, Any]) -> dict[str, Any]:
    """Gabungkan config tersimpan di atas DEFAULT, hanya kunci yang dikenal.

    Kunci tak dikenal dari versi lama diabaikan; kunci baru dari versi ini
    otomatis terisi default. `filter` dan `auth_utama` digabung satu level
    lebih dalam supaya kunci yang belum ada tidak menghapus yang sudah ada.
    """
    hasil = dict(DEFAULT)
    for kunci, nilai in data.items():
        if kunci not in DEFAULT:
            continue
        if kunci in ("filter", "auth_utama") and isinstance(nilai, dict):
            sub_gabung = dict(DEFAULT[kunci])
            for sk, sv in nilai.items():
                if sk in sub_gabung:
                    sub_gabung[sk] = sv
            hasil[kunci] = sub_gabung
        else:
            hasil[kunci] = nilai
    return hasil


def muat() -> dict[str, Any]:
    """Baca config.json. Selalu mengembalikan dict yang lengkap.

    File hilang/rusak -> pakai default (tidak pernah crash, tidak pernah
    menimpa file rusak tanpa jejak: file rusak disalin ke .rusak).
    """
    if not CONFIG_PATH.exists():
        return dict(DEFAULT)

    try:
        mentah = CONFIG_PATH.read_text(encoding="utf-8")
        data = json.loads(mentah)
        if not isinstance(data, dict):
            raise ValueError("config.json bukan objek JSON")
    except (OSError, json.JSONDecodeError, ValueError):
        # Simpan salinan supaya pengguna bisa memeriksa isinya.
        try:
            shutil.copy2(CONFIG_PATH, CONFIG_PATH.with_suffix(".json.rusak"))
        except OSError:
            pass
        return dict(DEFAULT)

    return _gabung_default(data)


def simpan(config: dict[str, Any]) -> None:
    """Tulis config.json secara atomik (tulis .tmp lalu ganti).

    Atomik = kalau aplikasi mati di tengah penulisan, config.json lama
    tetap utuh dan tidak jadi file separuh.
    """
    pastikan_folder()
    sementara = CONFIG_PATH.with_suffix(".json.tmp")
    try:
        # newline="\n" -> EOL stabil, tidak diterjemahkan jadi CRLF di Windows
        with sementara.open("w", encoding="utf-8", newline="\n") as berkas:
            json.dump(config, berkas, ensure_ascii=False, indent=2)
            berkas.write("\n")
        sementara.replace(CONFIG_PATH)
    except OSError:
        # Gagal menyimpan tidak boleh menjatuhkan aplikasi.
        try:
            sementara.unlink(missing_ok=True)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Helper kredensial
# ---------------------------------------------------------------------------

def ambil_auth_utama(config: dict[str, Any]) -> Kredensial:
    """Kredensial utama — dipakai semua akun yang tidak punya kredensial sendiri."""
    return Kredensial.dari_dict(config.get("auth_utama"))


def simpan_auth_utama(config: dict[str, Any], kredensial: Kredensial) -> None:
    """Tulis kredensial utama ke config (lalu simpan ke disk)."""
    config["auth_utama"] = kredensial.ke_dict()
    simpan(config)


# ---------------------------------------------------------------------------
# Helper akun
# ---------------------------------------------------------------------------

def ambil_akun(config: dict[str, Any]) -> list[Account]:
    """Daftar akun dari config sebagai objek Account."""
    hasil: list[Account] = []
    for item in config.get("akun", []):
        if isinstance(item, dict):
            akun = Account.dari_dict(item)
            if akun.username:
                hasil.append(akun)
    return hasil


def simpan_akun(config: dict[str, Any], akun: list[Account]) -> None:
    """Tulis daftar akun kembali ke config (lalu simpan ke disk)."""
    config["akun"] = [a.ke_dict() for a in akun]
    simpan(config)


def cari_akun(daftar: list[Account], akun_id: str) -> Account | None:
    for a in daftar:
        if a.id == akun_id:
            return a
    return None


def cari_akun_username(daftar: list[Account], username: str) -> Account | None:
    """Cari akun berdasarkan username (case-insensitive, '@' diabaikan)."""
    bersih = username.lstrip("@").lower()
    for a in daftar:
        if a.username.lower() == bersih:
            return a
    return None


def bersihkan_username(teks: str) -> str:
    """Normalisasi input username: buang '@', spasi, dan URL profil.

    Menerima: '@ElonMusk', 'elonmusk', 'https://x.com/elonmusk',
              'https://twitter.com/elonmusk/'
    """
    t = (teks or "").strip()
    if not t:
        return ""

    if "://" in t or t.lower().startswith(("x.com/", "twitter.com/", "www.")):
        t = t.split("://", 1)[-1]
        bagian = [b for b in t.split("/") if b]
        # buang domain, ambil segmen pertama sesudahnya
        if bagian and bagian[0].lower() in {"x.com", "twitter.com", "www.x.com",
                                            "www.twitter.com", "mobile.x.com",
                                            "mobile.twitter.com"}:
            bagian = bagian[1:]
        t = bagian[0] if bagian else ""

    t = t.lstrip("@").strip()
    # handle X hanya boleh huruf/angka/underscore
    t = "".join(ch for ch in t if ch.isalnum() or ch == "_")
    return t


def pecah_username_massal(teks: str) -> list[str]:
    """Ubah tempelan banyak username menjadi daftar username bersih.

    Menerima pemisah baris baru, koma, titik-koma, atau spasi — supaya
    pengguna bisa menempel dari sumber mana pun (kolom Excel, daftar
    WhatsApp, hasil copy dari web) tanpa merapikannya dulu.

    Duplikat dibuang dengan urutan kemunculan pertama dipertahankan,
    dan perbandingan duplikat tidak membedakan huruf besar/kecil.

    Contoh:
        "elonmusk\\n@jack, https://x.com/billgates"
        -> ["elonmusk", "jack", "billgates"]
    """
    if not teks:
        return []

    # Semua pemisah yang mungkin disamakan jadi baris baru.
    seragam = teks
    for pemisah in (",", ";", "\t", " "):
        seragam = seragam.replace(pemisah, "\n")

    hasil: list[str] = []
    sudah_ada: set[str] = set()

    for baris in seragam.splitlines():
        nama = bersihkan_username(baris)
        if not nama:
            continue
        kunci = nama.lower()
        if kunci in sudah_ada:
            continue
        sudah_ada.add(kunci)
        hasil.append(nama)

    return hasil


def pastikan_data_dir() -> None:
    pastikan_folder()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
