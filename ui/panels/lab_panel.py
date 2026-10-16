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
    QComboBox,
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
        self._current_collection_id = None
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

        self.board_label = QLabel("— 🎨 Main Canvas")
        self.board_label.setStyleSheet("color: #94A3B8; font-size: 12px;")
        header_layout.addWidget(self.board_label)

        self.rename_board_btn = QPushButton("✏️")
        self.rename_board_btn.setToolTip("Rename current board")
        self.rename_board_btn.setFixedWidth(26)
        self.rename_board_btn.clicked.connect(self._on_rename_active_board_clicked)
        header_layout.addWidget(self.rename_board_btn)

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

        # Level 1 Collection / Main Board controls (Visible for global Workbench)
        self.collection_container = QWidget()
        col_container_layout = QVBoxLayout(self.collection_container)
        col_container_layout.setContentsMargins(0, 0, 0, 4)
        col_container_layout.setSpacing(4)

        col_header_layout = QHBoxLayout()
        self.col_title_label = QLabel("MAIN BOARD")
        col_header_layout.addWidget(self.col_title_label)
        col_header_layout.addStretch()

        self.add_col_btn = QPushButton("➕")
        self.add_col_btn.setToolTip("Create New Main Board")
        self.add_col_btn.setFixedWidth(24)
        self.add_col_btn.clicked.connect(self._on_create_collection_clicked)
        col_header_layout.addWidget(self.add_col_btn)

        self.rename_col_btn = QPushButton("✏️")
        self.rename_col_btn.setToolTip("Rename Current Main Board")
        self.rename_col_btn.setFixedWidth(24)
        self.rename_col_btn.clicked.connect(self._on_rename_collection_clicked)
        col_header_layout.addWidget(self.rename_col_btn)

        self.delete_col_btn = QPushButton("🗑️")
        self.delete_col_btn.setToolTip("Delete Current Main Board")
        self.delete_col_btn.setFixedWidth(24)
        self.delete_col_btn.clicked.connect(self._on_delete_collection_clicked)
        col_header_layout.addWidget(self.delete_col_btn)
        col_container_layout.addLayout(col_header_layout)

        self.collection_combo = QComboBox()
        self.collection_combo.setStyleSheet("""
            QComboBox {
                background-color: #232736;
                color: #F1F5F9;
                border: 1px solid #343847;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
                font-weight: bold;
            }
            QComboBox::drop-down {
                border: none;
                width: 18px;
            }
            QComboBox QAbstractItemView {
                background-color: #1E2029;
                color: #F1F5F9;
                selection-background-color: #312E81;
                selection-color: #A5B4FC;
                border: 1px solid #343847;
            }
        """)
        self.collection_combo.currentIndexChanged.connect(self._on_collection_combo_changed)
        col_container_layout.addWidget(self.collection_combo)

        col_sep = QFrame()
        col_sep.setFrameShape(QFrame.HLine)
        col_sep.setStyleSheet("color: #2E3342; margin-top: 4px; margin-bottom: 4px;")
        col_container_layout.addWidget(col_sep)

        sidebar_layout.addWidget(self.collection_container)

        # Sidebar Header Row (Working Boards)
        sb_header_layout = QHBoxLayout()
        self.sb_title_label = QLabel("WORKBENCH BOARDS")
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
        self.canvas._context = self._context
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
        if hasattr(self, "canvas") and self.canvas and hasattr(self.canvas, "set_context"):
            self.canvas.set_context(context)
        self._update_canvas_context()
        if context and getattr(context, "lab_service", None):
            if not getattr(self, "_lab_signals_connected", False):
                try:
                    context.lab_service.manifest_updated.connect(self._on_manifest_updated)
                    context.lab_service.board_updated.connect(self._on_manifest_updated)
                    self._lab_signals_connected = True
                except Exception:
                    pass

    def _on_manifest_updated(self, project, board_id=None):
        try:
            is_same_project = (self._current_project == project) if (self._current_project and project) else (self._current_project is None and project is None)
            if is_same_project:
                self._refresh_boards_sidebar()
        except Exception:
            pass

    def _update_canvas_context(self):
        if hasattr(self, "canvas") and self.canvas:
            self.canvas.project = self._current_project
            self.canvas._board_id = self._current_board_id

            from ui.lab.nodes.node_context import NodeContext
            proj_loc = getattr(self._current_project, "location", None) if self._current_project else None
            thumb_svc = getattr(self._context, "thumbnail_service", None) if self._context else None
            asset_svc = getattr(self._context, "asset_service", None) if self._context else None

            node_ctx = NodeContext(
                project_location=proj_loc,
                thumbnail_service=thumb_svc,
                asset_service=asset_svc,
                app_context=self._context,
                project=self._current_project,
                board_id=self._current_board_id,
            )
            self.canvas.set_node_context(node_ctx)
            if hasattr(self.canvas, "node_context") and self.canvas.node_context:
                self.canvas.node_context.project = self._current_project
                self.canvas.node_context.board_id = self._current_board_id

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
            if hasattr(self, "_persist_viewport"):
                self._persist_viewport()

    def _on_project_nav_clicked(self):
        if self._context and hasattr(self._context, "workspace_manager") and self._context.workspace_manager:
            if self._current_project:
                self._context.workspace_manager.show_project(self._current_project, section="dashboard")
            else:
                self._context.workspace_manager.show_home()

    def show_project(self, project, board_id: str = None, board_name: str = None, collection_id: str = None, target_node_id: str = None, force_reload: bool = False):
        # 1. Flush pending saves for previous project & board BEFORE changing references
        self.flush_pending_saves()

        prev_project = self._current_project
        prev_board_id = self._current_board_id
        prev_collection_id = getattr(self, "_current_collection_id", None)

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

        if not self._context or not getattr(self._context, "lab_service", None):
            return

        lab_svc = self._context.lab_service

        # Update collection context
        if project is None:
            if hasattr(self, "collection_container"):
                self.collection_container.setVisible(True)
            if hasattr(self, "sb_title_label") and self.sb_title_label:
                self.sb_title_label.setText("WORKBENCH BOARDS")

            if collection_id:
                self._current_collection_id = collection_id
                lab_svc.set_active_collection_id(None, collection_id)
            elif board_id:
                b_entry = lab_svc.get_board_entry(None, board_id)
                if b_entry and b_entry.get("collection_id"):
                    self._current_collection_id = b_entry["collection_id"]
                    lab_svc.set_active_collection_id(None, self._current_collection_id)
            elif not getattr(self, "_current_collection_id", None):
                self._current_collection_id = lab_svc.get_active_collection_id(None)
                if not self._current_collection_id:
                    cols = lab_svc.list_collections(None)
                    if cols:
                        self._current_collection_id = cols[0]["id"]
        else:
            if hasattr(self, "collection_container"):
                self.collection_container.setVisible(False)
            if hasattr(self, "sb_title_label") and self.sb_title_label:
                self.sb_title_label.setText("PROJECT BOARDS")
            self._current_collection_id = None

        self._update_canvas_context()

        target_board = board_id or board_name

        # Resolve active board ID from manifest if none provided
        if not target_board:
            if project is None and self._current_collection_id:
                col_boards = lab_svc.list_boards(None, collection_id=self._current_collection_id)
                active_id = lab_svc.get_active_board_id(None)
                if active_id and any(b["id"] == active_id for b in col_boards):
                    target_board = active_id
                elif col_boards:
                    target_board = col_boards[0]["id"]
            else:
                target_board = lab_svc.get_active_board_id(project)

        if not target_board:
            manifest = lab_svc.get_manifest(project)
            target_board = manifest.get("active_board_id")

        # Fast path guard: If already showing the exact project, collection, and board, don't reload disk!
        project_same = (prev_project == project) if (prev_project and project) else (prev_project is None and project is None)
        col_same = (prev_collection_id == self._current_collection_id)
        if not force_reload and project_same and col_same and prev_board_id and (prev_board_id == target_board or self._current_board_name == target_board):
            if target_node_id and hasattr(self, "canvas") and self.canvas:
                self.canvas.focus_node(target_node_id)
            return

        self._switch_to_board(target_board, force_reload=force_reload)

        if target_node_id and hasattr(self, "canvas") and self.canvas:
            self.canvas.focus_node(target_node_id)

    def _switch_to_board(self, board_id: str, force_reload: bool = False):
        """Single canonical board switching pipeline used across all navigation entry points."""
        if not self._context or not getattr(self._context, "lab_service", None):
            return

        lab_svc = self._context.lab_service

        # 3. Resolve target entry and set current board ID/name
        entry = lab_svc.get_board_entry(self._current_project, board_id)
        if not entry:
            boards = lab_svc.list_boards(self._current_project, collection_id=self._current_collection_id)
            entry = boards[0] if boards else None

        target_id = entry["id"] if entry else board_id

        # Fast path check: if board is already loaded and active, skip canvas clear & reload
        if not force_reload and self._current_board_id == target_id and len(getattr(self.canvas, "_items_map", {})) > 0:
            return

        # 1. Flush pending saves of previous board
        if self._current_board_id:
            self.flush_pending_saves()

        # 2. Persist viewport of previous board
        if self._current_board_id and hasattr(self, "_persist_viewport"):
            self._persist_viewport()

        if entry:
            self._current_board_id = entry["id"]
            self._current_board_name = entry["name"]
            if entry.get("collection_id"):
                self._current_collection_id = entry["collection_id"]
            if hasattr(self, "board_label") and self.board_label:
                if self._current_project is None and self._current_collection_id:
                    col = lab_svc.get_collection(None, self._current_collection_id)
                    col_name = col["name"] if col else "Main"
                    self.board_label.setText(f"— {col_name} › 🎨 {self._current_board_name} Canvas")
                else:
                    self.board_label.setText(f"— 🎨 {self._current_board_name} Canvas")

        if self._current_board_id:
            lab_svc.set_active_board_id(self._current_project, self._current_board_id)

        self._update_canvas_context()

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
            if hasattr(self.canvas, "set_viewport_state"):
                self.canvas.set_viewport_state(viewport)

            # Load nodes & connectors into scene
            disk_items = board_data.get("items", [])
            disk_connectors = board_data.get("connectors", [])
            self.canvas.blockSignals(True)
            try:
                for item_data in disk_items:
                    node = self.canvas.add_node(item_data)
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
        except Exception as e:
            import traceback
            print(f"[CRITICAL EXCEPTION IN _switch_to_board]: {e}", flush=True)
            traceback.print_exc()
        finally:
            self._is_loading = False
            self._is_switching_board = False

    def _refresh_boards_sidebar(self):
        if not self._context or not getattr(self._context, "lab_service", None):
            return

        lab_svc = self._context.lab_service

        if self._current_project:
            if hasattr(self, "collection_container"):
                self.collection_container.setVisible(False)
            if hasattr(self, "sb_title_label") and self.sb_title_label:
                self.sb_title_label.setText("PROJECT BOARDS")
            boards = lab_svc.list_boards(self._current_project)
        else:
            if hasattr(self, "collection_container"):
                self.collection_container.setVisible(True)
            if hasattr(self, "sb_title_label") and self.sb_title_label:
                self.sb_title_label.setText("WORKBENCH BOARDS")

            # Refresh collections combo
            if hasattr(self, "collection_combo"):
                collections = lab_svc.list_collections(None)
                was_blocked = self.collection_combo.signalsBlocked()
                self.collection_combo.blockSignals(True)
                try:
                    self.collection_combo.clear()
                    active_idx = 0
                    for idx, c in enumerate(collections):
                        self.collection_combo.addItem(f"🗂️ {c['name']}", c["id"])
                        if c["id"] == self._current_collection_id:
                            active_idx = idx
                    if collections:
                        self.collection_combo.setCurrentIndex(active_idx)
                finally:
                    self.collection_combo.blockSignals(was_blocked)

            boards = lab_svc.list_boards(None, collection_id=self._current_collection_id)

        # Optimization: Reuse sidebar items if board count and IDs match
        if self.boards_list.count() == len(boards):
            matches = True
            for idx, b in enumerate(boards):
                list_item = self.boards_list.item(idx)
                if not list_item or list_item.data(Qt.UserRole) != b["id"] or list_item.data(Qt.UserRole + 1) != b["name"]:
                    matches = False
                    break
            if matches:
                self.boards_list.blockSignals(True)
                for idx, b in enumerate(boards):
                    if b["id"] == self._current_board_id:
                        self.boards_list.setCurrentItem(self.boards_list.item(idx))
                        break
                self.boards_list.blockSignals(False)
                return

        self.boards_list.blockSignals(True)
        self.boards_list.clear()

        active_item = None
        for b in boards:
            item = QListWidgetItem(f"🎨 {b['name']}")
            item.setData(Qt.UserRole, b["id"])
            item.setData(Qt.UserRole + 1, b["name"])
            self.boards_list.addItem(item)

            if b["id"] == self._current_board_id:
                active_item = item

        if active_item:
            self.boards_list.setCurrentItem(active_item)
        elif self.boards_list.count() > 0:
            self.boards_list.setCurrentRow(0)

        self.boards_list.blockSignals(False)

    def _on_collection_combo_changed(self, index: int):
        if index < 0 or not self._context or not getattr(self._context, "lab_service", None):
            return
        col_id = self.collection_combo.itemData(index)
        if not col_id or col_id == self._current_collection_id:
            return
        self._current_collection_id = col_id
        lab_svc = self._context.lab_service
        lab_svc.set_active_collection_id(None, col_id)
        col_boards = lab_svc.list_boards(None, collection_id=col_id)
        target_board = col_boards[0]["id"] if col_boards else None
        if target_board:
            self._switch_to_board(target_board)
        else:
            self._refresh_boards_sidebar()

    def _on_create_collection_clicked(self):
        if not self._context or not getattr(self._context, "lab_service", None):
            return
        lab_svc = self._context.lab_service
        name, ok = QInputDialog.getText(self, "New Main Board", "Enter main board collection name:", text="New Collection")
        if ok and name.strip():
            entry = lab_svc.create_collection(None, name.strip())
            if entry:
                self._current_collection_id = entry["id"]
                active_board = lab_svc.get_active_board_id(None)
                if active_board:
                    self._switch_to_board(active_board)
                else:
                    self._refresh_boards_sidebar()

    def _on_rename_collection_clicked(self):
        if not self._context or not getattr(self._context, "lab_service", None) or not self._current_collection_id:
            return
        lab_svc = self._context.lab_service
        col = lab_svc.get_collection(None, self._current_collection_id)
        current_name = col["name"] if col else "Collection"
        name, ok = QInputDialog.getText(self, "Rename Main Board", "Enter new name:", text=current_name)
        if ok and name.strip() and name.strip() != current_name:
            if lab_svc.rename_collection(None, self._current_collection_id, name.strip()):
                if self._current_project is None:
                    self.board_label.setText(f"— {name.strip()} › 🎨 {self._current_board_name} Canvas")
                self._refresh_boards_sidebar()

    def _on_delete_collection_clicked(self):
        if not self._context or not getattr(self._context, "lab_service", None) or not self._current_collection_id:
            return
        lab_svc = self._context.lab_service
        cols = lab_svc.list_collections(None)
        if len(cols) <= 1:
            QMessageBox.warning(
                self,
                "Cannot Delete Main Board",
                "Cannot delete the final remaining main board in Workbench."
            )
            return

        col = lab_svc.get_collection(None, self._current_collection_id)
        col_name = col["name"] if col else "Main Board"
        num_children = len(lab_svc.list_boards(None, collection_id=self._current_collection_id))

        reply = QMessageBox.question(
            self,
            "Delete Main Board",
            f"Are you sure you want to delete main board '{col_name}' and its {num_children} working boards?\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if lab_svc.delete_collection(None, self._current_collection_id):
                self._current_collection_id = lab_svc.get_active_collection_id(None)
                new_active = lab_svc.get_active_board_id(None)
                if new_active:
                    self._switch_to_board(new_active, force_reload=True)
                else:
                    self._refresh_boards_sidebar()

    def _on_sidebar_item_clicked(self, item: QListWidgetItem):
        if not item:
            return
        board_id = item.data(Qt.UserRole)
        if board_id and board_id != self._current_board_id:
            self._switch_to_board(board_id)

    def _on_create_board_clicked(self):
        if not self._context or not getattr(self._context, "lab_service", None):
            return

        title = f"New Lab Board ({self._current_project.name})" if self._current_project else "New Working Board"
        name, ok = QInputDialog.getText(self, title, "Enter board name:", text="Untitled Board")
        if ok and name.strip():
            lab_svc = self._context.lab_service
            new_entry = lab_svc.create_board(self._current_project, name.strip(), collection_id=self._current_collection_id)
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
                    if self._current_project is None and self._current_collection_id:
                        col = lab_svc.get_collection(None, self._current_collection_id)
                        col_name = col["name"] if col else "Main"
                        self.board_label.setText(f"— {col_name} › 🎨 {self._current_board_name} Canvas")
                    else:
                        self.board_label.setText(f"— 🎨 {self._current_board_name} Canvas")
                self._refresh_boards_sidebar()

    def _on_rename_active_board_clicked(self):
        if self._current_board_id:
            self._on_rename_board_clicked(self._current_board_id, self._current_board_name)

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
        boards = lab_svc.list_boards(self._current_project, collection_id=self._current_collection_id)
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
            was_active = (board_id == self._current_board_id)
            if hasattr(self, "_item_save_timer") and self._item_save_timer.isActive():
                self._item_save_timer.stop()
            if hasattr(self, "_save_timer") and self._save_timer.isActive():
                self._save_timer.stop()
            if was_active:
                self._current_board_id = None
            if lab_svc.delete_board(self._current_project, board_id):
                new_active = lab_svc.get_active_board_id(self._current_project)
                if was_active:
                    self._switch_to_board(new_active, force_reload=True)
                else:
                    self._refresh_boards_sidebar()


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
