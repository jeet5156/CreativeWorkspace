from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QInputDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction

from ui.widgets.infinite_canvas import InfiniteCanvas


class LabPanel(QWidget):
    """Top-level workspace panel for the Creative Lab infinite canvas environment."""

    def __init__(self, context=None):
        super().__init__()
        self._context = context
        self._current_project = None
        self._current_board_id = None
        self._current_board_name = "Main"
        self._sidebar_visible = True

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---------------------------------------------------------------------
        # Header Toolbar
        # ---------------------------------------------------------------------
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #1E2029;
                border-bottom: 1px solid #2E3342;
                padding: 4px 8px;
            }
            QLabel {
                color: #F1F5F9;
                font-size: 13px;
            }
            QPushButton {
                background-color: #282B37;
                color: #CBD5E1;
                border: 1px solid #343847;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #343847;
                color: #F1F5F9;
            }
            QPushButton:pressed {
                background-color: #6366F1;
                color: #FFFFFF;
            }
        """)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(8)

        # Toggle Sidebar Button
        self.toggle_sidebar_btn = QPushButton("📋 Boards")
        self.toggle_sidebar_btn.setToolTip("Toggle Boards Sidebar")
        self.toggle_sidebar_btn.clicked.connect(self._toggle_sidebar)
        header_layout.addWidget(self.toggle_sidebar_btn)

        self.project_nav_btn = QPushButton("📁 Overview")
        self.project_nav_btn.setToolTip("Return to Project Overview Dashboard")
        self.project_nav_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E293B;
                color: #60A5FA;
                border: 1px solid #3B82F6;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3B82F6;
                color: #FFFFFF;
            }
        """)
        self.project_nav_btn.clicked.connect(self._on_project_nav_clicked)
        header_layout.addWidget(self.project_nav_btn)

        self.title_label = QLabel("🧪 <b>Creative Lab</b>")
        header_layout.addWidget(self.title_label)

        self.board_label = QLabel("— Main Canvas")
        self.board_label.setStyleSheet("color: #94A3B8; font-size: 12px;")
        header_layout.addWidget(self.board_label)

        header_layout.addStretch()

        # Mouse coordinate tracking indicator
        self.coords_label = QLabel("X: 0, Y: 0")
        self.coords_label.setStyleSheet("color: #64748B; font-size: 11px; font-family: monospace;")
        header_layout.addWidget(self.coords_label)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet("color: #2E3342;")
        header_layout.addWidget(sep1)

        # Zoom Controls
        self.zoom_out_btn = QPushButton("−")
        self.zoom_out_btn.setToolTip("Zoom Out")
        self.zoom_out_btn.setFixedWidth(28)
        header_layout.addWidget(self.zoom_out_btn)

        self.zoom_val_label = QLabel("100%")
        self.zoom_val_label.setFixedWidth(44)
        self.zoom_val_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.zoom_val_label)

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setToolTip("Zoom In")
        self.zoom_in_btn.setFixedWidth(28)
        header_layout.addWidget(self.zoom_in_btn)

        self.zoom_reset_btn = QPushButton("1:1")
        self.zoom_reset_btn.setToolTip("Reset Zoom & Pan")
        header_layout.addWidget(self.zoom_reset_btn)

        # Grid Toggle
        self.grid_btn = QPushButton("Grid: On")
        self.grid_btn.setToolTip("Toggle Background Grid")
        header_layout.addWidget(self.grid_btn)

        # Quick Search Button
        self.search_btn = QPushButton("🔍 Search (Ctrl+K)")
        self.search_btn.setToolTip("Quick Node Search Palette (Ctrl+K)")
        header_layout.addWidget(self.search_btn)

        main_layout.addWidget(header)

        # ---------------------------------------------------------------------
        # Body Container (Left Boards Sidebar + Right Infinite Canvas)
        # ---------------------------------------------------------------------
        body_widget = QWidget()
        body_layout = QHBoxLayout(body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Left Boards Sidebar
        self.sidebar_frame = QFrame()
        self.sidebar_frame.setFixedWidth(220)
        self.sidebar_frame.setStyleSheet("""
            QFrame {
                background-color: #171922;
                border-right: 1px solid #2E3342;
            }
            QLabel {
                color: #94A3B8;
                font-size: 11px;
                font-weight: bold;
            }
            QListWidget {
                background-color: transparent;
                border: none;
                color: #CBD5E1;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px 10px;
                border-radius: 4px;
                margin: 2px 4px;
            }
            QListWidget::item:hover {
                background-color: #232736;
                color: #F1F5F9;
            }
            QListWidget::item:selected {
                background-color: #312E81;
                color: #A5B4FC;
                font-weight: bold;
            }
        """)

        sidebar_layout = QVBoxLayout(self.sidebar_frame)
        sidebar_layout.setContentsMargins(6, 8, 6, 8)
        sidebar_layout.setSpacing(6)

        # Sidebar Header Row
        sb_header_layout = QHBoxLayout()
        self.sb_title_label = QLabel("PROJECT BOARDS")
        sb_header_layout.addWidget(self.sb_title_label)
        sb_header_layout.addStretch()

        self.add_board_btn = QPushButton("➕ New")
        self.add_board_btn.setToolTip("Create New Board")
        self.add_board_btn.setStyleSheet("""
            QPushButton {
                background-color: #282B37;
                color: #A5B4FC;
                border: 1px solid #343847;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #343847;
                color: #FFFFFF;
            }
        """)
        self.add_board_btn.clicked.connect(self._on_create_board_clicked)
        sb_header_layout.addWidget(self.add_board_btn)
        sidebar_layout.addLayout(sb_header_layout)

        # Boards List Widget
        self.boards_list = QListWidget()
        self.boards_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.boards_list.customContextMenuRequested.connect(self._show_sidebar_context_menu)
        self.boards_list.itemClicked.connect(self._on_sidebar_item_clicked)
        sidebar_layout.addWidget(self.boards_list)

        body_layout.addWidget(self.sidebar_frame)

        # Infinite Canvas
        self.canvas = InfiniteCanvas(self)
        body_layout.addWidget(self.canvas)

        main_layout.addWidget(body_widget)

        # Connect canvas signals
        self.canvas.camera_changed.connect(self._on_camera_changed)
        self.canvas.cursor_position_changed.connect(self._on_cursor_position_changed)
        self.canvas.node_added.connect(self._on_node_changed)
        self.canvas.node_modified.connect(self._on_node_changed)
        self.canvas.node_removed.connect(self._on_node_changed)
        self.canvas.selection_changed.connect(self._on_selection_changed)

        # Connect toolbar button actions
        self.zoom_out_btn.clicked.connect(self.canvas.zoom_out)
        self.zoom_in_btn.clicked.connect(self.canvas.zoom_in)
        self.zoom_reset_btn.clicked.connect(self.canvas.reset_camera)
        self.grid_btn.clicked.connect(self._toggle_grid)
        self.search_btn.clicked.connect(self.canvas.open_node_search_dialog)

        # Debounce timer for persisting viewport state
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._persist_viewport)

        # Debounce timer for persisting board items
        self._item_save_timer = QTimer(self)
        self._item_save_timer.setSingleShot(True)
        self._item_save_timer.setInterval(500)
        self._item_save_timer.timeout.connect(self._persist_items)

    def set_context(self, context):
        self._context = context
        self._update_canvas_context()

    def _toggle_sidebar(self):
        self._sidebar_visible = not self._sidebar_visible
        self.sidebar_frame.setVisible(self._sidebar_visible)

    def flush_pending_saves(self):
        """Synchronously flush any pending debounced items or viewport saves."""
        if getattr(self, "_is_loading", False) or getattr(self, "_is_switching_board", False):
            return

        if hasattr(self, "_item_save_timer") and self._item_save_timer.isActive():
            self._item_save_timer.stop()
            self._persist_items()

        if hasattr(self, "_save_timer") and self._save_timer.isActive():
            self._save_timer.stop()
            self._persist_viewport()

    def _on_project_nav_clicked(self):
        if self._context and hasattr(self._context, "workspace_manager") and self._context.workspace_manager:
            if self._current_project:
                self._context.workspace_manager.show_project(self._current_project, section="dashboard")
            else:
                self._context.workspace_manager.show_home()

    def show_project(self, project, board_id: str = None, board_name: str = None, target_node_id: str = None):
        # 1. Flush pending saves for previous project & board BEFORE changing references
        self.flush_pending_saves()

        # 2. Update current project reference
        self._current_project = project
        if hasattr(self, "project_nav_btn"):
            if project:
                self.project_nav_btn.setText(f"📁 {project.name}")
            else:
                self.project_nav_btn.setText("🏠 Home")

        if hasattr(self, "title_label") and self.title_label:
            if project:
                self.title_label.setText("🧪 <b>Creative Lab</b>")
            else:
                self.title_label.setText("🛠️ <b>Workbench</b>")

        self._update_canvas_context()

        if not self._context or not getattr(self._context, "lab_service", None):
            return

        lab_svc = self._context.lab_service
        target_board = board_id or board_name

        # Resolve active board ID from manifest if none provided
        if not target_board:
            target_board = lab_svc.get_active_board_id(project)

        if not target_board:
            manifest = lab_svc.get_manifest(project)
            target_board = manifest.get("active_board_id")

        self._switch_to_board(target_board)

        if target_node_id and hasattr(self, "canvas") and self.canvas:
            self.canvas.focus_node(target_node_id)

    def _switch_to_board(self, board_id: str):
        """Single canonical board switching pipeline used across all navigation entry points."""
        if not self._context or not getattr(self._context, "lab_service", None):
            return

        lab_svc = self._context.lab_service

        # 1. Flush pending saves of previous board
        self.flush_pending_saves()

        # 2. Persist viewport of previous board
        self._persist_viewport()

        # 3. Resolve target entry and set current board ID/name
        entry = lab_svc.get_board_entry(self._current_project, board_id)
        if not entry:
            boards = lab_svc.list_boards(self._current_project)
            entry = boards[0] if boards else None

        if entry:
            self._current_board_id = entry["id"]
            self._current_board_name = entry["name"]
            self.board_label.setText(f"— {self._current_board_name} Canvas")

        if self._current_board_id:
            lab_svc.set_active_board_id(self._current_project, self._current_board_id)

        self._is_switching_board = True
        self._is_loading = True
        try:
            # 4. Clear canvas nodes
            was_blocked = self.canvas.signalsBlocked()
            self.canvas.blockSignals(True)
            try:
                self.canvas.clear_nodes()
            finally:
                self.canvas.blockSignals(was_blocked)

            # 5. Load target board data
            board_data = lab_svc.load_board(self._current_project, self._current_board_id)

            # 6. Restore viewport
            viewport = board_data.get("viewport", {})
            self.canvas.set_viewport_state(viewport)

            # Load nodes & connectors into scene
            disk_items = board_data.get("items", [])
            disk_connectors = board_data.get("connectors", [])
            self.canvas.blockSignals(True)
            try:
                for item_data in disk_items:
                    self.canvas.add_node(item_data)
                for conn_data in disk_connectors:
                    self.canvas.add_connector(conn_data)
            finally:
                self.canvas.blockSignals(was_blocked)

            # 7. Restore selection state / clear inspector
            if getattr(self._context, "inspector_panel", None):
                try:
                    self._context.inspector_panel.inspect(None)
                except Exception:
                    pass

            # 8 & 9. Update UI sidebar selection and board label
            self._refresh_boards_sidebar()
        finally:
            self._is_loading = False
            self._is_switching_board = False

    def _refresh_boards_sidebar(self):
        if not self._context or not getattr(self._context, "lab_service", None):
            return

        if hasattr(self, "sb_title_label") and self.sb_title_label:
            if self._current_project:
                self.sb_title_label.setText("PROJECT BOARDS")
            else:
                self.sb_title_label.setText("WORKBENCH BOARDS")

        lab_svc = self._context.lab_service
        boards = lab_svc.list_boards(self._current_project)

        self.boards_list.blockSignals(True)
        self.boards_list.clear()

        active_item = None
        for b in boards:
            item = QListWidgetItem(f"📋 {b['name']}")
            item.setData(Qt.UserRole, b["id"])
            item.setData(Qt.UserRole + 1, b["name"])
            self.boards_list.addItem(item)

            if b["id"] == self._current_board_id:
                active_item = item

        if active_item:
            self.boards_list.setCurrentItem(active_item)

        self.boards_list.blockSignals(False)

    def _on_sidebar_item_clicked(self, item: QListWidgetItem):
        if not item:
            return
        board_id = item.data(Qt.UserRole)
        if board_id and board_id != self._current_board_id:
            self._switch_to_board(board_id)

    def _on_create_board_clicked(self):
        if not self._context or not getattr(self._context, "lab_service", None):
            return

        name, ok = QInputDialog.getText(self, "New Board", "Enter board name:", text="Untitled Board")
        if ok and name.strip():
            lab_svc = self._context.lab_service
            new_entry = lab_svc.create_board(self._current_project, name.strip())
            if new_entry:
                self._switch_to_board(new_entry["id"])

    def _show_sidebar_context_menu(self, pos):
        item = self.boards_list.itemAt(pos)
        if not item:
            return

        board_id = item.data(Qt.UserRole)
        board_name = item.data(Qt.UserRole + 1)

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #202334;
                color: #F1F5F9;
                border: 1px solid #313652;
            }
            QMenu::item:selected {
                background-color: #312E81;
                color: #A5B4FC;
            }
        """)

        switch_act = QAction("Open Board", self)
        rename_act = QAction("✏️ Rename Board", self)
        dup_act = QAction("📋 Duplicate Board", self)
        delete_act = QAction("🗑️ Delete Board", self)

        switch_act.triggered.connect(lambda: self._switch_to_board(board_id))
        rename_act.triggered.connect(lambda: self._on_rename_board_clicked(board_id, board_name))
        dup_act.triggered.connect(lambda: self._on_duplicate_board_clicked(board_id))
        delete_act.triggered.connect(lambda: self._on_delete_board_clicked(board_id, board_name))

        menu.addAction(switch_act)
        menu.addAction(rename_act)
        menu.addAction(dup_act)
        menu.addSeparator()
        menu.addAction(delete_act)
        menu.exec_(self.boards_list.mapToGlobal(pos))

    def _on_rename_board_clicked(self, board_id: str, old_name: str):
        if not self._context or not getattr(self._context, "lab_service", None):
            return
        name, ok = QInputDialog.getText(self, "Rename Board", "Enter new board name:", text=old_name)
        if ok and name.strip():
            lab_svc = self._context.lab_service
            if lab_svc.rename_board(self._current_project, board_id, name.strip()):
                if board_id == self._current_board_id:
                    self._current_board_name = name.strip()
                    self.board_label.setText(f"— {self._current_board_name} Canvas")
                self._refresh_boards_sidebar()

    def _on_duplicate_board_clicked(self, board_id: str):
        if not self._context or not getattr(self._context, "lab_service", None):
            return
        lab_svc = self._context.lab_service
        new_entry = lab_svc.duplicate_board(self._current_project, board_id)
        if new_entry:
            self._switch_to_board(new_entry["id"])

    def _on_delete_board_clicked(self, board_id: str, board_name: str):
        if not self._context or not getattr(self._context, "lab_service", None):
            return
        lab_svc = self._context.lab_service
        boards = lab_svc.list_boards(self._current_project)
        if len(boards) <= 1:
            QMessageBox.warning(
                self,
                "Cannot Delete Board",
                "Cannot delete the final remaining board."
            )
            return

        reply = QMessageBox.question(
            self,
            "Delete Board",
            f"Are you sure you want to delete board '{board_name}'?\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Delete board via LabService (which handles active board fallback if needed)
            active_fallback = lab_svc.get_active_board_id(self._current_project)
            if lab_svc.delete_board(self._current_project, board_id):
                # Switch to newly set active board
                new_active = lab_svc.get_active_board_id(self._current_project)
                self._switch_to_board(new_active)

    def _update_canvas_context(self):
        from ui.lab.nodes.node_context import NodeContext
        proj_loc = getattr(self._current_project, "location", None) if self._current_project else None
        thumb_svc = getattr(self._context, "thumbnail_service", None) if self._context else None
        asset_svc = getattr(self._context, "asset_service", None) if self._context else None

        node_ctx = NodeContext(
            project_location=proj_loc,
            thumbnail_service=thumb_svc,
            asset_service=asset_svc,
            app_context=self._context,
        )
        self.canvas.set_node_context(node_ctx)

    def _on_camera_changed(self, viewport_state: dict):
        if getattr(self, "_is_loading", False) or getattr(self, "_is_switching_board", False):
            return
        zoom_pct = int(viewport_state.get("zoom", 1.0) * 100)
        self.zoom_val_label.setText(f"{zoom_pct}%")

        grid_on = viewport_state.get("grid_visible", True)
        self.grid_btn.setText("Grid: On" if grid_on else "Grid: Off")

        # Schedule debounced auto-save
        if self._context and getattr(self._context, "lab_service", None):
            self._save_timer.start()

    def _on_cursor_position_changed(self, x: float, y: float):
        self.coords_label.setText(f"X: {int(x)}, Y: {int(y)}")

    def _on_node_changed(self, data=None):
        if getattr(self, "_is_loading", False) or getattr(self, "_is_switching_board", False):
            return
        if not self._context or not getattr(self._context, "lab_service", None):
            return
        self._item_save_timer.start()

    def _on_selection_changed(self, selected_items: list):
        if not self._context or not getattr(self._context, "inspector_panel", None):
            return

        inspector = self._context.inspector_panel
        from ui.lab.connectors.connector_item import ConnectorItem
        try:
            all_selected = self.canvas._scene.selectedItems()
            sel_connectors = [it for it in all_selected if isinstance(it, ConnectorItem)]
            sel_nodes = [it for it in all_selected if not isinstance(it, ConnectorItem)]

            if len(sel_connectors) == 1 and not sel_nodes:
                from core.inspectable_adapters import ConnectorInspectable
                inspector.inspect(ConnectorInspectable(sel_connectors[0]))
            elif len(sel_nodes) == 1 and not sel_connectors:
                inspector.show_node(sel_nodes[0])
            elif len(sel_nodes) > 1:
                from core.inspectable_adapters import MultiNodeInspectable
                adapter = MultiNodeInspectable(sel_nodes)
                inspector.inspect(adapter)
            else:
                inspector.inspect(None)
        except Exception:
            pass

    def _toggle_grid(self):
        new_state = not self.canvas.is_grid_visible()
        self.canvas.set_grid_visible(new_state)

    def _persist_viewport(self):
        if getattr(self, "_is_loading", False) or getattr(self, "_is_switching_board", False):
            return
        if not self._context or not getattr(self._context, "lab_service", None):
            return
        try:
            viewport = self.canvas.get_viewport_state()
            self._context.lab_service.save_viewport(self._current_project, viewport, board_id_or_name=self._current_board_id or "Main")
        except Exception:
            pass

    def _persist_items(self):
        if getattr(self, "_is_loading", False) or getattr(self, "_is_switching_board", False):
            return
        if not self._context or not getattr(self._context, "lab_service", None):
            return
        try:
            items_data = [item.to_dict() for item in self.canvas._items_map.values()]
            connectors_data = [conn.to_dict() for conn in self.canvas._connector_map.values()]
            self._context.lab_service.save_items(
                self._current_project,
                items_data,
                connectors_list=connectors_data,
                board_id_or_name=self._current_board_id or "Main"
            )
        except Exception:
            pass
