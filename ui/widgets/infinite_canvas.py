import math
import uuid
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem, QMenu
from PySide6.QtCore import Qt, Signal, QPointF, QRectF, QPoint
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QAction

from core.canvas_clipboard import CanvasClipboard
from core.canvas_command import CanvasCommand
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
    selection_changed = Signal(list)

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

        # Canvas Clipboard subsystem instance
        self.clipboard = CanvasClipboard()
        self._last_context_scene_pos = None

        # Internal node dictionary: node_id -> NodeItem
        self._items_map = {}
        self._is_loading = False

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
        self.setDragMode(QGraphicsView.RubberBandDrag)

        # Connect scene selection changes to canvas signal
        self._scene.selectionChanged.connect(self._on_scene_selection_changed)

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

    def _on_scene_selection_changed(self):
        selected = self.selected_nodes()
        try:
            self.selection_changed.emit(selected)
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and self._space_pressed):
            self._is_panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            self.setDragMode(QGraphicsView.NoDrag)
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

        # Check drop attachment onto Frame nodes
        selected = self.selected_nodes()
        if selected:
            for node in selected:
                if not isinstance(node, FrameNodeItem):
                    node_center = node.sceneBoundingRect().center()
                    for item in self._items_map.values():
                        if isinstance(item, FrameNodeItem):
                            if item.sceneBoundingRect().contains(node_center):
                                item.attach_node(node)
                                break

        for item in self._items_map.values():
            if isinstance(item, FrameNodeItem) and item._is_drag_hovered:
                item._is_drag_hovered = False
                item.update()

        if self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.OpenHandCursor if self._space_pressed else Qt.ArrowCursor)
            self.setDragMode(QGraphicsView.RubberBandDrag)
            event.accept()
            self._emit_camera_changed()
            return
        super().mouseReleaseEvent(event)

    def execute_command(self, command, **kwargs):
        """Single command dispatcher for spatial canvas operations.
        Establishes command architecture foundation for future Undo/Redo stack integration.
        """
        # TODO: Push command to undo stack.

        cmd_val = command.value if isinstance(command, CanvasCommand) else str(command).lower()

        if cmd_val == CanvasCommand.COPY.value:
            return self.copy_selection()
        elif cmd_val == CanvasCommand.PASTE.value:
            mouse_pos = kwargs.get("mouse_pos") or self._last_context_scene_pos
            return self.paste(mouse_pos=mouse_pos)
        elif cmd_val == CanvasCommand.DUPLICATE.value:
            return self.duplicate_selection()
        elif cmd_val == CanvasCommand.DELETE.value:
            return self.delete_selection()
        elif cmd_val == CanvasCommand.SELECT_ALL.value:
            return self.select_all()
        elif cmd_val == CanvasCommand.CLEAR_SELECTION.value:
            return self.clear_selection()
        return None

    def copy_selection(self):
        """Serialize currently selected nodes into CanvasClipboard with Figma-style frame rules."""
        selected = self.selected_nodes()
        if not selected:
            return
        from services.frame_service import FrameService
        prepared_nodes = FrameService.prepare_clipboard_nodes(selected)
        self.clipboard.copy(prepared_nodes)

    def paste(self, mouse_pos: QPointF = None) -> list:
        """Deserialize nodes from CanvasClipboard, assign fresh UUIDs, apply offset, and select pasted nodes."""
        if not self.clipboard.has_content():
            return []

        nodes_data = self.clipboard.get_nodes()
        paste_count = self.clipboard.increment_paste_count()
        offset = 20.0 * paste_count

        centroid_offset_x = 0.0
        centroid_offset_y = 0.0
        if mouse_pos and nodes_data:
            xs = []
            ys = []
            for n in nodes_data:
                t = n.get("transform", {})
                if isinstance(t, dict):
                    x = float(t.get("x", 0.0))
                    y = float(t.get("y", 0.0))
                    w = float(t.get("width", 200.0))
                    h = float(t.get("height", 150.0))
                    xs.extend([x, x + w])
                    ys.extend([y, y + h])
            if xs and ys:
                center_x = (min(xs) + max(xs)) / 2.0
                center_y = (min(ys) + max(ys)) / 2.0
                centroid_offset_x = mouse_pos.x() - center_x
                centroid_offset_y = mouse_pos.y() - center_y

        pasted_nodes = []
        old_to_new_id_map = {}
        for node_data in nodes_data:
            old_id = node_data.get("id")
            new_id = str(uuid.uuid4())
            node_data["id"] = new_id
            if old_id:
                old_to_new_id_map[old_id] = new_id

            # Apply coordinate placement
            transform = node_data.get("transform", {})
            if isinstance(transform, dict):
                orig_x = float(transform.get("x", 0.0))
                orig_y = float(transform.get("y", 0.0))
                if mouse_pos:
                    transform["x"] = round(orig_x + centroid_offset_x + (offset - 20.0), 2)
                    transform["y"] = round(orig_y + centroid_offset_y + (offset - 20.0), 2)
                else:
                    transform["x"] = round(orig_x + offset, 2)
                    transform["y"] = round(orig_y + offset, 2)
                node_data["transform"] = transform

            node = self.add_node(node_data)
            if node:
                pasted_nodes.append(node)

        if pasted_nodes:
            from services.frame_service import FrameService
            FrameService.remap_pasted_memberships(pasted_nodes, old_to_new_id_map)
            # Transfer selection exclusively to newly pasted nodes and emit single selection_changed
            self.set_selected_nodes(pasted_nodes)

        return pasted_nodes

    def duplicate_selection(self) -> list:
        """Duplicate selected nodes by executing Copy -> Paste sequentially."""
        selected = self.selected_nodes()
        if not selected:
            return []
        self.copy_selection()
        return self.paste()

    def delete_selection(self):
        """Single canonical deletion handler for selected canvas nodes."""
        selected = self.selected_nodes()
        if not selected:
            return
        for node in selected:
            if getattr(node, "is_locked", False):
                continue
            if hasattr(node, "on_deleted"):
                try:
                    node.on_deleted()
                except Exception:
                    pass
            self.remove_node(node.id)
        self.clear_selection()

    delete_selected_nodes = delete_selection

    def keyPressEvent(self, event):
        mods = event.modifiers()
        key = event.key()

        if mods & Qt.ControlModifier:
            if key == Qt.Key_C:
                self.execute_command(CanvasCommand.COPY)
                event.accept()
                return
            elif key == Qt.Key_V:
                self.execute_command(CanvasCommand.PASTE)
                event.accept()
                return
            elif key == Qt.Key_D:
                self.execute_command(CanvasCommand.DUPLICATE)
                event.accept()
                return
            elif key == Qt.Key_A:
                self.select_all()
                event.accept()
                return

        if key == Qt.Key_Escape:
            self.execute_command(CanvasCommand.CLEAR_SELECTION)
            event.accept()
            return
        elif key == Qt.Key_Space and not event.isAutoRepeat():
            self._space_pressed = True
            if not self._is_panning:
                self.setCursor(Qt.OpenHandCursor)
            event.accept()
            return
        elif key in (Qt.Key_Delete, Qt.Key_Backspace):
            self.execute_command(CanvasCommand.DELETE)
            event.accept()
            return
        super().keyPressEvent(event)

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

        node_type = node_data.get("type", "note.blank")
        node = NodeRegistry.create_node(node_type, node_context=self.node_context)
        if not node:
            return None

        node.from_dict(node_data)
        node.node_modified.connect(self._on_node_item_modified)

        self._items_map[node.id] = node
        self._scene.addItem(node)

        # Emit node_added signal unless bulk loading
        if not self._is_loading:
            try:
                self.node_added.emit(node.to_dict())
            except Exception:
                pass
        return node

    # Backward compatibility alias
    add_item = add_node

    def remove_node(self, node_id: str):
        if node_id in self._items_map:
            node = self._items_map.pop(node_id)
            from ui.lab.nodes.frame_node_item import FrameNodeItem
            from services.frame_service import FrameService
            if isinstance(node, FrameNodeItem):
                FrameService.cleanup_frame_deletion(node, self)
            else:
                FrameService.cleanup_node_deletion(node_id, self._items_map)

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

    def clear_selection(self):
        self._scene.clearSelection()

    def select_all(self):
        for node in self._items_map.values():
            node.setSelected(True)

    def set_selected_nodes(self, nodes: list):
        self._scene.clearSelection()
        for node in nodes:
            if hasattr(node, "setSelected"):
                node.setSelected(True)

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
        self._last_context_scene_pos = scene_pos
        item = self.itemAt(event.pos())

        # If right-clicked on a spatial node item, display node context menu
        if isinstance(item, NodeItem):
            # Ensure the right-clicked item is selected if not already part of selection
            if not item.isSelected():
                self.set_selected_nodes([item])

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

            # Attach / Detach Frame submenus for spatial non-frame nodes
            from ui.lab.nodes.frame_node_item import FrameNodeItem
            from services.frame_service import FrameService
            if not isinstance(item, FrameNodeItem):
                all_frames = [it for it in self._items_map.values() if isinstance(it, FrameNodeItem)]
                if all_frames:
                    parent_id = item.payload.get("parent_frame_id") if hasattr(item, "payload") and isinstance(item.payload, dict) else None
                    if not parent_id:
                        attach_menu = menu.addMenu("🖼️  Attach to Frame")
                        for frame_item in all_frames:
                            title = str(frame_item.payload.get("title", "Section Frame"))
                            act = QAction(f"🖼️ {title}", attach_menu)
                            act.triggered.connect(lambda checked=False, f=frame_item, n=item: FrameService.attach_node(f, n))
                            attach_menu.addAction(act)
                    else:
                        current_frame = next((f for f in all_frames if f.id == parent_id), None)
                        detach_act = QAction("❌  Detach from Frame", self)
                        detach_act.triggered.connect(lambda checked=False, f=current_frame, n=item: FrameService.detach_node(f, n) if f else None)
                        menu.addAction(detach_act)

                        other_frames = [f for f in all_frames if f.id != parent_id]
                        if other_frames:
                            move_menu = menu.addMenu("↔️  Move to Frame")
                            for frame_item in other_frames:
                                title = str(frame_item.payload.get("title", "Section Frame"))
                                act = QAction(f"🖼️ {title}", move_menu)
                                act.triggered.connect(lambda checked=False, cur=current_frame, target=frame_item, n=item: FrameService.move_node_to_frame(n, cur, target))
                                move_menu.addAction(act)
                    menu.addSeparator()

            copy_act = QAction("📄  Copy", self)
            copy_act.triggered.connect(lambda: self.execute_command(CanvasCommand.COPY))
            menu.addAction(copy_act)

            dup_act = QAction("👯  Duplicate", self)
            dup_act.triggered.connect(lambda: self.execute_command(CanvasCommand.DUPLICATE))
            menu.addAction(dup_act)

            del_action = QAction("🗑  Delete Node", self)
            del_action.triggered.connect(lambda: self.execute_command(CanvasCommand.DELETE))
            menu.addAction(del_action)

            menu.exec_(event.globalPos())
            return

        menu = NodeRegistry.build_context_menu(self, scene_pos, self._create_node_from_def)

        # Prepend Canvas Edit Actions (Paste, Select All, Clear Selection)
        paste_act = QAction("📋  Paste", self)
        paste_act.setEnabled(self.clipboard.has_content())
        paste_act.triggered.connect(lambda: self.execute_command(CanvasCommand.PASTE, mouse_pos=scene_pos))

        select_all_act = QAction("🔲  Select All", self)
        select_all_act.triggered.connect(lambda: self.execute_command(CanvasCommand.SELECT_ALL))

        clear_sel_act = QAction("🚫  Clear Selection", self)
        clear_sel_act.triggered.connect(lambda: self.execute_command(CanvasCommand.CLEAR_SELECTION))

        actions = menu.actions()
        if actions:
            first_act = actions[0]
            menu.insertAction(first_act, paste_act)
            menu.insertAction(first_act, select_all_act)
            menu.insertAction(first_act, clear_sel_act)
            menu.insertSeparator(first_act)
        else:
            menu.addAction(paste_act)
            menu.addAction(select_all_act)
            menu.addAction(clear_sel_act)

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
