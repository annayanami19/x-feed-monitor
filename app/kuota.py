"""Pemantau pemakaian kuota X.

MASALAH YANG DIPECAHKAN
=======================
Rate-limit X tidak terlihat dari dalam aplikasi — pengguna baru tahu setelah
kena, dan saat itu sudah terlambat: semua akun berhenti diperbarui sampai
batasnya di-reset (±15 menit).

Modul ini membuat pemakaian itu TERLIHAT sebelum menjadi masalah:

  * menghitung berapa request yang dipakai aplikasi sendiri
  * membandingkan dengan batas yang diketahui
  * memperkirakan kapan batasnya akan tercapai pada laju sekarang
  * memberi peringatan saat pemakaian sudah tinggi

MENGAPA MENGHITUNG SENDIRI, BUKAN MEMBACA DARI twscrape
=======================================================
twscrape menyimpan jumlah request di database pool-nya, tapi angkanya
KUMULATIF (terus bertambah sejak pool dibuat) — tidak bisa dipakai untuk
menjawab "berapa request per jam sekarang?". Kita perlu angka per JENDELA
WAKTU, jadi aplikasi mencatat sendiri waktu tiap request.

BATAS YANG DIPAKAI
==================
X membatasi per endpoint per 15 menit. Angka di bawah adalah yang lazim
untuk endpoint publik X; kalau X mengubahnya, angka ini hanya memengaruhi
KETEPATAN PERINGATAN — bukan jalannya aplikasi (aplikasi tetap menangani
rate-limit sungguhan lewat pesan error dari X).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

#: Jendela waktu rate-limit X (detik). X menghitung per 15 menit.
JENDELA_DETIK = 15 * 60

#: Perkiraan batas request per endpoint per 15 menit.
#: Angka konservatif — lebih baik memperingatkan terlalu awal daripada
#: terlambat, karena kena limit berarti semua akun berhenti.
BATAS_ENDPOINT: dict[str, int] = {
    "UserTweets": 400,
    "UserByScreenName": 90,
}

#: Ambang peringatan (persentase dari batas).
AMBANG_PERINGATAN = 60.0
AMBANG_BAHAYA = 85.0


@dataclass
class StatusKuota:
    """Ringkasan pemakaian kuota pada jendela waktu sekarang."""

    total: int = 0
    per_endpoint: dict[str, int] = None  # type: ignore[assignment]
    batas_terdekat: str = ""            # endpoint dengan pemakaian tertinggi
    persen_tertinggi: float = 0.0
    perkiraan_habis_menit: float | None = None
    tingkat: str = "aman"               # aman | peringatan | bahaya

    def __post_init__(self) -> None:
        if self.per_endpoint is None:
            self.per_endpoint = {}

    def ringkas(self) -> str:
        """Teks singkat untuk statusbar."""
        if self.total == 0:
            return "kuota: belum ada request"

        # "0%" menyesatkan — pembulatan menyembunyikan request yang
        # nyata-nya ada. Tampilkan "<1%" sampai angkanya cukup besar.
        if self.persen_tertinggi < 1.0:
            persen = "<1%"
        else:
            persen = f"{self.persen_tertinggi:.0f}%"
        teks = f"kuota: {persen} ({self.batas_terdekat})"

        if self.perkiraan_habis_menit is not None and self.tingkat != "aman":
            teks += f" · penuh ~{self.perkiraan_habis_menit:.0f} mnt lagi"

        return teks

    def saran(self) -> str:
        """Saran tindakan untuk tooltip."""
        if self.tingkat == "aman":
            return (
                "Pemakaian kuota masih rendah.\n\n"
                f"{self._rincian()}"
            )

        baris = [
            f"Pemakaian kuota sudah {self.persen_tertinggi:.0f}% "
            f"pada endpoint {self.batas_terdekat}.",
            "",
        ]

        if self.perkiraan_habis_menit is not None:
            baris.append(
                f"Dengan laju sekarang, batasnya tercapai dalam "
                f"±{self.perkiraan_habis_menit:.0f} menit."
            )
            baris.append("")

        baris.extend([
            "Untuk memperlambat:",
            "  • Perpanjang Interval otomatis di Pengaturan",
            "  • Kurangi Postingan per akun (di atas 40 menambah request)",
            "  • Kurangi jumlah akun yang dipantau",
            "",
            self._rincian(),
        ])
        return "\n".join(baris)

    def _rincian(self) -> str:
        bagian = [f"Request dalam 15 menit terakhir: {self.total}"]
        for nama, jumlah in sorted(
            self.per_endpoint.items(), key=lambda x: -x[1]
        ):
            batas = BATAS_ENDPOINT.get(nama)
            if batas:
                bagian.append(f"  • {nama}: {jumlah}/{batas}")
            else:
                bagian.append(f"  • {nama}: {jumlah}")
        return "\n".join(bagian)


class PemantauKuota:
    """Mencatat waktu request dan menghitung pemakaian pada jendela waktu.

    Pemakaian: panggil `catat()` setiap kali satu request ke X selesai.
    Panggil `status()` kapan saja untuk mendapatkan ringkasannya.
    """

    def __init__(self) -> None:
        #: Waktu setiap request (monotonic), dipisah per endpoint.
        #: `deque` dipakai supaya yang sudah kedaluwarsa bisa dibuang dari
        #: depan tanpa memindai seluruh isinya.
        self._catatan: dict[str, deque[float]] = {}

    # ------------------------------------------------------------------
    def catat(self, endpoint: str = "UserTweets") -> None:
        """Catat satu request ke sebuah endpoint."""
        waktu = self._catatan.setdefault(endpoint, deque())
        waktu.append(time.monotonic())
        self._buang_kedaluwarsa(endpoint)

    def catat_banyak(self, jumlah: int, endpoint: str = "UserTweets") -> None:
        """Catat beberapa request sekaligus (dipakai saat membaca ulang)."""
        if jumlah <= 0:
            return
        waktu = self._catatan.setdefault(endpoint, deque())
        sekarang = time.monotonic()
        for _ in range(jumlah):
            waktu.append(sekarang)
        self._buang_kedaluwarsa(endpoint)

    def _buang_kedaluwarsa(self, endpoint: str) -> None:
        """Buang catatan yang sudah keluar dari jendela waktu."""
        waktu = self._catatan.get(endpoint)
        if not waktu:
            return
        batas = time.monotonic() - JENDELA_DETIK
        while waktu and waktu[0] < batas:
            waktu.popleft()

    # ------------------------------------------------------------------
    def status(self) -> StatusKuota:
        """Hitung pemakaian pada jendela waktu sekarang."""
        per_endpoint: dict[str, int] = {}
        for endpoint in list(self._catatan):
            self._buang_kedaluwarsa(endpoint)
            jumlah = len(self._catatan.get(endpoint, ()))
            if jumlah:
                per_endpoint[endpoint] = jumlah

        status = StatusKuota(per_endpoint=per_endpoint)
        status.total = sum(per_endpoint.values())

        # Endpoint dengan pemakaian tertinggi (relatif terhadap batasnya)
        # yang menentukan tingkat keparahan — bukan totalnya.
        for nama, jumlah in per_endpoint.items():
            batas = BATAS_ENDPOINT.get(nama)
            if not batas:
                continue
            persen = jumlah / batas * 100.0
            if persen > status.persen_tertinggi:
                status.persen_tertinggi = persen
                status.batas_terdekat = nama

        if status.persen_tertinggi >= AMBANG_BAHAYA:
            status.tingkat = "bahaya"
        elif status.persen_tertinggi >= AMBANG_PERINGATAN:
            status.tingkat = "peringatan"

        status.perkiraan_habis_menit = self._perkirakan_habis(
            per_endpoint, status.batas_terdekat
        )
        return status

    def _perkirakan_habis(
        self, per_endpoint: dict[str, int], endpoint: str
    ) -> float | None:
        """Perkirakan berapa menit lagi batas endpoint ini tercapai.

        Dihitung dari LAJU sekarang, bukan dari total. Mengembalikan None
        bila laju masih nol atau endpoint tidak punya batas yang diketahui.
        """
        batas = BATAS_ENDPOINT.get(endpoint)
        jumlah = per_endpoint.get(endpoint, 0)
        if not batas or jumlah <= 0 or jumlah >= batas:
            return None

        # Laju = jumlah request dibagi panjang jendela yang sudah berjalan.
        # Jendela dianggap penuh (15 menit) supaya perkiraannya konservatif:
        # pada awal pemakaian, laju terlihat lebih tinggi daripada kenyataan,
        # sehingga peringatan muncul lebih awal.
        laju_per_menit = jumlah / (JENDELA_DETIK / 60.0)
        if laju_per_menit <= 0:
            return None

        sisa = batas - jumlah
        return sisa / laju_per_menit

    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Kosongkan catatan (dipakai saat kredensial berganti)."""
        self._catatan.clear()

    def ada_data(self) -> bool:
        """True bila sudah ada request yang tercatat."""
        return any(self._catatan.values())
