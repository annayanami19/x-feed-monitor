# Changelog

Semua perubahan penting pada proyek ini didokumentasikan di file ini.

Format mengikuti [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
dan proyek ini mengikuti [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Jenis perubahan: `Ditambahkan` · `Diubah` · `Usang` · `Dihapus` · `Diperbaiki` · `Keamanan`

---

## [Unreleased]

### Ditambahkan
- (belum ada)

---

## [1.0.0] - 2026-09-29

Rilis pertama. Aplikasi desktop untuk memantau postingan dari banyak akun X
dalam satu feed gabungan.

### Ditambahkan

**Fitur utama**
- Feed gabungan: postingan dari semua akun yang dipantau dalam satu halaman,
  diurutkan berdasarkan waktu
- Kredensial utama diisi sekali di Pengaturan; menambah akun cukup username
- Tambah banyak akun sekaligus — tempel daftar username dipisah baris baru,
  koma, atau spasi (URL profil juga dikenali)
- Kredensial khusus per akun (opsional) untuk akun yang butuh auth berbeda,
  mis. akun private yang hanya di-follow akun X kedua
- Auto-poll dengan interval yang bisa diatur (1–60 menit) + tombol Refresh manual
- Jeda bertahap antar akun (default 3 detik, dengan variasi acak) untuk
  menghindari pola request yang menyerupai bot

**Filter**
- Pencarian keyword dengan dukungan frasa dalam tanda kutip (`"machine learning"`)
- Pilih akun lewat centang di panel kiri (tombol Semua / Kosong)
- Sembunyikan retweet · sembunyikan reply
- Filter periode: hari ini / 3 / 7 / 30 / 90 hari / semua waktu
- Semua pilihan filter tersimpan otomatis antar sesi

**Riwayat**
- Penyimpanan lokal SQLite dengan deduplikasi berdasarkan `tweet_id`
- Masa simpan yang bisa diatur (7–365 hari, atau selamanya)
- Pembersihan otomatis saat aplikasi dibuka + tombol bersihkan manual
- Angka statistik (like, retweet, balasan, dilihat) diperbarui tiap siklus

**Tampilan**
- Tema gelap dan terang, bisa diganti dari toolbar
- Kartu postingan dengan thumbnail gambar/video (maks. 4 media per postingan)
- Badge `RETWEET` dan `REPLY` pada kartu
- Teks postingan bisa diblok & di-copy seperti di browser
  (`Ctrl+C` menyalin blok, `Ctrl+A` memblok semua, `Esc` membatalkan)
- Tautan di dalam postingan bisa diklik, dengan konfirmasi berisi domain tujuan
- Panel detail di sisi kanan (klik dua kali kartu atau `Enter`)
- Klik kanan kartu: Buka di browser · Copy link · Copy teks · Lihat detail
- Notifikasi desktop untuk postingan baru saja, dengan opsi membatasi ke
  akun yang sedang ditampilkan
- Status per akun di panel filter (berhasil / error / nonaktif) beserta
  pesan error di tooltip

**Penanganan masalah**
- Pesan error berbahasa Indonesia dengan saran tindakan, bukan stack trace
- Pengklasifikasian error: kredensial kedaluwarsa, rate-limit, query ID
  berubah, akun dibatasi, akun tidak ditemukan, akun private, gangguan koneksi
- `run.bat` (launcher), `run-debug.bat` (dengan console), dan `update.bat`
  (memperbarui mesin pengambil data saat X merotasi endpoint)
- `run.bat` membuat virtual environment dan memasang komponen secara otomatis;
  pemasangan ulang hanya terjadi bila `requirements.txt` berubah
- Log internal library tersimpan di `data/logs/twscrape.log` (dipotong otomatis
  di 2 MB)

**Keamanan & privasi**
- Seluruh data runtime terpusat di `data/` yang dikecualikan dari git
- Telemetry bawaan `twscrape` (PostHog) dimatikan lewat `TWS_TELEMETRY=0`
- Backend HTTP `curl_cffi` untuk menyerupai TLS fingerprint browser asli

### Diperbaiki

Bug yang ditemukan dan diperbaiki sebelum rilis pertama:

- **Aplikasi tidak bisa dibuka lewat `run.bat`** — `pythonw.exe` tidak punya
  console sehingga `sys.stdout`/`sys.stderr` bernilai `None`, dan impor
  `twscrape` gagal total dengan `TypeError: Cannot log to objects of type
  'NoneType'`. Diperbaiki lewat `app/compat.py` yang mengganti stream kosong
  dengan handle file log sebelum library diimpor. Aplikasi tetap bisa dibuka
  lewat `run-debug.bat` karena launcher itu memakai `python.exe`.
- **Teks postingan menabrak avatar** — tinggi header (24px) lebih pendek dari
  tinggi avatar (38px), sehingga isi postingan mulai 8px sebelum avatar
  selesai digambar. Jaraknya sekarang dihitung dari nilai maksimum keduanya.
- **Blok teks hilang saat Qt mengukur ulang** — pengukuran tinggi kartu
  memakai dokumen teks yang sama dengan yang dipakai menggambar, sehingga
  seleksi aktif tertimpa. Sekarang memakai dua dokumen terpisah.
- **File pool menumpuk di `data/pools/`** — tombol "Uji Koneksi" membuat
  akun sementara dengan id acak, meninggalkan satu file database setiap kali
  ditekan. Sekarang memakai id tetap `_uji` yang dihapus setelah pengujian.
- **Pelacakan rate-limit tidak akurat** — setiap akun target diberi pool
  sendiri walau kredensialnya sama, sehingga aplikasi mengira punya banyak
  kuota padahal kenyataannya satu akun X. Akun yang berbagi kredensial kini
  juga berbagi satu pool.
- **Akun yang dibatalkan centangnya menyembunyikan semua akun** — daftar
  kosong punya arti ganda ("tanpa batasan" vs "tidak ada yang dipilih").
  Dipisahkan lewat flag `semua_akun`.
- **Config baru tidak terbentuk saat aplikasi pertama dibuka** — file
  `data/config.json` kini ditulis sejak awal supaya lokasinya jelas.
- **Tidak ada penanganan `QSizeF` pada `setPageSize`** — dokumen teks gagal
  dibangun; `setPageSize` memerlukan `QSizeF`, bukan `QSize`.
- **`PaintContext.palette.setColor()` dipanggil dengan argumen salah** —
  render kartu gagal; `setColor` memerlukan pasangan (peran, warna).
- **Scroll kembali ke atas setiap siklus polling** — pembacaan ulang feed
  kini mempertahankan posisi scroll.
- **Feed dibaca ulang puluhan kali per siklus** — satu siklus memancarkan
  hasil per akun; pembacaan ulang kini digabungkan dengan penundaan 400 ms.
- **Daftar akun di panel tidak terisi saat aplikasi dibuka** — hanya terisi
  setelah polling pertama selesai.
- **Panel detail tampil di bawah feed, bukan di samping** — tata letaknya
  memakai layout vertikal, seharusnya horizontal.

### Keamanan

- Kredensial disimpan **tanpa enkripsi** di `data/config.json` (pilihan desain
  demi kesederhanaan). Folder `data/` dikecualikan dari git lewat `.gitignore`,
  dan hal ini didokumentasikan di README serta panduan pakai.
- Peringatan risiko akun: pengambilan data otomatis melanggar Ketentuan
  Layanan X. README menyarankan memakai akun sampingan, bukan akun utama.
- Telemetry pihak ketiga dari `twscrape` dinonaktifkan sebelum library diimpor.

---

## Catatan untuk versi berikutnya

Saat menambah perubahan baru:

1. Tulis di bagian `[Unreleased]` dengan jenis yang sesuai
2. Saat merilis, ubah `[Unreleased]` menjadi `[X.Y.Z] - YYYY-MM-DD`
   dan tambahkan `[Unreleased]` baru di atasnya
3. Perbarui `__version__` di `app/__init__.py`
4. Tambahkan tautan perbandingan di bagian bawah file ini

Panduan versi ([Semantic Versioning](https://semver.org/spec/v2.0.0.html)):

| Perubahan | Versi |
|---|---|
| Perbaikan bug, tanpa mengubah cara pakai | `PATCH` (1.0.**1**) |
| Fitur baru, tetap kompatibel | `MINOR` (1.**1**.0) |
| Mengubah cara pakai / config lama tidak kompatibel | `MAJOR` (**2**.0.0) |

---

[Unreleased]: https://github.com/annayanami19/x-feed-monitor/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/annayanami19/x-feed-monitor/releases/tag/v1.0.0
