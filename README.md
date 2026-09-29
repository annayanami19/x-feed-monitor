# X Feed Monitor

> Aplikasi desktop untuk memantau postingan dari **banyak akun X/Twitter sekaligus dalam satu feed gabungan**.

Cukup isi kredensial **sekali** di Pengaturan, lalu tambahkan akun yang ingin dipantau — cukup dengan username-nya.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](#prasyarat)
[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)](CHANGELOG.md)

---

## Daftar isi

- [Cara kerjanya](#cara-kerjanya)
- [Fitur](#fitur)
- [Instalasi](#instalasi)
- [Langkah pertama](#langkah-pertama)
- [Pemakaian](#pemakaian)
- [Pengaturan](#pengaturan)
- [Pemecahan masalah](#pemecahan-masalah)
- [⚠️ Keamanan & risiko](#️-keamanan--risiko)
- [Struktur proyek](#struktur-proyek)
- [Pengembangan](#pengembangan)
- [Lisensi](#lisensi)

---

## Cara kerjanya

```
   kredensial milikmu  ──►  minta ke X  ──►  "tampilkan postingan @oranglain"
        (kunci)                              X: "oke, ini postingannya"
```

**`auth_token` yang kamu isi adalah milik akunmu sendiri** — bukan akun yang dipantau. Itu kunci untuk meminta data ke X.

| Pertanyaan | Jawaban |
|---|---|
| Berapa kali isi kredensial? | **Sekali saja** di Pengaturan |
| Berapa akun yang bisa dipantau? | Berapa pun, dengan kredensial yang sama |
| Bisa pantau akun private? | **Bisa**, selama akunmu **mem-follow** akun itu |
| Perlu kredensial akun private-nya? | Tidak perlu — dan memang tidak mungkin didapat |
| Kalau tidak mem-follow? | Postingannya kosong (bukan error) |

> ⚠️ **Akun private yang tidak kamu follow akan tampak seperti "tidak ada postingan"** — X mengembalikan hasil kosong, bukan pesan error. Kalau sebuah akun private tidak memunculkan apa pun, periksa dulu apakah akunmu sudah di-approve sebagai follower.

---

## Fitur

### Feed
- **Satu halaman untuk semua akun** — postingan digabung dan diurutkan berdasarkan waktu
- **Thumbnail gambar & video** langsung di kartu (video diberi tanda ▶)
- **Teks postingan bisa diblok & di-copy** seperti di browser
- **Tautan bisa diklik** — muncul peringatan berisi domain tujuan lebih dulu
- **Panel detail** di sisi kanan (klik dua kali kartu atau `Enter`)
- **Klik kanan** kartu → Buka di browser · Copy link · Copy teks · Lihat detail

### Filter
- **Pencarian keyword** — mendukung frasa dengan tanda kutip: `"machine learning" ai`
- **Pilih akun** — centang di panel kiri; tombol `Semua` / `Kosong` untuk cepat
- **Sembunyikan retweet** dan **sembunyikan reply**
- **Periode** — hari ini / 3 / 7 / 30 / 90 hari / semua waktu
- Semua pilihan filter tersimpan otomatis antar sesi

### Riwayat
- Disimpan lokal di SQLite — tidak hilang saat aplikasi ditutup
- **Tidak ada duplikat** walau di-refresh berkali-kali
- Masa simpan bisa diatur: 7 / 14 / 30 / 90 / 180 / 365 hari, atau selamanya

### Notifikasi & tampilan
- Notifikasi desktop untuk postingan **baru saja** (bukan pengulangan)
- Bisa dibatasi hanya untuk akun yang sedang ditampilkan
- Tema **gelap** dan **terang**, bisa diganti kapan saja

### Penanganan masalah
- Pesan error berbahasa Indonesia dengan **saran tindakan**, bukan stack trace
- **`update.bat`** — memperbarui mesin pengambil data saat X merotasi endpoint
- Log internal tersimpan di `data/logs/twscrape.log`

---

## Instalasi

### Prasyarat

| Kebutuhan | Keterangan |
|---|---|
| **Windows 10/11** | Aplikasi ini dibuat dan diuji untuk Windows |
| **Python 3.10+** | [Unduh di python.org](https://www.python.org/downloads/) — **centang "Add python.exe to PATH"** saat memasang |
| Koneksi internet | Untuk mengambil postingan dari X |

### Langkah

1. **Unduh** repositori ini (tombol `Code` → `Download ZIP`), lalu ekstrak
2. **Dobel-klik `run.bat`**

Saat pertama kali dijalankan, `run.bat` otomatis:
- memeriksa Python sudah terpasang
- membuat virtual environment di `.venv`
- memasang komponen yang dibutuhkan (±2–5 menit)
- membuka aplikasi

Pembukaan berikutnya langsung cepat karena komponen sudah tersimpan.

| File | Kegunaan |
|---|---|
| `run.bat` | Menjalankan aplikasi (pakai ini sehari-hari) |
| `run-debug.bat` | Menjalankan dengan jendela pesan — pakai kalau ada masalah |
| `update.bat` | Memperbarui mesin pengambil data kalau postingan berhenti muncul |

---

## Langkah pertama

### 1. Isi kredensial (sekali saja)

1. Buka **Pengaturan** di toolbar
2. Pada grup **Auth Utama**, tempel `auth_token` dan `ct0`
3. Klik **Uji Auth** → harus hijau
4. Klik **Simpan**

**Cara mengambil `auth_token` + `ct0` dari browser:**

1. Buka **x.com** dan pastikan sudah **login**
2. Tekan **`F12`** untuk membuka DevTools
3. Buka tab **Application** (Chrome/Edge) atau **Storage** (Firefox)
4. Pilih **Cookies** → **`https://x.com`**
5. Salin nilai **`auth_token`** (±40 karakter) dan **`ct0`** (±160 karakter)

> 💡 **Cara cepat:** buka DevTools → tab **Console**, lalu jalankan:
> ```js
> copy(document.cookie.split('; ').filter(c => /^(auth_token|ct0)=/.test(c)).join('; '))
> ```
> Hasilnya sudah tersalin ke clipboard dalam format yang bisa langsung ditempel.

### 2. Tambahkan akun yang dipantau

1. Buka **Akun** di toolbar
2. Tempel satu atau banyak username sekaligus:

```
elonmusk
@jack
https://x.com/billgates
```

Boleh dipisah **baris baru**, **koma**, atau **spasi** — semuanya dikenali. URL profil juga diterima.

3. Klik **Tambah** → semuanya langsung masuk
4. Klik **Simpan & Tutup**

Postingan akan langsung ditarik, lalu diperbarui otomatis tiap 5 menit.

---

## Pemakaian

### Copy teks postingan

1. **Tahan & geser** mouse di atas teks → teks terblok (biru)
2. Tekan **Ctrl+C** → yang tersalin **hanya bagian yang diblok**

| Aksi | Tombol |
|---|---|
| Blok teks | Tahan & geser mouse |
| Copy yang diblok | **Ctrl+C** |
| Blok seluruh postingan | **Ctrl+A** |
| Batalkan blok | **Esc** |

Kalau tidak ada blok aktif, **Ctrl+C** menyalin link postingan.

### Membuka tautan

Klik tautan di dalam teks postingan → muncul konfirmasi:

```
┌─ Buka tautan di browser? ─────────────────────┐
│ ⚠  Tautan ini akan dibuka di browser default   │
│    kamu.                                       │
│                                                │
│    Menuju ke:                                  │
│    youtube.com                                 │
│                                                │
│    https://youtube.com/watch?v=abc123          │
│                                                │
│              [ Buka browser ]  [ Batal ]       │
└────────────────────────────────────────────────┘
```

**Mengapa ada konfirmasi?** Tautan di X sering ditulis dalam bentuk pendek (`t.co/xxxx`) yang **menyembunyikan alamat aslinya**. Konfirmasi ini menampilkan **domain sebenarnya** sebelum browser dibuka. Tombol **Batal** adalah pilihan bawaan.

### Membaca kartu

```
🖼 Andi Pratama                          2 mnt
   @andipratama  [RETWEET]  [REPLY]
   Isi postingan ditampilkan di sini, maksimal 8 baris.
   Tautan seperti youtube.com bisa diklik langsung.
   ┌──────────┬──────────┐
   │ gambar 1 │ ▶ video  │
   └──────────┴──────────┘
   ♥ 12   ↻ 3   💬 1   👁 240
```

- **`[RETWEET]`** — ini retweet; nama & isi yang tampil adalah **penulis aslinya**
- **`[REPLY]`** — ini balasan
- **▶** — video, **GIF** — animasi

### Status akun di panel filter

| Tanda | Arti |
|---|---|
| `●` hijau | Terakhir berhasil diambil |
| `⚠` merah | Error — arahkan kursor ke nama untuk melihat pesannya |
| `○` abu-abu | Belum pernah diambil |
| `⏸` | Akun dinonaktifkan |

### Auth khusus (opsional)

Kalau ada akun tertentu yang butuh kredensial **berbeda** dari yang utama:

1. Buka **Akun** → pilih akunnya
2. Centang **"Pakai auth khusus untuk akun ini"**
3. Isi `auth_token` dan `ct0` yang berbeda
4. Klik **Uji Koneksi**, lalu **Simpan perubahan**

**Kapan ini perlu?** Contoh: kamu punya 2 akun X, dan sebuah akun private hanya di-follow oleh akun X yang **kedua**. Akun private itu perlu auth khusus; sisanya tetap pakai auth utama.

Kolom **Auth** di tabel menunjukkan akun mana yang memakai `Utama` dan mana yang `Khusus`.

---

## Pengaturan

Klik tombol **Pengaturan** di toolbar:

| Grup | Pengaturan | Keterangan |
|---|---|---|
| **Auth Utama** | auth_token, ct0 | Dipakai semua akun. Cukup diisi sekali. |
| **Pengambilan data** | Interval otomatis | Seberapa sering memeriksa postingan baru. Default 5 menit. |
| | Postingan per akun | Berapa postingan terbaru yang ditarik tiap siklus. Default 20. |
| | Jeda antar akun | Jeda antar request. Default 3 detik — jangan dikurangi kecuali akunmu sedikit. |
| **Riwayat** | Simpan riwayat | Berapa lama postingan disimpan sebelum dihapus otomatis. |
| | Bersihkan sekarang | Terapkan masa simpan saat itu juga. |
| | Hapus semua | Kosongkan seluruh riwayat. |
| **Tampilan** | Tema | Gelap atau terang. |
| **Notifikasi** | Notifikasi | Nyalakan/matikan, dan batasi ke akun yang ditampilkan. |

### Anggaran rate-limit

Rate-limit X dihitung **per akun X**, bukan per akun target. Kalau semua akun target memakai kredensial utama yang sama, mereka **berbagi satu kuota** (endpoint `UserTweets` ±450 request / 15 menit).

| Pemakaian | Perhitungan |
|---|---|
| 1 akun target, interval 5 menit | 3 request / 15 menit |
| 30 akun target, interval 5 menit | 30 × 3 = **90 request / 15 menit** |
| Batas X | ±450 request / 15 menit |

30 akun dengan interval 5 menit memakai ±20% kuota. Untuk memantau lebih banyak akun, perpanjang interval, kurangi **Postingan per akun**, atau tambahkan auth khusus supaya kuotanya terpisah.

---

## Pemecahan masalah

| Gejala | Penyebab & solusi |
|---|---|
| **Aplikasi tidak mau terbuka** | Jalankan `run-debug.bat`. Pesan errornya tampil di jendela itu dan tersimpan di `error.log`. |
| **Jalan di `run-debug.bat` tapi tidak di `run.bat`** | `run.bat` memakai `pythonw.exe` (tanpa console) sehingga `sys.stdout`/`sys.stderr` bernilai `None`. Sudah ditangani otomatis oleh `app/compat.py`. |
| **"Kredensial belum diisi"** | Buka **Pengaturan → Auth Utama** dan isi auth_token + ct0. |
| **"Python tidak ditemukan"** | Pasang Python 3.10+ dari [python.org](https://www.python.org/downloads/) dan centang **"Add python.exe to PATH"**. |
| **"Python terdeteksi tapi tidak bisa dijalankan"** | Matikan App execution alias: Settings → Apps → Advanced app settings → App execution aliases → matikan `python.exe`. |
| **Postingan berhenti muncul padahal akun normal** | X mengganti endpoint internalnya. Jalankan **`update.bat`**. |
| **"Kredensial tidak valid atau kedaluwarsa"** | Cookie sudah tidak berlaku (logout / ganti password). Ambil ulang `auth_token` + `ct0`. |
| **"Kena rate-limit dari X"** | Perpanjang **Interval otomatis**, lalu tunggu ±15 menit. |
| **"Ditolak X (403)"** | Akunmu dibatasi X. Login ulang di browser, atau pakai akun lain sebagai auth. |
| **Akun private tidak muncul postingannya** | Akun yang dipakai untuk auth **harus mem-follow** akun private tersebut. |
| **Notifikasi tidak muncul** | Settings → Sistem → Notifikasi → pastikan notifikasi aplikasi ini diizinkan. |
| **Thumbnail tidak muncul** | Cek koneksi. Kalau gambar sudah kedaluwarsa di server X, thumbnail memang tidak bisa dimuat. |

---

## ⚠️ Keamanan & risiko

### Kredensial = password akun

`auth_token` **setara dengan password akun X-mu**. Siapa pun yang memilikinya bisa mengakses akun tersebut sepenuhnya, termasuk mengirim postingan.

- Nilainya disimpan **tanpa enkripsi** di `data/config.json` (pilihan desain demi kesederhanaan)
- **Jangan pernah** membagikan file `data/config.json` ke siapa pun
- **Jangan commit** folder `data/` ke git — sudah otomatis dikecualikan lewat `.gitignore`
- Kalau PC dipakai bersama orang lain, pertimbangkan memakai akun khusus untuk aplikasi ini

**Kalau `data/config.json` bocor:** segera **logout** dari akun X tersebut di browser (ini membatalkan `auth_token` lama), lalu ambil kredensial baru.

### Risiko akun dibatasi

Pengambilan data otomatis **melanggar Ketentuan Layanan X**. Akun yang dipakai berisiko dibatasi atau ditangguhkan.

- **Sangat disarankan memakai akun sampingan**, bukan akun utama
- Jangan perkecil **Jeda antar akun** kalau memantau banyak akun
- Aplikasi memakai jeda bertahap + variasi acak agar polanya tidak menyerupai bot

### Privasi

Aplikasi hanya berkomunikasi dengan:
- **x.com** — mengambil postingan
- **twimg.com** — mengambil thumbnail

Telemetry bawaan library `twscrape` (yang mengirim event ke PostHog, termasuk hash machine-id) **dimatikan** di `app/twitter_client.py` lewat `TWS_TELEMETRY=0`.

Tidak ada data yang dikirim ke server pihak ketiga mana pun.

---

## Struktur proyek

```
x-feed-monitor/
├── run.bat / run-debug.bat / update.bat   Launcher Windows
├── app.py                                  Titik masuk aplikasi
├── requirements.txt                        Daftar komponen
├── CHANGELOG.md                            Riwayat perubahan
├── LICENSE                                 Lisensi MIT
│
├── assets/                                 Aset statis (ikut repositori)
│   ├── icon.ico                            Ikon Windows, 7 ukuran sekaligus
│   └── icon.png                            Versi 256px
│
├── tools/                                  Skrip bantu (tidak dipakai saat runtime)
│   └── buat_ikon.py                        Membuat ulang ikon di atas
│
├── app/                                    Kode aplikasi
│   ├── twitter_client.py                   Satu-satunya file yang bicara ke X
│   ├── poller.py                           Pengambilan data di thread terpisah
│   ├── db.py                               Riwayat SQLite + migrasi
│   ├── models.py                           Struktur data (Account, Post, Link, Media)
│   ├── config.py                           Baca/tulis config.json
│   ├── filters.py                          Logika filter
│   ├── thumbnails.py                       Unduh + cache gambar
│   ├── notifier.py                         Notifikasi desktop
│   ├── ikon.py                             Pemuat ikon aplikasi
│   ├── compat.py                           Perbaikan pythonw (sys.stderr None)
│   ├── paths.py                            Semua path terpusat
│   └── ui/                                 Seluruh tampilan (PyQt6)
│       ├── main_window.py                  Jendela utama & wiring
│       ├── feed_view.py                    Kartu postingan (delegate)
│       ├── teks_isi.py                     Teks bisa diblok & tautan bisa diklik
│       ├── accounts_dialog.py              Kelola akun
│       ├── settings_dialog.py              Pengaturan
│       ├── post_detail.py                  Panel detail
│       ├── theme.py                        Tema gelap & terang
│       └── widgets.py                      Komponen kecil yang dipakai ulang
│
├── data/                                   DATA RUNTIME — jangan dibagikan
│   ├── config.json                         Kredensial + daftar akun  ← RAHASIA
│   ├── feed.db                             Riwayat postingan
│   ├── pools/                              Sesi tersimpan per kredensial
│   └── cache/thumbs/                       Cache gambar
│
└── docs/                                   Dokumen teknis
    ├── 01-planning.md                      Latar belakang & keputusan teknologi
    ├── 02-arsitektur.md                    Alur data & titik-titik rawan
    └── 03-panduan-pakai.md                 Panduan lengkap
```

---

## Pengembangan

### Menyiapkan lingkungan

```bash
git clone https://github.com/annayanami19/x-feed-monitor.git
cd x-feed-monitor

python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

### Menjalankan

```bash
python app.py                   # dengan console (melihat error)
pythonw app.py                  # tanpa console (seperti run.bat)
```

> **Penting saat menguji:** jalankan lewat **`pythonw`** juga, bukan hanya `python`.
> `pythonw` tidak punya console sehingga `sys.stdout`/`sys.stderr` bernilai `None` —
> dan itu pernah membuat aplikasi gagal total saat dibuka lewat `run.bat`.
> Lihat `app/compat.py` untuk penjelasannya.

### Konvensi kode

- **Bahasa komentar & UI:** Indonesia
- **Penamaan:** `snake_case` untuk fungsi/variabel, `CamelCase` untuk kelas
- **Komentar menjelaskan MENGAPA, bukan APA.** Kode yang jelas sudah menjelaskan "apa";
  komentar dipakai untuk keputusan yang tidak terlihat dari kodenya
- Setiap file diawali docstring yang menjelaskan perannya

### Struktur tanggung jawab

| Lapisan | Boleh tahu tentang | Tidak boleh tahu tentang |
|---|---|---|
| `app/ui/` | Qt, model, config | `twscrape`, SQL |
| `app/poller.py` | `twitter_client`, model | Qt widget, DB |
| `app/twitter_client.py` | `twscrape`, model | Qt, DB |
| `app/db.py` | SQLite, model | jaringan, Qt |
| `app/models.py` | — | semuanya |

**Aturan utama:** `app/ui/` tidak pernah mengimpor `twscrape`. Semua akses jaringan
lewat `poller` → `twitter_client`.

### Membuat ulang ikon

Ikon dibuat dari kode, bukan file biner yang di-commit tanpa penjelasan:

```bash
python tools/buat_ikon.py
```

Menghasilkan `assets/icon.ico` (7 ukuran: 16/24/32/48/64/128/256 px) dan
`assets/icon.png` (256px).

**Mengapa banyak ukuran?** Windows memilih ukuran berbeda tergantung tempatnya —
16px di judul jendela, 32px di taskbar, 256px di Explorer. Satu file `.ico`
yang berisi semuanya membuat ikon tetap tajam di semua tempat.

Ingin mengubah warna atau bentuk? Semua ada di `tools/buat_ikon.py` — bagian
warna di atas file, dan bentuk di fungsi `_gambar_ikon()`.

### Menambah versi baru

1. Ubah `__version__` di `app/__init__.py`
2. Catat perubahan di `CHANGELOG.md` (pindahkan dari `[Unreleased]`)
3. Beri tag: `git tag v1.0.1 && git push --tags`

Panduan versi: perbaikan bug → `PATCH`, fitur baru → `MINOR`, perubahan yang
memecah kompatibilitas → `MAJOR`.

---

## Lisensi

[MIT](LICENSE) — bebas dipakai, diubah, dan disebarkan, asalkan mencantumkan
pemilik aslinya.

---

## Penafian

Proyek ini tidak berafiliasi dengan X Corp. Pengambilan data otomatis
**melanggar Ketentuan Layanan X** dan akun yang dipakai berisiko dibatasi.
Gunakan dengan risiko sendiri, dan sangat disarankan memakai akun sampingan.
