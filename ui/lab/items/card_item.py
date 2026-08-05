import uuid
from PySide6.QtWidgets import QGraphicsObject, QGraphicsItem, QStyle
from PySide6.QtCore import Signal, QRectF, QPointF
from PySide6.QtGui import QPen, QColor

from ui.lab.items.card_types import CardType


class CardItem(QGraphicsObject):
    """Abstract spatial base class for all spatial Lab canvas cards.

    Encapsulates positioning, selection, z-ordering, and serialization interface.
    Decoupled from note semantics so future card subclasses (AssetCardItem, ImageCardItem, AICardItem)
    can inherit cleanly.
    """

    card_modified = Signal(object)

    def __init__(self, card_type: CardType = CardType.NOTE, parent=None):
        super().__init__(parent)
        self.id = str(uuid.uuid4())
        self.card_type = card_type
        self.z_order = 1
        self.is_locked = False
        self.background_color = "#1E2029"

        # Item interaction flags
        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

    # -------------------------------------------------------------------------
    # Geometry Change & Signals
    # -------------------------------------------------------------------------

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self._emit_modified()
        return super().itemChange(change, value)

    def _emit_modified(self):
        try:
            self.card_modified.emit(self.to_dict())
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Serialization Interface
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict:
        pos = self.pos()
        return {
            "id": self.id,
            "type": self.card_type.value if isinstance(self.card_type, CardType) else str(self.card_type),
            "transform": {
                "x": round(pos.x(), 2),
                "y": round(pos.y(), 2),
                "z": int(self.zValue()),
            },
            "style": {
                "background": self.background_color,
            },
            "payload": {},
        }

    def from_dict(self, data: dict):
        if not data or not isinstance(data, dict):
            return

        self.id = str(data.get("id", self.id))

        transform = data.get("transform", {})
        if isinstance(transform, dict):
            x = float(transform.get("x", 0.0))
            y = float(transform.get("y", 0.0))
            z = int(transform.get("z", 1))
            self.setPos(x, y)
            self.setZValue(z)
            self.z_order = z

        style = data.get("style", {})
        if isinstance(style, dict):
            self.background_color = str(style.get("background", "#1E2029"))

    # -------------------------------------------------------------------------
    # Selection Rendering Helper
    # -------------------------------------------------------------------------

    def draw_selection_outline(self, painter, rect: QRectF, radius: float = 8.0):
        if self.isSelected():
            pen = QPen(QColor("#6366F1"))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)
