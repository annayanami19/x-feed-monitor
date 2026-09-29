"""Tema tampilan: Dark & Light.

Ditulis sebagai QSS (Qt Style Sheet) yang di-inject ke QApplication.
Paletnya sengaja dipisah dari QSS-nya supaya komponen Python (mis. delegate
yang menggambar kartu sendiri) bisa memakai warna yang sama — kalau warna
hanya hidup di dalam string QSS, delegate tidak bisa membacanya.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palet:
    """Kumpulan warna satu tema."""

    nama: str

    latar: str              # latar jendela
    latar_alt: str          # latar panel / sidebar
    kartu: str              # latar kartu postingan
    kartu_hover: str        # kartu saat disorot mouse
    kartu_pilih: str        # kartu terpilih
    garis: str              # garis pemisah / border

    teks: str               # teks utama
    teks_redup: str         # teks sekunder (waktu, angka)
    teks_samar: str         # teks tersier

    aksen: str              # warna utama (tombol, highlight)
    aksen_teks: str         # teks di atas warna aksen
    sukses: str
    peringatan: str
    bahaya: str

    retweet: str            # warna badge retweet
    reply: str              # warna badge reply


DARK = Palet(
    nama="dark",
    latar="#0f1419",
    latar_alt="#161b22",
    kartu="#1a2028",
    kartu_hover="#212a33",
    kartu_pilih="#24303d",
    garis="#2a333d",
    teks="#e7edf3",
    teks_redup="#8b98a5",
    teks_samar="#5f6b78",
    aksen="#1d9bf0",
    aksen_teks="#ffffff",
    sukses="#00ba7c",
    peringatan="#ffad1f",
    bahaya="#f4212e",
    retweet="#00ba7c",
    reply="#1d9bf0",
)

LIGHT = Palet(
    nama="light",
    latar="#f7f9fa",
    latar_alt="#ffffff",
    kartu="#ffffff",
    kartu_hover="#f2f5f7",
    kartu_pilih="#e6f2fb",
    garis="#dde3e8",
    teks="#0f1419",
    teks_redup="#5b6b7b",
    teks_samar="#8b98a5",
    aksen="#1d9bf0",
    aksen_teks="#ffffff",
    sukses="#00a86b",
    peringatan="#e08a00",
    bahaya="#d92027",
    retweet="#00a86b",
    reply="#1d9bf0",
)

PALET: dict[str, Palet] = {"dark": DARK, "light": LIGHT}


def ambil_palet(nama: str) -> Palet:
    return PALET.get(nama, DARK)


# ---------------------------------------------------------------------------
# QSS
# ---------------------------------------------------------------------------

def qss(nama: str) -> str:
    """Bangun stylesheet lengkap untuk sebuah tema."""
    p = ambil_palet(nama)

    return f"""
/* ===================== Dasar ===================== */
QWidget {{
    background: {p.latar};
    color: {p.teks};
    font-family: "Segoe UI", "Inter", system-ui, sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog {{
    background: {p.latar};
}}
QToolTip {{
    background: {p.latar_alt};
    color: {p.teks};
    border: 1px solid {p.garis};
    border-radius: 6px;
    padding: 6px 8px;
}}

/* ===================== Tombol ===================== */
QPushButton {{
    background: {p.latar_alt};
    color: {p.teks};
    border: 1px solid {p.garis};
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 500;
}}
QPushButton:hover {{
    background: {p.kartu_hover};
    border-color: {p.aksen};
}}
QPushButton:pressed {{
    background: {p.kartu_pilih};
}}
QPushButton:disabled {{
    color: {p.teks_samar};
    border-color: {p.garis};
    background: {p.latar};
}}
QPushButton#utama {{
    background: {p.aksen};
    color: {p.aksen_teks};
    border: none;
    font-weight: 600;
}}
QPushButton#utama:hover {{
    background: {p.aksen};
    opacity: 0.9;
}}
QPushButton#utama:disabled {{
    background: {p.garis};
    color: {p.teks_samar};
}}
QPushButton#bahaya {{
    background: transparent;
    color: {p.bahaya};
    border: 1px solid {p.bahaya};
}}
QPushButton#bahaya:hover {{
    background: {p.bahaya};
    color: #ffffff;
}}
QPushButton#ikon {{
    padding: 6px 9px;
    min-width: 18px;
}}

/* ===================== Input ===================== */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {{
    background: {p.latar_alt};
    color: {p.teks};
    border: 1px solid {p.garis};
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: {p.aksen};
    selection-color: {p.aksen_teks};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QComboBox:focus {{
    border-color: {p.aksen};
}}
QLineEdit::placeholder {{
    color: {p.teks_samar};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: {p.latar_alt};
    color: {p.teks};
    border: 1px solid {p.garis};
    selection-background-color: {p.kartu_pilih};
    selection-color: {p.teks};
    outline: none;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background: {p.latar_alt};
    border: none;
    width: 16px;
}}

/* ===================== Daftar & Tabel ===================== */
QListView, QTableView, QTreeView {{
    background: {p.latar};
    border: none;
    outline: none;
}}
QListView::item {{
    border: none;
}}
QHeaderView::section {{
    background: {p.latar_alt};
    color: {p.teks_redup};
    border: none;
    border-bottom: 1px solid {p.garis};
    padding: 7px 10px;
    font-weight: 600;
}}

/* ===================== Panel samping ===================== */
QFrame#panelFilter {{
    background: {p.latar_alt};
    border-right: 1px solid {p.garis};
}}
QLabel#judulPanel {{
    color: {p.teks_redup};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.6px;
}}

/* ===================== Kartu akun di panel ===================== */
QListWidget#daftarAkun {{
    background: transparent;
    border: none;
}}
QListWidget#daftarAkun::item {{
    padding: 7px 8px;
    border-radius: 7px;
    margin: 1px 2px;
}}
QListWidget#daftarAkun::item:hover {{
    background: {p.kartu_hover};
}}
QListWidget#daftarAkun::item:selected {{
    background: {p.kartu_pilih};
    color: {p.teks};
}}

/* ===================== Toolbar ===================== */
QToolBar {{
    background: {p.latar_alt};
    border: none;
    border-bottom: 1px solid {p.garis};
    padding: 6px 8px;
    spacing: 6px;
}}
QToolBar QLabel {{
    color: {p.teks_redup};
    padding: 0 4px;
}}

/* ===================== Status bar ===================== */
QStatusBar {{
    background: {p.latar_alt};
    color: {p.teks_redup};
    border-top: 1px solid {p.garis};
}}
QStatusBar::item {{
    border: none;
}}

/* ===================== Scrollbar ===================== */
QScrollBar:vertical {{
    background: transparent;
    width: 11px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {p.garis};
    border-radius: 5px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background: {p.teks_samar};
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 11px;
}}
QScrollBar::handle:horizontal {{
    background: {p.garis};
    border-radius: 5px;
    min-width: 32px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0; width: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}

/* ===================== Lain-lain ===================== */
QSplitter::handle {{
    background: {p.garis};
    width: 1px;
}}
QCheckBox, QRadioButton {{
    spacing: 8px;
    padding: 3px 0;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {p.garis};
    border-radius: 4px;
    background: {p.latar_alt};
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {p.aksen};
    border-color: {p.aksen};
}}
QRadioButton::indicator {{
    border-radius: 8px;
}}
QMenu {{
    background: {p.latar_alt};
    color: {p.teks};
    border: 1px solid {p.garis};
    border-radius: 8px;
    padding: 5px;
}}
QMenu::item {{
    padding: 7px 22px 7px 14px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {p.kartu_pilih};
}}
QMenu::separator {{
    height: 1px;
    background: {p.garis};
    margin: 5px 8px;
}}
QTabWidget::pane {{
    border: 1px solid {p.garis};
    border-radius: 8px;
}}
QTabBar::tab {{
    background: {p.latar_alt};
    color: {p.teks_redup};
    padding: 8px 16px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {p.kartu};
    color: {p.teks};
}}
QGroupBox {{
    border: 1px solid {p.garis};
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 10px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: {p.teks_redup};
}}
QProgressBar {{
    background: {p.latar_alt};
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {p.aksen};
    border-radius: 4px;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QFrame#pemisah {{
    background: {p.garis};
    max-height: 1px;
}}
"""
