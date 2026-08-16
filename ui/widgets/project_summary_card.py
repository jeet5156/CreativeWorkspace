"""Reusable summary card and availability widgets for the Project Dashboard."""

from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor

from ui.theme import (
    CARD_BG,
    CARD_HOVER,
    BORDER_COLOR,
    TEXT_PRIMARY,
    TEXT_MUTED,
    ACCENT,
)


class ProjectMetricCard(QFrame):
    """Clean metric card displaying a top-level workspace count (e.g. KNOWLEDGE, ASSETS, LIBRARY, LAB)."""

    clicked = Signal()

    def __init__(
        self,
        title: str,
        icon: str = "📁",
        count: int = 0,
        subtitle: str = "",
        accent_color: str = ACCENT,
        parent: QWidget = None,
    ):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.accent_color = accent_color

        self.setStyleSheet(f"""
            ProjectMetricCard {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 12px;
            }}
            ProjectMetricCard:hover {{
                background-color: {CARD_HOVER};
                border: 1px solid {accent_color};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        # Header row: Icon & Title
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        self.icon_lbl = QLabel(icon)
        self.icon_lbl.setStyleSheet("font-size: 16px;")
        header_row.addWidget(self.icon_lbl)

        self.title_lbl = QLabel(title.upper())
        self.title_lbl.setStyleSheet(f"""
            color: {TEXT_MUTED};
            font-size: 11px;
            font-weight: bold;
            letter-spacing: 0.8px;
        """)
        header_row.addWidget(self.title_lbl)
        header_row.addStretch()

        layout.addLayout(header_row)

        # Large Count
        self.count_lbl = QLabel(str(count))
        self.count_lbl.setStyleSheet(f"""
            color: {TEXT_PRIMARY};
            font-size: 28px;
            font-weight: bold;
        """)
        layout.addWidget(self.count_lbl)

        # Subtitle / Hint
        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(self.sub_lbl)

    def set_count(self, count: int, subtitle: str = None):
        self.count_lbl.setText(str(count))
        if subtitle is not None:
            self.sub_lbl.setText(subtitle)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class AvailabilityItemWidget(QFrame):
    """Clickable single availability status row (e.g. 🟢 Available  18)."""

    clicked = Signal(str)

    def __init__(
        self,
        status_key: str,
        label: str,
        icon: str,
        count: int = 0,
        badge_bg: str = "#14382B",
        badge_text: str = "#34D399",
        parent: QWidget = None,
    ):
        super().__init__(parent)
        self.status_key = status_key
        self.setCursor(Qt.PointingHandCursor)

        self.setStyleSheet(f"""
            AvailabilityItemWidget {{
                background-color: #14161D;
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 6px 12px;
            }}
            AvailabilityItemWidget:hover {{
                background-color: #1E222D;
                border: 1px solid {badge_text};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        self.icon_lbl = QLabel(icon)
        self.icon_lbl.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.icon_lbl)

        self.label_lbl = QLabel(label)
        self.label_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 500;")
        layout.addWidget(self.label_lbl)

        layout.addStretch()

        self.badge_lbl = QLabel(str(count))
        self.badge_lbl.setStyleSheet(f"""
            font-size: 11px;
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 4px;
            background-color: {badge_bg};
            color: {badge_text};
        """)
        layout.addWidget(self.badge_lbl)

    def set_count(self, count: int):
        self.badge_lbl.setText(str(count))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.status_key)
        super().mouseReleaseEvent(event)


class ProjectAvailabilityCard(QFrame):
    """Section card displaying global library asset availability states."""

    filter_requested = Signal(str)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            ProjectAvailabilityCard {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 14px;
            }}
            QLabel#card_header {{
                color: {ACCENT};
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        title = QLabel("LIBRARY REFERENCES AVAILABILITY")
        title.setObjectName("card_header")
        header_row.addWidget(title)
        header_row.addStretch()

        self.total_ref_lbl = QLabel("0 references")
        self.total_ref_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        header_row.addWidget(self.total_ref_lbl)
        layout.addLayout(header_row)

        # 4 Status rows in a 2x2 grid
        grid = QGridLayout()
        grid.setSpacing(8)

        self.item_available = AvailabilityItemWidget(
            status_key="available",
            label="Available",
            icon="🟢",
            count=0,
            badge_bg="#14382B",
            badge_text="#34D399",
        )
        self.item_available.clicked.connect(self._on_item_clicked)
        grid.addWidget(self.item_available, 0, 0)

        self.item_offline = AvailabilityItemWidget(
            status_key="offline",
            label="Offline Drive",
            icon="🟠",
            count=0,
            badge_bg="#3B2D1B",
            badge_text="#FBBF24",
        )
        self.item_offline.clicked.connect(self._on_item_clicked)
        grid.addWidget(self.item_offline, 0, 1)

        self.item_missing = AvailabilityItemWidget(
            status_key="missing",
            label="Missing",
            icon="🔴",
            count=0,
            badge_bg="#381E24",
            badge_text="#F87171",
        )
        self.item_missing.clicked.connect(self._on_item_clicked)
        grid.addWidget(self.item_missing, 1, 0)

        self.item_changed = AvailabilityItemWidget(
            status_key="possibly_changed",
            label="Changed",
            icon="🔵",
            count=0,
            badge_bg="#1E2E4A",
            badge_text="#60A5FA",
        )
        self.item_changed.clicked.connect(self._on_item_clicked)
        grid.addWidget(self.item_changed, 1, 1)

        layout.addLayout(grid)

    def update_counts(self, available: int, offline: int, missing: int, changed: int):
        self.item_available.set_count(available)
        self.item_offline.set_count(offline)
        self.item_missing.set_count(missing)
        self.item_changed.set_count(changed)
        total = available + offline + missing + changed
        self.total_ref_lbl.setText(f"{total} reference{'s' if total != 1 else ''}")

    def _on_item_clicked(self, key: str):
        self.filter_requested.emit(key)
