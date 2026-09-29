# 02 — Arsitektur

Alur data, pembagian tanggung jawab, dan titik-titik rawan.

---

## Alur data

```
                    ┌──────────────────────────────────────┐
                    │  GUI THREAD (Qt event loop)          │
                    │                                      │
  run.bat ────────► │  app.py ──► JendelaUtama             │
                    │               ├─ Toolbar             │
                    │               ├─ Panel filter        │
                    │               ├─ TampilanFeed        │
                    │               └─ PanelDetail         │
                    └───────────────┬──────────────────────┘
                                    │ Qt Signal (queued, aman antar-thread)
                    ┌───────────────▼──────────────────────┐
                    │  WORKER THREAD                       │
                    │  (QThread + event loop asyncio)      │
                    │                                      │
                    │  PollerWorker._siklus()              │
                    │    for akun in akun_aktif:           │
                    │      KlienAkun(akun)                 │
                    │        ├─ ambil_profil()             │
                    │        ├─ ambil_postingan()          │
                    │        └─ tweet_ke_post()            │
                    │      jeda 3 dtk (±acak)              │
                    └───────────────┬──────────────────────┘
                                    │ HTTPS
                    ┌───────────────▼──────────────────────┐
                    │  X GraphQL (x.com/i/api/graphql)     │
                    │    UserByScreenName  → username→id   │
                    │    UserTweets        → timeline      │
                    └──────────────────────────────────────┘
```

Hasil kembali ke GUI lewat sinyal, lalu:

```
postingan_masuk(posts, ringkas)
      │
      ├─► RiwayatDB.simpan_banyak(posts)   → INSERT OR IGNORE (dedupe)
      │        └─ mengembalikan HANYA yang baru
      │                └─► Notifier.beritahu_banyak()   (postingan baru saja)
      │
      └─► _jadwalkan_muat_ulang()  → QTimer 400 ms
               └─► RiwayatDB.ambil(filters) → TampilanFeed.ganti_posts()
```

---

## Pembagian tanggung jawab

| File | Tanggung jawab | Tidak boleh tahu tentang |
|---|---|---|
| `app/paths.py` | Semua path file | — |
| `app/models.py` | Struktur data (`Account`, `Post`, `Media`) | jaringan, DB, Qt |
| `app/config.py` | Baca/tulis `config.json` | jaringan, Qt |
| `app/db.py` | Riwayat SQLite | jaringan, Qt |
| `app/filters.py` | Logika filter | jaringan, DB, Qt |
| `app/twitter_client.py` | **Satu-satunya** file yang bicara ke X | Qt, DB |
| `app/poller.py` | Orkestrasi pengambilan di thread terpisah | DB, tampilan |
| `app/thumbnails.py` | Unduh + cache gambar | DB |
| `app/notifier.py` | Notifikasi desktop | DB, jaringan |
| `app/ui/*` | Tampilan & interaksi | twscrape, SQL |

Aturan penting: **`app/ui/` tidak pernah mengimpor `twscrape`**. Semua akses jaringan lewat `poller` → `twitter_client`.

---

## Keputusan arsitektur

### 1. Kredensial: satu utama + override opsional

**Konsep yang harus dipahami lebih dulu:** `auth_token` + `ct0` adalah kredensial milik **akun yang meminta data** — bukan akun yang dipantau. Satu kredensial bisa dipakai untuk membaca timeline berapa pun akun lain.

Modelnya:

```
   Kredensial utama (Pengaturan)
          │
          ├──► dipakai akun A  ──┐
          ├──► dipakai akun B  ──┼──► SATU pool bersama (_utama.db)
          └──► dipakai akun C  ──┘
                                  └──► pelacakan rate-limit akurat

   Kredensial khusus akun D ──────────► pool sendiri (D.db)
                                          └──► limit terpisah (akun X berbeda)
```

**Mengapa begini:** twscrape melacak rate-limit **per akun per endpoint** di dalam database pool-nya. Kalau tiap target diberi pool sendiri walau kredensialnya sama, aplikasi akan mengira punya 30 kuota padahal kenyataannya satu akun X — dan menabrak limit asli X.

### 2. Akun private: siapa yang butuh kredensial apa

| Pertanyaan | Jawaban |
|---|---|
| Perlu kredensial akun private-nya? | **Tidak.** Tidak mungkin juga — cookie sesi orang lain tidak bisa didapat. |
| Kredensial siapa yang dipakai? | Kredensial **pengikutnya**. Kalau akunmu mem-follow akun private itu, auth-mu sudah cukup. |
| Kalau tidak mem-follow? | X mengembalikan **HTTP 200 dengan timeline KOSONG** — bukan error. Jadi terlihat seperti "0 postingan". |

Poin terakhir itu penting dan **tidak bisa dideteksi dari respons API**. Karena itu:

- `jelaskan_error()` punya pola untuk kata "protected" (dipakai bila pesan itu muncul)
- Dokumentasi (README + panduan) menjelaskan gejalanya secara eksplisit, karena aplikasi tidak bisa membedakan "akun private yang tidak di-follow" dari "akun yang memang belum posting"

### 3. Satu pool twscrape per KREDENSIAL (bukan per akun)

`QueueClient` twscrape memilih akun lewat `pool.get_for_queue()`, yang mengambil akun mana pun yang aktif dan belum terkunci. **Tidak ada parameter untuk memaksa akun tertentu.**

Karena tiap pool hanya berisi **satu** entri akun, entri yang terpilih selalu entri yang benar:

| Kondisi akun | Pool | Nama entri di pool |
|---|---|---|
| Pakai kredensial utama | `data/pools/_utama.db` (bersama) | `utama` (tetap) |
| Punya kredensial sendiri | `data/pools/<id>.db` | username target |

Catatan: nama entri di pool **bukan** untuk autentikasi. twscrape memakainya hanya untuk memilih User-Agent secara deterministik (`Account.make_client` → `random.Random(seed).choice(uas)`), jadi satu nama tetap untuk pool bersama sudah benar.

Pool sementara untuk tombol "Uji" memakai id tetap `_uji` dan **selalu dihapus setelah pengujian** — kalau id-nya diacak, tiap klik akan meninggalkan file sampah di `data/pools/`.

### 4. Worker thread dengan event loop sendiri

twscrape seluruhnya `async def`. Qt punya event loop sendiri di thread utama.

**Kalau dipaksa satu thread:** memanggil `await` di thread GUI akan membekukan UI selama request berjalan (bisa 5–30 detik per akun × 30 akun).

**Solusi:** `QThread` dengan `asyncio.new_event_loop()` sendiri. Komunikasi hanya lewat Qt Signal (otomatis *queued* antar-thread). Worker tidak pernah menyentuh widget.

**Aturan yang dipegang:** worker tidak memutasi objek `Account` milik GUI. Ia bekerja di salinan (`Account.dari_dict(akun.ke_dict())`) dan mengirim hasilnya lewat sinyal — GUI yang menuliskan ke objek asli. Tanpa aturan ini, `user_id`/`last_error` akan dimutasi dari dua thread sekaligus.

### 5. Delegate, bukan tumpukan widget

**Alternatif yang ditolak:** satu `QWidget` per postingan.

**Mengapa ditolak:** dengan riwayat 5.000 postingan, Qt harus membuat dan menata 5.000 widget. Scrolling jadi tersendat dan memori membengkak.

**Solusi:** `QStyledItemDelegate` yang menggambar kartu langsung ke kanvas. Qt hanya memanggil `paint()` untuk kartu yang **terlihat** — biaya render konstan.

#### Konsekuensi: teks tidak otomatis bisa diblok

Kanvas tidak punya konsep "teks yang bisa diblok". Karena itu isi postingan digambar lewat **QTextDocument** (di `app/ui/teks_isi.py`), bukan `painter.drawText()`. Ini memberi tiga hal sekaligus:

| Kebutuhan | Cara |
|---|---|
| Teks bisa diblok | `QTextDocument` + `PaintContext.selections` |
| Tautan bisa diklik | HTML `<a href>` + `documentLayout().anchorAt()` |
| Posisi klik → karakter | `documentLayout().hitTest()` |

**Dua dokumen, bukan satu.** `DelegateKartu` menyimpan `dok` (untuk menggambar, menyimpan seleksi) dan `dok_ukur` (untuk mengukur tinggi kartu). Kalau keduanya satu objek, memanggil `sizeHint()` akan menimpa dokumen yang sedang menampung seleksi — dan blok teks yang sedang diblok langsung hilang.

**Koordinat.** `option.rect` yang diterima `paint()` sudah dalam koordinat viewport (Qt sudah memperhitungkan posisi scroll), jadi dokumen digambar di `(x, y)` tanpa koreksi. Untuk klik, `_koordinat_teks()` mengubah posisi mouse viewport menjadi koordinat **lokal di dalam teks** dengan mengurangi `x`/`y` area teks kartu.

**Tautan pendek (`t.co`).** X menulis tautan di isi postingan dalam bentuk pendek yang menyembunyikan alamat aslinya. `Post.links` menyimpan alamat sebenarnya (`expanded_url` dari twscrape), dan `DokumenTeks._url_asli()` menerjemahkannya saat menggambar `<a href>`. Inilah yang membuat popup konfirmasi bisa menampilkan **domain tujuan sebenarnya**, bukan `t.co`.

### 6. Isolasi twscrape

Seluruh ketergantungan pada twscrape ada di `app/twitter_client.py`. Kalau library ini rusak atau ditinggalkan (seperti yang terjadi pada `twikit`), penggantiannya cukup mengubah satu file.

Antarmuka yang harus dipenuhi pengganti:
```python
class KlienAkun:
    async def ambil_profil(self, paksa: bool = False) -> dict
    async def ambil_postingan(self, batas: int) -> list[Post]
    async def segarkan_cookie(self) -> None
    async def tutup(self) -> None
```

### 7. Dedupe di level database

`tweet_id` adalah `PRIMARY KEY`, dan penyimpanan memakai `INSERT OR IGNORE`.

Dua manfaat:
- Refresh berkali-kali tidak menghasilkan baris ganda
- `simpan_banyak()` mengembalikan **hanya baris yang benar-benar baru** → itulah yang dipakai untuk notifikasi. Tanpa ini, setiap siklus polling akan memunculkan notifikasi ulang untuk postingan yang sama.

### 8. Debounce pembacaan feed

Satu siklus polling memancarkan `postingan_masuk` **sekali per akun**. Dengan 30 akun, feed akan dibaca ulang dari DB 30 kali dalam beberapa detik.

**Solusi:** `QTimer` 400 ms yang menggabungkan semuanya jadi satu pembacaan.

### 9. Pemantau kuota dihitung sendiri (bukan dibaca dari twscrape)

Rate-limit X tidak terlihat dari dalam aplikasi — pengguna baru tahu setelah kena, dan saat itu semua akun sudah berhenti diperbarui ±15 menit. Modul `app/kuota.py` membuat pemakaian itu terlihat **sebelum** menjadi masalah: label di statusbar berubah warna (abu → kuning → merah) seiring pemakaian mendekati batas.

**Mengapa menghitung sendiri, bukan membaca statistik twscrape:** twscrape menyimpan jumlah request di DB pool-nya tapi angkanya **kumulatif sejak pool dibuat** — tidak bisa menjawab "berapa request dalam 15 menit terakhir?", padahal jendela 15 menit itulah yang X pakai. Maka `PemantauKuota` mencatat waktu tiap request (`time.monotonic`) dalam `deque` per endpoint, membuang yang kedaluwarsa, dan menghitung persentase terhadap `BATAS_ENDPOINT` yang diketahui.

**Alur datanya satu arah tanpa kunci:** thread worker memanggil `_kuota.catat(endpoint)` setiap request selesai, lalu di akhir siklus memancarkan `kuota_diperbarui` berisi `StatusKuota` (objek dataclass polos). GUI hanya mengubah label — tidak pernah menyentuh `PemantauKuota` langsung, jadi tidak ada akses lintas-thread ke struktur internalnya. `atur_auth_utama()` memanggil `_kuota.reset()` karena kuota berpindah milik akun X yang lain.

**Penghematan yang benar** sudah tertanam di `ambil_profil()`: `user_id` tiap akun disimpan sekali ke config, sehingga tiap siklus cukup 1 request `UserTweets` per akun. `sinceId` sengaja **tidak** dipakai — X tetap menghitung satu halaman penuh sebagai satu request walau postingan barunya sedikit, jadi tidak menghemat apa-apa.

---

## Titik rawan & penanganannya

| Titik rawan | Dampak | Penanganan |
|---|---|---|
| **`sys.stderr` = None di pythonw** | **Aplikasi tidak bisa dibuka sama sekali** lewat `run.bat` (tetapi normal lewat `run-debug.bat`) | `app/compat.py` mengganti stream yang None dengan file log **sebelum** twscrape diimpor — lihat bagian di bawah |
| **Query ID X berotasi** | Semua request 404 | `update.bat`; pesan error di UI menyebut solusinya. Terisolasi di 1 file. |
| **twscrape berhenti dirawat** | Aplikasi mati perlahan | Adapter 1 file; ganti backend tanpa menyentuh sisa aplikasi |
| **X menambah feature-flag baru** | Error "features cannot be null" | twscrape menambahkan flag itu sendiri saat runtime (self-heal) |
| **Auth kedaluwarsa** | Satu akun gagal terus | Status per akun di panel; pesan "ambil ulang auth" |
| **Rate-limit (429)** | Akun terkunci sementara | twscrape mengunci per akun & endpoint; akun lain tetap jalan |
| **`ondemand.s.js` X berubah** | `x-client-transaction-id` gagal dibuat | **Tidak berdampak** — dua endpoint yang dipakai tidak mewajibkannya (sudah diuji) |
| **Gambar gagal diunduh** | Thumbnail kosong | Ditandai gagal, tidak dicoba ulang terus-menerus |
| **Koneksi terputus** | Error per akun | Diklasifikasi sebagai gangguan koneksi, akun lain tetap diproses |
| **App mati saat menulis config** | Config rusak | Penulisan atomik (tulis `.tmp` → `replace`) |
| **Config rusak** | Aplikasi tidak bisa dibuka | Salinan disimpan sebagai `.json.rusak`, aplikasi jalan dengan default |

---

## Bug yang pernah terjadi: `sys.stderr = None` di pythonw

**Gejala:** aplikasi **tidak bisa dibuka sama sekali** lewat `run.bat`, tapi berjalan normal lewat `run-debug.bat`. `error.log` berisi:

```
File ".../twscrape/logger.py", line 35, in <module>
    logger.add(sys.stderr, filter=_filter)
TypeError: Cannot log to objects of type 'NoneType'
```

**Penyebab:** `run.bat` memakai **`pythonw.exe`** supaya tidak ada jendela console hitam. Tapi `pythonw.exe` tidak punya handle console, sehingga `sys.stdout` dan `sys.stderr` bernilai **`None`**.

twscrape memakai loguru dan menjalankan `logger.add(sys.stderr)` saat **diimpor**. Dengan `sys.stderr = None`, impornya gagal — dan karena ini terjadi saat impor, seluruh aplikasi ikut gagal.

**Mengapa sulit terlihat:** `run-debug.bat` memakai `python.exe` (punya console), jadi `sys.stderr` normal dan aplikasi jalan. Perbedaannya hanya di launcher.

**Perbaikan:** `app/compat.py` → `pastikan_std_stream()` mengganti stream yang `None` dengan handle file log sungguhan (`data/logs/twscrape.log`). Dipanggil di dua tempat:

1. `app.py` — sebelum impor apa pun yang memakai logging
2. `app/twitter_client.py` — sebelum `from twscrape import ...`

Efek sampingnya menguntungkan: pesan internal twscrape (rate-limit, akun terkunci, kegagalan request) kini tersimpan di `data/logs/twscrape.log` dan bisa diperiksa saat ada masalah. File log dipotong otomatis bila melewati 2 MB.

**Pelajaran untuk perubahan berikutnya:** setiap kode yang menulis ke `stdout`/`stderr` (termasuk `print()`) harus diuji lewat `pythonw.exe`, bukan hanya `python.exe`.

---

## Struktur data

### `data/config.json`
```json
{
  "auth_utama": {
    "auth_token": "…RAHASIA…",
    "ct0": "…RAHASIA…"
  },
  "interval_menit": 5,
  "post_per_akun": 20,
  "jeda_antar_akun": 3,
  "retensi_hari": 30,
  "bersihkan_otomatis": true,
  "tema": "dark",
  "notifikasi_aktif": true,
  "filter": {
    "semua_akun": true,
    "akun_ids": [],
    "keyword": "",
    "sembunyikan_retweet": true,
    "sembunyikan_reply": true,
    "rentang_hari": 0
  },
  "akun": [
    {
      "id": "a1b2c3d4e5f6",
      "username": "contoh",
      "label": "",
      "enabled": true,
      "auth_token": "",
      "ct0": "",
      "user_id": "12345",
      "display_name": "Contoh",
      "avatar_url": "",
      "last_error": null,
      "last_fetch": "2026-09-29T10:00:00+00:00",
      "last_status": "ok"
    }
  ],
  "versi_config": 2
}
```

**Catatan penting soal `akun[].auth_token` / `ct0`:**
Field ini **opsional** dan biasanya kosong. Dibiarkan kosong = akun memakai `auth_utama`.
Diisi = akun memakai kredensial sendiri (lihat `Account.punya_auth_sendiri()`).

**Kompatibilitas config versi lama (versi 1):** config lama tidak punya `auth_utama` dan setiap akun punya auth sendiri. `_gabung_default()` menambahkan `auth_utama` kosong secara otomatis, dan akun-akun lama yang auth-nya terisi otomatis diperlakukan sebagai "kredensial khusus" — tidak ada yang rusak, tanpa kode migrasi khusus.

### `data/feed.db` → tabel `posts`
```sql
CREATE TABLE posts (
    tweet_id      TEXT PRIMARY KEY,   -- dedupe
    account_id    TEXT NOT NULL,      -- akun mana yang memantau
    username      TEXT NOT NULL,      -- penulis sebenarnya (bisa beda saat RT)
    display_name  TEXT,
    content       TEXT,
    created_at    TEXT NOT NULL,      -- ISO8601 UTC, dipakai untuk urut & filter
    url           TEXT,
    like_count    INTEGER,
    retweet_count INTEGER,
    reply_count   INTEGER,
    view_count    INTEGER,
    media_json    TEXT,               -- JSON list Media
    links_json    TEXT,               -- JSON list Link (url asli + teks tampil)
    is_retweet    INTEGER,
    is_reply      INTEGER,
    lang          TEXT,
    fetched_at    TEXT
);
CREATE INDEX idx_posts_created  ON posts (created_at DESC);
CREATE INDEX idx_posts_account  ON posts (account_id);
```

Catatan: `username` adalah **penulis sebenarnya**, bukan pemilik akun yang dipantau. Saat sebuah akun me-retweet, baris tersimpan dengan `username` penulis asli + `is_retweet = 1`.

**Migrasi kolom baru.** `CREATE TABLE IF NOT EXISTS` tidak menyentuh tabel yang sudah ada, jadi database dari versi sebelumnya tidak akan punya kolom baru. `RiwayatDB._migrasi()` menambahkan kolom yang kurang lewat `ALTER TABLE` — data lama tetap utuh dan tidak perlu diisi ulang. Daftar kolom yang perlu ditambahkan ada di konstanta `KOLOM_TAMBAHAN`.

---

## Alur error

```
Exception dari twscrape
        │
        ▼
twitter_client.jelaskan_error(e)
        │
        ├─ cocokkan dengan _POLA_ERROR
        │     → (pesan Indonesia, saran tindakan)
        │
        └─ tidak cocok
              → pesan mentah (dipotong 200 char) + saran umum
        │
        ▼
HasilAkun(berhasil=False, pesan, saran)
        │
        ▼
GUI: akun.last_error = "pesan. saran"
     panel: tanda ⚠ + tooltip berisi detailnya
```

Pola yang dikenali (berurut dari yang paling spesifik): feature-flag usang, query ID berubah, rate-limit, auth tidak valid, 403/akun dibatasi, akun tidak ditemukan, akun private, gangguan koneksi.

---

## Siklus hidup aplikasi

```
run.bat
  ├─ periksa Python
  ├─ buat .venv (sekali)
  ├─ pip install -r requirements.txt (kalau hash berubah)
  └─ pythonw app.py
        │
        ▼
  app.py: pastikan_folder() → QApplication → JendelaUtama
        │
        ▼
  __init__:
    muat config
    bersihkan riwayat lama (kalau retensi aktif)
    rakit tampilan
    buat timer (SEBELUM worker — handler sinyal menyentuh timer)
    jalankan worker
    muat feed dari DB
    tampilkan tray icon
    QTimer.singleShot(600, mulai_refresh)
        │
        ▼
  closeEvent:  (urutan ini PENTING — lihat penjelasan di bawah)
    1. _sedang_tutup = True      → tolak pekerjaan yang datang terlambat
    2. _putus_sinyal_worker()    → tutup jalur worker → UI
    3. hentikan timer, simpan config, db.tutup()
    4. notifier + thumbnail berhenti
    5. worker.hentikan(1000ms)   → kalau gagal: paksa_hentikan(600ms)
```

Catatan: menutup jendela = **keluar total** (pilihan pengguna). Notifikasi dan polling berhenti.

---

## Penutupan jendela: mengapa urutannya begitu

Ini bagian yang pernah bermasalah, dan urutannya tidak boleh ditukar.

### Masalah aslinya: jendela menggantung 13 detik

Versi awal memanggil `worker.hentikan()` yang menunggu sampai **15 detik**.
Kalau worker sedang di tengah request jaringan ke X, jendela membeku selama
itu — Windows menganggapnya "Not Responding" dan menampilkan dialog yang
**terlihat seperti aplikasi crash**.

Request jaringan yang sedang berjalan **tidak bisa dibatalkan**: Python harus
menunggu socket selesai atau timeout. Dengan beberapa akun, totalnya bisa
belasan detik.

**Perbaikan:** worker diberi 1 detik untuk berhenti rapi. Kalau belum,
`paksa_hentikan()` memanggil `QThread.terminate()`.

Hasil terukur: **13,15 detik → 1,62 detik** (uji: `tools/uji_tutup.py`).

### Bahaya kedua: handler menyentuh objek yang sudah dibongkar

Worker berjalan di thread sendiri dan bisa memancarkan sinyal **kapan saja**.
Handler-nya menyentuh database dan widget:

| Handler | Menyentuh | Error kalau terlambat |
|---|---|---|
| `_pada_postingan_masuk` | `self.db.simpan_banyak()` | `ProgrammingError: Cannot operate on a closed database` |
| `_pada_siklus_mulai` | `self.aksi_refresh` | `RuntimeError: wrapped C/C++ object has been deleted` |

**Tiga lapis pengaman:**

1. **`_putus_sinyal_worker()`** dipanggil **sebelum** `db.tutup()`.
   Setelah sinyal diputus, apa pun yang dilakukan worker tidak akan
   menyentuh objek yang sedang dibongkar. Ini pengaman utama.

2. **Penanda `_sedang_tutup`** diset paling awal. `muat_ulang_feed()` dan
   `_pada_postingan_masuk()` langsung keluar bila penanda ini aktif —
   menangkap kasus timer yang terlanjur memancarkan sinyalnya.

3. **`paksa_hentikan()` dipanggil setelah sinyal diputus**, sehingga
   penghentian paksa tidak bisa memicu error di UI.

### Mengapa `terminate()` aman di sini

`QThread.terminate()` memang tidak rapi, tapi pada tahap ini aplikasi sedang
ditutup dan menggantung lebih buruk daripada penghentian yang tidak rapi:

- Database memakai **WAL** — penulisan yang belum selesai di-rollback otomatis
- **Config sudah disimpan** sebelum fungsi ini dipanggil
- Yang tertahan hanyalah **request jaringan** yang hasilnya belum tentu ada

### Cara menguji ulang

```bash
python tools/uji_tutup.py
```

Menutup jendela pada 6 waktu berbeda relatif terhadap siklus polling
(200ms sampai 4000ms), lalu melaporkan durasi penutupan dan error yang
tertangkap. Semua skenario harus lulus di bawah 3 detik tanpa error.
