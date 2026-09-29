# 03 — Panduan Pakai

Panduan langkah demi langkah, dari instalasi sampai pemecahan masalah.

---

## 0. Cara kerjanya (baca dulu)

```
   auth milikmu  ──►  minta ke X  ──►  "tampilkan postingan @oranglain"
   (kunci)                             X: "oke, ini postingannya"
```

**auth_token yang kamu isi adalah milik akunmu sendiri** — bukan akun yang dipantau.

| Pertanyaan | Jawaban |
|---|---|
| Berapa kali isi auth? | **Sekali saja** di Pengaturan |
| Berapa akun yang bisa dipantau? | Berapa pun, dengan auth yang sama |
| Bisa pantau akun private? | **Bisa**, selama akunmu **mem-follow** akun itu |
| Perlu auth akun private-nya? | Tidak perlu — dan memang tidak mungkin didapat |
| Kalau tidak mem-follow? | Postingannya kosong (bukan error) |

> ⚠️ **Akun private yang tidak kamu follow akan tampak seperti "tidak ada postingan"** — X mengembalikan hasil kosong, bukan pesan error. Kalau sebuah akun private tidak memunculkan apa pun, periksa dulu apakah akunmu sudah di-approve sebagai follower.

---

## 1. Instalasi

### Prasyarat
- **Windows 10/11**
- **Python 3.10 atau lebih baru** — [unduh di python.org](https://www.python.org/downloads/)
  - ⚠️ Saat memasang, **centang "Add python.exe to PATH"**
- Koneksi internet

### Langkah
1. **Dobel-klik `run.bat`.**
2. Saat pertama kali, akan muncul pesan bahwa komponen sedang dipasang (±2–5 menit).
3. Setelah selesai, jendela aplikasi terbuka.

Pembukaan berikutnya langsung cepat (komponen sudah tersimpan di `.venv`).

### Kalau gagal
Jalankan **`run-debug.bat`** — pesan errornya akan tampil di jendela itu dan tersimpan di `error.log`.

---

## 2. Mengambil auth value dari browser

Aplikasi ini tidak meminta password X. Sebagai gantinya, ia memakai cookie sesi yang sudah ada di browser kamu.

### Chrome / Edge
1. Buka **x.com** dan pastikan sudah **login**.
2. Tekan **`F12`** untuk membuka DevTools.
3. Buka tab **Application**.
4. Di panel kiri: **Storage → Cookies → `https://x.com`**.
5. Cari dua baris berikut dan **salin nilainya** (klik dua kali pada kolom *Value*, lalu Ctrl+C):

| Nama cookie | Panjang | Bentuk |
|---|---|---|
| `auth_token` | ±40 karakter | huruf & angka acak |
| `ct0` | ±160 karakter | huruf & angka acak |

### Firefox
1. Buka **x.com** dan login.
2. Tekan **`F12`**.
3. Buka tab **Storage** → **Cookies** → **`https://x.com`**.
4. Salin nilai `auth_token` dan `ct0` seperti di atas.

### Yang harus diperhatikan
- Salin **nilai**-nya saja, **bukan** `auth_token=nilainya`
- Jangan sampai ada spasi di depan/belakang
- `auth_token` yang benar **tidak mengandung** tanda `=` atau spasi (aplikasi akan menolak kalau ada)

> 💡 **Cara cepat:** buka DevTools → tab **Console**, lalu jalankan:
> ```js
> copy(document.cookie.split('; ').filter(c => /^(auth_token|ct0)=/.test(c)).join('; '))
> ```
> Hasilnya sudah tersalin ke clipboard dalam format yang bisa langsung ditempel.

---

## 3. Mengisi auth (sekali saja)

1. Klik tombol **`Pengaturan`** di toolbar.
2. Pada grup **Auth Utama** (paling atas), tempel `auth_token` dan `ct0`.
3. Klik **Uji Auth**:
   - ✅ Hijau = kredensial valid
   - ❌ Merah = ada masalah (pesannya menjelaskan)
4. Klik **Simpan**.

Selesai. Kamu tidak perlu mengisi auth lagi untuk akun-akun berikutnya.

---

## 4. Menambahkan akun yang dipantau

1. Klik tombol **`Akun`** di toolbar.
2. Di kotak **Tambah akun**, tempel satu atau banyak username sekaligus:

```
elonmusk
@jack
https://x.com/billgates
```

Boleh dipisah **baris baru**, **koma**, atau **spasi** — semuanya dikenali. URL profil juga diterima.

3. Klik **Tambah**.

Aplikasi akan melaporkan hasilnya, misalnya *"12 akun ditambahkan, 2 dilewati (sudah ada)"*.

4. Klik **Simpan & Tutup**.

Postingan akan langsung ditarik.

### Mengubah akun
1. Pilih akun di tabel (atau klik dua kali barisnya).
2. Ubah **Username** / **Label** / status **Aktif**.
3. Klik **Simpan perubahan**.

### Menghapus akun
Pilih akun → **Hapus**. Riwayat postingannya tetap ada di database.

### Kolom "Auth" di tabel
| Nilai | Arti |
|---|---|
| `Utama` | Memakai auth dari Pengaturan (kasus normal) |
| `Khusus` | Memakai auth sendiri (lihat bagian berikut) |

---

## 5. Auth khusus (opsional, jarang dipakai)

Kalau ada akun tertentu yang butuh kredensial **berbeda** dari yang utama:

1. Buka **Akun** → pilih akunnya
2. Centang **"Pakai auth khusus untuk akun ini"**
3. Isi `auth_token` dan `ct0` yang berbeda
4. Klik **Uji Koneksi** untuk memastikan
5. Klik **Simpan perubahan**

**Kapan ini perlu?** Contoh nyata: kamu punya 2 akun X, dan sebuah akun private hanya di-follow oleh akun X yang **kedua**. Akun private itu perlu auth khusus (memakai akun kedua); akun-akun lain tetap pakai auth utama.

**Catatan:** akun dengan auth khusus punya kuota rate-limit sendiri, karena dihitung per akun X. Ini berguna kalau memantau sangat banyak akun.

Untuk kembali ke auth utama: hilangkan centangnya, lalu simpan.

---

## 6. Memakai feed

| Aksi | Cara |
|---|---|
| Blok teks | **Tahan & geser** mouse di atas teks postingan |
| Copy teks terblok | **Ctrl+C** |
| Blok seluruh isi postingan | **Ctrl+A** |
| Batalkan blok | **Esc** |
| Buka tautan | **Klik** tautan di dalam teks → konfirmasi |
| Buka detail | **Klik dua kali** kartu, atau **Enter** |
| Buka di browser | **Klik kanan** → Buka di browser |
| Copy link | **Klik kanan** → Copy link, atau **Ctrl+C** (tanpa blok aktif) |
| Copy teks lengkap | **Klik kanan** → Copy teks postingan |
| Refresh sekarang | Tombol **Refresh** atau **F5** |
| Tutup panel detail | Tombol **✕** di panel |

### Membaca kartu
```
🖼 Andi Pratama                          2 mnt
   @andipratama  [RETWEET]  [REPLY]
   Isi postingan ditampilkan di sini, maksimal 8 baris.
   Tautan seperti youtube.com bisa diklik langsung.
   Kalau lebih panjang akan muncul "… klik dua kali untuk selengkapnya".
   ┌──────────┬──────────┐
   │ gambar 1 │ ▶ video  │
   └──────────┴──────────┘
   ♥ 12   ↻ 3   💬 1   👁 240
```

- **`[RETWEET]`** — ini retweet; nama & isi yang tampil adalah **penulis aslinya**
- **`[REPLY]`** — ini balasan
- **▶** — video, **GIF** — animasi (klik untuk membuka di browser)

### Cara copy teks postingan

1. **Tahan & geser** mouse di atas teks → teks terblok (berwarna biru)
2. Tekan **Ctrl+C** → yang tersalin **hanya bagian yang diblok**

Kalau tidak ada blok aktif, **Ctrl+C** menyalin link postingan (perilaku lama).

**Ctrl+A** memblok seluruh isi postingan yang sedang dipilih. **Esc** membatalkan blok.

### Membuka tautan di dalam postingan

Klik tautan di dalam teks → muncul konfirmasi:

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

**Mengapa ada konfirmasi ini?**

Tautan di X sering ditulis dalam bentuk pendek — misalnya `t.co/abc123` — yang **menyembunyikan ke mana sebenarnya tautan itu membawa**. Konfirmasi menampilkan **domain sebenarnya** sebelum browser dibuka, jadi kamu bisa membatalkan kalau tujuannya tidak dikenal.

- **Batal** adalah pilihan bawaan: menekan Enter tanpa sengaja tidak akan membuka browser
- Kursor berubah jadi **tangan** saat berada di atas tautan, jadi terlihat bisa diklik

> 💡 Kalau ingin membuka tanpa konfirmasi sama sekali, pakai **klik kanan → Buka di browser** pada kartu (itu membuka postingannya sendiri di X, bukan tautan di dalamnya).

### Filter

Panel kiri:

| Kontrol | Fungsi |
|---|---|
| **Kotak pencarian** | Cari kata di isi postingan, nama, atau hashtag |
| **Daftar akun** | Centang akun yang ingin ditampilkan |
| **Semua / Kosong** | Centang atau lepaskan semua akun sekaligus |
| **Sembunyikan retweet** | Jangan tampilkan retweet |
| **Sembunyikan reply** | Jangan tampilkan balasan |

Toolbar:

| Kontrol | Fungsi |
|---|---|
| **Periode** | Batasi ke hari ini / 3 / 7 / 30 / 90 hari / semua waktu |

### Pencarian lanjutan
- Beberapa kata = **semua** harus ada: `ai startup` → postingan yang memuat keduanya
- Frasa dengan tanda kutip: `"machine learning"` → harus persis berurutan
- Pencarian **tidak membedakan** huruf besar/kecil

### Angka di samping nama akun
Jumlah postingan akun itu **di database** (bukan yang sedang tampil).

### Tanda status di depan nama
| Tanda | Arti |
|---|---|
| `●` hijau | Terakhir berhasil diambil |
| `⚠` merah | Error — arahkan kursor ke nama untuk melihat pesannya |
| `○` abu-abu | Belum pernah diambil |
| `⏸` | Akun dinonaktifkan |

Filter tersimpan otomatis — saat aplikasi dibuka lagi, pilihanmu tetap sama.

### Indikator kuota di statusbar

Di kanan-bawah jendela ada angka berawalan **kuota:** — pemakaian rate-limit 15 menit terakhir dari request yang dikirim aplikasi ini sendiri.

| Warna | Arti |
|---|---|
| Abu-abu | Aman (di bawah 60% batas) |
| Kuning | Peringatan — sempurnakan pengaturan bila mau menambah akun |
| Merah | Bahaya — jangan tambah beban; tunggu ±15 menit sampai ter-reset |

Arahkan kursor ke angkanya untuk melihat rincian per endpoint dan perkiraan kapan batasnya tercapai. Kalau sering masuk zona kuning/merah: perpanjang **Interval otomatis**, kurangi **Postingan per akun** (di atas 40 menambah request), atau kurangi jumlah akun. Penghematan terbesar sudah otomatis: `user_id` tiap akun di-cache, jadi tiap siklus cukup 1 request per akun.

---

## 7. Pengaturan

Klik **Pengaturan** di toolbar.

### Auth Utama
Kredensial yang dipakai semua akun. Lihat bagian 3 di atas.

### Pengambilan data

| Pengaturan | Default | Keterangan |
|---|---|---|
| **Interval otomatis** | 5 menit | Seberapa sering memeriksa postingan baru. Pilihan: 1, 2, 5, 10, 15, 30, 60 menit, atau mati. |
| **Postingan per akun** | 20 | Berapa postingan terbaru yang ditarik tiap siklus. |
| **Jeda antar akun** | 3 detik | Jeda antar request. **Jangan dikurangi** kalau memantau banyak akun — request beruntun mudah terdeteksi sebagai bot. |

### Riwayat

| Pengaturan | Keterangan |
|---|---|
| **Simpan riwayat** | 7 / 14 / 30 / 90 / 180 / 365 hari, atau selamanya |
| **Bersihkan otomatis saat dibuka** | Terapkan masa simpan tiap kali aplikasi dijalankan |
| **Bersihkan sekarang** | Terapkan saat itu juga |
| **Hapus semua** | Kosongkan seluruh riwayat (tidak bisa dibatalkan) |

Di bawahnya terlihat jumlah postingan dan ukuran file database.

### Tampilan & Notifikasi

| Pengaturan | Keterangan |
|---|---|
| **Tema** | Gelap / terang (bisa juga lewat tombol 🌙/☀ di toolbar) |
| **Notifikasi** | Nyalakan/matikan |
| **Hanya untuk akun yang ditampilkan** | Notifikasi hanya untuk akun yang centangnya aktif |

---

## 8. Pemecahan masalah

### Aplikasi tidak mau terbuka
1. Jalankan **`run-debug.bat`** — pesan errornya tampil di situ
2. Lihat juga file **`error.log`** di folder aplikasi
3. Kirimkan isi `error.log` saat melaporkan masalah

### Aplikasi jalan di `run-debug.bat` tapi tidak di `run.bat`
Perbedaan keduanya hanya di launcher:
- `run.bat` → `pythonw.exe` (tanpa jendela console)
- `run-debug.bat` → `python.exe` (dengan jendela console)

`pythonw.exe` membuat `sys.stdout`/`sys.stderr` bernilai `None`, yang bisa membuat library yang menulis log saat diimpor gagal total.

Aplikasi sudah menangani ini otomatis lewat `app/compat.py` (stream yang `None` diganti handle file log). Kalau masalahnya masih muncul, kirimkan isi `error.log`.

### "Kredensial belum diisi"
Buka **Pengaturan → Auth Utama**, isi `auth_token` dan `ct0`, lalu klik **Simpan**.

### Akun private tidak memunculkan postingan
**Ini kasus paling sering disalahpahami.** X mengembalikan hasil **kosong** (bukan error) untuk akun private yang tidak kamu follow.

- Pastikan akunmu sudah **di-approve sebagai follower** akun tersebut
- Cek dengan membuka profilnya di browser — kalau di browser juga tidak terlihat, berarti belum jadi follower
- Kalau kamu punya akun X lain yang jadi follower-nya, pakai **auth khusus** (bagian 5) dengan kredensial akun itu

### "Python tidak ditemukan"
Pasang Python dari [python.org](https://www.python.org/downloads/), dan **centang "Add python.exe to PATH"** saat memasang.

### "Python terdeteksi tapi tidak bisa dijalankan"
Windows punya "App execution alias" yang menunjuk ke Microsoft Store.
1. Settings → Apps → Advanced app settings → **App execution aliases**
2. **Matikan** `python.exe` dan `python3.exe`
3. Pasang Python asli dari python.org
4. Jalankan `run.bat` lagi

### "Gagal memasang komponen"
Kemungkinan: tidak ada internet, koneksi terputus, atau proxy/firewall memblokir `pypi.org`. Periksa koneksi lalu jalankan ulang.

### Postingan tidak muncul sama sekali
1. **Klik `Pengaturan`** → cek **Auth Utama** sudah terisi
2. Klik **Uji Auth** — kalau merah, ambil ulang `auth_token` + `ct0`
3. Kalau auth hijau tapi tetap kosong → jalankan **`update.bat`**

### Postingan berhenti muncul padahal sebelumnya lancar
X mengganti endpoint internalnya. **Jalankan `update.bat`**, lalu buka aplikasi lagi.

### "Kredensial tidak valid atau kedaluwarsa"
Cookie sudah tidak berlaku. Biasanya karena:
- Logout dari browser
- Ganti password
- Login dari perangkat lain yang membatalkan sesi lama

**Solusi:** ambil ulang `auth_token` + `ct0`, lalu perbarui di **Pengaturan → Auth Utama**.

### "Kena rate-limit dari X"
Terlalu sering meminta data. **Penting dipahami:** rate-limit dihitung per **akun X**, bukan per akun yang dipantau. Kalau 30 akun memakai auth yang sama, mereka berbagi satu kuota.

- Tunggu ±15 menit
- Perpanjang **Interval otomatis**
- Kurangi jumlah akun yang dipantau, atau turunkan **Postingan per akun**
- Untuk memantau sangat banyak akun, tambahkan auth khusus supaya kuotanya terpisah

### "Ditolak X (403)"
Akun yang dipakai untuk auth dibatasi X. Login ulang akun itu di browser, atau pakai akun lain sebagai auth utama.

### Thumbnail tidak muncul
- Periksa koneksi internet
- Kalau gambar sudah dihapus dari server X, thumbnail memang tidak bisa dimuat (postingannya tetap tampil)
- Coba hapus folder `data/cache/thumbs/` lalu buka aplikasi lagi

### Notifikasi tidak muncul
1. Settings → Sistem → **Notifikasi** → pastikan notifikasi diizinkan
2. Cari "X Feed Monitor" di daftar aplikasi → pastikan **aktif**
3. Pastikan notifikasi dicentang di Pengaturan

### Aplikasi terasa lambat
- Kurangi **Postingan per akun**
- Turunkan **masa simpan riwayat** (mis. 30 → 7 hari)
- Gunakan filter **Periode** untuk membatasi yang ditampilkan

### Panel akun kiri kosong
Tambahkan akun lewat tombol **`Akun`** di toolbar.

### Di mana log internal disimpan?
`data/logs/twscrape.log` — memuat pesan dari library pengambil data: rate-limit, akun terkunci, kegagalan request. Berguna saat menelusuri masalah yang tidak tampil di UI. File ini dipotong otomatis bila melewati 2 MB.

---

## 9. ⚠️ Keamanan & risiko

### auth_token = password akun
Siapa pun yang memiliki `auth_token` bisa **mengakses akun X tersebut sepenuhnya**, termasuk mengirim postingan.

- Nilainya disimpan **tanpa enkripsi** di `data/config.json`
- **Jangan pernah** membagikan file itu ke siapa pun
- **Jangan upload** folder `data/` ke mana pun
- Folder `data/` sudah otomatis dikecualikan dari git lewat `.gitignore`
- Kalau PC dipakai bersama orang lain, gunakan akun khusus untuk aplikasi ini

**Kalau `data/config.json` tidak sengaja bocor:** segera **logout** dari akun X tersebut di browser (ini membatalkan `auth_token` lama), lalu ambil auth baru.

### Risiko akun dibatasi
Pengambilan data otomatis **melanggar Ketentuan Layanan X**. Akun yang dipakai berisiko dibatasi atau ditangguhkan.

- **Sangat disarankan memakai akun sampingan**, bukan akun utama
- Jangan perkecil **Jeda antar akun** kalau memantau banyak akun
- Aplikasi memakai jeda bertahap + variasi acak agar polanya tidak menyerupai bot

### Privasi
Aplikasi hanya berkomunikasi dengan:
- **x.com** — mengambil postingan
- **twimg.com** — mengambil thumbnail

Telemetry bawaan library `twscrape` (mengirim event ke PostHog, termasuk hash machine-id) **dimatikan** di `app/twitter_client.py`.

Tidak ada data yang dikirim ke server pihak ketiga mana pun.

---

## 10. Backup & pindah komputer

**Seluruh data ada di folder `data/`.**

| Ingin memindahkan | Caranya |
|---|---|
| Auth + pengaturan + daftar akun | Salin `data/config.json` |
| Riwayat postingan | Salin `data/feed.db` |
| Semuanya | Salin seluruh folder `data/` |

> ⚠️ `config.json` memuat auth value. Kalau memindahkannya, pastikan tujuannya aman.

**Menyetel ulang total:** hapus folder `data/`. Aplikasi akan membuatnya lagi dengan pengaturan default (auth, akun & riwayat hilang).
