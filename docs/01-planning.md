# 01 — Planning

Latar belakang, ruang lingkup, dan keputusan teknologi.

---

## Kebutuhan

Aplikasi desktop untuk memantau postingan dari **11–30 akun X** dalam **satu feed gabungan**.

| Aspek | Kebutuhan |
|---|---|
| Platform | Windows, Python 3.10+ |
| GUI | PyQt6 (tampilan modern, tabel/list cepat) |
| Auth | **Satu kredensial utama** + override opsional per akun |
| Sumber auth | Disalin manual dari browser (DevTools → Cookies) |
| Pembaruan | Otomatis tiap 5 menit + tombol Refresh manual |
| Isi postingan | Postingan asli + retweet (tanpa reply) |
| Filter | Akun · keyword · sembunyikan RT/reply · periode |
| Riwayat | SQLite, masa simpan bisa diatur |
| Notifikasi | Desktop, hanya untuk postingan baru |
| Media | Thumbnail di kartu, klik buka browser |
| Tema | Gelap & terang |
| Launcher | `.bat`, dobel-klik |

### Non-tujuan
- Tidak untuk memposting, membalas, atau mengirim DM
- Tidak mengunduh video ke disk
- Tidak memakai API resmi X (berbayar)
- Tidak mendukung multi-user di satu PC

---

## Keputusan: mengapa satu kredensial utama

**Konsep yang menentukan seluruh desain ini:** `auth_token` + `ct0` adalah kredensial milik **akun yang meminta data**, bukan akun yang dipantau.

```
   auth-mu (kunci)  ──►  minta ke X  ──►  "tampilkan postingan @oranglain"
                                          X: "oke, ini postingannya"
```

Satu kredensial bisa dipakai untuk membaca timeline berapa pun akun lain.

### Koreksi dari rancangan awal

Versi pertama aplikasi ini memaksa pengguna mengisi auth untuk **setiap** akun yang ditambahkan, atas dasar pemahaman bahwa "membaca akun private butuh auth akun itu sendiri".

**Pemahaman itu salah.** Yang benar:

| Pertanyaan | Jawaban |
|---|---|
| Perlu kredensial akun private-nya? | **Tidak.** Cookie sesi orang lain juga tidak mungkin didapat. |
| Kredensial siapa yang dipakai? | Kredensial **pengikutnya**. Auth-mu sendiri cukup, asalkan akunmu mem-follow akun private itu. |
| Kalau tidak mem-follow? | X mengembalikan **HTTP 200 dengan timeline kosong** — bukan error. Terlihat seperti "0 postingan". |

Konsekuensinya, memaksa auth per akun hanya menambah pekerjaan tanpa manfaat: pengguna mengisi nilai yang **sama** berulang kali. Desain diperbaiki menjadi:

- **Satu kredensial utama** di Pengaturan — cukup diisi sekali
- **Override opsional per akun** — hanya untuk kasus langka (mis. akun private yang hanya di-follow akun X kedua)
- Tambah akun cukup **username**, dan bisa **banyak sekaligus**

### Catatan tentang akun private

Karena kegagalan "tidak mem-follow" muncul sebagai timeline kosong (bukan error), aplikasi **tidak bisa membedakannya** dari akun yang memang belum posting. Karena itu:

- `jelaskan_error()` tetap punya pola untuk kata "protected"
- Gejalanya dijelaskan eksplisit di README dan panduan pakai, karena hanya pengguna yang tahu apakah ia mem-follow akun tersebut atau tidak

---

## Keputusan: pemilihan library

Ini keputusan paling penting di project ini, karena seluruh aplikasi bergantung pada satu library untuk bicara dengan X.

### Kandidat 1: `twikit` — ❌ DITOLAK

| Pemeriksaan | Hasil |
|---|---|
| Rilis terakhir | **Feb 2025** (±19 bulan sebelum project ini dibuat) |
| Commit kode terakhir | Apr 2025 |
| `ClientTransaction` (header anti-bot) | **Rusak sejak Mar 2026**, tidak ada perbaikan |
| Query ID GraphQL | Hardcoded di `twikit/client/gql.py`, **tanpa mekanisme pembaruan otomatis** |
| Respons maintainer | Tidak merespons; PR perbaikan ditutup tanpa di-merge |
| Status repo | Tidak diarsipkan, tapi README mengarah ke project penerus yang "under development" |

**Alasan penolakan:** library ini rusak pada saat project dimulai, dan tidak ada pihak yang memperbaikinya. Memakainya berarti menyerahkan aplikasi pada kode mati.

### Kandidat 2: binary `xtractor.exe` (dipakai project lain di workspace) — ❌ DITOLAK

Project `Twitter-X-Media-Batch-Downloader-Python` di workspace yang sama memakai binary Go pihak ketiga.

**Alasan penolakan:** hasil pemeriksaan binary menunjukkan adanya jalur kode yang **mengunggah `auth_token` ke server pihak ketiga** (`auth.twitterdl.app`). Mengirim kredensial akun ke server yang tidak dikenal tidak dapat diterima — apalagi untuk aplikasi yang memegang auth 30 akun.

### Kandidat 3: `twscrape` — ✅ DIPILIH

| Pemeriksaan | Hasil |
|---|---|
| Rilis terakhir | **v0.20.1, 25 Agu 2026** (aktif) |
| Commit terakhir | **22 Sep 2026** |
| Stars / lisensi | 2.809 / MIT |
| Dukungan Python 3.13 | Ya (classifier resmi 3.13 & 3.14) |
| Auth cookie-only | Ya — `add_account_cookies(user, "auth_token=…; ct0=…")`, tanpa login password |
| `x-client-transaction-id` | Diimplementasikan, dan menangani format lama (`ondemand.s.*.js`) **maupun** baru (`sign.o-*.js`) |
| Backend HTTP | Mendukung `curl_cffi` (meniru TLS fingerprint browser) selain `httpx` bawaan |
| Status per akun | `accounts_info()` → `{logged_in, active, last_used, total_req, error_msg}` |
| Rate-limit | Dilacak per akun per endpoint; akun terkunci otomatis sampai reset |
| Pembaruan query ID | Ada script `update-gql-ops.py` yang meng-scrape bundle JS X; dijalankan maintainer tiap rilis |
| Fitur self-heal | Menambahkan sendiri feature-flag GraphQL yang baru diminta X |

**Alasan pemilihan:** satu-satunya kandidat yang aktif dirawat pada saat project dibuat, dan satu-satunya yang menyediakan data status per akun — yang persis dibutuhkan untuk panel status di GUI.

### Risiko yang diterima

Query ID twscrape masih **hardcoded per rilis** (bukan di-refresh otomatis saat runtime). Artinya, saat X merotasi endpoint, aplikasi akan gagal sampai library diperbarui.

**Mitigasi:**
1. `update.bat` — pembaruan satu klik
2. Pesan error di UI menyebutkan solusinya secara eksplisit (lihat `_POLA_ERROR` di `app/twitter_client.py`)
3. Seluruh ketergantungan pada twscrape **terisolasi di satu file** (`app/twitter_client.py`), sehingga penggantian mesin tidak menyentuh sisa aplikasi

### Pemeriksaan penting yang menghemat banyak kerja

Sebelum menulis kode, dilakukan pengujian langsung ke endpoint X untuk memastikan apakah header `x-client-transaction-id` **wajib** untuk dua endpoint yang dipakai aplikasi ini.

**Hasil:** `UserByScreenName` dan `UserTweets` tetap mengembalikan **HTTP 200** dengan auth yang valid, bahkan ketika header tersebut diisi nilai sampah.

**Dampaknya:** komponen paling rapuh dari ekosistem ini (parsing & eksekusi JavaScript X) ternyata **tidak diperlukan** untuk kasus penggunaan aplikasi ini. Ini menghilangkan sumber kerusakan terbesar.

---

## Keputusan teknis lain

| Keputusan | Alasan |
|---|---|
| **Penyimpanan auth plaintext** | Pilihan sadar pemilik aplikasi demi kesederhanaan. Dimintai konfirmasi eksplisit, dan `.gitignore` wajib meng-cover `data/`. |
| **`.bat` + venv otomatis** | Pengguna tidak perlu menyentuh terminal. Hash `requirements.txt` disimpan agar pemasangan hanya terjadi saat daftar komponen berubah. |
| **QThread + event loop asyncio sendiri** | twscrape sepenuhnya `async`; Qt punya event loop sendiri. Digabung di satu thread akan membekukan UI. |
| **QListView + delegate** | Membuat satu QWidget per postingan akan tersendat saat riwayat ribuan baris. Delegate hanya menggambar yang terlihat. |
| **Pool twscrape per KREDENSIAL, bukan per akun** | twscrape memilih akun otomatis dari pool dan tidak bisa di-pin, jadi tiap pool hanya boleh berisi satu entri. Tapi entri itu dipecah per kredensial — bukan per akun target — supaya pelacakan rate-limit akurat. Lihat `docs/02-arsitektur.md` §3. |
| **Jeda bertahap antar akun** | 30 request serentak mudah terdeteksi sebagai bot. Default 3 detik + variasi acak. |
| **Cache `user_id`** | Menghemat 1 request per akun per siklus (username jarang berubah). |
| **Backend HTTP `curl_cffi`** | Meniru TLS fingerprint browser sungguhan. Default twscrape (`httpx`) memakai fingerprint Python yang mudah dikenali X — ini menurunkan risiko 403 / "looks automated". Diset lewat `TWS_HTTP_BACKEND=curl` (bisa ditimpa dari luar bila perlu). |
| **Telemetry twscrape dimatikan** | `TWS_TELEMETRY=0` diset sebelum import — library ini mengirim event ke PostHog termasuk hash machine-id. |
| **Konfigurasi JSON, bukan QSettings** | Mengikuti konvensi project lain di workspace: seluruh data runtime terpusat di satu folder yang mudah di-backup/dihapus. |

---

## Anggaran rate-limit

Rate-limit X dihitung **per akun X**, bukan per akun target. Karena semua akun target umumnya memakai kredensial utama yang sama, mereka **berbagi satu kuota** (endpoint `UserTweets` ±450 request / 15 menit).

| Pemakaian | Perhitungan |
|---|---|
| 1 akun target, interval 5 menit | 3 request / 15 menit |
| 30 akun target, interval 5 menit | 30 × 3 = **90 request / 15 menit** (satu kuota bersama) |
| Batas X | ±450 request / 15 menit |

**Kesimpulan:** 30 akun dengan interval 5 menit memakai ±20% dari kuota — masih aman, tapi **bukan lagi 0,7%** seperti perhitungan versi lama yang salah menganggap tiap akun punya kuota sendiri.

**Kalau memantau banyak akun:**
- Interval 5 menit masih aman sampai ±100 akun
- Untuk lebih dari itu, perpanjang interval atau tambah kredensial khusus (masing-masing punya kuota sendiri)
- Turunkan **Postingan per akun** untuk mengurangi jumlah request per siklus

Inilah alasan **pool bersama** penting: kalau tiap akun target diberi pool sendiri, twscrape akan mengira punya 30 kuota terpisah dan aplikasi tidak akan tahu bahwa kuota sebenarnya sudah hampir habis.
