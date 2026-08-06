from datetime import datetime
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from models.client import Client
from ui.theme import CARD_BG, CARD_HOVER, BORDER_COLOR, TEXT_PRIMARY, TEXT_MUTED, ACCENT


class ClientCard(QFrame):
    """Reusable Client Card component for Client Workspace landing view.

    Displays company logo placeholder, status badge, client type, projects/contacts counts,
    pin icon placeholder, accent strip, last updated timestamp, and Open action button.
    """

    clicked = Signal(object)
    open_requested = Signal(object)
    pin_toggled = Signal(object)

    STATUS_COLORS = {
        "active": "#38BDF8",      # Bright Cyan / Blue
        "returning": "#818CF8",   # Indigo
        "negotiation": "#FBBF24", # Amber
        "conversation": "#A7F3D0",# Mint
        "prospect": "#F59E0B",   # Orange
        "reached out": "#EAB308",# Yellow
        "completed": "#34D399",  # Green
        "archived": "#94A3B8",   # Slate Gray
    }

    def __init__(self, client: Client, parent=None):
        super().__init__(parent)
        self.client = client
        self._hovered = False

        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(220)
        self.setMaximumWidth(320)

        self._init_ui()
        self._update_appearance()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # 1. Top Accent Color Strip & Pin Placeholder Header
        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        # Accent Bar Indicator
        status_key = str(self.client.status or "Active").lower()
        accent_color = self.STATUS_COLORS.get(status_key, "#38BDF8")

        accent_strip = QFrame()
        accent_strip.setFixedSize(12, 12)
        accent_strip.setStyleSheet(f"background-color: {accent_color}; border-radius: 6px;")
        header_row.addWidget(accent_strip)

        # Company Logo Placeholder
        logo_lbl = QLabel("🏢")
        logo_lbl.setFont(QFont("Segoe UI", 12))
        header_row.addWidget(logo_lbl)

        # Company Name
        name_text = self.client.name if self.client.name else "Untitled Client"
        self.title_lbl = QLabel(name_text)
        self.title_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.title_lbl.setStyleSheet(f"color: {TEXT_PRIMARY};")
        self.title_lbl.setToolTip(name_text)
        header_row.addWidget(self.title_lbl, 1)

        # Pin / Favorite Icon Placeholder
        self.pin_btn = QPushButton("📌")
        self.pin_btn.setFixedSize(22, 22)
        self.pin_btn.setToolTip("Pin to top")
        self.pin_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 11px;
                color: #64748B;
            }
            QPushButton:hover {
                color: #F59E0B;
            }
        """)
        self.pin_btn.clicked.connect(lambda: self.pin_toggled.emit(self.client))
        header_row.addWidget(self.pin_btn)

        main_layout.addLayout(header_row)

        # 2. Status Badge & Client Type Row
        badge_row = QHBoxLayout()
        badge_row.setSpacing(6)

        status_str = str(self.client.status or "Active").upper()
        self.status_badge = QLabel(status_str)
        self.status_badge.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self.status_badge.setStyleSheet(f"""
            QLabel {{
                background-color: #1E2029;
                color: {accent_color};
                border: 1px solid {accent_color};
                border-radius: 4px;
                padding: 2px 6px;
            }}
        """)
        badge_row.addWidget(self.status_badge)

        type_str = str(self.client.client_type or "Game Studio")
        self.type_lbl = QLabel(type_str)
        self.type_lbl.setFont(QFont("Segoe UI", 8))
        self.type_lbl.setStyleSheet(f"color: {TEXT_MUTED};")
        badge_row.addWidget(self.type_lbl)
        badge_row.addStretch()

        main_layout.addLayout(badge_row)

        # 3. Metrics Summary (Projects & Contacts)
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(12)

        proj_count = len(self.client.project_ids) if self.client.project_ids else 0
        self.proj_lbl = QLabel(f"📁 {proj_count} Project{'s' if proj_count != 1 else ''}")
        self.proj_lbl.setFont(QFont("Segoe UI", 9))
        self.proj_lbl.setStyleSheet("color: #CBD5E1;")
        metrics_row.addWidget(self.proj_lbl)

        cont_count = len(self.client.contacts) if self.client.contacts else 0
        self.cont_lbl = QLabel(f"👤 {cont_count} Contact{'s' if cont_count != 1 else ''}")
        self.cont_lbl.setFont(QFont("Segoe UI", 9))
        self.cont_lbl.setStyleSheet("color: #CBD5E1;")
        metrics_row.addWidget(self.cont_lbl)
        metrics_row.addStretch()

        main_layout.addLayout(metrics_row)

        # 4. Bottom Row: Last Updated & Open Button
        bottom_row = QHBoxLayout()

        updated_dt = self.client.modified if hasattr(self.client, "modified") else datetime.now()
        updated_str = updated_dt.strftime("%b %d") if hasattr(updated_dt, "strftime") else str(updated_dt)[:10]
        self.updated_lbl = QLabel(f"Updated {updated_str}")
        self.updated_lbl.setFont(QFont("Segoe UI", 8))
        self.updated_lbl.setStyleSheet(f"color: {TEXT_MUTED};")
        bottom_row.addWidget(self.updated_lbl)
        bottom_row.addStretch()

        self.open_btn = QPushButton("Open")
        self.open_btn.setStyleSheet("""
            QPushButton {
                background-color: #2E3342;
                color: #F1F5F9;
                border: 1px solid #343847;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #38BDF8;
                color: #0F172A;
            }
        """)
        self.open_btn.clicked.connect(lambda: self.open_requested.emit(self.client))
        bottom_row.addWidget(self.open_btn)

        main_layout.addLayout(bottom_row)

    def _update_appearance(self):
        if self._hovered:
            self.setStyleSheet(f"""
                ClientCard {{
                    background-color: {CARD_HOVER};
                    border: 1px solid #38BDF8;
                    border-radius: 8px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                ClientCard {{
                    background-color: {CARD_BG};
                    border: 1px solid {BORDER_COLOR};
                    border-radius: 8px;
                }}
            """)

    def enterEvent(self, event):
        self._hovered = True
        self._update_appearance()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._update_appearance()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.client)
            event.accept()
            return
        super().mousePressEvent(event)
