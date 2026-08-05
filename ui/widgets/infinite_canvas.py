import math
import uuid
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem, QMenu
from PySide6.QtCore import Qt, Signal, QPointF, QRectF, QPoint
from PySide6.QtGui import QPainter, QPen, QColor, QBrush

from ui.lab.nodes.node_definition import NodeDefinition
from ui.lab.nodes.node_capability import NodeCapability
from ui.lab.nodes.node_item import NodeItem
from ui.lab.nodes.node_registry import NodeRegistry
from ui.lab.nodes.node_context import NodeContext


class InfiniteCanvas(QGraphicsView):
    """Infinite 2D spatial canvas powered by QGraphicsView.

    Supports smooth mouse-centric panning and zooming, infinite background grid rendering,
    camera tracking, spatial node item management, and data-driven context menus.
    """

    camera_changed = Signal(dict)
    cursor_position_changed = Signal(float, float)
    node_added = Signal(dict)
    node_modified = Signal(dict)
    node_removed = Signal(str)

    # Aliases for backward compatibility
    card_added = node_added
    card_modified = node_modified
    card_removed = node_removed

    MIN_ZOOM = 0.1
    MAX_ZOOM = 5.0
    ZOOM_STEP = 1.15

    def __init__(self, parent=None):
        super().__init__(parent)

        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(-50000, -50000, 100000, 100000)
        self.setScene(self._scene)

        # Shared Node Context for all spatial items
        self.node_context = NodeContext()

        # Internal node dictionary: node_id -> NodeItem
        self._items_map = {}

        # Viewport rendering flags
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setBackgroundBrush(QBrush(QColor("#1A1C23")))

        # State
        self._zoom_level = 1.0
        self._grid_visible = True
        self._grid_size = 20
        self._snap_to_grid = False
        self._is_panning = False
        self._pan_start = QPoint()
        self._space_pressed = False

        # Center view at scene origin initially
        self.centerOn(0, 0)

    # -------------------------------------------------------------------------
    # Camera & Viewport API
    # -------------------------------------------------------------------------

    def get_viewport_state(self) -> dict:
        center = self.mapToScene(self.viewport().rect().center())
        return {
            "zoom": round(self._zoom_level, 4),
            "pan_x": round(center.x(), 2),
            "pan_y": round(center.y(), 2),
            "grid_visible": self._grid_visible,
            "grid_size": self._grid_size,
            "snap_to_grid": self._snap_to_grid,
            "active_tool": "select",
        }

    def set_viewport_state(self, state: dict):
        if not state or not isinstance(state, dict):
            return

        self._grid_visible = bool(state.get("grid_visible", True))
        self._grid_size = int(state.get("grid_size", 20))
        self._snap_to_grid = bool(state.get("snap_to_grid", False))

        target_zoom = float(state.get("zoom", 1.0))
        target_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, target_zoom))
        scale_factor = target_zoom / self._zoom_level
        self.scale(scale_factor, scale_factor)
        self._zoom_level = target_zoom

        pan_x = float(state.get("pan_x", 0.0))
        pan_y = float(state.get("pan_y", 0.0))
        self.centerOn(pan_x, pan_y)

        self.viewport().update()
        self._emit_camera_changed()

    def reset_camera(self):
        scale_factor = 1.0 / self._zoom_level
        self.scale(scale_factor, scale_factor)
        self._zoom_level = 1.0
        self.centerOn(0, 0)
        self.viewport().update()
        self._emit_camera_changed()

    def zoom_in(self):
        self._apply_zoom(self.ZOOM_STEP)

    def zoom_out(self):
        self._apply_zoom(1.0 / self.ZOOM_STEP)

    def set_grid_visible(self, visible: bool):
        self._grid_visible = visible
        self.viewport().update()
        self._emit_camera_changed()

    def is_grid_visible(self) -> bool:
        return self._grid_visible

    # -------------------------------------------------------------------------
    # Zooming Logic
    # -------------------------------------------------------------------------

    def _apply_zoom(self, factor: float):
        new_zoom = self._zoom_level * factor
        if new_zoom < self.MIN_ZOOM:
            factor = self.MIN_ZOOM / self._zoom_level
            new_zoom = self.MIN_ZOOM
        elif new_zoom > self.MAX_ZOOM:
            factor = self.MAX_ZOOM / self._zoom_level
            new_zoom = self.MAX_ZOOM

        self.scale(factor, factor)
        self._zoom_level = new_zoom
        self.viewport().update()
        self._emit_camera_changed()

    def wheelEvent(self, event):
        angle = event.angleDelta().y()
        if angle > 0:
            self._apply_zoom(self.ZOOM_STEP)
        elif angle < 0:
            self._apply_zoom(1.0 / self.ZOOM_STEP)
        event.accept()

    # -------------------------------------------------------------------------
    # Panning & Mouse Interactions
    # -------------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and self._space_pressed):
            self._is_panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        self.cursor_position_changed.emit(scene_pos.x(), scene_pos.y())

        if self._is_panning:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()

            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())

            event.accept()
            return

        # Check drag hover feedback for Frame nodes when dragging spatial nodes
        selected = self.selected_nodes()
        if selected and (event.buttons() & Qt.LeftButton):
            from ui.lab.nodes.frame_node_item import FrameNodeItem
            dragged_centers = [n.sceneBoundingRect().center() for n in selected if not isinstance(n, FrameNodeItem)]
            if dragged_centers:
                for item in self._items_map.values():
                    if isinstance(item, FrameNodeItem):
                        frame_rect = item.sceneBoundingRect()
                        is_hovered = any(frame_rect.contains(pt) for pt in dragged_centers)
                        if item._is_drag_hovered != is_hovered:
                            item._is_drag_hovered = is_hovered
                            item.update()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        from ui.lab.nodes.frame_node_item import FrameNodeItem
        for item in self._items_map.values():
            if isinstance(item, FrameNodeItem) and item._is_drag_hovered:
                item._is_drag_hovered = False
                item.update()

        if self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.OpenHandCursor if self._space_pressed else Qt.ArrowCursor)
            event.accept()
            self._emit_camera_changed()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._space_pressed = True
            if not self._is_panning:
                self.setCursor(Qt.OpenHandCursor)
            event.accept()
            return
        elif event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected_nodes()
            event.accept()
            return
        super().keyPressEvent(event)

    def delete_selected_nodes(self):
        selected = self.selected_nodes()
        for node in selected:
            if getattr(node, "is_locked", False):
                continue
            if hasattr(node, "on_deleted"):
                try:
                    node.on_deleted()
                except Exception:
                    pass
            self.remove_node(node.id)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._space_pressed = False
            if not self._is_panning:
                self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().keyReleaseEvent(event)

    def _emit_camera_changed(self):
        try:
            self.camera_changed.emit(self.get_viewport_state())
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Infinite Grid Painting
    # -------------------------------------------------------------------------

    def drawBackground(self, painter: QPainter, rect: QRectF):
        painter.fillRect(rect, QColor("#14161D"))

        if not self._grid_visible:
            return

        grid_size = self._grid_size
        left = int(math.floor(rect.left() / grid_size)) * grid_size
        top = int(math.floor(rect.top() / grid_size)) * grid_size

        dot_pen = QPen(QColor("#2E3342"))
        dot_pen.setWidth(1)
        painter.setPen(dot_pen)

        x = left
        while x < rect.right():
            y = top
            while y < rect.bottom():
                painter.drawPoint(int(x), int(y))
                y += grid_size
            x += grid_size

    def set_node_context(self, context: NodeContext):
        """Update shared NodeContext and propagate to all existing scene node items."""
        self.node_context = context or NodeContext()
        for node in self._items_map.values():
            if hasattr(node, "set_node_context"):
                node.set_node_context(self.node_context)

    def update_project_location(self, project_location: str):
        """Update project_location in shared NodeContext and propagate to all scene items."""
        if not self.node_context:
            self.node_context = NodeContext()
        self.node_context.project_location = project_location
        for node in self._items_map.values():
            if hasattr(node, "set_node_context"):
                node.set_node_context(self.node_context)

    # -------------------------------------------------------------------------
    # Spatial Node Item API (Data-Driven, Zero Switches)
    # -------------------------------------------------------------------------

    def add_node(self, node_data: dict) -> NodeItem:
        if not node_data or not isinstance(node_data, dict):
            return None

        # Extract type or legacy payload note_type
        type_id = str(node_data.get("type", "")).lower()
        if not type_id or type_id == "note":
            payload = node_data.get("payload", {})
            note_type = str(payload.get("note_type", "blank")).lower()
            type_id = f"note.{note_type}"

        # Delegate instantiation to NodeRegistry with standard NodeContext
        node = NodeRegistry.create_node(type_id, node_data, node_context=self.node_context)
        node.node_modified.connect(self._on_node_item_modified)

        self._scene.addItem(node)
        self._items_map[node.id] = node
        return node

    # Backward compatibility alias
    add_item = add_node

    def remove_node(self, node_id: str):
        if node_id in self._items_map:
            node = self._items_map.pop(node_id)
            self._scene.removeItem(node)
            try:
                self.node_removed.emit(node_id)
            except Exception:
                pass

    remove_item = remove_node

    def find_node(self, node_id: str) -> NodeItem:
        return self._items_map.get(node_id)

    find_item = find_node

    def selected_nodes(self) -> list:
        return [it for it in self._scene.selectedItems() if isinstance(it, NodeItem)]

    selected_card_items = selected_nodes

    def clear_nodes(self):
        for node_id, node in list(self._items_map.items()):
            self._scene.removeItem(node)
        self._items_map.clear()

    clear_items = clear_nodes

    def _on_node_item_modified(self, node_dict: dict):
        try:
            self.node_modified.emit(node_dict)
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Context Menu (Generated Dynamically via NodeRegistry)
    # -------------------------------------------------------------------------

    def contextMenuEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        item = self.itemAt(event.pos())

        # If right-clicked on a spatial node item, display node context menu
        if isinstance(item, NodeItem):
            menu = QMenu(self)
            menu.setStyleSheet("""
                QMenu {
                    background-color: #1E2029;
                    border: 1px solid #343847;
                    border-radius: 6px;
                    padding: 4px;
                }
                QMenu::item {
                    color: #CBD5E1;
                    padding: 6px 12px;
                    border-radius: 4px;
                    font-size: 12px;
                }
                QMenu::item:selected {
                    background-color: #343847;
                    color: #F1F5F9;
                }
            """)
            if hasattr(item, "on_context_menu"):
                item.on_context_menu(menu)
                if not menu.isEmpty():
                    menu.addSeparator()

            target_node_id = item.id
            del_action = QAction("🗑  Delete Node", self)
            del_action.triggered.connect(lambda: self.remove_node(target_node_id))
            menu.addAction(del_action)

            menu.exec_(event.globalPos())
            return

        menu = NodeRegistry.build_context_menu(self, scene_pos, self._create_node_from_def)
        menu.exec_(event.globalPos())

    def _create_node_from_def(self, defn: NodeDefinition, scene_pos: QPointF):
        node_data = {
            "id": str(uuid.uuid4()),
            "type": defn.type_id,
            "transform": {
                "x": round(scene_pos.x(), 2),
                "y": round(scene_pos.y(), 2),
                "z": 1,
                "width": defn.default_size[0],
                "height": defn.default_size[1],
                "rotation": 0.0,
            },
            "style": {
                "background": defn.background_color,
                "accent": defn.accent_color,
            },
            "metadata": {
                "version": 1,
                "locked": False,
            },
            "payload": dict(defn.payload_schema),
        }

        node = self.add_node(node_data)
        if node:
            node.setSelected(True)
            try:
                self.node_added.emit(node.to_dict())
            except Exception:
                pass
