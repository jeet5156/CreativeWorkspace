import copy
import uuid
from datetime import datetime
from PySide6.QtWidgets import QGraphicsObject, QGraphicsItem
from PySide6.QtCore import Signal, QRectF, Qt
from PySide6.QtGui import QPen, QColor

from ui.lab.nodes.node_definition import NodeDefinition
from ui.lab.nodes.node_capability import NodeCapability
from ui.lab.nodes.node_context import NodeContext


class NodeItem(QGraphicsObject):
    """Abstract spatial base class for all Lab canvas node items.

    Encapsulates positioning, selection, z-ordering, capability querying,
    engine-level metadata, and standardized serialization.
    """

    node_modified = Signal(object)

    def __init__(self, definition: NodeDefinition, parent=None, node_context: NodeContext = None):
        super().__init__(parent)
        self.definition = definition
        self.node_context = node_context or NodeContext()
        self.id = str(uuid.uuid4())
        self.z_order = 1

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
        self.tags = []
        self.version = 1

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
        """Hook invoked when context menu is building for this node."""
        pass

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
            "metadata": {
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "version": self.version,
                "locked": self.is_locked,
                "hidden": self.is_hidden,
                "collapsed": self.is_collapsed,
                "favorite": self.is_favorite,
                "tags": list(self.tags),
            },
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
            self.created_at = str(metadata.get("created_at", self.created_at))
            self.updated_at = str(metadata.get("updated_at", self.updated_at))
            self.version = int(metadata.get("version", self.version))
            self.is_locked = bool(metadata.get("locked", self.is_locked))
            self.is_hidden = bool(metadata.get("hidden", self.is_hidden))
            self.is_collapsed = bool(metadata.get("collapsed", self.is_collapsed))
            self.is_favorite = bool(metadata.get("favorite", self.is_favorite))
            self.tags = list(metadata.get("tags", self.tags))

        # Restore Domain Payload
        payload = data.get("payload", {})
        if isinstance(payload, dict):
            self.payload = copy.deepcopy(payload)
        self._log_state("AFTER from_dict()")

    # -------------------------------------------------------------------------
    # Visual Helper
    # -------------------------------------------------------------------------

    def draw_selection_outline(self, painter, rect: QRectF, radius: float = 8.0):
        if self.isSelected():
            pen = QPen(QColor("#6366F1"))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)
