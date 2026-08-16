"""Global Settings Dialog for CreativeWorkspace.

Provides unified preferences management with category navigation:
- General Preferences
- AI & Provider Configuration (Settings -> AI)
"""

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QLabel,
    QPushButton,
    QFrame,
    QWidget,
)

from ui.widgets.ai_settings_widget import AISettingsWidget


class SettingsDialog(QDialog):
    """Application preferences and settings dialog."""

    def __init__(self, context=None, parent=None, initial_section: str = "general"):
        super().__init__(parent)
        self.context = context
        self.ai_service = getattr(context, "ai_service", None) if context else None

        self.setWindowTitle("Settings")
        self.resize(680, 520)
        self.setModal(True)
        self.setStyleSheet("background-color: #0F1117;")

        self._setup_ui()
        self.open_section(initial_section)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Content Split: Sidebar (Left) + Stacked Pages (Right)
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # 1. Left Sidebar Categories
        sidebar_frame = QFrame()
        sidebar_frame.setFixedWidth(180)
        sidebar_frame.setStyleSheet("""
            QFrame {
                background-color: #12141C;
                border-right: 1px solid #282C40;
            }
        """)
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setContentsMargins(8, 14, 8, 14)
        sidebar_layout.setSpacing(6)

        title_lbl = QLabel("Preferences")
        title_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title_lbl.setStyleSheet("color: #F1F5F9; padding-left: 6px; margin-bottom: 6px;")
        sidebar_layout.addWidget(title_lbl)

        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                color: #CBD5E1;
                font-size: 12px;
                outline: none;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 6px;
                margin-bottom: 2px;
            }
            QListWidget::item:hover {
                background-color: #1E2235;
                color: #F1F5F9;
            }
            QListWidget::item:selected {
                background-color: #283556;
                color: #38BDF8;
                font-weight: bold;
            }
        """)

        item_general = QListWidgetItem("⚙️  General")
        item_general.setData(Qt.UserRole, "general")
        self.nav_list.addItem(item_general)

        item_ai = QListWidgetItem("✨  AI & Intelligence")
        item_ai.setData(Qt.UserRole, "ai")
        self.nav_list.addItem(item_ai)

        self.nav_list.currentRowChanged.connect(self._on_category_changed)
        sidebar_layout.addWidget(self.nav_list, 1)

        body_layout.addWidget(sidebar_frame)

        # 2. Right Stacked Widget
        self.pages_stack = QStackedWidget()
        self.pages_stack.setStyleSheet("background-color: #0F1117;")

        # Page 0: General
        self.general_page = self._create_general_page()
        self.pages_stack.addWidget(self.general_page)

        # Page 1: AI Settings
        self.ai_settings_widget = AISettingsWidget(self.ai_service)
        self.pages_stack.addWidget(self.ai_settings_widget)

        body_layout.addWidget(self.pages_stack, 1)
        main_layout.addLayout(body_layout, 1)

        # 3. Bottom Action Bar
        bottom_bar = QFrame()
        bottom_bar.setStyleSheet("""
            QFrame {
                background-color: #141620;
                border-top: 1px solid #282C40;
                padding: 6px 12px;
            }
        """)
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(12, 8, 12, 8)
        bottom_layout.setSpacing(8)
        bottom_layout.addStretch()

        self.btn_close = QPushButton("Close")
        self.btn_close.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #1E2235;
                color: #CBD5E1;
                border: 1px solid #3E4564;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #283556;
                color: #FFFFFF;
                border-color: #6366F1;
            }
        """)
        self.btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(self.btn_close)

        main_layout.addWidget(bottom_bar)

    def _create_general_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("⚙️ General Preferences")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setStyleSheet("color: #F1F5F9;")
        layout.addWidget(title)

        info_card = QFrame()
        info_card.setStyleSheet("""
            QFrame {
                background-color: #141620;
                border: 1px solid #282C40;
                border-radius: 8px;
                padding: 14px;
            }
            QLabel {
                color: #94A3B8;
                font-size: 12px;
            }
        """)
        info_layout = QVBoxLayout(info_card)
        info_layout.setSpacing(8)

        lbl1 = QLabel("CreativeWorkspace Studio Edition")
        lbl1.setFont(QFont("Segoe UI", 11, QFont.Bold))
        lbl1.setStyleSheet("color: #CBD5E1;")
        info_layout.addWidget(lbl1)

        lbl2 = QLabel("• Local-first project architecture with atomic JSON persistence.")
        lbl3 = QLabel("• Non-destructive AI integrations and universal spatial canvas.")
        lbl4 = QLabel("• Theme: Dark Modern Glassmorphism (Default)")
        info_layout.addWidget(lbl2)
        info_layout.addWidget(lbl3)
        info_layout.addWidget(lbl4)

        layout.addWidget(info_card)
        layout.addStretch()
        return page

    def _on_category_changed(self, index: int):
        self.pages_stack.setCurrentIndex(index)

    def open_section(self, section_name: str):
        """Navigate directly to a specific settings section (e.g. 'ai' or 'general')."""
        target = section_name.strip().lower()
        if target in ("ai", "ai_settings", "provider", "providers"):
            self.nav_list.setCurrentRow(1)
            self.pages_stack.setCurrentIndex(1)
            self.ai_settings_widget.reload_from_service()
        else:
            self.nav_list.setCurrentRow(0)
            self.pages_stack.setCurrentIndex(0)
