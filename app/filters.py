"""Logika filter feed.

Sengaja dipisah dari GUI supaya:
  * bisa diuji tanpa membuka aplikasi
  * aturannya ada di satu tempat, tidak tersebar di dalam widget

Filter yang sudah diterapkan di SQL (db.py) TIDAK diulang di sini —
fungsi di file ini hanya untuk hal-hal yang butuh logika Python.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .models import Post

# ---------------------------------------------------------------------------
# Rentang waktu siap pakai
# ---------------------------------------------------------------------------

#: (label, jumlah hari). 0 = tanpa batas.
RENTANG_PILIHAN: tuple[tuple[str, int], ...] = (
    ("Semua waktu", 0),
    ("Hari ini", 1),
    ("3 hari terakhir", 3),
    ("7 hari terakhir", 7),
    ("30 hari terakhir", 30),
    ("90 hari terakhir", 90),
)


def batas_waktu(hari: int) -> str | None:
    """ISO timestamp batas bawah untuk `hari` terakhir. None = tanpa batas."""
    if hari <= 0:
        return None
    batas = datetime.now(timezone.utc) - timedelta(days=hari)
    return batas.isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Pencarian keyword
# ---------------------------------------------------------------------------

def _pecah_keyword(teks: str) -> list[str]:
    """Pisahkan query menjadi istilah, hormati tanda kutip untuk frasa.

    Contoh:  'ai "machine learning" -spam'
      -> ['ai', 'machine learning', 'spam']  (tanda '-' diabaikan)
    """
    istilah: list[str] = []
    for cocok in re.finditer(r'"([^"]+)"|(\S+)', teks or ""):
        frasa, kata = cocok.group(1), cocok.group(2)
        nilai = (frasa or kata or "").strip().lstrip("-")
        if nilai:
            istilah.append(nilai.lower())
    return istilah


def cocok_keyword(post: Post, teks: str) -> bool:
    """True bila SEMUA istilah ditemukan di konten/nama/hashtag.

    Pencocokan bersifat case-insensitive dan mencari di konten, display
    name, username, serta hashtag.
    """
    istilah = _pecah_keyword(teks)
    if not istilah:
        return True

    ladang = " ".join([
        post.content,
        post.display_name,
        post.username,
        " ".join(f"#{h}" for h in _hashtag(post.content)),
    ]).lower()

    return all(i in ladang for i in istilah)


def _hashtag(konten: str) -> list[str]:
    return re.findall(r"#(\w+)", konten or "")


# ---------------------------------------------------------------------------
# Kumpulan kriteria filter
# ---------------------------------------------------------------------------

@dataclass
class KriteriaFilter:
    """Semua pilihan filter yang aktif di UI.

    Dikirim ke db.ambil() untuk penyaringan di SQL; sisanya (keyword
    lanjutan) disaring di Python.
    """

    #: True = tampilkan semua akun (daftar `akun_ids` diabaikan).
    #:
    #: Dipisah dari `akun_ids` karena daftar kosong punya arti ganda:
    #: "tidak ada batasan" vs "tidak ada akun yang dipilih". Tanpa flag ini,
    #: menghilangkan centang semua akun akan justru menampilkan semuanya.
    semua_akun: bool = True
    akun_ids: list[str] = field(default_factory=list)

    keyword: str = ""
    sembunyikan_retweet: bool = True
    sembunyikan_reply: bool = True
    rentang_hari: int = 0

    def akun_dipilih(self) -> list[str]:
        """Daftar akun yang membatasi query. Kosong = tanpa batasan akun."""
        if self.semua_akun:
            return []
        return list(self.akun_ids)

    def ke_dict(self) -> dict:
        return {
            "semua_akun": self.semua_akun,
            "akun_ids": list(self.akun_ids),
            "keyword": self.keyword,
            "sembunyikan_retweet": self.sembunyikan_retweet,
            "sembunyikan_reply": self.sembunyikan_reply,
            "rentang_hari": self.rentang_hari,
        }

    @classmethod
    def dari_dict(cls, data: dict | None) -> "KriteriaFilter":
        data = data or {}
        akun_ids = list(data.get("akun_ids") or [])
        # Kompatibilitas dengan config lama yang belum punya `semua_akun`:
        # daftar kosong berarti "semua akun".
        semua = data.get("semua_akun")
        if semua is None:
            semua = not akun_ids
        return cls(
            semua_akun=bool(semua),
            akun_ids=akun_ids,
            keyword=str(data.get("keyword") or ""),
            sembunyikan_retweet=bool(data.get("sembunyikan_retweet", True)),
            sembunyikan_reply=bool(data.get("sembunyikan_reply", True)),
            rentang_hari=int(data.get("rentang_hari") or 0),
        )

    def ada_filter_aktif(self) -> bool:
        """True bila ada filter yang membatasi hasil (untuk badge di UI)."""
        return bool(
            not self.semua_akun
            or self.keyword.strip()
            or self.sembunyikan_retweet
            or self.sembunyikan_reply
            or self.rentang_hari > 0
        )

    def ringkas(self, jumlah_akun: int = 0) -> str:
        """Deskripsi singkat filter aktif, untuk statusbar."""
        bagian: list[str] = []
        if not self.semua_akun:
            if self.akun_ids:
                bagian.append(f"{len(self.akun_ids)} akun dipilih")
            else:
                bagian.append("tidak ada akun dipilih")
        elif jumlah_akun:
            bagian.append(f"semua {jumlah_akun} akun")
        if self.keyword.strip():
            bagian.append(f'cari "{self.keyword.strip()}"')
        if self.sembunyikan_retweet:
            bagian.append("tanpa retweet")
        if self.sembunyikan_reply:
            bagian.append("tanpa reply")
        for label, hari in RENTANG_PILIHAN:
            if hari == self.rentang_hari and hari > 0:
                bagian.append(label.lower())
                break
        return " · ".join(bagian) if bagian else "tanpa filter"


# ---------------------------------------------------------------------------
# Penyaringan di sisi Python (setelah data keluar dari DB)
# ---------------------------------------------------------------------------

def saring(posts: list[Post], kriteria: KriteriaFilter) -> list[Post]:
    """Terapkan sisa kriteria yang tidak bisa diwakili di SQL."""
    hasil = posts

    # Keyword: db.ambil() sudah menyaring kasar (LIKE), ini menyaring presisi
    # (semua istilah harus ada, dukungan frasa dalam tanda kutip).
    if kriteria.keyword.strip():
        hasil = [p for p in hasil if cocok_keyword(p, kriteria.keyword)]

    return hasil
