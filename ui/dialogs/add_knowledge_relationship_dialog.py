"""Dialog for selecting and adding relationships (Projects, Library Assets, Project Assets, Lab Nodes) to Knowledge Documents."""

from typing import Optional, Dict, Any, Tuple
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QComboBox,
    QPushButton,
)

from models.library_models import AssetAvailability


class AddKnowledgeRelationshipDialog(QDialog):
    """Dialog allowing users to link Projects, Library Assets, Project Assets, or Lab Nodes."""

    def __init__(self, context=None, parent=None, current_doc=None):
        super().__init__(parent)
        self.setWindowTitle("Link Knowledge Relationship")
        self.resize(560, 480)
        self.setModal(True)

        self._context = context
        self._current_doc = current_doc
        self._selected_result: Optional[Tuple[str, Dict[str, Any]]] = None

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #141620;
                color: #F1F5F9;
            }
            QTabWidget::pane {
                border: 1px solid #282C40;
                background-color: #12141C;
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #1E2029;
                color: #94A3B8;
                border: 1px solid #282C40;
                padding: 8px 14px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 600;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background-color: #283556;
                color: #38BDF8;
                border-bottom: 1px solid #283556;
            }
            QLineEdit, QComboBox {
                background-color: #1E2029;
                color: #F1F5F9;
                border: 1px solid #2E3342;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #38BDF8;
            }
            QListWidget {
                background-color: #12141C;
                color: #CBD5E1;
                border: 1px solid #282C40;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 4px;
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

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header Title
        hdr = QLabel("🔗 Link Knowledge Relationship")
        hdr.setFont(QFont("Segoe UI", 13, QFont.Bold))
        hdr.setStyleSheet("color: #F1F5F9;")
        main_layout.addWidget(hdr)

        # Tabs for 4 relationship types
        self.tabs = QTabWidget()

        self.tab_projects = self._create_projects_tab()
        self.tabs.addTab(self.tab_projects, "📁 Projects")

        self.tab_library = self._create_library_tab()
        self.tabs.addTab(self.tab_library, "📚 Library Assets")

        self.tab_project_assets = self._create_project_assets_tab()
        self.tabs.addTab(self.tab_project_assets, "📦 Project Assets")

        self.tab_lab_nodes = self._create_lab_nodes_tab()
        self.tabs.addTab(self.tab_lab_nodes, "🎨 Lab Nodes")

        main_layout.addWidget(self.tabs, 1)

        # Bottom Action Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #1E2029;
                color: #94A3B8;
                border: 1px solid #2E3342;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #282C40;
                color: #F1F5F9;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_link = QPushButton("Link Relationship")
        self.btn_link.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
        """)
        self.btn_link.clicked.connect(self._on_link_clicked)
        btn_row.addWidget(self.btn_link)

        main_layout.addLayout(btn_row)

    # -------------------------------------------------------------------------
    # Tab 1: Projects
    # -------------------------------------------------------------------------
    def _create_projects_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Select a project to associate with this Knowledge note:"))

        self.projects_list = QListWidget()
        self.projects_list.itemDoubleClicked.connect(self._on_link_clicked)

        proj_svc = getattr(self._context, "project_service", None) if self._context else None
        if proj_svc:
            all_projs = proj_svc.all_projects()
            for p in all_projs:
                p_name = p.name or Path(p.location).name
                item = QListWidgetItem(f"📁  {p_name} ({p.project_type.capitalize()})")
                item.setData(Qt.UserRole, p_name)
                item.setToolTip(p.location)
                self.projects_list.addItem(item)

        if self.projects_list.count() > 0:
            self.projects_list.setCurrentRow(0)

        layout.addWidget(self.projects_list, 1)
        return widget

    # -------------------------------------------------------------------------
    # Tab 2: Global Library Assets
    # -------------------------------------------------------------------------
    def _create_library_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.lib_search = QLineEdit()
        self.lib_search.setPlaceholderText("Filter library assets...")
        self.lib_search.textChanged.connect(self._filter_library_assets)
        layout.addWidget(self.lib_search)

        self.library_list = QListWidget()
        self.library_list.itemDoubleClicked.connect(self._on_link_clicked)
        layout.addWidget(self.library_list, 1)

        self._filter_library_assets("")
        return widget

    def _filter_library_assets(self, query: str):
        self.library_list.clear()
        lib_svc = getattr(self._context, "library_service", None) if self._context else None
        if not lib_svc:
            return

        query_clean = query.strip().lower()
        if hasattr(lib_svc, "query_assets"):
            assets = lib_svc.query_assets(query=query_clean) if query_clean else lib_svc.query_assets()
        elif hasattr(lib_svc, "get_assets"):
            assets = lib_svc.get_assets()
        else:
            assets = []

        for a in assets:
            avail = lib_svc.get_asset_availability(a) if hasattr(lib_svc, "get_asset_availability") else AssetAvailability.AVAILABLE
            status_icon = "🟢" if avail == AssetAvailability.AVAILABLE else ("🟠" if avail == AssetAvailability.OFFLINE else "🔴")
            item_text = f"{status_icon}  {a.filename}  [{getattr(a, 'category', 'Assets')} • {getattr(a, 'friendly_type', 'Asset')}]"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, a.id)
            item.setToolTip(f"ID: {a.id}\nPath: {getattr(a, 'drive_relative_path', '')}\nStatus: {getattr(avail, 'value', str(avail))}")
            self.library_list.addItem(item)

        if self.library_list.count() > 0:
            self.library_list.setCurrentRow(0)

    # -------------------------------------------------------------------------
    # Tab 3: Project-Local Assets
    # -------------------------------------------------------------------------
    def _create_project_assets_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.proj_asset_search = QLineEdit()
        self.proj_asset_search.setPlaceholderText("Filter project assets...")

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Project:"))
        self.proj_asset_combo = QComboBox()

        proj_svc = getattr(self._context, "project_service", None) if self._context else None
        if proj_svc:
            for p in proj_svc.all_projects():
                self.proj_asset_combo.addItem(f"📁 {p.name}", p)

        self.proj_asset_combo.currentIndexChanged.connect(self._on_proj_asset_combo_changed)
        top_row.addWidget(self.proj_asset_combo, 1)
        layout.addLayout(top_row)

        self.proj_asset_search.textChanged.connect(self._filter_project_assets)
        layout.addWidget(self.proj_asset_search)

        self.proj_asset_list = QListWidget()
        self.proj_asset_list.itemDoubleClicked.connect(self._on_link_clicked)
        layout.addWidget(self.proj_asset_list, 1)

        self._filter_project_assets("")
        return widget

    def _on_proj_asset_combo_changed(self):
        query = self.proj_asset_search.text() if hasattr(self, "proj_asset_search") else ""
        self._filter_project_assets(query)

    def _filter_project_assets(self, query: str):
        self.proj_asset_list.clear()
        asset_svc = getattr(self._context, "asset_service", None) if self._context else None
        curr_proj = self.proj_asset_combo.currentData()
        if not asset_svc or not curr_proj:
            return

        query_clean = query.strip().lower()
        assets = asset_svc.get_assets(curr_proj)

        for a in assets:
            fn = a.get("filename", "")
            rp = a.get("relative_path", "")
            cat = a.get("category", "Assets")
            a_id = a.get("id", "")

            if not query_clean or query_clean in fn.lower() or query_clean in rp.lower() or query_clean in cat.lower():
                item = QListWidgetItem(f"📦  {fn}  [{cat} • {rp}]")
                item.setData(Qt.UserRole, {"project_id": curr_proj.name, "asset_id": a_id, "relative_path": rp})
                item.setToolTip(f"ID: {a_id}\nRelative Path: {rp}")
                self.proj_asset_list.addItem(item)

        if self.proj_asset_list.count() > 0:
            self.proj_asset_list.setCurrentRow(0)

    # -------------------------------------------------------------------------
    # Tab 4: Creative Lab Nodes
    # -------------------------------------------------------------------------
    def _create_lab_nodes_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.lab_search = QLineEdit()
        self.lab_search.setPlaceholderText("Filter lab nodes...")

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Project / Board:"))
        self.lab_proj_combo = QComboBox()

        proj_svc = getattr(self._context, "project_service", None) if self._context else None
        self.lab_proj_combo.addItem("🛠️ Global Workbench", None)
        if proj_svc:
            for p in proj_svc.all_projects():
                self.lab_proj_combo.addItem(f"📁 {p.name}", p)

        self.lab_proj_combo.currentIndexChanged.connect(self._on_lab_proj_combo_changed)
        top_row.addWidget(self.lab_proj_combo, 1)
        layout.addLayout(top_row)

        self.lab_search.textChanged.connect(self._filter_lab_nodes)
        layout.addWidget(self.lab_search)

        self.lab_nodes_list = QListWidget()
        self.lab_nodes_list.itemDoubleClicked.connect(self._on_link_clicked)
        layout.addWidget(self.lab_nodes_list, 1)

        self._filter_lab_nodes("")
        return widget

    def _on_lab_proj_combo_changed(self):
        query = self.lab_search.text() if hasattr(self, "lab_search") else ""
        self._filter_lab_nodes(query)

    def _filter_lab_nodes(self, query: str):
        self.lab_nodes_list.clear()
        lab_svc = getattr(self._context, "lab_service", None) if self._context else None
        proj = self.lab_proj_combo.currentData()
        if not lab_svc:
            return

        query_clean = query.strip().lower()
        boards = lab_svc.list_boards(proj)
        proj_name = proj.name if proj else None

        for b in boards:
            b_id = b.get("id")
            b_name = b.get("name", "Board")
            board_data = lab_svc.load_board(proj, b_id)
            items = board_data.get("items", [])

            for node in items:
                n_id = node.get("id")
                n_type = node.get("type", "node")
                payload = node.get("payload", {})
                title = payload.get("title") or payload.get("label") or payload.get("name") or n_type

                if not query_clean or query_clean in str(title).lower() or query_clean in str(n_type).lower() or query_clean in b_name.lower():
                    item = QListWidgetItem(f"🎨  {title}  [{b_name} • {n_type}]")
                    item.setData(Qt.UserRole, {"node_id": n_id, "board_id": b_id, "project_id": proj_name})
                    item.setToolTip(f"Node ID: {n_id}\nBoard: {b_name}")
                    self.lab_nodes_list.addItem(item)

        if self.lab_nodes_list.count() > 0:
            self.lab_nodes_list.setCurrentRow(0)

    # -------------------------------------------------------------------------
    # Final Result Extraction
    # -------------------------------------------------------------------------
    def _on_link_clicked(self):
        tab_idx = self.tabs.currentIndex()

        if tab_idx == 0:
            # Project
            curr = self.projects_list.currentItem()
            if curr:
                self._selected_result = ("project", {"project_id": curr.data(Qt.UserRole)})
                self.accept()
        elif tab_idx == 1:
            # Library Asset
            curr = self.library_list.currentItem()
            if curr:
                self._selected_result = ("library_asset", {"asset_id": curr.data(Qt.UserRole)})
                self.accept()
        elif tab_idx == 2:
            # Project Asset
            curr = self.proj_asset_list.currentItem()
            if curr:
                self._selected_result = ("project_asset", curr.data(Qt.UserRole))
                self.accept()
        elif tab_idx == 3:
            # Lab Node
            curr = self.lab_nodes_list.currentItem()
            if curr:
                self._selected_result = ("lab_node", curr.data(Qt.UserRole))
                self.accept()

    def get_selected_relationship(self) -> Optional[Tuple[str, Dict[str, Any]]]:
        return self._selected_result
