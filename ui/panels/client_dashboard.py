from typing import Optional, List
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QPushButton,
    QToolButton,
    QMenu,
    QScrollArea,
    QGroupBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QAction

from models.client import Client, ClientContact
from models.project import Project


class ClientOverviewPanel(QWidget):
    """Read-only Client Overview Panel view.

    Displays Client Header, Status Badge, Associated Projects (queried dynamically from ProjectService),
    Contacts, Recent Activity feed, and Quick Actions Toolbar.
    All property editing belongs strictly in the Inspector.
    """

    open_project_requested = Signal(object)      # Emits Project or project_id
    reveal_project_requested = Signal(object)    # Emits Project or project_id
    new_project_requested = Signal(object)       # Emits Client
    new_contact_requested = Signal(object)       # Emits Client
    edit_client_requested = Signal(object)       # Emits Client
    archive_client_requested = Signal(object)    # Emits Client
    duplicate_client_requested = Signal(object)  # Emits Client
    delete_client_requested = Signal(object)     # Emits Client
    export_client_requested = Signal(object)     # Emits Client

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_client: Optional[Client] = None
        self.associated_projects: List[Project] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Scroll Area Container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; }")

        container = QWidget()
        self.container_layout = QVBoxLayout(container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(20)

        # 1. Header Frame
        self.header_frame = QFrame()
        self.header_frame.setStyleSheet("""
            QFrame {
                background-color: #1E2029;
                border: 1px solid #343847;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        header_layout = QHBoxLayout(self.header_frame)

        info_vbox = QVBoxLayout()
        self.name_label = QLabel("No Client Selected")
        self.name_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        self.name_label.setStyleSheet("color: #F1F5F9;")
        info_vbox.addWidget(self.name_label)

        self.role_company_label = QLabel("—")
        self.role_company_label.setFont(QFont("Segoe UI", 11))
        self.role_company_label.setStyleSheet("color: #94A3B8;")
        info_vbox.addWidget(self.role_company_label)

        header_layout.addLayout(info_vbox)
        header_layout.addStretch()

        self.priority_badge = QLabel("PRIORITY: MEDIUM")
        self.priority_badge.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.priority_badge.setStyleSheet("""
            QLabel {
                background-color: #2D2319;
                color: #F59E0B;
                border: 1px solid #F59E0B;
                border-radius: 6px;
                padding: 6px 12px;
            }
        """)
        header_layout.addWidget(self.priority_badge)

        self.status_badge = QLabel("ACTIVE")
        self.status_badge.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.status_badge.setStyleSheet("""
            QLabel {
                background-color: #1E2E4A;
                color: #38BDF8;
                border: 1px solid #38BDF8;
                border-radius: 6px;
                padding: 6px 14px;
            }
        """)
        header_layout.addWidget(self.status_badge)

        self.container_layout.addWidget(self.header_frame)

        # 2. Quick Actions Toolbar
        actions_frame = QFrame()
        actions_frame.setStyleSheet("""
            QFrame {
                background-color: #1E2029;
                border: 1px solid #343847;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton, QToolButton {
                background-color: #202334;
                color: #F1F5F9;
                border: 1px solid #313652;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton:hover, QToolButton:hover {
                background-color: #262A3E;
                border-color: #38BDF8;
            }
        """)
        actions_layout = QHBoxLayout(actions_frame)

        actions_title = QLabel("Quick Actions:")
        actions_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        actions_title.setStyleSheet("color: #CBD5E1;")
        actions_layout.addWidget(actions_title)

        self.btn_new_project = QPushButton("➕ New Project")
        self.btn_new_project.setStyleSheet("font-weight: bold; background-color: #3B82F6; color: #FFFFFF;")
        self.btn_new_project.clicked.connect(self._on_new_project_clicked)
        actions_layout.addWidget(self.btn_new_project)

        self.btn_edit_client = QPushButton("✏ Edit Client")
        self.btn_edit_client.clicked.connect(self._on_edit_client_clicked)
        actions_layout.addWidget(self.btn_edit_client)

        self.btn_new_contact = QPushButton("👤 New Contact")
        self.btn_new_contact.clicked.connect(self._on_new_contact_clicked)
        actions_layout.addWidget(self.btn_new_contact)

        self.btn_open_portfolio = QPushButton("🌐 Open Website")
        self.btn_open_portfolio.clicked.connect(self._on_open_website_clicked)
        actions_layout.addWidget(self.btn_open_portfolio)

        actions_layout.addStretch()

        # Three-dot overflow menu (Archive, Duplicate, Delete, Export)
        self.btn_more_menu = QToolButton()
        self.btn_more_menu.setText("⋮")
        self.btn_more_menu.setPopupMode(QToolButton.InstantPopup)
        
        more_menu = QMenu(self.btn_more_menu)
        
        archive_action = QAction("Archive Client", self)
        archive_action.triggered.connect(lambda: self.archive_client_requested.emit(self.current_client))
        more_menu.addAction(archive_action)

        dup_action = QAction("Duplicate Client", self)
        dup_action.triggered.connect(lambda: self.duplicate_client_requested.emit(self.current_client))
        more_menu.addAction(dup_action)

        export_action = QAction("Export Client Data", self)
        export_action.triggered.connect(lambda: self.export_client_requested.emit(self.current_client))
        more_menu.addAction(export_action)

        more_menu.addSeparator()

        delete_action = QAction("Delete Client", self)
        delete_action.triggered.connect(lambda: self.delete_client_requested.emit(self.current_client))
        more_menu.addAction(delete_action)

        self.btn_more_menu.setMenu(more_menu)
        actions_layout.addWidget(self.btn_more_menu)

        self.container_layout.addWidget(actions_frame)

        # 3. Main Projects Box
        self.projects_box = QGroupBox("Associated Projects")
        self.projects_box.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.projects_box.setStyleSheet("QGroupBox { color: #F1F5F9; font-weight: bold; border: 1px solid #343847; border-radius: 8px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; }")
        self.projects_layout = QVBoxLayout(self.projects_box)
        self.projects_layout.setSpacing(10)
        self.container_layout.addWidget(self.projects_box)

        # 4. Contacts Box
        contacts_box = QGroupBox("Contacts")
        contacts_box.setFont(QFont("Segoe UI", 11, QFont.Bold))
        contacts_box.setStyleSheet("QGroupBox { color: #F1F5F9; font-weight: bold; border: 1px solid #343847; border-radius: 8px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; }")
        self.contacts_layout = QVBoxLayout(contacts_box)
        self.contacts_layout.setSpacing(10)
        self.container_layout.addWidget(contacts_box)

        # 5. Recent Activity Box
        activity_box = QGroupBox("Recent Activity")
        activity_box.setFont(QFont("Segoe UI", 11, QFont.Bold))
        activity_box.setStyleSheet("QGroupBox { color: #F1F5F9; font-weight: bold; border: 1px solid #343847; border-radius: 8px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; }")
        self.activity_layout = QVBoxLayout(activity_box)

        self.activity_label = QLabel("No activity yet.")
        self.activity_label.setFont(QFont("Segoe UI", 10))
        self.activity_label.setStyleSheet("color: #64748B; padding: 10px;")
        self.activity_layout.addWidget(self.activity_label)

        self.container_layout.addWidget(activity_box)
        self.container_layout.addStretch()

        scroll.setWidget(container)
        layout.addWidget(scroll)

    def set_client(self, client: Optional[Client], project_service=None):
        self.current_client = client

        # Always query ProjectService dynamically if available
        if client and project_service and hasattr(project_service, "get_projects_for_client"):
            self.associated_projects = project_service.get_projects_for_client(client.id)
        elif client and project_service and hasattr(project_service, "all_projects"):
            self.associated_projects = [p for p in project_service.all_projects() if getattr(p, "client_id", None) == client.id]
        else:
            self.associated_projects = []

        if not client:
            self.name_label.setText("No Client Selected")
            self.role_company_label.setText("—")
            self.status_badge.setText("INACTIVE")
            self.priority_badge.setText("PRIORITY: —")
            self.projects_box.setTitle("Associated Projects")
            self._clear_layouts()
            return

        # Header Info
        self.name_label.setText(client.name or "Untitled Client")
        sub_info = []
        if client.company:
            sub_info.append(client.company)
        if client.client_type:
            sub_info.append(client.client_type)
        if client.industry:
            sub_info.append(client.industry)
        self.role_company_label.setText(" • ".join(sub_info) if sub_info else "Client Entity")

        status_str = str(client.status or "Active").upper()
        self.status_badge.setText(status_str)

        prio_str = str(getattr(client, "priority", "Medium")).upper()
        self.priority_badge.setText(f"PRIORITY: {prio_str}")

        # Update Project Count Breakdown (e.g., "Associated Projects (4 Active, 2 Completed)")
        counts_by_status = {}
        for p in self.associated_projects:
            st = str(getattr(p, "status", "active")).capitalize()
            counts_by_status[st] = counts_by_status.get(st, 0) + 1
        
        if self.associated_projects:
            breakdown_parts = [f"{count} {st}" for st, count in counts_by_status.items()]
            breakdown_str = ", ".join(breakdown_parts)
            self.projects_box.setTitle(f"Associated Projects ({breakdown_str})")
        else:
            self.projects_box.setTitle("Associated Projects (0)")

        # Populate Rich Projects List
        self._clear_layout(self.projects_layout)
        if self.associated_projects:
            for proj in self.associated_projects:
                card = QFrame()
                card.setStyleSheet("QFrame { background-color: #14161D; border: 1px solid #2E3342; border-radius: 6px; padding: 12px; }")
                clayout = QHBoxLayout(card)

                # Left side: Category badge, Project name, Status, Last modified
                info_layout = QVBoxLayout()
                info_layout.setSpacing(4)

                top_row = QHBoxLayout()
                cat_str = getattr(proj, "project_type", "General").capitalize()
                cat_lbl = QLabel(f"● {cat_str}")
                cat_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
                cat_lbl.setStyleSheet("color: #38BDF8;")
                top_row.addWidget(cat_lbl)

                name_lbl = QLabel(proj.name)
                name_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
                name_lbl.setStyleSheet("color: #F1F5F9;")
                top_row.addWidget(name_lbl)
                top_row.addStretch()

                info_layout.addLayout(top_row)

                meta_row = QHBoxLayout()
                p_status = getattr(proj, "status", "active").capitalize()
                status_sub = QLabel(p_status)
                status_sub.setFont(QFont("Segoe UI", 9))
                status_sub.setStyleSheet("color: #10B981; font-weight: bold;")
                meta_row.addWidget(status_sub)

                mod_dt = getattr(proj, "modified", datetime.now())
                mod_str = mod_dt.strftime("%d %b %Y") if isinstance(mod_dt, datetime) else str(mod_dt)
                mod_lbl = QLabel(f"Modified {mod_str}")
                mod_lbl.setFont(QFont("Segoe UI", 9))
                mod_lbl.setStyleSheet("color: #64748B;")
                meta_row.addWidget(mod_lbl)
                meta_row.addStretch()

                info_layout.addLayout(meta_row)

                clayout.addLayout(info_layout, 1)

                # Right side action buttons: Open & Reveal in Explorer
                btn_layout = QHBoxLayout()
                btn_layout.setSpacing(8)

                open_btn = QPushButton("Open")
                open_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3B82F6;
                        color: #FFFFFF;
                        border-radius: 4px;
                        padding: 6px 14px;
                        font-weight: bold;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #2563EB;
                    }
                """)
                open_btn.clicked.connect(lambda checked=False, p=proj: self.open_project_requested.emit(p))
                btn_layout.addWidget(open_btn)

                reveal_btn = QPushButton("Reveal in Explorer")
                reveal_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2E3342;
                        color: #CBD5E1;
                        border: 1px solid #343847;
                        border-radius: 4px;
                        padding: 6px 12px;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #343847;
                        color: #F1F5F9;
                    }
                """)
                reveal_btn.clicked.connect(lambda checked=False, p=proj: self.reveal_project_requested.emit(p))
                btn_layout.addWidget(reveal_btn)

                clayout.addLayout(btn_layout)
                self.projects_layout.addWidget(card)
        else:
            no_proj = QLabel("No projects assigned yet.")
            no_proj.setStyleSheet("color: #64748B; padding: 6px;")
            self.projects_layout.addWidget(no_proj)

        # Populate Contacts List
        self._clear_layout(self.contacts_layout)
        if client.contacts:
            for contact in client.contacts:
                ccard = QFrame()
                ccard.setStyleSheet("QFrame { background-color: #14161D; border: 1px solid #2E3342; border-radius: 6px; padding: 8px; }")
                playout = QVBoxLayout(ccard)
                cname = QLabel(f"👤  {contact.name}")
                cname.setFont(QFont("Segoe UI", 10, QFont.Bold))
                cname.setStyleSheet("color: #F1F5F9;")
                playout.addWidget(cname)
                crole = QLabel(contact.role or "Contact Person")
                crole.setStyleSheet("color: #94A3B8; font-size: 11px;")
                playout.addWidget(crole)
                if contact.email:
                    cemail = QLabel(contact.email)
                    cemail.setStyleSheet("color: #38BDF8; font-size: 11px;")
                    playout.addWidget(cemail)
                self.contacts_layout.addWidget(ccard)
        else:
            no_cont = QLabel("No contacts added yet.")
            no_cont.setStyleSheet("color: #64748B; padding: 6px;")
            self.contacts_layout.addWidget(no_cont)

    def _clear_layouts(self):
        self._clear_layout(self.projects_layout)
        self._clear_layout(self.contacts_layout)

    def _clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _on_new_project_clicked(self):
        if self.current_client:
            self.new_project_requested.emit(self.current_client)

    def _on_edit_client_clicked(self):
        if self.current_client:
            self.edit_client_requested.emit(self.current_client)

    def _on_new_contact_clicked(self):
        if self.current_client:
            self.new_contact_requested.emit(self.current_client)

    def _on_open_website_clicked(self):
        if self.current_client and self.current_client.website:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            url_str = self.current_client.website
            if not url_str.startswith("http"):
                url_str = f"https://{url_str}"
            QDesktopServices.openUrl(QUrl(url_str))


# Backward compatibility alias
ClientDashboard = ClientOverviewPanel
