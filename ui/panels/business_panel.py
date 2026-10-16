from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QGridLayout,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont

from ui.theme import BG_DARK, CARD_BG, CARD_HOVER, BORDER_COLOR, TEXT_PRIMARY, TEXT_MUTED, ACCENT


class BusinessPanel(QWidget):
    """Business Hub landing page for CreativeWorkspace.

    Provides clear, useful entry points for:
    - Clients and contacts (active integration via ClientService).
    - Jobs and projects pipeline (active integration via ProjectService).
    - Quotes and invoices (clearly marked future roadmap module).
    - Income and expenses (clearly marked future roadmap module).
    """

    def __init__(self, context=None, parent=None):
        super().__init__(parent)
        self.context = context
        self._init_ui()

    def minimumSizeHint(self) -> QSize:
        return QSize(350, 250)

    def sizeHint(self) -> QSize:
        return QSize(800, 600)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scroll Area to ensure graceful layout on smaller windows
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet(f"background-color: {BG_DARK}; border: none;")

        container = QWidget()
        container.setStyleSheet(f"background-color: {BG_DARK};")
        content_layout = QVBoxLayout(container)
        content_layout.setContentsMargins(32, 28, 32, 32)
        content_layout.setSpacing(24)

        # -------------------------------------------------------------
        # 1. Header Row
        # -------------------------------------------------------------
        header_layout = QHBoxLayout()
        header_text_layout = QVBoxLayout()
        header_text_layout.setSpacing(4)

        title_lbl = QLabel("💼 Business Hub")
        title_lbl.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
        header_text_layout.addWidget(title_lbl)

        subtitle_lbl = QLabel("Studio client relationships, active project pipelines, and commercial operations.")
        subtitle_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px; background: transparent;")
        header_text_layout.addWidget(subtitle_lbl)

        header_layout.addLayout(header_text_layout)
        header_layout.addStretch()

        # Quick Actions
        self.btn_open_clients = QPushButton("👥 Clients Directory")
        self.btn_open_clients.setCursor(Qt.PointingHandCursor)
        self.btn_open_clients.setStyleSheet(f"""
            QPushButton {{
                background-color: {CARD_BG};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {CARD_HOVER};
                border-color: {ACCENT};
            }}
        """)
        self.btn_open_clients.clicked.connect(self._on_navigate_clients)
        header_layout.addWidget(self.btn_open_clients)

        self.btn_open_projects = QPushButton("📁 Projects Pipeline")
        self.btn_open_projects.setCursor(Qt.PointingHandCursor)
        self.btn_open_projects.setStyleSheet(f"""
            QPushButton {{
                background-color: {CARD_BG};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {CARD_HOVER};
                border-color: {ACCENT};
            }}
        """)
        self.btn_open_projects.clicked.connect(self._on_navigate_projects)
        header_layout.addWidget(self.btn_open_projects)

        content_layout.addLayout(header_layout)

        # -------------------------------------------------------------
        # 2. Key Metrics Row
        # -------------------------------------------------------------
        self.metrics_layout = QHBoxLayout()
        self.metrics_layout.setSpacing(16)
        content_layout.addLayout(self.metrics_layout)

        # -------------------------------------------------------------
        # 3. Two-Column Card Grid
        # -------------------------------------------------------------
        cards_grid = QGridLayout()
        cards_grid.setSpacing(20)

        # Card 1: Clients & Contacts
        self.clients_card = self._create_clients_card()
        cards_grid.addWidget(self.clients_card, 0, 0)

        # Card 2: Jobs & Projects
        self.projects_card = self._create_projects_card()
        cards_grid.addWidget(self.projects_card, 0, 1)

        # Card 3: Quotes & Invoices (Coming Soon)
        self.quotes_card = self._create_quotes_card()
        cards_grid.addWidget(self.quotes_card, 1, 0)

        # Card 4: Income & Expenses (Coming Soon)
        self.finance_card = self._create_finance_card()
        cards_grid.addWidget(self.finance_card, 1, 1)

        content_layout.addLayout(cards_grid)
        content_layout.addStretch()

        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

        # Populate with data
        self.refresh()

    def set_context(self, context):
        self.context = context
        self.refresh()

    def refresh(self):
        """Reload live client and project summaries."""
        client_svc = getattr(self.context, "client_service", None) if self.context else None
        project_svc = getattr(self.context, "project_service", None) if self.context else None

        clients = client_svc.clients if (client_svc and hasattr(client_svc, "clients")) else []
        projects = project_svc.projects if (project_svc and hasattr(project_svc, "projects")) else []

        active_clients = [c for c in clients if getattr(c, "status", "").lower() == "active"]
        total_contacts = sum(len(getattr(c, "contacts", [])) for c in clients)

        # Rebuild metrics row
        self._rebuild_metrics(len(clients), len(active_clients), total_contacts, len(projects))

        # Update Clients list preview
        self._update_clients_preview(clients)

        # Update Projects list preview
        self._update_projects_preview(projects)

    def _rebuild_metrics(self, total_clients: int, active_clients: int, total_contacts: int, total_projects: int):
        while self.metrics_layout.count():
            item = self.metrics_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        metrics_data = [
            ("TOTAL CLIENTS", str(total_clients), f"{active_clients} Active Clients", "#10B981", self._on_navigate_clients),
            ("SAVED CONTACTS", str(total_contacts), "Across all studios", "#6366F1", self._on_navigate_clients),
            ("ACTIVE JOBS", str(total_projects), "Production projects", "#3B82F6", self._on_navigate_projects),
            ("FINANCIAL HUB", "Roadmap", "Quotes & Invoicing", "#8B5CF6", None),
        ]

        for label, val, subtitle, accent_col, click_handler in metrics_data:
            frame = QFrame()
            frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {CARD_BG};
                    border: 1px solid {BORDER_COLOR};
                    border-radius: 8px;
                    padding: 12px 16px;
                }}
            """)
            if click_handler:
                frame.setCursor(Qt.PointingHandCursor)
                frame.mousePressEvent = lambda e, h=click_handler: h()

            fl = QVBoxLayout(frame)
            fl.setContentsMargins(4, 4, 4, 4)
            fl.setSpacing(4)

            lbl = QLabel(label)
            lbl.setStyleSheet("color: #94A3B8; font-size: 10px; font-weight: bold; letter-spacing: 0.5px; background: transparent;")
            fl.addWidget(lbl)

            vlbl = QLabel(val)
            vlbl.setFont(QFont("Segoe UI", 18, QFont.Bold))
            vlbl.setStyleSheet(f"color: {accent_col}; background: transparent;")
            fl.addWidget(vlbl)

            sublbl = QLabel(subtitle)
            sublbl.setStyleSheet("color: #64748B; font-size: 11px; background: transparent;")
            fl.addWidget(sublbl)

            self.metrics_layout.addWidget(frame)

    # -----------------------------------------------------------------
    # Card 1: Clients & Contacts
    # -----------------------------------------------------------------
    def _create_clients_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 12px;
                padding: 20px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        icon = QLabel("👥")
        icon.setStyleSheet("font-size: 20px; background: transparent;")
        hdr.addWidget(icon)

        title = QLabel("Clients & Contacts")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
        hdr.addWidget(title)
        hdr.addStretch()

        btn_go = QPushButton("Open Directory →")
        btn_go.setCursor(Qt.PointingHandCursor)
        btn_go.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: #A5B4FC;
                border: none;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                color: #FFFFFF;
                text-decoration: underline;
            }}
        """)
        btn_go.clicked.connect(self._on_navigate_clients)
        hdr.addWidget(btn_go)
        card_layout.addLayout(hdr)

        desc = QLabel("Manage accounts, communication history, creative briefs, and studio contact directories.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;")
        card_layout.addWidget(desc)

        self.clients_preview_container = QVBoxLayout()
        self.clients_preview_container.setSpacing(6)
        card_layout.addLayout(self.clients_preview_container)

        card_layout.addStretch()
        return card

    def _update_clients_preview(self, clients: List):
        while self.clients_preview_container.count():
            item = self.clients_preview_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not clients:
            empty_lbl = QLabel("No clients created yet. Add clients to track commissions and agency work.")
            empty_lbl.setStyleSheet("color: #64748B; font-size: 12px; font-style: italic; background: transparent;")
            self.clients_preview_container.addWidget(empty_lbl)
            return

        for c in clients[:4]:
            c_row = QFrame()
            c_row.setStyleSheet(f"""
                QFrame {{
                    background-color: #1A1C28;
                    border: 1px solid #282C3E;
                    border-radius: 6px;
                    padding: 8px 12px;
                }}
                QFrame:hover {{
                    background-color: #232738;
                    border-color: #383E58;
                }}
            """)
            c_row.setCursor(Qt.PointingHandCursor)
            c_row.mousePressEvent = lambda e, client=c: self._on_client_row_clicked(client)

            row_layout = QHBoxLayout(c_row)
            row_layout.setContentsMargins(6, 4, 6, 4)

            name_lbl = QLabel(getattr(c, "name", "Unnamed Client"))
            name_lbl.setStyleSheet("font-weight: bold; font-size: 12px; color: #F1F5F9; background: transparent;")
            row_layout.addWidget(name_lbl)

            company = getattr(c, "company", "")
            if company:
                comp_lbl = QLabel(f"· {company}")
                comp_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; background: transparent;")
                row_layout.addWidget(comp_lbl)

            row_layout.addStretch()

            status = getattr(c, "status", "Active")
            st_lbl = QLabel(status)
            st_color = "#10B981" if status.lower() == "active" else "#94A3B8"
            st_lbl.setStyleSheet(f"""
                color: {st_color};
                background-color: rgba(16, 185, 129, 0.12);
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: bold;
            """)
            row_layout.addWidget(st_lbl)

            contacts_count = len(getattr(c, "contacts", []))
            contacts_lbl = QLabel(f"👤 {contacts_count}")
            contacts_lbl.setStyleSheet("color: #64748B; font-size: 11px; background: transparent;")
            row_layout.addWidget(contacts_lbl)

            self.clients_preview_container.addWidget(c_row)

    # -----------------------------------------------------------------
    # Card 2: Jobs & Projects Pipeline
    # -----------------------------------------------------------------
    def _create_projects_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 12px;
                padding: 20px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)

        hdr = QHBoxLayout()
        icon = QLabel("🚀")
        icon.setStyleSheet("font-size: 20px; background: transparent;")
        hdr.addWidget(icon)

        title = QLabel("Jobs & Projects Pipeline")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
        hdr.addWidget(title)
        hdr.addStretch()

        btn_go = QPushButton("Open Pipeline →")
        btn_go.setCursor(Qt.PointingHandCursor)
        btn_go.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: #A5B4FC;
                border: none;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                color: #FFFFFF;
                text-decoration: underline;
            }}
        """)
        btn_go.clicked.connect(self._on_navigate_projects)
        hdr.addWidget(btn_go)
        card_layout.addLayout(hdr)

        desc = QLabel("Track active production deliverables, Lab boards, concept research, and project statuses.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;")
        card_layout.addWidget(desc)

        self.projects_preview_container = QVBoxLayout()
        self.projects_preview_container.setSpacing(6)
        card_layout.addLayout(self.projects_preview_container)

        card_layout.addStretch()
        return card

    def _update_projects_preview(self, projects: List):
        while self.projects_preview_container.count():
            item = self.projects_preview_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not projects:
            empty_lbl = QLabel("No active projects. Create a new project to start tracking studio jobs.")
            empty_lbl.setStyleSheet("color: #64748B; font-size: 12px; font-style: italic; background: transparent;")
            self.projects_preview_container.addWidget(empty_lbl)
            return

        for p in projects[:4]:
            p_row = QFrame()
            p_row.setStyleSheet(f"""
                QFrame {{
                    background-color: #1A1C28;
                    border: 1px solid #282C3E;
                    border-radius: 6px;
                    padding: 8px 12px;
                }}
                QFrame:hover {{
                    background-color: #232738;
                    border-color: #383E58;
                }}
            """)
            p_row.setCursor(Qt.PointingHandCursor)
            p_row.mousePressEvent = lambda e, proj=p: self._on_project_row_clicked(proj)

            row_layout = QHBoxLayout(p_row)
            row_layout.setContentsMargins(6, 4, 6, 4)

            name_lbl = QLabel(getattr(p, "name", "Unnamed Project"))
            name_lbl.setStyleSheet("font-weight: bold; font-size: 12px; color: #F1F5F9; background: transparent;")
            row_layout.addWidget(name_lbl)

            ptype = getattr(p, "project_type", "general")
            ptype_lbl = QLabel(f"· {ptype.title()}")
            ptype_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; background: transparent;")
            row_layout.addWidget(ptype_lbl)

            row_layout.addStretch()

            open_hint = QLabel("Open Canvas ↗")
            open_hint.setStyleSheet("color: #6366F1; font-size: 11px; font-weight: bold; background: transparent;")
            row_layout.addWidget(open_hint)

            self.projects_preview_container.addWidget(p_row)

    # -----------------------------------------------------------------
    # Card 3: Quotes & Invoices (Roadmap)
    # -----------------------------------------------------------------
    def _create_quotes_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px dashed #3A3F58;
                border-radius: 12px;
                padding: 20px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)

        hdr = QHBoxLayout()
        icon = QLabel("📄")
        icon.setStyleSheet("font-size: 20px; background: transparent;")
        hdr.addWidget(icon)

        title = QLabel("Quotes & Invoices")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
        hdr.addWidget(title)
        hdr.addStretch()

        badge = QLabel("🗓️ Coming Soon")
        badge.setStyleSheet("""
            background-color: #312E81;
            color: #C7D2FE;
            font-size: 11px;
            font-weight: bold;
            border-radius: 6px;
            padding: 3px 8px;
        """)
        hdr.addWidget(badge)
        card_layout.addLayout(hdr)

        desc = QLabel(
            "Commercial billing module for generating itemized quotes, milestone-based invoices, "
            "and tracking payment statuses for client deliverables."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;")
        card_layout.addWidget(desc)

        features = [
            "Itemized creative estimates & rate calculation",
            "Milestone-based billing linked to project exports",
            "PDF invoice export and client payment receipts",
        ]
        feat_layout = QVBoxLayout()
        feat_layout.setSpacing(6)
        for f in features:
            flbl = QLabel(f"  •  {f}")
            flbl.setStyleSheet("color: #64748B; font-size: 11px; background: transparent;")
            feat_layout.addWidget(flbl)
        card_layout.addLayout(feat_layout)

        card_layout.addStretch()
        return card

    # -----------------------------------------------------------------
    # Card 4: Income & Expenses (Roadmap)
    # -----------------------------------------------------------------
    def _create_finance_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px dashed #3A3F58;
                border-radius: 12px;
                padding: 20px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)

        hdr = QHBoxLayout()
        icon = QLabel("📈")
        icon.setStyleSheet("font-size: 20px; background: transparent;")
        hdr.addWidget(icon)

        title = QLabel("Income & Expenses")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
        hdr.addWidget(title)
        hdr.addStretch()

        badge = QLabel("🗓️ Coming Soon")
        badge.setStyleSheet("""
            background-color: #312E81;
            color: #C7D2FE;
            font-size: 11px;
            font-weight: bold;
            border-radius: 6px;
            padding: 3px 8px;
        """)
        hdr.addWidget(badge)
        card_layout.addLayout(hdr)

        desc = QLabel(
            "Financial overview of studio revenue, operating expenses, asset licensing costs, "
            "and project profitability breakdown."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;")
        card_layout.addWidget(desc)

        features = [
            "Studio cash flow and revenue tracking across clients",
            "Asset subscriptions and production tool expense logging",
            "Real-time profit margin analysis per completed job",
        ]
        feat_layout = QVBoxLayout()
        feat_layout.setSpacing(6)
        for f in features:
            flbl = QLabel(f"  •  {f}")
            flbl.setStyleSheet("color: #64748B; font-size: 11px; background: transparent;")
            feat_layout.addWidget(flbl)
        card_layout.addLayout(feat_layout)

        card_layout.addStretch()
        return card

    # -----------------------------------------------------------------
    # Navigation Handlers
    # -----------------------------------------------------------------
    def _on_navigate_clients(self):
        wm = getattr(self.context, "workspace_manager", None) if self.context else None
        if wm and hasattr(wm, "show_module"):
            wm.show_module("clients")

    def _on_navigate_projects(self):
        wm = getattr(self.context, "workspace_manager", None) if self.context else None
        if wm and hasattr(wm, "show_module"):
            wm.show_module("projects_dashboard")

    def _on_client_row_clicked(self, client):
        wm = getattr(self.context, "workspace_manager", None) if self.context else None
        if wm and hasattr(wm, "show_module"):
            wm.show_module("clients")
            cp = getattr(wm, "client_panel", None)
            if cp and hasattr(cp, "open_client_dashboard"):
                try:
                    cp.open_client_dashboard(client)
                except Exception:
                    pass

    def _on_project_row_clicked(self, project):
        wm = getattr(self.context, "workspace_manager", None) if self.context else None
        if wm and hasattr(wm, "show_project"):
            wm.show_project(project, section="dashboard")
