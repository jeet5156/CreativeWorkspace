from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QFrame,
    QScrollArea,
    QGridLayout,
    QStackedWidget,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from models.client import Client
from ui.widgets.client_card import ClientCard
from ui.panels.client_dashboard import ClientDashboard
from ui.dialogs.client_dialog import ClientDialog
from core.inspectable_adapters import ClientInspectable


class ClientWorkspacePanel(QWidget):
    """Container-based Client Workspace Panel (Header → Search Bar → Card Grid → Dashboard Host).

    Supports:
    - Empty State banner with + Create Client action.
    - Responsive grid of ClientCards with persistent + Create Client header action.
    - Live Search filtering by client name, company, or type.
    - Embedded read-only ClientDashboard host with live Inspector auto-save integration.
    """

    client_selected = Signal(object)

    def __init__(self, context=None, parent=None):
        super().__init__(parent)
        self.context = context
        self.client_service = getattr(context, "client_service", None) if context else None
        self.project_service = getattr(context, "project_service", None) if context else None
        self.current_client: Optional[Client] = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # 1. Header Row (Title & Persistent + Create Client Button)
        header_row = QHBoxLayout()

        title_lbl = QLabel("Clients")
        title_lbl.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title_lbl.setStyleSheet("color: #F1F5F9;")
        header_row.addWidget(title_lbl)

        header_row.addStretch()

        self.btn_back_to_grid = QPushButton("← All Clients")
        self.btn_back_to_grid.setStyleSheet("""
            QPushButton {
                background-color: #2E3342;
                color: #F1F5F9;
                border: 1px solid #343847;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #38BDF8;
                color: #0F172A;
            }
        """)
        self.btn_back_to_grid.setVisible(False)
        self.btn_back_to_grid.clicked.connect(self.show_card_grid)
        header_row.addWidget(self.btn_back_to_grid)

        self.btn_create_client = QPushButton("➕ Create Client")
        self.btn_create_client.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: #FFFFFF;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
        """)
        self.btn_create_client.clicked.connect(self.prompt_create_client)
        header_row.addWidget(self.btn_create_client)

        main_layout.addLayout(header_row)

        # 2. Search Bar
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search clients by name, company, or type...")
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #1E2029;
                color: #F1F5F9;
                border: 1px solid #343847;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #38BDF8;
            }
        """)
        self.search_edit.textChanged.connect(self._on_search_changed)
        main_layout.addWidget(self.search_edit)

        # 3. Stack Host Container
        self.stack = QStackedWidget()

        # View 0: Empty State Banner
        self.empty_widget = self._create_empty_state_widget()
        self.stack.addWidget(self.empty_widget)

        # View 1: Card Grid Scroll Area
        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setFrameShape(QFrame.NoFrame)
        self.grid_scroll.setStyleSheet("QScrollArea { background-color: transparent; }")

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(16)
        self.grid_scroll.setWidget(self.grid_container)
        self.stack.addWidget(self.grid_scroll)

        # View 2: Dashboard Host Panel
        self.dashboard_panel = ClientDashboard()
        self.dashboard_panel.open_project_requested.connect(self._on_open_project)
        self.dashboard_panel.reveal_project_requested.connect(self._on_reveal_project)
        self.dashboard_panel.new_project_requested.connect(self.prompt_create_project_for_client)
        self.dashboard_panel.edit_client_requested.connect(self.prompt_edit_client)
        self.dashboard_panel.archive_client_requested.connect(self.archive_client)
        self.dashboard_panel.duplicate_client_requested.connect(self.duplicate_client)
        self.dashboard_panel.delete_client_requested.connect(self.prompt_delete_client)
        self.stack.addWidget(self.dashboard_panel)

        # View 3: Root Clients Dashboard (Module Summary View)
        from ui.panels.client_root_dashboard import ClientRootDashboard
        self.root_dashboard = ClientRootDashboard()
        self.root_dashboard.create_client_requested.connect(self.prompt_create_client)
        self.root_dashboard.client_selected.connect(self.show_client_dashboard)
        self.stack.addWidget(self.root_dashboard)

        main_layout.addWidget(self.stack)

        # Wire client_service and project_service signal connections if context is available
        if self.client_service:
            try:
                self.client_service.client_created.connect(lambda c: self.refresh())
                self.client_service.client_updated.connect(lambda c: self.refresh())
                self.client_service.client_deleted.connect(lambda cid: self.on_client_deleted(cid))
            except Exception:
                pass

        if self.project_service:
            try:
                self.project_service.project_created.connect(lambda p: self._on_project_changed())
                self.project_service.project_updated.connect(lambda p: self._on_project_changed())
                self.project_service.project_deleted.connect(lambda p: self._on_project_changed())
            except Exception:
                pass

        self.refresh()

    def set_context(self, context):
        self.context = context
        self.client_service = getattr(context, "client_service", None)
        self.project_service = getattr(context, "project_service", None)
        if self.client_service:
            try:
                self.client_service.client_created.connect(lambda c: self.refresh())
                self.client_service.client_updated.connect(lambda c: self.refresh())
                self.client_service.client_deleted.connect(lambda cid: self.on_client_deleted(cid))
            except Exception:
                pass
        if self.project_service:
            try:
                self.project_service.project_created.connect(lambda p: self._on_project_changed())
                self.project_service.project_updated.connect(lambda p: self._on_project_changed())
                self.project_service.project_deleted.connect(lambda p: self._on_project_changed())
            except Exception:
                pass
        self.refresh()

    def _on_project_changed(self):
        if self.current_client:
            self.show_client_dashboard(self.current_client)

    def _create_empty_state_widget(self) -> QWidget:
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: #1E2029;
                border: 1px dashed #343847;
                border-radius: 12px;
                padding: 40px;
            }
        """)
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        icon_lbl = QLabel("👥")
        icon_lbl.setFont(QFont("Segoe UI", 36))
        layout.addWidget(icon_lbl, alignment=Qt.AlignCenter)

        head_lbl = QLabel("No clients yet.")
        head_lbl.setFont(QFont("Segoe UI", 16, QFont.Bold))
        head_lbl.setStyleSheet("color: #F1F5F9;")
        layout.addWidget(head_lbl, alignment=Qt.AlignCenter)

        sub_lbl = QLabel("Manage studios, freelance clients, publishers,\nand collaborators from one place.")
        sub_lbl.setFont(QFont("Segoe UI", 11))
        sub_lbl.setAlignment(Qt.AlignCenter)
        sub_lbl.setStyleSheet("color: #94A3B8;")
        layout.addWidget(sub_lbl, alignment=Qt.AlignCenter)

        btn = QPushButton("➕ Create Client")
        btn.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: #FFFFFF;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
        """)
        btn.clicked.connect(self.prompt_create_client)
        layout.addWidget(btn, alignment=Qt.AlignCenter)

        return widget

    def refresh(self):
        if not self.client_service:
            self.stack.setCurrentWidget(self.empty_widget)
            return

        clients = self.client_service.list_clients()

        # Update root dashboard metrics
        if hasattr(self, "root_dashboard") and self.root_dashboard:
            try:
                self.root_dashboard.set_clients(clients)
            except Exception:
                pass

        # Update Explorer if available
        if self.context and hasattr(self.context, "explorer_panel") and self.context.explorer_panel:
            try:
                self.context.explorer_panel.load_clients(clients)
            except Exception:
                pass

        if not clients:
            self.stack.setCurrentWidget(self.empty_widget)
            self.search_edit.setVisible(False)
            self.btn_back_to_grid.setVisible(False)
            return

        self.search_edit.setVisible(True)

        # Filter clients by search text
        query = self.search_edit.text().strip().lower()
        if query:
            filtered = [
                c for c in clients
                if query in c.name.lower() or query in c.company.lower() or query in c.client_type.lower()
            ]
        else:
            filtered = clients

        # Populate Grid
        self._clear_grid()
        col_count = 3
        for idx, client in enumerate(filtered):
            card = ClientCard(client)
            card.open_requested.connect(self.show_client_dashboard)
            card.clicked.connect(self.show_client_dashboard)
            row = idx // col_count
            col = idx % col_count
            self.grid_layout.addWidget(card, row, col)

        if query:
            self.stack.setCurrentWidget(self.grid_scroll)
        elif self.stack.currentWidget() in (self.dashboard_panel, self.root_dashboard, self.grid_scroll):
            pass
        else:
            self.stack.setCurrentWidget(self.grid_scroll)

    def _clear_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item and item.widget():
                w = item.widget()
                w.setParent(None)
                w.deleteLater()

    def show_clients_root_dashboard(self):
        self.current_client = None
        self.btn_back_to_grid.setVisible(False)
        clients = self.client_service.list_clients() if self.client_service else []
        if not clients:
            self.stack.setCurrentWidget(self.empty_widget)
        elif hasattr(self, "root_dashboard") and self.root_dashboard:
            self.root_dashboard.set_clients(clients)
            self.stack.setCurrentWidget(self.root_dashboard)
        else:
            self.show_card_grid()

    def show_card_grid(self):
        self.current_client = None
        self.btn_back_to_grid.setVisible(False)
        self.refresh()
        clients = self.client_service.list_clients() if self.client_service else []
        if clients:
            self.stack.setCurrentWidget(self.grid_scroll)
        else:
            self.stack.setCurrentWidget(self.empty_widget)

    def show_client_dashboard(self, client: Client):
        if not client:
            return

        self.current_client = client
        self.dashboard_panel.set_client(client, project_service=self.project_service)
        self.stack.setCurrentWidget(self.dashboard_panel)
        self.btn_back_to_grid.setVisible(True)

        # Set ClientInspectable in Inspector
        inspector = getattr(self.context, "inspector_panel", None) if self.context else None
        if inspector:
            try:
                adapter = ClientInspectable(client, client_service=self.client_service, on_updated_callback=self._on_client_inspected_updated)
                inspector.inspect(adapter)
            except Exception:
                pass

        try:
            self.client_selected.emit(client)
        except Exception:
            pass

    def prompt_edit_client(self, client: Optional[Client] = None):
        target = client or self.current_client
        if not target:
            return

        dialog = ClientDialog(self, client=target)
        if dialog.exec() == ClientDialog.Accepted:
            data = dialog.get_client_data()
            if data and data.get("name"):
                target.name = data["name"]
                target.company = data.get("company", "")
                target.priority = data.get("priority", "Medium")
                target.client_type = data.get("client_type", "Game Studio")
                target.status = data.get("status", "Active")
                target.industry = data.get("industry", "")
                target.website = data.get("website", "")
                target.country = data.get("country", "")
                target.tags = data.get("tags", [])
                target.notes = data.get("notes", "")

                if self.client_service:
                    self.client_service.save_client(target)
                self.refresh()
                self.show_client_dashboard(target)

    def archive_client(self, client: Optional[Client] = None):
        target = client or self.current_client
        if target and self.client_service:
            self.client_service.archive_client(target.id)
            self.refresh()
            self.show_client_dashboard(target)

    def duplicate_client(self, client: Optional[Client] = None):
        target = client or self.current_client
        if target and self.client_service:
            dup = self.client_service.duplicate_client(target.id)
            if dup:
                self.refresh()
                self.show_client_dashboard(dup)

    def prompt_delete_client(self, client: Optional[Client] = None):
        target = client or self.current_client
        if target and self.client_service:
            self.client_service.delete_client(target.id, self.project_service)

    def prompt_create_project_for_client(self, client: Client):
        if not client or not self.project_service:
            return

        from ui.dialogs.new_project_dialog import NewProjectDialog
        clients_list = self.client_service.list_clients() if self.client_service else []
        dialog = NewProjectDialog(
            parent=self,
            clients=clients_list,
            preselected_client_id=client.id,
            lock_client=True,
        )

        if dialog.exec():
            name = dialog.name_edit.text().strip()
            ptype = dialog.type_combo.currentText()
            loc = dialog.location_edit.text().strip()
            desc = dialog.description_edit.toPlainText()
            snap = dialog.snapshot_path
            selected_cid = dialog.get_selected_client_id() or client.id

            if not name or not loc:
                return

            project = self.project_service.create_project(
                name=name,
                project_type=ptype,
                location=loc,
                description=desc,
                snapshot_path=snap,
            )

            # Delegate to canonical MainWindow.register_and_open_project helper if available
            mw = getattr(self.context, "main_window", None) if self.context else None
            if mw and hasattr(mw, "register_and_open_project"):
                mw.register_and_open_project(project, client_id=selected_cid)
            else:
                # Fallback to local bookkeeping
                project.client_id = selected_cid
                self.project_service.save_project(project)
                if self.client_service:
                    self.client_service.assign_project_to_client(project.name, selected_cid, self.project_service)
                if self.context and getattr(self.context, "settings_service", None):
                    self.context.settings_service.add_recent_project(project.location)
                if self.context and getattr(self.context, "explorer_panel", None):
                    self.context.explorer_panel.load_projects(self.project_service.all_projects())
                self._on_open_project(project)

            # Refresh Client Dashboard
            if client:
                self.show_client_dashboard(client)

    def _on_client_inspected_updated(self, client: Client):
        """Callback when Client properties are live-edited in Inspector."""
        if self.current_client and self.current_client.id == client.id:
            self.dashboard_panel.set_client(client, project_service=self.project_service)
        if hasattr(self, "root_dashboard") and self.root_dashboard and self.client_service:
            self.root_dashboard.set_clients(self.client_service.list_clients())
        if self.context and hasattr(self.context, "explorer_panel") and self.context.explorer_panel and self.client_service:
            self.context.explorer_panel.load_clients(self.client_service.list_clients())

    def on_client_deleted(self, client_id: str):
        """Handle client deletion by clearing dashboard if open and refreshing grid & explorer."""
        self.refresh()
        clients = self.client_service.list_clients() if self.client_service else []
        if not clients:
            self.stack.setCurrentWidget(self.empty_widget)
        elif self.current_client and self.current_client.id == client_id:
            self.show_clients_root_dashboard()

        # Clear Inspector if currently inspecting deleted client
        inspector = getattr(self.context, "inspector_panel", None) if self.context else None
        if inspector:
            try:
                inspector.clear_inspection()
            except Exception:
                pass

    def prompt_create_client(self):
        dialog = ClientDialog(self)
        if dialog.exec() == ClientDialog.Accepted:
            data = dialog.get_client_data()
            if data and data.get("name"):
                new_client = self.client_service.create_client(
                    name=data["name"],
                    company=data.get("company", ""),
                    priority=data.get("priority", "Medium"),
                    client_type=data.get("client_type", "Game Studio"),
                    status=data.get("status", "Active"),
                    industry=data.get("industry", ""),
                    website=data.get("website", ""),
                    country=data.get("country", ""),
                    tags=data.get("tags", []),
                    notes=data.get("notes", ""),
                )
                self.refresh()
                self.show_client_dashboard(new_client)

    def _on_search_changed(self, text: str):
        if text.strip():
            self.stack.setCurrentWidget(self.grid_scroll)
        self.refresh()

    def _on_open_project(self, project):
        if self.context and hasattr(self.context, "workspace_manager") and self.context.workspace_manager:
            try:
                self.context.workspace_manager.show_project(project)
            except Exception:
                pass

    def _on_reveal_project(self, project):
        if self.context and hasattr(self.context, "explorer_panel") and self.context.explorer_panel:
            try:
                self.context.explorer_panel.reveal_project(project)
            except Exception:
                pass

