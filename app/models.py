"""Model data aplikasi.

Model inti:
  - Kredensial : sepasang auth_token + ct0 (kunci untuk minta data ke X)
  - Account    : akun X yang dipantau (boleh punya kredensial sendiri)
  - Post       : satu postingan yang sudah dinormalisasi

Semuanya sengaja dibuat "bodoh" (tanpa logika jaringan/DB) supaya mudah
di-serialisasi ke JSON maupun SQLite.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def waktu_sekarang() -> str:
    """Timestamp ISO8601 UTC — format standar yang dipakai seluruh aplikasi."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def buat_id() -> str:
    """Id pendek yang unik untuk sebuah akun."""
    return uuid.uuid4().hex[:12]


#: Pola URL di dalam teks. Sengaja sederhana — hanya untuk menemukan
#: tautan di isi postingan, bukan untuk validasi ketat.
_POLA_URL = re.compile(
    r"(?:https?://|www\.)[^\s<>\"')]+",
    re.IGNORECASE,
)


def _normalisasi_kunci_link(teks: str) -> str:
    """Bentuk pembanding tautan: tanpa skema, tanpa 'www.', tanpa garis miring akhir."""
    t = (teks or "").strip().lower()
    for awalan in ("https://", "http://"):
        if t.startswith(awalan):
            t = t[len(awalan):]
            break
    if t.startswith("www."):
        t = t[4:]
    return t.rstrip("/")


def cari_url_di_teks(teks: str) -> list[str]:
    """Temukan semua URL yang tertulis di dalam sebuah teks."""
    return [m.group(0) for m in _POLA_URL.finditer(teks or "")]


# ---------------------------------------------------------------------------
# Kredensial
# ---------------------------------------------------------------------------

@dataclass
class Kredensial:
    """Sepasang cookie yang dipakai untuk meminta data ke X.

    Keduanya diambil manual oleh pengguna dari browser (DevTools) dan
    bersifat RAHASIA: siapa pun yang memilikinya bisa mengakses akun X
    tersebut sepenuhnya.

    Perlu dipahami: kredensial ini milik **akun yang meminta**, bukan akun
    yang dipantau. Satu kredensial bisa dipakai untuk membaca timeline
    berapa pun akun lain (termasuk akun private selama akun pemilik
    kredensial mem-follow-nya).
    """

    auth_token: str = ""
    ct0: str = ""

    def lengkap(self) -> bool:
        """True bila kedua nilainya terisi."""
        return bool(self.auth_token and self.ct0)

    def cookie_string(self) -> str:
        """Format cookie yang diminta twscrape: 'auth_token=...; ct0=...'."""
        return f"auth_token={self.auth_token}; ct0={self.ct0}"

    def sidik(self) -> str:
        """Penanda isi, dipakai untuk mendeteksi perubahan kredensial.

        Hanya untuk perbandingan internal — TIDAK dimaksudkan sebagai
        pengamanan, dan tidak boleh ditampilkan ke pengguna.
        """
        return f"{self.auth_token}\x00{self.ct0}"

    def ke_dict(self) -> dict[str, Any]:
        return {"auth_token": self.auth_token, "ct0": self.ct0}

    @classmethod
    def dari_dict(cls, data: dict[str, Any] | None) -> "Kredensial":
        """Bangun Kredensial dari dict. Tahan terhadap None / nilai aneh."""
        if not isinstance(data, dict):
            return cls()
        return cls(
            auth_token=str(data.get("auth_token") or ""),
            ct0=str(data.get("ct0") or ""),
        )


# ---------------------------------------------------------------------------
# Akun
# ---------------------------------------------------------------------------

@dataclass
class Account:
    """Satu akun X yang dipantau.

    Akun ini adalah **target pantauan** — yang postingannya ingin dilihat.
    Umumnya cukup diisi `username`-nya saja; pengambilan datanya memakai
    kredensial utama dari Pengaturan.

    `auth_token` + `ct0` di sini bersifat **OPSIONAL** dan hanya dipakai
    sebagai pengecualian: bila akun ini butuh kredensial berbeda dari yang
    utama (mis. akun private yang hanya di-follow oleh akun X kedua).
    Dibiarkan kosong = pakai kredensial utama.
    """

    username: str                      # handle tanpa '@'
    label: str = ""                    # nama tampilan (opsional, untuk UI)
    id: str = field(default_factory=buat_id)
    enabled: bool = True

    # --- kredensial khusus (opsional; kosong = pakai kredensial utama) ---
    auth_token: str = ""
    ct0: str = ""

    # Cache — diisi saat runtime, ikut tersimpan supaya tidak perlu
    # request UserByScreenName tiap siklus polling.
    user_id: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None

    # Status terakhir (untuk panel status di UI)
    last_error: str | None = None
    last_fetch: str | None = None
    last_status: str = "belum"          # belum | ok | error | dimatikan

    # ------------------------------------------------------------------
    def nama_tampil(self) -> str:
        """Label yang dipakai di UI."""
        return self.label or self.display_name or f"@{self.username}"

    def punya_auth_sendiri(self) -> bool:
        """True bila akun ini memakai kredensial sendiri (bukan yang utama)."""
        return bool(self.auth_token and self.ct0)

    def kredensial_sendiri(self) -> Kredensial:
        """Kredensial khusus milik akun ini (bisa saja kosong)."""
        return Kredensial(auth_token=self.auth_token, ct0=self.ct0)

    def siap_dipantau(self) -> bool:
        """True bila akun ini punya cukup info untuk diambil postingannya.

        Hanya mengecek username — ketersediaan kredensial diperiksa di
        tempat lain, karena akun tanpa kredensial sendiri masih bisa
        dipantau memakai kredensial utama.
        """
        return bool(self.username)

    def ke_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def dari_dict(cls, data: dict[str, Any]) -> "Account":
        """Bangun Account dari dict, abaikan kunci yang tidak dikenal."""
        dikenal = {f for f in cls.__dataclass_fields__}
        bersih = {k: v for k, v in data.items() if k in dikenal}
        bersih.setdefault("username", "")
        return cls(**bersih)


# ---------------------------------------------------------------------------
# Postingan
# ---------------------------------------------------------------------------

@dataclass
class Media:
    """Satu item media (gambar / video / gif) pada postingan."""

    url: str = ""            # URL gambar (atau thumbnail untuk video)
    tipe: str = "photo"      # photo | video | animated
    video_url: str = ""      # URL video terbaik (bila tipe video/animated)

    def ke_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def dari_dict(cls, data: dict[str, Any]) -> "Media":
        return cls(
            url=data.get("url", ""),
            tipe=data.get("tipe", "photo"),
            video_url=data.get("video_url", ""),
        )


@dataclass
class Link:
    """Satu tautan di dalam postingan.

    X menampilkan tautan dalam bentuk pendek (`t.co/xxxx`), sedangkan alamat
    sebenarnya ada di sini. Keduanya disimpan karena keduanya dipakai:
      * `teks`  — bentuk yang muncul di isi postingan, dipakai untuk
                  mencocokkan saat menggambar
      * `url`   — alamat sebenarnya, dipakai saat pengguna mengklik

    Memakai `url` (bukan `teks`) penting untuk fitur konfirmasi: pengguna
    harus melihat domain TUJUAN sebenarnya, bukan `t.co` yang menyembunyikan
    ke mana tautan itu membawa.
    """

    url: str = ""            # alamat sebenarnya (expanded)
    teks: str = ""           # bentuk yang tampil di isi postingan

    def ke_dict(self) -> dict[str, Any]:
        return {"url": self.url, "teks": self.teks}

    @classmethod
    def dari_dict(cls, data: dict[str, Any]) -> "Link":
        if not isinstance(data, dict):
            return cls()
        return cls(
            url=str(data.get("url") or ""),
            teks=str(data.get("teks") or ""),
        )


@dataclass
class Post:
    """Satu postingan yang sudah dinormalisasi dari model twscrape."""

    tweet_id: str
    account_id: str
    username: str
    display_name: str = ""
    content: str = ""
    created_at: str = field(default_factory=waktu_sekarang)
    url: str = ""

    like_count: int = 0
    retweet_count: int = 0
    reply_count: int = 0
    view_count: int | None = None

    media: list[Media] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    is_retweet: bool = False
    is_reply: bool = False
    lang: str = ""

    fetched_at: str = field(default_factory=waktu_sekarang)

    # ------------------------------------------------------------------
    def media_json(self) -> str:
        return json.dumps([m.ke_dict() for m in self.media], ensure_ascii=False)

    def links_json(self) -> str:
        return json.dumps([l.ke_dict() for l in self.links], ensure_ascii=False)

    @staticmethod
    def baca_media(teks: str | None) -> list[Media]:
        """Parse kolom media_json dari DB. Tahan terhadap data rusak."""
        if not teks:
            return []
        try:
            data = json.loads(teks)
        except (json.JSONDecodeError, TypeError):
            return []
        if not isinstance(data, list):
            return []
        return [Media.dari_dict(d) for d in data if isinstance(d, dict)]

    @staticmethod
    def baca_links(teks: str | None) -> list[Link]:
        """Parse kolom links_json dari DB. Tahan terhadap data rusak."""
        if not teks:
            return []
        try:
            data = json.loads(teks)
        except (json.JSONDecodeError, TypeError):
            return []
        if not isinstance(data, list):
            return []
        return [Link.dari_dict(d) for d in data if isinstance(d, dict)]

    def peta_link(self) -> dict[str, str]:
        """{teks tampil -> url asli} untuk mencocokkan tautan di isi postingan.

        Pencocokan tidak membedakan huruf besar/kecil dan mengabaikan
        perbedaan skema (`http://` vs `https://`), karena X kadang
        menampilkan tautan tanpa skema.
        """
        peta: dict[str, str] = {}
        for link in self.links:
            if not link.url:
                continue
            for kunci in (link.teks, link.url):
                if kunci:
                    peta[_normalisasi_kunci_link(kunci)] = link.url
        return peta

    def ke_dict(self) -> dict[str, Any]:
        """Untuk export CSV/JSON — media & tautan diratakan jadi teks."""
        return {
            "tweet_id": self.tweet_id,
            "username": self.username,
            "display_name": self.display_name,
            "content": self.content,
            "created_at": self.created_at,
            "url": self.url,
            "like_count": self.like_count,
            "retweet_count": self.retweet_count,
            "reply_count": self.reply_count,
            "view_count": self.view_count,
            "is_retweet": self.is_retweet,
            "is_reply": self.is_reply,
            "lang": self.lang,
            "media": " | ".join(m.url for m in self.media),
            "links": " | ".join(l.url for l in self.links),
        }
