"""Semua path aplikasi terpusat di sini.

Prinsip: path SELALU diturunkan dari lokasi file ini, tidak pernah dari
current working directory. Ini supaya aplikasi tetap benar walau dijalankan
dari folder mana pun (mis. saat .bat di-dobel-klik dari shortcut).
"""

from __future__ import annotations

from pathlib import Path

# x-feed-monitor/  (app/paths.py -> app/ -> root)
BASE_DIR: Path = Path(__file__).resolve().parent.parent

# Folder data runtime — SEMUANYA di sini supaya mudah di-backup / dihapus.
# Isi folder ini TIDAK boleh masuk git (lihat .gitignore) karena memuat
# auth_token.
DATA_DIR: Path = BASE_DIR / "data"

CONFIG_PATH: Path = DATA_DIR / "config.json"          # pengaturan + akun + auth
DB_PATH: Path = DATA_DIR / "feed.db"                  # riwayat postingan

# Satu database pool twscrape PER AKUN (bukan satu untuk semua).
#
# Alasannya: twscrape memilih akun secara otomatis dari pool dan tidak
# menyediakan cara untuk "pin" akun tertentu pada satu request. Padahal
# aplikasi ini memakai auth per akun — membaca timeline akun private hanya
# bisa memakai auth akun itu sendiri. Dengan mengisolasi tiap akun di
# pool-nya sendiri (1 pool = 1 akun), akun yang terpilih selalu akun yang benar.
POOLS_DIR: Path = DATA_DIR / "pools"

CACHE_DIR: Path = DATA_DIR / "cache"
THUMBS_DIR: Path = CACHE_DIR / "thumbs"               # cache thumbnail
LOGS_DIR: Path = DATA_DIR / "logs"                    # log internal library

# Log internal twscrape. Hanya dipakai saat aplikasi dijalankan lewat
# pythonw.exe (tanpa console) — lihat app/compat.py.
LOG_PATH: Path = LOGS_DIR / "twscrape.log"

ERROR_LOG: Path = BASE_DIR / "error.log"              # jejak error saat crash


def pastikan_folder() -> None:
    """Buat seluruh folder yang dibutuhkan. Aman dipanggil berulang."""
    for folder in (DATA_DIR, POOLS_DIR, CACHE_DIR, THUMBS_DIR, LOGS_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def pool_untuk(account_id: str) -> Path:
    """Path database pool twscrape milik satu akun."""
    return POOLS_DIR / f"{account_id}.db"
