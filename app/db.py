"""Riwayat postingan di SQLite.

Peran tabel `posts`:
  * dedupe      -> tweet_id sebagai PRIMARY KEY; refresh berkali-kali tidak
                   menghasilkan baris ganda
  * riwayat     -> postingan lama tetap ada walau sudah hilang dari timeline X
  * cepat       -> feed dibaca dari DB, bukan dari jaringan

Semua akses dari satu koneksi (aplikasi desktop single-user), tapi tetap
memakai WAL supaya pembacaan tidak terblokir saat penulisan.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Post
from .paths import DB_PATH, pastikan_folder

SKEMA = """
CREATE TABLE IF NOT EXISTS posts (
    tweet_id      TEXT PRIMARY KEY,
    account_id    TEXT NOT NULL,
    username      TEXT NOT NULL,
    display_name  TEXT NOT NULL DEFAULT '',
    content       TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    url           TEXT NOT NULL DEFAULT '',
    like_count    INTEGER NOT NULL DEFAULT 0,
    retweet_count INTEGER NOT NULL DEFAULT 0,
    reply_count   INTEGER NOT NULL DEFAULT 0,
    view_count    INTEGER,
    media_json    TEXT NOT NULL DEFAULT '[]',
    links_json    TEXT NOT NULL DEFAULT '[]',
    is_retweet    INTEGER NOT NULL DEFAULT 0,
    is_reply      INTEGER NOT NULL DEFAULT 0,
    lang          TEXT NOT NULL DEFAULT '',
    fetched_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_posts_created  ON posts (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_account  ON posts (account_id);
CREATE INDEX IF NOT EXISTS idx_posts_username ON posts (username);
"""

#: Kolom yang ditambahkan setelah versi pertama dirilis.
#: Format: (nama kolom, definisi SQL). Diterapkan lewat ALTER TABLE bila
#: belum ada — supaya database lama tidak perlu dihapus dan diisi ulang.
KOLOM_TAMBAHAN: tuple[tuple[str, str], ...] = (
    ("links_json", "TEXT NOT NULL DEFAULT '[]'"),
)


class RiwayatDB:
    """Pembungkus tipis di atas sqlite3 untuk tabel posts."""

    def __init__(self, path: Path | str = DB_PATH) -> None:
        pastikan_folder()
        self.path = str(path)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._siapkan()

    # ------------------------------------------------------------------
    def _siapkan(self) -> None:
        with self.conn:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.executescript(SKEMA)
        self._migrasi()

    def _migrasi(self) -> None:
        """Tambahkan kolom baru ke database lama (tanpa menghapus data).

        `CREATE TABLE IF NOT EXISTS` tidak menyentuh tabel yang sudah ada,
        jadi database dari versi sebelumnya tidak akan punya kolom baru.
        ALTER TABLE di sini membuat keduanya kompatibel.
        """
        try:
            ada = {
                str(baris[1])
                for baris in self.conn.execute("PRAGMA table_info(posts)")
            }
        except sqlite3.Error:
            return

        for nama, definisi in KOLOM_TAMBAHAN:
            if nama in ada:
                continue
            try:
                with self.conn:
                    self.conn.execute(
                        f"ALTER TABLE posts ADD COLUMN {nama} {definisi}"
                    )
            except sqlite3.Error:
                # Kolom mungkin sudah ada (balapan dengan proses lain) —
                # abaikan, karena tujuan kita hanya memastikan kolomnya ada.
                pass

    def tutup(self) -> None:
        try:
            self.conn.close()
        except sqlite3.Error:
            pass

    # ------------------------------------------------------------------
    # Tulis
    # ------------------------------------------------------------------
    def simpan_banyak(self, posts: Iterable[Post]) -> list[Post]:
        """Simpan postingan; kembalikan HANYA yang benar-benar baru.

        Yang dikembalikan inilah yang dipakai untuk notifikasi — jadi
        notifikasi tidak akan muncul dua kali untuk postingan yang sama.
        """
        baru: list[Post] = []
        with self.conn:
            for p in posts:
                cur = self.conn.execute(
                    """
                    INSERT OR IGNORE INTO posts (
                        tweet_id, account_id, username, display_name, content,
                        created_at, url, like_count, retweet_count, reply_count,
                        view_count, media_json, links_json, is_retweet, is_reply,
                        lang, fetched_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        p.tweet_id, p.account_id, p.username, p.display_name,
                        p.content, p.created_at, p.url, p.like_count,
                        p.retweet_count, p.reply_count, p.view_count,
                        p.media_json(), p.links_json(), int(p.is_retweet),
                        int(p.is_reply), p.lang, p.fetched_at,
                    ),
                )
                if cur.rowcount > 0:
                    baru.append(p)
        return baru

    def perbarui_statistik(self, posts: Iterable[Post]) -> None:
        """Perbarui angka like/retweet/view postingan yang sudah tersimpan.

        X menaikkan angka ini terus; tanpa pembaruan, angka di feed akan
        beku di nilai saat pertama kali diambil.
        """
        with self.conn:
            for p in posts:
                self.conn.execute(
                    """
                    UPDATE posts
                       SET like_count = ?, retweet_count = ?, reply_count = ?,
                           view_count = ?
                     WHERE tweet_id = ?
                    """,
                    (p.like_count, p.retweet_count, p.reply_count,
                     p.view_count, p.tweet_id),
                )

    # ------------------------------------------------------------------
    # Baca
    # ------------------------------------------------------------------
    def ambil(
        self,
        *,
        batas: int = 500,
        akun_ids: Sequence[str] | None = None,
        keyword: str = "",
        sembunyikan_retweet: bool = False,
        sembunyikan_reply: bool = False,
        sejak: str | None = None,
    ) -> list[Post]:
        """Baca riwayat dengan filter.

        Filter diterapkan di SQL (bukan di Python) supaya tetap cepat walau
        riwayatnya sudah puluhan ribu baris.
        """
        syarat: list[str] = []
        nilai: list[object] = []

        if akun_ids:
            tanda = ",".join("?" for _ in akun_ids)
            syarat.append(f"account_id IN ({tanda})")
            nilai.extend(akun_ids)

        if keyword:
            syarat.append("(content LIKE ? OR username LIKE ? OR display_name LIKE ?)")
            pola = f"%{keyword}%"
            nilai.extend([pola, pola, pola])

        if sembunyikan_retweet:
            syarat.append("is_retweet = 0")
        if sembunyikan_reply:
            syarat.append("is_reply = 0")
        if sejak:
            syarat.append("created_at >= ?")
            nilai.append(sejak)

        where = f"WHERE {' AND '.join(syarat)}" if syarat else ""
        sql = f"""
            SELECT * FROM posts
            {where}
            ORDER BY created_at DESC
            LIMIT ?
        """
        nilai.append(int(batas))

        try:
            baris = self.conn.execute(sql, nilai).fetchall()
        except sqlite3.Error:
            return []
        return [self._ke_post(b) for b in baris]

    def jumlah(self) -> int:
        try:
            return int(self.conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0])
        except (sqlite3.Error, TypeError):
            return 0

    def jumlah_per_akun(self) -> dict[str, int]:
        """{account_id: jumlah} — untuk angka di samping tiap akun di panel filter."""
        try:
            baris = self.conn.execute(
                "SELECT account_id, COUNT(*) FROM posts GROUP BY account_id"
            ).fetchall()
        except sqlite3.Error:
            return {}
        return {str(b[0]): int(b[1]) for b in baris}

    def ada_tweet(self, tweet_id: str) -> bool:
        try:
            return self.conn.execute(
                "SELECT 1 FROM posts WHERE tweet_id = ? LIMIT 1", (tweet_id,)
            ).fetchone() is not None
        except sqlite3.Error:
            return False

    def id_terbaru_per_akun(self) -> dict[str, str]:
        """{account_id: created_at terbaru} — dipakai untuk hitung post baru."""
        try:
            baris = self.conn.execute(
                "SELECT account_id, MAX(created_at) FROM posts GROUP BY account_id"
            ).fetchall()
        except sqlite3.Error:
            return {}
        return {str(b[0]): str(b[1]) for b in baris if b[1]}

    # ------------------------------------------------------------------
    # Pemeliharaan
    # ------------------------------------------------------------------
    def bersihkan(self, retensi_hari: int) -> int:
        """Hapus postingan lebih tua dari `retensi_hari`. 0 = simpan selamanya.

        Mengembalikan jumlah baris yang dihapus.
        """
        if retensi_hari <= 0:
            return 0

        batas = datetime.now(timezone.utc) - timedelta(days=retensi_hari)
        batas_iso = batas.isoformat(timespec="seconds")
        try:
            with self.conn:
                cur = self.conn.execute(
                    "DELETE FROM posts WHERE created_at < ?", (batas_iso,)
                )
                return int(cur.rowcount or 0)
        except sqlite3.Error:
            return 0

    def hapus_semua(self) -> int:
        """Kosongkan riwayat. Mengembalikan jumlah baris yang dihapus."""
        try:
            with self.conn:
                cur = self.conn.execute("DELETE FROM posts")
                return int(cur.rowcount or 0)
        except sqlite3.Error:
            return 0

    def hapus_akun(self, account_id: str) -> int:
        """Hapus semua postingan milik satu akun (dipakai saat akun dihapus)."""
        try:
            with self.conn:
                cur = self.conn.execute(
                    "DELETE FROM posts WHERE account_id = ?", (account_id,)
                )
                return int(cur.rowcount or 0)
        except sqlite3.Error:
            return 0

    def vakum(self) -> None:
        """Rapatkan file DB setelah banyak penghapusan."""
        try:
            self.conn.execute("VACUUM")
        except sqlite3.Error:
            pass

    def ukuran_mb(self) -> float:
        """Ukuran file DB dalam MB (termasuk -wal)."""
        total = 0
        for akhiran in ("", "-wal", "-shm"):
            p = Path(self.path + akhiran)
            if p.exists():
                total += p.stat().st_size
        return round(total / (1024 * 1024), 2)

    # ------------------------------------------------------------------
    @staticmethod
    def _ke_post(baris: sqlite3.Row) -> Post:
        # `links_json` bisa belum ada di baris dari database versi lama
        # (ALTER TABLE menambahkannya dengan nilai default, tapi pembacaan
        # tetap dibuat defensif supaya tidak pernah melempar).
        try:
            links_mentah = baris["links_json"]
        except (IndexError, KeyError):
            links_mentah = None

        return Post(
            tweet_id=str(baris["tweet_id"]),
            account_id=str(baris["account_id"]),
            username=str(baris["username"]),
            display_name=str(baris["display_name"] or ""),
            content=str(baris["content"] or ""),
            created_at=str(baris["created_at"]),
            url=str(baris["url"] or ""),
            like_count=int(baris["like_count"] or 0),
            retweet_count=int(baris["retweet_count"] or 0),
            reply_count=int(baris["reply_count"] or 0),
            view_count=(int(baris["view_count"]) if baris["view_count"] is not None else None),
            media=Post.baca_media(baris["media_json"]),
            links=Post.baca_links(links_mentah),
            is_retweet=bool(baris["is_retweet"]),
            is_reply=bool(baris["is_reply"]),
            lang=str(baris["lang"] or ""),
            fetched_at=str(baris["fetched_at"] or ""),
        )
