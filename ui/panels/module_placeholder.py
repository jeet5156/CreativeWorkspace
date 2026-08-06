from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QFrame, QHBoxLayout
from PySide6.QtCore import Qt
from ui.theme import CARD_BG, BORDER_COLOR, TEXT_PRIMARY, TEXT_MUTED


class ModulePlaceholder(QWidget):
    """Clean informational UI placeholder for future roadmap modules.

    Contains zero services, zero persistence, and zero business logic.
    """

    def __init__(self, title: str, description: str, badge: str = "Coming Soon", icon: str = "🚀"):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 12px;
                padding: 24px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)

        # Header Row
        header_row = QHBoxLayout()
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 32px; background: transparent;")
        header_row.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-weight: bold; font-size: 20px; color: {TEXT_PRIMARY}; background: transparent;")
        header_row.addWidget(title_label)

        header_row.addStretch()

        badge_label = QLabel(f" {badge} ")
        badge_label.setStyleSheet("""
            background-color: #312E81;
            color: #A5B4FC;
            font-size: 11px;
            font-weight: bold;
            border-radius: 6px;
            padding: 4px 8px;
        """)
        header_row.addWidget(badge_label)

        card_layout.addLayout(header_row)

        # Description
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px; background: transparent;")
        card_layout.addWidget(desc_label)

        layout.addWidget(card)
        layout.addStretch()
