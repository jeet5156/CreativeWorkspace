import math
import uuid
from typing import Optional, List, Dict
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsPathItem, QMenu
from PySide6.QtCore import Qt, Signal, QPointF, QRectF, QPoint
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QAction, QPainterPath

from core.canvas_clipboard import CanvasClipboard
from core.canvas_command import CanvasCommand
from services.connection_manager import ConnectionManager
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
        self.connection_manager = ConnectionManager(self)
        self._connector_map = self.connection_manager._connectors
        self._is_loading = False

        # Phase 2 Navigation Subsystems
        from ui.lab.models.navigation_history import NavigationHistoryService
        self.nav_history_service = NavigationHistoryService()
        self._board_id = "Main"
        self._saved_views = {}

        # Connection drag preview state
        self._drag_connection_start_node = None
        self._drag_connection_start_anchor = "center"
        self._drag_connection_preview_item = None

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

        # Drag & Drop Router Subsystem Adapter
        from ui.lab.drop.drop_router import DropRouter
        self.drop_router = DropRouter()
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.StrongFocus)

        from PySide6.QtGui import QKeySequence, QShortcut

        self._back_shortcut = QShortcut(QKeySequence(Qt.ALT | Qt.Key_Left), self)
        self._back_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._back_shortcut.activated.connect(self._on_shortcut_go_back)

        self._forward_shortcut = QShortcut(QKeySequence(Qt.ALT | Qt.Key_Right), self)
        self._forward_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._forward_shortcut.activated.connect(self._on_shortcut_go_forward)

        # Center view at scene origin initially
        self.centerOn(0, 0)

    # -------------------------------------------------------------------------
    # Drag & Drop Adapter Event Handlers
    # -------------------------------------------------------------------------

    def dragEnterEvent(self, event):
        from ui.lab.drop.drop_context import DropContext
        pos = self.mapToScene(event.position().toPoint() if hasattr(event, "position") else event.pos())
        proj_loc = self.node_context.project_location if hasattr(self, "node_context") and self.node_context else None
        context = DropContext(event.mimeData(), pos, project_location=proj_loc)

        if self.drop_router.can_route(context):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        from ui.lab.drop.drop_context import DropContext
        pos = self.mapToScene(event.position().toPoint() if hasattr(event, "position") else event.pos())
        proj_loc = self.node_context.project_location if hasattr(self, "node_context") and self.node_context else None
        context = DropContext(event.mimeData(), pos, project_location=proj_loc)

        if self.drop_router.can_route(context):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        from ui.lab.drop.drop_context import DropContext
        pos = self.mapToScene(event.position().toPoint() if hasattr(event, "position") else event.pos())
        proj_loc = self.node_context.project_location if hasattr(self, "node_context") and self.node_context else None
        context = DropContext(event.mimeData(), pos, project_location=proj_loc)

        nodes_data = self.drop_router.route_drop(context)
        if nodes_data:
            self.clear_selection()
            created_nodes = []
            for node_data in nodes_data:
                node = self.add_node(node_data)
                if node:
                    node.setSelected(True)
                    created_nodes.append(node)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

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

    def focus_node(self, node, padding: float = 50.0):
        """Center and fit view on node bounding rect using fitInView."""
        if not node:
            return
        rect = node.sceneBoundingRect().adjusted(-padding, -padding, padding, padding)
        self.fitInView(rect, Qt.KeepAspectRatio)
        self._zoom_level = self.transform().m11()
        self.viewport().update()
        self._emit_camera_changed()

    center_on_node = focus_node
    zoom_to_rect = focus_node

    def fit_selection(self, padding: float = 50.0):
        """Fit viewport to combined bounding rect of currently selected spatial nodes."""
        selected = self.selected_nodes()
        if not selected:
            return

        if len(selected) == 1:
            self.focus_node(selected[0], padding=padding)
            return

        min_x = min(node.sceneBoundingRect().left() for node in selected)
        min_y = min(node.sceneBoundingRect().top() for node in selected)
        max_x = max(node.sceneBoundingRect().right() for node in selected)
        max_y = max(node.sceneBoundingRect().bottom() for node in selected)

        rect = QRectF(min_x, min_y, max_x - min_x, max_y - min_y).adjusted(-padding, -padding, padding, padding)
        self.fitInView(rect, Qt.KeepAspectRatio)
        self._zoom_level = self.transform().m11()
        self.viewport().update()
        self._emit_camera_changed()

    def fit_view(self, padding: float = 50.0):
        """Fit viewport to combined bounding rect of all spatial nodes on the canvas."""
        nodes = list(self._items_map.values())
        if not nodes:
            self.reset_camera()
            return

        min_x = min(node.sceneBoundingRect().left() for node in nodes)
        min_y = min(node.sceneBoundingRect().top() for node in nodes)
        max_x = max(node.sceneBoundingRect().right() for node in nodes)
        max_y = max(node.sceneBoundingRect().bottom() for node in nodes)

        rect = QRectF(min_x, min_y, max_x - min_x, max_y - min_y).adjusted(-padding, -padding, padding, padding)
        self.fitInView(rect, Qt.KeepAspectRatio)
        self._zoom_level = self.transform().m11()
        self.viewport().update()
        self._emit_camera_changed()

    fit_all = fit_view

    def reveal_parent_frame_if_needed(self, node):
        """If node is attached to a collapsed frame, expand the parent frame via FrameService."""
        if not node or not hasattr(node, "payload") or not isinstance(node.payload, dict):
            return
        parent_id = node.payload.get("parent_frame_id")
        if parent_id and parent_id in self._items_map:
            parent_frame = self._items_map[parent_id]
            if hasattr(parent_frame, "payload") and isinstance(parent_frame.payload, dict):
                if parent_frame.payload.get("collapsed", False):
                    from services.frame_service import FrameService
                    FrameService.set_collapsed(parent_frame, False, scene=self.scene())

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

        if event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            items_near = self.scene().items(QRectF(scene_pos.x() - 24, scene_pos.y() - 24, 48, 48))
            node = None
            for it in items_near:
                curr = it
                while curr:
                    if isinstance(curr, NodeItem):
                        node = curr
                        break
                    curr = curr.parentItem()
                if node:
                    break

            if node and hasattr(node, "get_closest_anchor"):
                anchor_id, anchor_pos = node.get_closest_anchor(scene_pos)
                if anchor_id and anchor_id != "center":
                    dx = scene_pos.x() - anchor_pos.x()
                    dy = scene_pos.y() - anchor_pos.y()
                    dist = math.hypot(dx, dy)
                    print(f"[TRACE] Stage 1 & 2: Anchor hit test dist={dist:.1f}px for anchor '{anchor_id}' on node {node.id}")
                    if dist <= 24.0:  # 24px hit radius for anchor ports
                        print(f"[TRACE] Stage 2: Begin connection drag from node {node.id} anchor '{anchor_id}'")
                        self.start_connection_drag(node, source_anchor=anchor_id, mouse_scene_pos=scene_pos)
                        event.accept()
                        return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        self.cursor_position_changed.emit(scene_pos.x(), scene_pos.y())

        if self._drag_connection_start_node:
            print(f"[TRACE] Stage 3: Mouse move preview update to scene pos ({scene_pos.x():.1f}, {scene_pos.y():.1f})")
            self.update_connection_drag(scene_pos)
            event.accept()
            return

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

        if self._drag_connection_start_node:
            scene_pos = self.mapToScene(event.pos())
            items_near = self.scene().items(QRectF(scene_pos.x() - 24, scene_pos.y() - 24, 48, 48))
            target_node = None
            for it in items_near:
                curr = it
                while curr:
                    if isinstance(curr, NodeItem):
                        target_node = curr
                        break
                    curr = curr.parentItem()
                if target_node and target_node != self._drag_connection_start_node:
                    break

            if target_node and target_node != self._drag_connection_start_node:
                tgt_anchor = "center"
                if hasattr(target_node, "get_closest_anchor"):
                    a_id, _ = target_node.get_closest_anchor(scene_pos)
                    if a_id:
                        tgt_anchor = a_id
                print(f"[TRACE] Stage 4: Mouse release target node detected: {target_node.id} anchor '{tgt_anchor}'")
                self.finish_connection_drag(target_node, target_anchor=tgt_anchor)
            else:
                print("[TRACE] Mouse release without valid target node -> cancelling drag")
                self.cancel_connection_drag()
            event.accept()
            return

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
        """Serialize currently selected nodes and connecting lines into CanvasClipboard."""
        selected = self.selected_nodes()
        if not selected:
            return
        from services.frame_service import FrameService
        prepared_nodes = FrameService.prepare_clipboard_nodes(selected)

        # Copy connectors where both source and target are selected
        selected_ids = {n.id if hasattr(n, "id") else str(n.get("id")) for n in prepared_nodes}
        prepared_connectors = []
        for conn in self._connector_map.values():
            if conn.source_id in selected_ids and conn.target_id in selected_ids:
                prepared_connectors.append(conn.to_dict())

        self.clipboard.copy(prepared_nodes, connectors=prepared_connectors)

    def paste(self, mouse_pos: QPointF = None) -> list:
        """Deserialize nodes and connectors from CanvasClipboard, assign fresh UUIDs, apply offset, and select pasted nodes."""
        if not self.clipboard.has_content():
            return []

        nodes_data = self.clipboard.get_nodes()
        connectors_data = self.clipboard.get_connectors()
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

        # Paste remapped connectors between pasted nodes
        for conn_data in connectors_data:
            old_src = conn_data.get("source_node_id") or conn_data.get("source_id")
            old_tgt = conn_data.get("target_node_id") or conn_data.get("target_id")
            if old_src in old_to_new_id_map and old_tgt in old_to_new_id_map:
                new_conn_data = dict(conn_data)
                new_conn_data["id"] = str(uuid.uuid4())
                new_conn_data["source_id"] = old_to_new_id_map[old_src]
                new_conn_data["target_id"] = old_to_new_id_map[old_tgt]
                new_conn_data["source_node_id"] = old_to_new_id_map[old_src]
                new_conn_data["target_node_id"] = old_to_new_id_map[old_tgt]
                self.add_connector(new_conn_data)

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
        """Single canonical deletion handler for selected canvas nodes and connectors."""
        from ui.lab.connectors.connector_item import ConnectorItem
        selected_items = list(self._scene.selectedItems())
        if not selected_items:
            return
        for item in selected_items:
            if isinstance(item, ConnectorItem):
                self.remove_connector(item.id)
            elif isinstance(item, NodeItem):
                if getattr(item, "is_locked", False):
                    continue
                if hasattr(item, "on_deleted"):
                    try:
                        item.on_deleted()
                    except Exception:
                        pass
                self.remove_node(item.id)
        self.clear_selection()

    delete_selected_nodes = delete_selection

    def is_editing_text(self) -> bool:
        """Query if any child QGraphicsItem or QWidget currently has text editing focus."""
        scene = self.scene()
        if scene:
            focus_item = scene.focusItem()
            if focus_item:
                if hasattr(focus_item, "widget") and callable(focus_item.widget):
                    w = focus_item.widget()
                    if hasattr(w, "isReadOnly") and not w.isReadOnly():
                        return True
                if hasattr(focus_item, "textInteractionFlags"):
                    flags = focus_item.textInteractionFlags()
                    if flags & (Qt.TextEditorInteraction | Qt.TextEditable):
                        return True

        from PySide6.QtWidgets import QApplication, QTextEdit
        focus_widget = QApplication.focusWidget()
        if focus_widget and focus_widget != self and focus_widget != self.viewport():
            if isinstance(focus_widget, QTextEdit) or (focus_widget.parent() and isinstance(focus_widget.parent(), QTextEdit)):
                p = focus_widget if isinstance(focus_widget, QTextEdit) else focus_widget.parent()
                if not p.isReadOnly():
                    return True

        return False

    def keyPressEvent(self, event):
        if self.is_editing_text():
            super().keyPressEvent(event)
            return

        mods = event.modifiers()
        key = event.key()

        if mods & Qt.AltModifier:
            if key == Qt.Key_Left:
                self.go_back_history()
                event.accept()
                return
            elif key == Qt.Key_Right:
                self.go_forward_history()
                event.accept()
                return

        # Home / Ctrl+0 -> Reset Camera
        if key == Qt.Key_Home or (mods & Qt.ControlModifier and key == Qt.Key_0):
            self.reset_camera()
            event.accept()
            return

        # Shift+F -> Fit View / Fit All
        if (mods & Qt.ShiftModifier) and key == Qt.Key_F:
            self.fit_view()
            event.accept()
            return
        elif key == Qt.Key_F and not mods:
            if self.selected_nodes():
                self.fit_selection()
            else:
                self.fit_view()
            event.accept()
            return

        # + / = -> Zoom In, - -> Zoom Out
        if key in (Qt.Key_Plus, Qt.Key_Equal) and not (mods & (Qt.ControlModifier | Qt.AltModifier)):
            self.zoom_in()
            event.accept()
            return
        elif key == Qt.Key_Minus and not (mods & (Qt.ControlModifier | Qt.AltModifier)):
            self.zoom_out()
            event.accept()
            return

        if key == Qt.Key_Escape:
            self.clear_neighbor_highlight()
            self.clear_selection()
            event.accept()
            return

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
            elif key == Qt.Key_K:
                self.open_node_search_dialog()
                event.accept()
                return

        if key == Qt.Key_Escape:
            if self._drag_connection_preview_item:
                self.cancel_connection_drag()
                event.accept()
                return
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

    def push_navigation_state(self, node_id: Optional[str] = None):
        """Record current spatial state into NavigationHistoryService stack."""
        from ui.lab.models.navigation_history import NavigationEvent
        center = self.mapToScene(self.viewport().rect().center())
        evt = NavigationEvent(
            board_id=getattr(self, "_board_id", "Main"),
            node_id=node_id,
            camera_x=center.x(),
            camera_y=center.y(),
            zoom=self._zoom_level
        )
        self.nav_history_service.push_event(evt)

    def go_back_history(self):
        """VS Code 'Go Back' navigation restoring previous board, node selection, and camera zoom/pan."""
        evt = self.nav_history_service.go_back()
        if evt:
            self._restore_navigation_event(evt)

    def go_forward_history(self):
        """VS Code 'Go Forward' navigation restoring forward board, node selection, and camera zoom/pan."""
        evt = self.nav_history_service.go_forward()
        if evt:
            self._restore_navigation_event(evt)

    def _restore_navigation_event(self, evt):
        if evt.node_id and evt.node_id in self._items_map:
            node = self._items_map[evt.node_id]
            self.set_selected_nodes([node])
            self.focus_node(node)
        else:
            self.centerOn(evt.camera_x, evt.camera_y)

    def highlight_neighborhood(self, node_id: str):
        """Set opacity=1.0 for connected neighborhood nodes/connectors and 0.2 for unrelated items."""
        if node_id not in self._items_map:
            return

        connected_rels = self.connection_manager.get_node_relationships(node_id)
        connected_node_ids = {node_id}
        connected_conn_ids = set()

        for r in connected_rels:
            connected_node_ids.add(r.source_node_id)
            connected_node_ids.add(r.target_node_id)
            connected_conn_ids.add(r.id)

        for nid, item in self._items_map.items():
            if nid in connected_node_ids:
                item.setOpacity(1.0)
            else:
                item.setOpacity(0.2)

        for conn in self.connectors():
            if conn.id in connected_conn_ids:
                conn.setOpacity(1.0)
            else:
                conn.setOpacity(0.2)

    def clear_neighbor_highlight(self):
        """Restore opacity=1.0 for all canvas items."""
        for item in self._items_map.values():
            item.setOpacity(1.0)
        for conn in self.connectors():
            conn.setOpacity(1.0)

    def save_camera_view(self, name: str):
        """Create and store a first-class project-level SavedView asset."""
        from ui.lab.models.saved_view import SavedView
        center = self.mapToScene(self.viewport().rect().center())
        sv = SavedView(
            name=name,
            board_id=getattr(self, "_board_id", "Main"),
            camera_x=center.x(),
            camera_y=center.y(),
            zoom=self._zoom_level
        )
        self._saved_views[sv.id] = sv
        return sv

    def restore_camera_view(self, view_id_or_model):
        """Restore camera view with smooth animated zoom/pan interpolation."""
        from ui.lab.models.saved_view import SavedView
        sv = view_id_or_model if isinstance(view_id_or_model, SavedView) else self._saved_views.get(view_id_or_model)
        if not sv:
            return

        self.push_navigation_state()
        start_center = self.mapToScene(self.viewport().rect().center())
        target_center = QPointF(sv.camera_x, sv.camera_y)
        start_zoom = self._zoom_level
        target_zoom = sv.zoom

        from PySide6.QtCore import QVariantAnimation, QEasingCurve
        anim = QVariantAnimation(self)
        anim.setDuration(350)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)

        def _step(progress):
            cx = start_center.x() + (target_center.x() - start_center.x()) * progress
            cy = start_center.y() + (target_center.y() - start_center.y()) * progress
            z = start_zoom + (target_zoom - start_zoom) * progress

            self.centerOn(cx, cy)
            scale_factor = z / self._zoom_level if self._zoom_level != 0 else 1.0
            self.scale(scale_factor, scale_factor)
            self._zoom_level = z

        anim.valueChanged.connect(_step)
        anim.start()

    def open_node_search_dialog(self):
        """Open the Ctrl+K Quick Search Palette for spatial canvas nodes."""
        from ui.dialogs.node_search_dialog import NodeSearchDialog
        nodes = list(self._items_map.values())
        dlg = NodeSearchDialog(nodes, parent=self)
        dlg.node_selected.connect(self._on_search_node_selected)
        dlg.exec_()

    def _on_shortcut_go_back(self):
        if not self.is_editing_text():
            self.go_back_history()

    def _on_shortcut_go_forward(self):
        if not self.is_editing_text():
            self.go_forward_history()

    def _on_search_node_selected(self, node_id: str):
        node = self.node(node_id)
        if node:
            # Capture current starting location if back stack is empty
            if not self.nav_history_service._back_stack:
                self.push_navigation_state()

            self.reveal_parent_frame_if_needed(node)
            self.set_selected_nodes([node])
            self.focus_node(node)
            self.push_navigation_state(node_id)

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
        node = NodeRegistry.create_node(node_type, data=node_data, node_context=self.node_context)
        if not node:
            return None

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

            # Cleanup all attached connectors (no orphan connectors)
            attached_conns = [cid for cid, conn in self._connector_map.items() if conn.source_id == node_id or conn.target_id == node_id]
            for cid in attached_conns:
                self.remove_connector(cid)

            self._scene.removeItem(node)
            try:
                self.node_removed.emit(node_id)
            except Exception:
                pass

    remove_item = remove_node

    def node(self, node_id: str) -> NodeItem:
        """UUID-based lookup returning live NodeItem instance."""
        return self._items_map.get(str(node_id))

    find_node = node
    find_item = node

    # -------------------------------------------------------------------------
    # Connector API (Delegated to ConnectionManager) & Drag Preview
    # -------------------------------------------------------------------------

    def connector(self, connector_id: str):
        """UUID-based lookup returning live ConnectorItem instance."""
        return self.connection_manager.connector(connector_id)

    def connectors(self) -> list:
        """Return list of all live ConnectorItem instances on the canvas."""
        return self.connection_manager.connectors()

    def add_connector(self, connector_data: dict):
        """Instantiate and register a first-class ConnectorItem via ConnectionManager."""
        conn = self.connection_manager.add_connector(connector_data)
        if conn and not self._is_loading:
            try:
                self.node_added.emit(conn.to_dict())
            except Exception:
                pass
        return conn

    def remove_connector(self, connector_id: str) -> bool:
        """Remove a ConnectorItem via ConnectionManager."""
        res = self.connection_manager.remove_connector(connector_id)
        if res and not self._is_loading:
            try:
                self.node_removed.emit(connector_id)
            except Exception:
                pass
        return res

    def connect_nodes(self, source_id: str, target_id: str, **kwargs):
        """Convenience API to create a new ConnectorItem between source and target nodes."""
        conn = self.connection_manager.connect_nodes(source_id, target_id, **kwargs)
        if conn and not self._is_loading:
            try:
                self.node_added.emit(conn.to_dict())
            except Exception:
                pass
        return conn

    def selected_connectors(self) -> list:
        """Return list of currently selected ConnectorItem instances."""
        from ui.lab.connectors.connector_item import ConnectorItem
        return [it for it in self._scene.selectedItems() if isinstance(it, ConnectorItem)]

    def clear_connectors(self):
        """Clear all connectors from scene and internal connector map."""
        self.connection_manager.clear()

    # -------------------------------------------------------------------------
    # Interactive Connection Creation Drag Preview
    # -------------------------------------------------------------------------

    def start_connection_drag(self, source_node: NodeItem, source_anchor: str = "center", mouse_scene_pos: QPointF = None):
        """Begin interactive connection preview from a source node anchor port."""
        if not source_node:
            return
        self._drag_connection_start_node = source_node
        self._drag_connection_start_anchor = source_anchor

        if not self._drag_connection_preview_item:
            self._drag_connection_preview_item = QGraphicsPathItem()
            pen = QPen(QColor("#6366F1"), 2, Qt.DashLine)
            pen.setCapStyle(Qt.RoundCap)
            self._drag_connection_preview_item.setPen(pen)
            self._drag_connection_preview_item.setZValue(-4)
            self._scene.addItem(self._drag_connection_preview_item)

        if mouse_scene_pos:
            self.update_connection_drag(mouse_scene_pos)

    def update_connection_drag(self, mouse_scene_pos: QPointF):
        """Update live preview Bezier curve geometry following current mouse cursor position."""
        if not self._drag_connection_start_node or not self._drag_connection_preview_item:
            return

        if hasattr(self._drag_connection_start_node, "get_anchor_scene_pos"):
            src_pt = self._drag_connection_start_node.get_anchor_scene_pos(self._drag_connection_start_anchor)
        else:
            src_pt = self._drag_connection_start_node.sceneBoundingRect().center()

        dx = mouse_scene_pos.x() - src_pt.x()
        dy = mouse_scene_pos.y() - src_pt.y()
        ctrl1 = QPointF(src_pt.x() + dx * 0.5, src_pt.y())
        ctrl2 = QPointF(mouse_scene_pos.x() - dx * 0.5, mouse_scene_pos.y())

        path = QPainterPath()
        path.moveTo(src_pt)
        path.cubicTo(ctrl1, ctrl2, mouse_scene_pos)
        self._drag_connection_preview_item.setPath(path)

    def finish_connection_drag(self, target_node: NodeItem, target_anchor: str = "center") -> bool:
        """Complete connection drag by creating a permanent ConnectorItem and prompting for relationship type."""
        src_node = self._drag_connection_start_node
        src_anchor = self._drag_connection_start_anchor
        self.cancel_connection_drag()

        if src_node and target_node and src_node.id != target_node.id:
            conn = self.connect_nodes(
                src_node.id,
                target_node.id,
                source_anchor=src_anchor,
                target_anchor=target_anchor
            )
            if conn:
                self.prompt_connector_relationship_type(conn)
            return conn is not None
        return False

    def prompt_connector_relationship_type(self, conn):
        """Prompt user for relationship type immediately after creating connector using RelationshipPickerDialog."""
        from ui.dialogs.relationship_picker_dialog import RelationshipPickerDialog
        curr_type = getattr(conn, "relationship_type", "related_to") or "related_to"
        dlg = RelationshipPickerDialog(parent=self, current_type_id=curr_type)
        if dlg.exec_() == RelationshipPickerDialog.Accepted:
            defn = dlg.selected_definition()
            if defn:
                self.connection_manager.change_type(conn.id, defn.id)

    def prompt_relationship_type_change(self, conn):
        """Prompt user to change relationship type via RelationshipPickerDialog palette."""
        self.prompt_connector_relationship_type(conn)

    def set_selected_connectors(self, connectors: list):
        """Set active canvas selection to target list of connectors."""
        self._scene.clearSelection()
        for c in connectors:
            c.setSelected(True)

    def cancel_connection_drag(self):
        """Cancel drag preview and remove temporary preview item from scene."""
        if self._drag_connection_preview_item:
            if self._drag_connection_preview_item in self._scene.items():
                self._scene.removeItem(self._drag_connection_preview_item)
            self._drag_connection_preview_item = None
        self._drag_connection_start_node = None
        self._drag_connection_start_anchor = "center"

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
        self.clear_connectors()
        for node_id, node in list(self._items_map.items()):
            self._scene.removeItem(node)
        self._items_map.clear()

    clear_items = clear_nodes

    def _on_node_item_modified(self, node_dict: dict):
        # Update path geometry of connected ConnectorItem instances
        node_id = node_dict.get("id") if isinstance(node_dict, dict) else None
        if node_id:
            for conn in self._connector_map.values():
                if conn.source_id == node_id or conn.target_id == node_id:
                    conn.update_path()

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

        from ui.lab.connectors.connector_item import ConnectorItem
        if isinstance(item, ConnectorItem):
            if not item.isSelected():
                self._scene.clearSelection()
                item.setSelected(True)

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

            def prompt_edit_label():
                lbl, ok = QInputDialog.getText(self, "Edit Connector Label", "Label text:", text=item.label)
                if ok:
                    item.label = lbl.strip()
                    item._emit_modified()

            edit_lbl_act = QAction("✏️  Edit Label...", self)
            edit_lbl_act.triggered.connect(prompt_edit_label)
            menu.addAction(edit_lbl_act)

            del_conn_act = QAction("🗑  Delete Connector", self)
            del_conn_act.triggered.connect(lambda: self.remove_connector(item.id))
            menu.addAction(del_conn_act)

            menu.exec_(event.globalPos())
            return

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

            # Connection context actions
            selected_nodes = self.selected_nodes()
            other_selected = [n for n in selected_nodes if n.id != item.id]
            if len(other_selected) == 1:
                source_node = other_selected[0]
                src_title = str(source_node.payload.get("title", "Node")) if hasattr(source_node, "payload") else "Node"
                connect_act = QAction(f"🔗  Connect From Selected Node ('{src_title}')", self)
                connect_act.triggered.connect(lambda checked=False, s=source_node, t=item: self.connect_nodes(s.id, t.id))
                menu.addAction(connect_act)

            attached_conns = [c for c in self._connector_map.values() if c.source_id == item.id or c.target_id == item.id]
            if attached_conns:
                disc_act = QAction("✂️  Disconnect Node", self)
                def disconnect_target():
                    for c in list(attached_conns):
                        self.remove_connector(c.id)
                disc_act.triggered.connect(disconnect_target)
                menu.addAction(disc_act)
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

            # Multi-Selection Actions (Create Frame from Selection, Batch Pin/Unpin, Batch Tagging, Fit Selection)
            selected_nodes = self.selected_nodes()

            if len(selected_nodes) > 1:
                menu.addSeparator()

                # Navigation: Fit Selection
                fit_sel_act = QAction("🔍  Fit Selection", self)
                fit_sel_act.triggered.connect(lambda: self.fit_selection())
                menu.addAction(fit_sel_act)

                # 1. Create Frame from Selection
                create_frame_act = QAction("🖼️  Create Frame from Selection", self)
                create_frame_act.triggered.connect(lambda: FrameService.create_frame_from_selection(selected_nodes, self))
                menu.addAction(create_frame_act)

                # 2. Batch Pin / Unpin
                has_unpinned = any(not getattr(n, "is_pinned", False) for n in selected_nodes)
                has_pinned = any(bool(getattr(n, "is_pinned", False)) for n in selected_nodes)

                if has_unpinned:
                    pin_batch_act = QAction("📌  Pin Selected Nodes", self)
                    def _pin_all():
                        for n in selected_nodes:
                            if hasattr(n, "set_pinned"):
                                n.set_pinned(True)
                    pin_batch_act.triggered.connect(_pin_all)
                    menu.addAction(pin_batch_act)

                if has_pinned:
                    unpin_batch_act = QAction("📍  Unpin Selected Nodes", self)
                    def _unpin_all():
                        for n in selected_nodes:
                            if hasattr(n, "set_pinned"):
                                n.set_pinned(False)
                    unpin_batch_act.triggered.connect(_unpin_all)
                    menu.addAction(unpin_batch_act)

                # 3. Batch Tagging
                from PySide6.QtWidgets import QInputDialog
                tag_batch_act = QAction("🏷️  Add Tags to Selected Nodes...", self)
                def _prompt_batch_tags():
                    from core.inspectable_adapters import MultiNodeInspectable
                    text, ok = QInputDialog.getText(self, "Add Tags to Selection", "Enter tags (comma-separated):")
                    if ok and text.strip():
                        MultiNodeInspectable(selected_nodes).set_inspectable_property("tags", text.strip())
                tag_batch_act.triggered.connect(_prompt_batch_tags)
                menu.addAction(tag_batch_act)

                menu.addSeparator()
            elif len(selected_nodes) == 1:
                menu.addSeparator()

                if isinstance(item, FrameNodeItem):
                    focus_frame_act = QAction("🔍  Focus Frame", self)
                    focus_frame_act.triggered.connect(lambda checked=False, f=item: self.focus_node(f))
                    menu.addAction(focus_frame_act)

                    fit_contents_act = QAction("↔️  Fit Frame Contents", self)
                    fit_contents_act.triggered.connect(lambda checked=False, f=item: FrameService.fit_to_contents(f, scene=self.scene()))
                    menu.addAction(fit_contents_act)
                else:
                    focus_node_act = QAction("🔍  Focus Node", self)
                    focus_node_act.triggered.connect(lambda checked=False, n=item: self.focus_node(n))
                    menu.addAction(focus_node_act)

                create_frame_act = QAction("🖼️  Create Frame from Selection", self)
                create_frame_act.triggered.connect(lambda: FrameService.create_frame_from_selection(selected_nodes, self))
                menu.addAction(create_frame_act)
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

        # Canvas Edit Actions (Paste, Select All, Clear Selection)
        paste_act = QAction("📋  Paste", self)
        paste_act.setEnabled(self.clipboard.has_content())
        paste_act.triggered.connect(lambda: self.execute_command(CanvasCommand.PASTE, mouse_pos=scene_pos))

        select_all_act = QAction("🔲  Select All", self)
        select_all_act.triggered.connect(lambda: self.execute_command(CanvasCommand.SELECT_ALL))

        clear_sel_act = QAction("🚫  Clear Selection", self)
        clear_sel_act.triggered.connect(lambda: self.execute_command(CanvasCommand.CLEAR_SELECTION))

        # Background Navigation Actions
        home_act = QAction("🏠  Home View", self)
        home_act.triggered.connect(self.reset_camera)

        fit_all_act = QAction("🔍  Fit All Nodes", self)
        fit_all_act.triggered.connect(self.fit_view)

        actions = menu.actions()
        if actions:
            first_act = actions[0]
            menu.insertAction(first_act, home_act)
            menu.insertAction(first_act, fit_all_act)
            menu.insertSeparator(first_act)
            menu.insertAction(first_act, paste_act)
            menu.insertAction(first_act, select_all_act)
            menu.insertAction(first_act, clear_sel_act)
            menu.insertSeparator(first_act)
        else:
            menu.addAction(home_act)
            menu.addAction(fit_all_act)
            menu.addSeparator()
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
