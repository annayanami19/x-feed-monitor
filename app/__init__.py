"""x-feed-monitor — feed gabungan X/Twitter multi-akun.

Nilai versi di sini adalah SUMBER KEBENARAN untuk seluruh aplikasi.
Saat merilis versi baru:

  1. Ubah `__version__` di file ini
  2. Catat perubahannya di CHANGELOG.md
  3. Beri tag git dengan format `v<versi>` (mis. `v1.0.0`)

Versi mengikuti Semantic Versioning (https://semver.org/):
  MAJOR — perubahan yang membuat cara pakai / config lama tidak kompatibel
  MINOR — fitur baru, tetap kompatibel dengan versi sebelumnya
  PATCH — perbaikan bug, tanpa mengubah cara pakai
"""

from __future__ import annotations

__version__ = "1.0.0"
__app_name__ = "X Feed Monitor"
__author__ = "x-feed-monitor contributors"
__license__ = "MIT"
__url__ = "https://github.com/annayanami19/x-feed-monitor"


def versi_lengkap() -> str:
    """Teks versi untuk ditampilkan di UI (mis. judul jendela)."""
    return f"{__app_name__} v{__version__}"
