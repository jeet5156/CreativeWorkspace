from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QPushButton,
    QScrollArea,
    QGridLayout,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from models.client import Client
from ui.widgets.client_card import ClientCard


class ClientRootDashboard(QWidget):
    """Top-level Clients Module Page (Root Clients view when selecting 👥 Clients in Explorer).

    Displays:
    - Summary Metrics (Total Clients, Active, Prospects, Archived)
    - Recent Clients Section
    - Recent Activity Summary Feed
    - Persistent + Create Client Action Button
    """

    create_client_requested = Signal()
    client_selected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.clients: List[Client] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Scroll container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; }")

        container = QWidget()
        self.container_layout = QVBoxLayout(container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(20)

        # 1. Module Header
        header_row = QHBoxLayout()

        title_vbox = QVBoxLayout()
        title_lbl = QLabel("Clients Dashboard")
        title_lbl.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title_lbl.setStyleSheet("color: #F1F5F9;")
        title_vbox.addWidget(title_lbl)

        sub_lbl = QLabel("Central management for studios, publishers, and freelance accounts.")
        sub_lbl.setFont(QFont("Segoe UI", 11))
        sub_lbl.setStyleSheet("color: #94A3B8;")
        title_vbox.addWidget(sub_lbl)

        header_row.addLayout(title_vbox)
        header_row.addStretch()

        self.btn_create_client = QPushButton("➕ Create Client")
        self.btn_create_client.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: #FFFFFF;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
        """)
        self.btn_create_client.clicked.connect(self.create_client_requested.emit)
        header_row.addWidget(self.btn_create_client)

        self.container_layout.addLayout(header_row)

        # 2. Metric Cards Row
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(16)

        self.card_total = self._create_metric_card("Total Clients", "0", "#38BDF8", "👥")
        self.card_active = self._create_metric_card("Active", "0", "#10B981", "🟢")
        self.card_prospects = self._create_metric_card("Prospects", "0", "#F59E0B", "🟡")
        self.card_archived = self._create_metric_card("Archived", "0", "#EF4444", "🔴")

        metrics_layout.addWidget(self.card_total)
        metrics_layout.addWidget(self.card_active)
        metrics_layout.addWidget(self.card_prospects)
        metrics_layout.addWidget(self.card_archived)

        self.container_layout.addLayout(metrics_layout)

        # 3. Main Split Section (Recent Clients + Recent Activity)
        main_split = QHBoxLayout()
        main_split.setSpacing(20)

        # Left: Recent Clients Box
        clients_box = QFrame()
        clients_box.setStyleSheet("""
            QFrame {
                background-color: #1E2029;
                border: 1px solid #343847;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        clients_box_layout = QVBoxLayout(clients_box)
        clients_box_layout.setSpacing(12)

        c_header = QLabel("Recent Clients")
        c_header.setFont(QFont("Segoe UI", 12, QFont.Bold))
        c_header.setStyleSheet("color: #F1F5F9;")
        clients_box_layout.addWidget(c_header)

        self.recent_grid_container = QWidget()
        self.recent_grid_layout = QGridLayout(self.recent_grid_container)
        self.recent_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_grid_layout.setSpacing(12)
        clients_box_layout.addWidget(self.recent_grid_container)

        main_split.addWidget(clients_box, 2)

        # Right: Recent Activity Box
        activity_box = QFrame()
        activity_box.setStyleSheet("""
            QFrame {
                background-color: #1E2029;
                border: 1px solid #343847;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        activity_box_layout = QVBoxLayout(activity_box)
        activity_box_layout.setSpacing(12)

        a_header = QLabel("Recent Activity")
        a_header.setFont(QFont("Segoe UI", 12, QFont.Bold))
        a_header.setStyleSheet("color: #F1F5F9;")
        activity_box_layout.addWidget(a_header)

        self.activity_feed_layout = QVBoxLayout()
        self.activity_feed_layout.setSpacing(8)

        self.no_activity_lbl = QLabel("No client activity recorded yet.")
        self.no_activity_lbl.setStyleSheet("color: #64748B; padding: 10px; font-size: 11px;")
        self.activity_feed_layout.addWidget(self.no_activity_lbl)

        activity_box_layout.addLayout(self.activity_feed_layout)
        activity_box_layout.addStretch()

        main_split.addWidget(activity_box, 1)

        self.container_layout.addLayout(main_split)
        self.container_layout.addStretch()

        scroll.setWidget(container)
        layout.addWidget(scroll)

    def _create_metric_card(self, title: str, initial_value: str, color_hex: str, icon_str: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #1E2029;
                border: 1px solid #343847;
                border-radius: 8px;
                padding: 16px;
            }}
        """)
        clayout = QHBoxLayout(card)
        clayout.setContentsMargins(12, 12, 12, 12)

        vbox = QVBoxLayout()
        vbox.setSpacing(4)

        lbl_title = QLabel(title.upper())
        lbl_title.setFont(QFont("Segoe UI", 9, QFont.Bold))
        lbl_title.setStyleSheet("color: #94A3B8;")
        vbox.addWidget(lbl_title)

        lbl_val = QLabel(initial_value)
        lbl_val.setObjectName("value_label")
        lbl_val.setFont(QFont("Segoe UI", 22, QFont.Bold))
        lbl_val.setStyleSheet(f"color: {color_hex};")
        vbox.addWidget(lbl_val)

        clayout.addLayout(vbox)
        clayout.addStretch()

        icon_lbl = QLabel(icon_str)
        icon_lbl.setFont(QFont("Segoe UI", 24))
        clayout.addWidget(icon_lbl)

        return card

    def set_clients(self, clients: List[Client]):
        self.clients = clients or []

        # Update metrics
        total = len(self.clients)
        active_count = sum(1 for c in self.clients if str(c.status).lower() in ("active", "conversation", "negotiation", "returning"))
        prospect_count = sum(1 for c in self.clients if str(c.status).lower() in ("prospect", "reached out"))
        archived_count = sum(1 for c in self.clients if str(c.status).lower() in ("archived", "completed"))

        self.card_total.findChild(QLabel, "value_label").setText(str(total))
        self.card_active.findChild(QLabel, "value_label").setText(str(active_count))
        self.card_prospects.findChild(QLabel, "value_label").setText(str(prospect_count))
        self.card_archived.findChild(QLabel, "value_label").setText(str(archived_count))

        # Clear existing grid
        while self.recent_grid_layout.count():
            item = self.recent_grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self.clients:
            col_count = 2
            for idx, client in enumerate(self.clients[:6]):  # Display top 6 recent
                card = ClientCard(client)
                card.clicked.connect(lambda c=client: self.client_selected.emit(c))
                card.open_requested.connect(lambda c=client: self.client_selected.emit(c))
                row = idx // col_count
                col = idx % col_count
                self.recent_grid_layout.addWidget(card, row, col)
        else:
            empty_lbl = QLabel("No clients created yet. Click '+ Create Client' to start.")
            empty_lbl.setStyleSheet("color: #64748B; padding: 20px; font-size: 12px;")
            self.recent_grid_layout.addWidget(empty_lbl, 0, 0)
