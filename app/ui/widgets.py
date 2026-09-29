"""Komponen UI kecil yang dipakai ulang di beberapa tempat."""

from __future__ import annotations

from datetime import datetime, timezone

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)

# ---------------------------------------------------------------------------
# Format waktu
# ---------------------------------------------------------------------------

def waktu_relatif(iso: str) -> str:
    """Ubah timestamp ISO jadi teks relatif berbahasa Indonesia.

    Contoh: 'baru saja', '5 mnt', '3 jm', '2 hr', '12 Sep'.
    """
    if not iso:
        return ""
    try:
        saat = datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return ""

    if saat.tzinfo is None:
        saat = saat.replace(tzinfo=timezone.utc)

    selisih = (datetime.now(timezone.utc) - saat).total_seconds()

    if selisih < 0:
        # Postingan dengan waktu di masa depan (jam server X meleset) —
        # tampilkan sebagai "baru saja" daripada angka negatif yang membingungkan.
        return "baru saja"
    if selisih < 60:
        return "baru saja"
    if selisih < 3600:
        return f"{int(selisih // 60)} mnt"
    if selisih < 86400:
        return f"{int(selisih // 3600)} jm"
    if selisih < 7 * 86400:
        return f"{int(selisih // 86400)} hr"

    bulan = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
             "Jul", "Agu", "Sep", "Okt", "Nov", "Des")
    if saat.year == datetime.now(timezone.utc).year:
        return f"{saat.day} {bulan[saat.month - 1]}"
    return f"{saat.day} {bulan[saat.month - 1]} {saat.year}"


def waktu_lengkap(iso: str) -> str:
    """Timestamp lengkap untuk tooltip."""
    if not iso:
        return ""
    try:
        saat = datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return iso
    if saat.tzinfo is None:
        saat = saat.replace(tzinfo=timezone.utc)
    lokal = saat.astimezone()
    return lokal.strftime("%d %B %Y, %H:%M:%S")


def angka_ringkas(n: int | None) -> str:
    """Ringkas angka besar: 1.234 -> '1,2 rb', 1_500_000 -> '1,5 jt'."""
    if n is None:
        return "—"
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1000:.1f} rb".replace(".", ",")
    return f"{n / 1_000_000:.1f} jt".replace(".", ",")


# ---------------------------------------------------------------------------
# Label yang bisa diklik
# ---------------------------------------------------------------------------

class LabelKlik(QLabel):
    """QLabel yang memancarkan sinyal saat diklik."""

    diklik = pyqtSignal()

    def __init__(self, teks: str = "", parent: QWidget | None = None) -> None:
        super().__init__(teks, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - API Qt
        if event.button() == Qt.MouseButton.LeftButton:
            self.diklik.emit()
        super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------------
# Badge
# ---------------------------------------------------------------------------

class Badge(QLabel):
    """Label kecil berwarna (mis. 'RETWEET', 'REPLY', jumlah error)."""

    def __init__(self, teks: str = "", warna: str = "#1d9bf0",
                 parent: QWidget | None = None) -> None:
        super().__init__(teks, parent)
        self.set_warna(warna)

    def set_warna(self, warna: str) -> None:
        self.setStyleSheet(
            f"color: {warna};"
            f"border: 1px solid {warna};"
            "border-radius: 7px;"
            "padding: 1px 6px;"
            "font-size: 10px;"
            "font-weight: 700;"
        )


# ---------------------------------------------------------------------------
# Garis pemisah
# ---------------------------------------------------------------------------

def pemisah_horizontal(parent: QWidget | None = None) -> QFrame:
    garis = QFrame(parent)
    garis.setObjectName("pemisah")
    garis.setFrameShape(QFrame.Shape.HLine)
    garis.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return garis


# ---------------------------------------------------------------------------
# Baris "label : nilai"
# ---------------------------------------------------------------------------

class BarisInfo(QWidget):
    """Satu baris informasi: label redup di kiri, nilai di kanan."""

    def __init__(self, label: str, nilai: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        tata = QHBoxLayout(self)
        tata.setContentsMargins(0, 2, 0, 2)
        tata.setSpacing(10)

        self.label = QLabel(label)
        self.label.setMinimumWidth(110)
        self.label.setStyleSheet("color: #8b98a5;")

        self.nilai = QLabel(nilai)
        self.nilai.setWordWrap(True)
        self.nilai.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.nilai.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        tata.addWidget(self.label)
        tata.addWidget(self.nilai, 1)

    def set_nilai(self, teks: str) -> None:
        self.nilai.setText(teks)
