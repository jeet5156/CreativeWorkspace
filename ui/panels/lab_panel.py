from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
)
from PySide6.QtCore import Qt, QTimer

from ui.widgets.infinite_canvas import InfiniteCanvas


class LabPanel(QWidget):
    """Top-level workspace panel for the Creative Lab infinite canvas environment."""

    def __init__(self, context=None):
        super().__init__()
        self._context = context
        self._current_project = None
        self._current_board_name = "Main"

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

        title_label = QLabel("🧪 <b>Creative Lab</b>")
        header_layout.addWidget(title_label)

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

        main_layout.addWidget(header)

        # ---------------------------------------------------------------------
        # Infinite Canvas
        # ---------------------------------------------------------------------
        self.canvas = InfiniteCanvas(self)
        main_layout.addWidget(self.canvas)

        # Connect canvas signals
        self.canvas.camera_changed.connect(self._on_camera_changed)
        self.canvas.cursor_position_changed.connect(self._on_cursor_position_changed)
        self.canvas.node_added.connect(self._on_node_changed)
        self.canvas.node_modified.connect(self._on_node_changed)
        self.canvas.node_removed.connect(self._on_node_changed)

        # Connect toolbar button actions
        self.zoom_out_btn.clicked.connect(self.canvas.zoom_out)
        self.zoom_in_btn.clicked.connect(self.canvas.zoom_in)
        self.zoom_reset_btn.clicked.connect(self.canvas.reset_camera)
        self.grid_btn.clicked.connect(self._toggle_grid)

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

    def show_project(self, project, board_name: str = "Main"):
        self._current_project = project
        self._current_board_name = board_name
        self.board_label.setText(f"— {board_name} Canvas")
        self._update_canvas_context()

        if not self._context or not getattr(self._context, "lab_service", None):
            return

        try:
            board_data = self._context.lab_service.load_board(project, board_name=board_name)
            viewport = board_data.get("viewport", {})
            self.canvas.set_viewport_state(viewport)

            # Clear and load spatial nodes into scene
            self.canvas.clear_nodes()
            for item_data in board_data.get("items", []):
                self.canvas.add_node(item_data)
        except Exception:
            pass

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
        zoom_pct = int(viewport_state.get("zoom", 1.0) * 100)
        self.zoom_val_label.setText(f"{zoom_pct}%")

        grid_on = viewport_state.get("grid_visible", True)
        self.grid_btn.setText("Grid: On" if grid_on else "Grid: Off")

        # Schedule debounced auto-save
        if self._current_project:
            self._save_timer.start()

    def _on_cursor_position_changed(self, x: float, y: float):
        self.coords_label.setText(f"X: {int(x)}, Y: {int(y)}")

    def _on_node_changed(self, data=None):
        if self._current_project:
            self._item_save_timer.start()

    def _toggle_grid(self):
        new_state = not self.canvas.is_grid_visible()
        self.canvas.set_grid_visible(new_state)

    def _persist_viewport(self):
        if not self._current_project or not self._context or not getattr(self._context, "lab_service", None):
            return
        try:
            viewport = self.canvas.get_viewport_state()
            self._context.lab_service.save_viewport(self._current_project, viewport, board_name=self._current_board_name)
        except Exception:
            pass

    def _persist_items(self):
        if not self._current_project or not self._context or not getattr(self._context, "lab_service", None):
            return
        try:
            items_data = [item.to_dict() for item in self.canvas._items_map.values()]
            self._context.lab_service.save_items(self._current_project, items_data, board_name=self._current_board_name)
        except Exception:
            pass
