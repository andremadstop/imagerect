"""Centralized theme helpers and palette for the ImageRect desktop UI."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

BG_DARKEST = "#0d0e12"
BG_DARK = "#1a1b22"
BG_MID = "#24252e"
BG_LIGHTER = "#2e3040"
BORDER = "#3a3c4a"
ACCENT = "#4a9eff"
ACCENT_DIM = "#2d6bbf"
SUCCESS = "#5ec269"
WARNING = "#ffb347"
ERROR = "#ff5353"
TEXT = "#e0e0e8"
TEXT_DIM = "#8888a0"
TEXT_BRIGHT = "#ffffff"


def build_app_font() -> QFont:
    font = QFont()
    font.setFamilies(["Inter", "Segoe UI", "SF Pro", "Sans Serif"])
    font.setPixelSize(13)
    return font


def apply_theme(app: QApplication) -> None:
    app.setFont(build_app_font())
    app.setStyleSheet(build_stylesheet())


def build_stylesheet() -> str:
    return f"""
    QMainWindow, QWidget {{
        background: {BG_DARK};
        color: {TEXT};
        selection-background-color: rgba(74, 158, 255, 50);
        selection-color: {TEXT_BRIGHT};
        font-size: 13px;
    }}
    QMainWindow {{
        background: {BG_DARK};
    }}
    QToolBar {{
        background: {BG_DARK};
        spacing: 4px;
        padding: 6px;
        border: none;
    }}
    QToolBar QToolButton {{
        background: transparent;
        color: {TEXT};
        border: 1px solid transparent;
        border-radius: 6px;
        padding: 8px 14px;
        margin: 0 2px;
    }}
    QToolBar QToolButton:hover {{
        background: {BG_LIGHTER};
        border-color: {BORDER};
    }}
    QToolBar QToolButton:pressed {{
        background: {ACCENT_DIM};
    }}
    QMenuBar {{
        background: {BG_DARK};
        color: {TEXT};
        border: none;
    }}
    QMenuBar::item {{
        background: transparent;
        padding: 6px 10px;
        border-radius: 4px;
    }}
    QMenuBar::item:selected {{
        background: {BG_LIGHTER};
    }}
    QMenu {{
        background: {BG_DARK};
        color: {TEXT};
        border: 1px solid {BORDER};
        padding: 6px;
    }}
    QMenu::item {{
        padding: 8px 16px;
        border-radius: 4px;
    }}
    QMenu::item:selected {{
        background: {ACCENT_DIM};
        color: {TEXT_BRIGHT};
    }}
    QTableWidget {{
        background: {BG_DARK};
        alternate-background-color: {BG_MID};
        color: {TEXT};
        gridline-color: {BORDER};
        border: 1px solid {BORDER};
        border-radius: 6px;
        font-size: 11px;
    }}
    QTableWidget::item {{
        padding: 6px;
        border: none;
    }}
    QTableWidget::item:hover {{
        background: rgba(46, 48, 64, 180);
    }}
    QTableWidget::item:selected {{
        background: rgba(74, 158, 255, 50);
        color: {TEXT_BRIGHT};
    }}
    QHeaderView::section {{
        background: {BG_MID};
        color: {TEXT_BRIGHT};
        padding: 8px;
        border: none;
        border-bottom: 1px solid {BORDER};
        font-size: 12px;
        font-weight: 600;
    }}
    QSplitter::handle {{
        background: {BORDER};
        width: 2px;
        height: 2px;
        margin: 0;
    }}
    QGroupBox {{
        border: 1px solid {BORDER};
        border-radius: 6px;
        margin-top: 14px;
        padding-top: 14px;
        font-size: 13px;
    }}
    QGroupBox::title {{
        color: {TEXT_DIM};
        left: 10px;
        top: -6px;
        padding: 0 4px;
        font-size: 15px;
        font-weight: 600;
    }}
    QScrollBar:vertical, QScrollBar:horizontal {{
        background: transparent;
        border: none;
        margin: 0;
    }}
    QScrollBar:vertical {{
        width: 8px;
    }}
    QScrollBar:horizontal {{
        height: 8px;
    }}
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
        background: {BG_LIGHTER};
        border-radius: 4px;
        min-width: 24px;
        min-height: 24px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line,
    QScrollBar::add-page, QScrollBar::sub-page {{
        background: transparent;
        border: none;
    }}
    QDialog {{
        background: {BG_DARK};
        color: {TEXT};
    }}
    QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit, QListWidget {{
        background: {BG_MID};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 6px 8px;
    }}
    QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QListWidget:focus {{
        border: 1px solid {ACCENT};
    }}
    QPushButton {{
        background: {BG_LIGHTER};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 8px 14px;
    }}
    QPushButton:hover {{
        background: {ACCENT_DIM};
        color: {TEXT_BRIGHT};
    }}
    QPushButton:pressed {{
        background: {ACCENT};
    }}
    QPushButton[primary="true"] {{
        background: {ACCENT};
        border-color: {ACCENT_DIM};
        color: {TEXT_BRIGHT};
    }}
    QPushButton[primary="true"]:hover {{
        background: {ACCENT_DIM};
    }}
    QCheckBox {{
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 3px;
        border: 1px solid {BORDER};
        background: {BG_MID};
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border-color: {ACCENT_DIM};
    }}
    QStatusBar {{
        background: {BG_DARK};
        color: {TEXT_DIM};
        border: none;
    }}
    QStatusBar::item {{
        border: none;
    }}
    QToolTip {{
        background: {BG_MID};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 6px 8px;
    }}
    QFrame#infoSeparator {{
        background: {BORDER};
        min-height: 1px;
        max-height: 1px;
        border: none;
    }}
    """


def make_symbol_icon(symbol: str, size: int = 28) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    font = QFont()
    font.setFamilies(["Inter", "Segoe UI Emoji", "Noto Color Emoji", "Sans Serif"])
    font.setPixelSize(int(size * 0.7))
    painter.setFont(font)
    painter.setPen(QColor(TEXT))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, symbol)
    painter.end()
    return QIcon(pixmap)


def color_for_rms(rms_error: float | None) -> str:
    if rms_error is None:
        return TEXT_DIM
    if rms_error < 1.0:
        return SUCCESS
    if rms_error < 3.0:
        return WARNING
    return ERROR


def color_for_residual(residual: float | None) -> str:
    if residual is None:
        return TEXT_DIM
    if residual < 1.0:
        return SUCCESS
    if residual < 3.0:
        return WARNING
    return ERROR


def icon_size() -> QSize:
    return QSize(28, 28)
