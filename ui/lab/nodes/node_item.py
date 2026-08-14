import copy
import uuid
from datetime import datetime
from PySide6.QtWidgets import QGraphicsObject, QGraphicsItem
from PySide6.QtCore import Signal, QRectF, Qt, QPointF
from PySide6.QtGui import QPen, QColor, QFont, QBrush, QPainter, QPainterPath

from ui.lab.nodes.node_definition import NodeDefinition
from ui.lab.nodes.node_capability import NodeCapability
from ui.lab.nodes.node_context import NodeContext


class NodeItem(QGraphicsObject):
    """Abstract spatial base class for all Lab canvas node items.

    Encapsulates positioning, selection, z-ordering, capability querying,
    engine-level metadata, and standardized serialization.
    """

    node_modified = Signal(object)

    @property
    def project(self):
        if hasattr(self, "_project_val") and self._project_val is not None:
            return self._project_val
        return self.node_context.project if hasattr(self, "node_context") and self.node_context else None

    @project.setter
    def project(self, val):
        self._project_val = val
        if hasattr(self, "node_context") and self.node_context:
            self.node_context.project = val

    @property
    def _board_id(self):
        if hasattr(self, "_board_id_val") and self._board_id_val is not None:
            return self._board_id_val
        return self.node_context.board_id if hasattr(self, "node_context") and self.node_context else None

    @_board_id.setter
    def _board_id(self, val):
        self._board_id_val = val
        if hasattr(self, "node_context") and self.node_context:
            self.node_context.board_id = val

    def __init__(self, definition: NodeDefinition, parent=None, node_context: NodeContext = None):
        super().__init__(parent)
        self.definition = definition
        self.node_context = node_context or NodeContext()
        self.id = str(uuid.uuid4())
        self.z_order = 1
        self._project_val = None
        self._board_id_val = None

        # Surface & Bounds
        self.width = definition.default_size[0] if definition else 260.0
        self.height = definition.default_size[1] if definition else 180.0
        self.background_color = definition.background_color if definition else "#1E2029"

        # Engine-level Metadata
        now = datetime.now().isoformat()
        self.created_at = now
        self.updated_at = now
        self.is_locked = False
        self.is_hidden = False
        self.is_collapsed = False
        self.is_favorite = False
        self.is_pinned = False
        self.tags = []
        self.version = 1

        self.metadata = {
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "locked": self.is_locked,
            "hidden": self.is_hidden,
            "collapsed": self.is_collapsed,
            "favorite": self.is_favorite,
            "pinned": self.is_pinned,
            "tags": list(self.tags),
        }

        # Domain Payload Dictionary (Deep Copy to isolate nested schemas)
        self.payload = {}
        if definition and definition.payload_schema:
            self.payload = copy.deepcopy(definition.payload_schema)

        # Qt Interaction Flags
        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

    def set_node_context(self, context: NodeContext):
        """Update standard shared context (ThumbnailService, project location, etc.)."""
        self.node_context = context or NodeContext()

    def set_pinned(self, pinned: bool):
        self.is_pinned = bool(pinned)
        if isinstance(getattr(self, "metadata", None), dict):
            self.metadata["pinned"] = self.is_pinned
        self._emit_modified()
        self.update()

    def toggle_pinned(self):
        self.set_pinned(not getattr(self, "is_pinned", False))

    # -------------------------------------------------------------------------
    # Node Lifecycle Hooks (Predictable Extensibility Interface)
    # -------------------------------------------------------------------------

    def on_created(self):
        """Hook invoked when node is newly created on the canvas."""
        pass

    def on_loaded(self):
        """Hook invoked after node state is fully loaded from JSON data."""
        pass

    def on_selected(self):
        """Hook invoked when node receives selection."""
        pass

    def on_deselected(self):
        """Hook invoked when node loses selection."""
        pass

    def on_double_clicked(self, event):
        """Hook invoked when node receives double click."""
        pass

    def on_deleted(self):
        """Hook invoked before node is removed from canvas scene."""
        pass

    def on_saved(self):
        """Hook invoked after node state is serialized and saved to disk."""
        pass

    def on_context_menu(self, menu):
        """Hook invoked when context menu is building for this spatial node."""
        from PySide6.QtGui import QAction
        is_pinned = getattr(self, "is_pinned", False)
        pin_lbl = "📍 Unpin Node" if is_pinned else "📌 Pin Node"

        pin_act = QAction(pin_lbl, menu)
        conn_act = QAction("🔗 Select Connected Nodes", menu)
        hl_act = QAction("✨ Highlight Neighborhood", menu)
        focus_act = QAction("🎯 Focus Neighborhood", menu)

        menu.addSeparator()
        menu.addAction(pin_act)
        menu.addAction(conn_act)
        menu.addAction(hl_act)
        menu.addAction(focus_act)

        def _handle(action):
            if action == pin_act:
                self.toggle_pinned()
            elif action in (conn_act, hl_act, focus_act):
                if hasattr(self.scene(), "views") and self.scene().views():
                    canvas = self.scene().views()[0]
                    if action == conn_act:
                        if hasattr(canvas, "connection_manager"):
                            rels = canvas.connection_manager.get_node_relationships(self.id)
                            nids = set()
                            for r in rels:
                                nids.add(r.source_node_id)
                                nids.add(r.target_node_id)
                            target_nodes = [canvas.node(nid) for nid in nids if canvas.node(nid)]
                            canvas.set_selected_nodes(target_nodes)
                    elif action == hl_act:
                        canvas.highlight_neighborhood(self.id)
                    elif action == focus_act:
                        canvas.focus_node(self)
                        canvas.highlight_neighborhood(self.id)

        menu.triggered.connect(_handle)

    def _log_state(self, stage: str):
        pass

    def on_property_changed(self, key: str, value):
        """Hook invoked when a payload or metadata property is mutated."""
        self._log_state(f"BEFORE on_property_changed({key})")
        self.payload[key] = value
        self.updated_at = datetime.now().isoformat()
        self._emit_modified()
        self._log_state(f"AFTER on_property_changed({key})")

    # -------------------------------------------------------------------------
    # Tags & Searchable Knowledge Metadata API
    # -------------------------------------------------------------------------

    def add_tag(self, tag: str) -> bool:
        """Add a tag to the node, ensuring deduplication."""
        t = str(tag or "").strip().lower()
        if t and t not in self.tags:
            self.tags.append(t)
            self.updated_at = datetime.now().isoformat()
            self._emit_modified()
            return True
        return False

    def remove_tag(self, tag: str) -> bool:
        """Remove a tag from the node."""
        t = str(tag or "").strip().lower()
        if t in self.tags:
            self.tags.remove(t)
            self.updated_at = datetime.now().isoformat()
            self._emit_modified()
            return True
        return False

    def set_tags(self, tags: list):
        """Set tag list."""
        self.tags = [str(t).strip().lower() for t in (tags or []) if str(t).strip()]
        self.updated_at = datetime.now().isoformat()
        self._emit_modified()

    def get_searchable_text(self) -> str:
        """Extract all searchable text content (title, payload, tags, type)."""
        title = self.definition.title if self.definition else ""
        type_id = self.definition.type_id if self.definition else ""
        payload_str = " ".join(str(v) for v in self.payload.values() if isinstance(v, (str, int, float)))
        tags_str = " ".join(self.tags)
        return f"{title} {type_id} {payload_str} {tags_str}".lower()

    def get_knowledge_metadata(self) -> dict:
        """Return rich standardized knowledge metadata schema for AI retrieval."""
        pos = self.pos()
        title = self.definition.title if self.definition else "Node"
        content = ""
        if isinstance(self.payload, dict):
            content = str(self.payload.get("content") or self.payload.get("title") or "")

        parent_frame = self.payload.get("parent_frame_id") if isinstance(self.payload, dict) else None

        return {
            "id": self.id,
            "type": self.definition.type_id if self.definition else "node.unknown",
            "title": title,
            "content": content,
            "tags": list(self.tags),
            "relationships": [],
            "created": self.created_at,
            "modified": self.updated_at,
            "board": None,
            "frame": parent_frame,
            "position": [round(pos.x(), 2), round(pos.y(), 2)],
        }

    # -------------------------------------------------------------------------
    # Connection Anchor / Port API (Extensible Endpoint Architecture)
    # -------------------------------------------------------------------------

    def get_connection_anchors(self) -> dict:
        """Return dict of anchor identifier -> local QPointF coordinates."""
        w = float(self.width)
        h = float(self.height)
        return {
            "center": QPointF(w / 2.0, h / 2.0),
            "top": QPointF(w / 2.0, 0.0),
            "bottom": QPointF(w / 2.0, h),
            "left": QPointF(0.0, h / 2.0),
            "right": QPointF(w, h / 2.0),
        }

    def get_anchor_scene_pos(self, anchor_id: str = "center") -> QPointF:
        """Return scene coordinates for a specific anchor port."""
        anchors = self.get_connection_anchors()
        local_pos = anchors.get(anchor_id) or anchors.get("center") or QPointF(self.width / 2.0, self.height / 2.0)
        return self.mapToScene(local_pos)

    def get_closest_anchor(self, scene_point: QPointF) -> tuple:
        """Return tuple of (anchor_id, anchor_scene_pos) closest to scene_point."""
        anchors = self.get_connection_anchors()
        best_id = "center"
        best_pos = self.get_anchor_scene_pos("center")
        best_dist = float("inf")

        for aid in anchors.keys():
            sp = self.get_anchor_scene_pos(aid)
            dx = scene_point.x() - sp.x()
            dy = scene_point.y() - sp.y()
            dist_sq = dx * dx + dy * dy
            if dist_sq < best_dist:
                best_dist = dist_sq
                best_id = aid
                best_pos = sp

        return best_id, best_pos

    # -------------------------------------------------------------------------
    # Capability Query Helper
    # -------------------------------------------------------------------------

    def has_capability(self, capability: NodeCapability) -> bool:
        """Query if this node possesses a specific capability flag."""
        if not self.definition:
            return False
        return capability in self.definition.capabilities

    # -------------------------------------------------------------------------
    # Qt Event Handlers
    # -------------------------------------------------------------------------

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.updated_at = datetime.now().isoformat()
            self._emit_modified()
        elif change == QGraphicsItem.ItemSelectedHasChanged:
            if value:
                self.on_selected()
            else:
                self.on_deselected()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event):
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.update()
        super().hoverLeaveEvent(event)

    def _emit_modified(self):
        try:
            self.node_modified.emit(self.to_dict())
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Standardized Serialization (.lab.json)
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict:
        self._log_state("BEFORE to_dict()")
        pos = self.pos()
        if not isinstance(getattr(self, "metadata", None), dict):
            self.metadata = {}
        self.metadata.update({
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "locked": self.is_locked,
            "hidden": self.is_hidden,
            "collapsed": self.is_collapsed,
            "favorite": self.is_favorite,
            "pinned": self.is_pinned,
            "tags": list(self.tags),
        })
        res = {
            "id": self.id,
            "type": self.definition.type_id if self.definition else "node.unknown",
            "transform": {
                "x": round(pos.x(), 2),
                "y": round(pos.y(), 2),
                "z": int(self.zValue()),
                "width": round(self.width, 2),
                "height": round(self.height, 2),
                "rotation": round(self.rotation(), 2),
            },
            "style": {
                "background": self.background_color,
                "accent": self.definition.accent_color if self.definition else "#6366F1",
            },
            "metadata": dict(self.metadata),
            "payload": copy.deepcopy(self.payload),
        }
        self._log_state("AFTER to_dict()")
        return res

    def from_dict(self, data: dict):
        if not data or not isinstance(data, dict):
            return

        self._log_state("BEFORE from_dict()")
        if data.get("id"):
            self.id = str(data["id"])

        # Restore Transform
        transform = data.get("transform", {})
        if isinstance(transform, dict):
            x = float(transform.get("x", 0.0))
            y = float(transform.get("y", 0.0))
            default_z = getattr(self, "z_order", 1)
            z = int(transform.get("z", default_z))
            self.width = float(transform.get("width", self.width))
            self.height = float(transform.get("height", self.height))
            rot = float(transform.get("rotation", 0.0))

            self.setPos(x, y)
            self.setZValue(z)
            self.setRotation(rot)
            self.z_order = z

        # Restore Style
        style = data.get("style", {})
        if isinstance(style, dict):
            self.background_color = str(style.get("background", self.background_color))

        # Restore Engine Metadata
        metadata = data.get("metadata", {})
        if isinstance(metadata, dict):
            if "pinned" not in metadata:
                metadata["pinned"] = False
            self.created_at = str(metadata.get("created_at", self.created_at))
            self.updated_at = str(metadata.get("updated_at", self.updated_at))
            self.version = int(metadata.get("version", self.version))
            self.is_locked = bool(metadata.get("locked", self.is_locked))
            self.is_hidden = bool(metadata.get("hidden", self.is_hidden))
            self.is_collapsed = bool(metadata.get("collapsed", self.is_collapsed))
            self.is_favorite = bool(metadata.get("favorite", self.is_favorite))
            self.is_pinned = bool(metadata.get("pinned", self.is_pinned))
            self.tags = list(metadata.get("tags", self.tags))
            if not isinstance(getattr(self, "metadata", None), dict):
                self.metadata = {}
            self.metadata.update(metadata)

        # Restore Domain Payload
        payload = data.get("payload", {})
        if isinstance(payload, dict):
            self.payload = copy.deepcopy(payload)
        self._log_state("AFTER from_dict()")

    # -------------------------------------------------------------------------
    # Visual Helpers (Tag Chips, Pinned Vector Badge & Clean Anchor Ports)
    # -------------------------------------------------------------------------

    def draw_tag_badges(self, painter, rect: QRectF):
        """Paint visual colored tag chip badges at the bottom edge of node cards."""
        if not self.tags:
            return

        painter.save()
        font = QFont("Segoe UI", 8, QFont.Bold)
        painter.setFont(font)
        fm = painter.fontMetrics()

        x_offset = 12.0
        y_pos = rect.height() - 22.0

        tag_colors = ["#312E81", "#1E3A8A", "#14532D", "#701A75", "#831843", "#7C2D12"]
        text_colors = ["#A5B4FC", "#93C5FD", "#86EFAC", "#F0ABFC", "#F472B6", "#FDBA74"]

        for i, tag in enumerate(self.tags[:4]):
            txt = f"🏷️ {tag}"
            txt_w = fm.horizontalAdvance(txt) + 10
            txt_h = 16.0

            if x_offset + txt_w > rect.width() - 10:
                break

            badge_rect = QRectF(x_offset, y_pos, txt_w, txt_h)
            c_idx = i % len(tag_colors)

            painter.setBrush(QBrush(QColor(tag_colors[c_idx])))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(badge_rect, 4.0, 4.0)

            painter.setPen(QPen(QColor(text_colors[c_idx])))
            painter.drawText(badge_rect, Qt.AlignCenter, txt)

            x_offset += txt_w + 6.0

        painter.restore()

    def draw_pinned_badge(self, painter, rect: QRectF):
        """Render crisp QPainter vector pin badge at top-right corner of node header."""
        if getattr(self, "is_pinned", False):
            badge_size = 14.0
            bx = rect.right() - badge_size - 8.0
            by = rect.top() + 7.0
            badge_rect = QRectF(bx, by, badge_size, badge_size)

            painter.save()
            painter.setRenderHint(painter.RenderHint.Antialiasing if hasattr(painter, "RenderHint") else QPainter.Antialiasing)
            bg_color = QColor("#F59E0B")
            bg_color.setAlpha(45)
            painter.setBrush(QBrush(bg_color))
            painter.setPen(QPen(QColor("#F59E0B"), 1.2))
            painter.drawEllipse(badge_rect)

            dot_rect = QRectF(bx + 4.0, by + 4.0, 6.0, 6.0)
            painter.setBrush(QBrush(QColor("#FBBF24")))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(dot_rect)
            painter.restore()

    def draw_anchor_ports(self, painter, rect: QRectF):
        """Paint small anchor handle ports ONLY when node is selected or hovered to keep canvas clean."""
        if not (self.isSelected() or self.isUnderMouse()):
            return

        painter.save()
        anchors = self.get_connection_anchors()

        painter.setBrush(QBrush(QColor("#6366F1")))
        painter.setPen(QPen(QColor("#FFFFFF"), 1.5))

        for aid, local_pos in anchors.items():
            if aid == "center":
                continue
            painter.drawEllipse(local_pos, 4.0, 4.0)

        painter.restore()

    def draw_selection_outline(self, painter, rect: QRectF, radius: float = 8.0):
        self.draw_pinned_badge(painter, rect)
        if self.isSelected():
            pen = QPen(QColor("#6366F1"))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)

        # Draw clean anchor ports on hover / selection
        self.draw_anchor_ports(painter, rect)
