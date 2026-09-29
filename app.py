"""x-feed-monitor — titik masuk aplikasi.

Jalankan lewat run.bat (mode normal) atau run-debug.bat (dengan console).

Semua error yang tidak tertangani ditulis ke error.log di folder aplikasi
SEKALIGUS ditampilkan sebagai dialog — karena mode normal dijalankan dengan
pythonw (tanpa console), error yang hanya dicetak ke stderr akan hilang
tanpa jejak.
"""

from __future__ import annotations

import sys
import traceback

# --- path: pastikan folder aplikasi bisa diimpor walau dijalankan dari mana pun
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.compat import pastikan_std_stream  # noqa: E402
from app.paths import ERROR_LOG, pastikan_folder  # noqa: E402

# Jalankan SEBELUM impor apa pun yang memakai logging.
#
# run.bat memakai pythonw.exe (tanpa console) sehingga sys.stderr bernilai
# None. twscrape memanggil logger.add(sys.stderr) saat diimpor dan akan crash
# bila stderr masih None. Lihat app/compat.py untuk penjelasan lengkapnya.
pastikan_std_stream()


def _tulis_error(teks: str) -> None:
    """Simpan jejak error ke error.log (best effort)."""
    try:
        with ERROR_LOG.open("a", encoding="utf-8", newline="\n") as berkas:
            berkas.write(teks)
            if not teks.endswith("\n"):
                berkas.write("\n")
    except OSError:
        pass


def main() -> int:
    """Jalankan aplikasi. Mengembalikan kode keluar."""
    from PyQt6.QtWidgets import QApplication, QMessageBox

    from app import __app_name__, __version__

    pastikan_folder()

    # --- Aplikasi Qt ---
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("x-feed-monitor")

    # Tutup aplikasi saat jendela terakhir ditutup (perilaku yang diharapkan
    # untuk aplikasi desktop biasa).
    app.setQuitOnLastWindowClosed(True)

    try:
        from app.ui.main_window import JendelaUtama

        jendela = JendelaUtama()
        jendela.show()
        return app.exec()

    except Exception:
        teks = traceback.format_exc()
        _tulis_error(teks)
        try:
            QMessageBox.critical(
                None,
                "X Feed Monitor — Error",
                "Aplikasi gagal dijalankan.\n\n"
                f"Detail teknis sudah disimpan di:\n{ERROR_LOG}\n\n"
                "--- cuplikan ---\n" + teks[-1500:],
            )
        except Exception:  # noqa: BLE001 - dialog pun bisa gagal; jangan menutupi error asli
            pass
        raise


if __name__ == "__main__":
    sys.exit(main())
