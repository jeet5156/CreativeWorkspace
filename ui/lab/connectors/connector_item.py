import math
from typing import Optional, Dict, Any
from PySide6.QtWidgets import QGraphicsObject, QStyleOptionGraphicsItem, QWidget, QMenu
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QPainterPath, QPainterPathStroker, QPolygonF, QAction

from ui.lab.models.relationship import Relationship
from ui.lab.models.relationship_registry import RelationshipRegistry


class ConnectorItem(QGraphicsObject):
    """QGraphicsObject presentation View item rendering a domain Relationship.

    Follows clean architectural ownership:
    - Pure presentation View layer wrapping a Relationship domain object.
    - ConnectorItem MUST NEVER mutate Relationship directly. All edits route via ConnectionManager.
    - Renders dynamic Bezier tangent curves (Blender/Blueprint style) based on anchor orientation.
    - Renders arrowheads ONLY if RelationshipRegistry defines directional=True.
    - Centered rounded pill label displays f"{type_label}: {title}" or type_label.
    """

    STYLES = ["bezier", "straight", "orthogonal", "mindmap"]

    def __init__(self, relationship: Optional[Any] = None, manager=None, parent=None):
        super().__init__(parent=parent)
        self.setZValue(-5)
        self.setFlags(
            QGraphicsObject.ItemIsSelectable
            | QGraphicsObject.ItemIsFocusable
        )

        self._manager = manager

        # Accept domain Relationship instance or construct default fallback
        if isinstance(relationship, Relationship):
            self.relationship = relationship
        elif isinstance(relationship, dict):
            self.relationship = Relationship.from_dict(relationship)
        else:
            self.relationship = Relationship()

        self._path: QPainterPath = QPainterPath()
        self._src_pos: QPointF = QPointF(0, 0)
        self._tgt_pos: QPointF = QPointF(0, 0)

    # -------------------------------------------------------------------------
    # Convenience Domain Property Accessors (Read-Only Projection)
    # -------------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self.relationship.id

    @property
    def source_id(self) -> str:
        return self.relationship.source_node_id

    @property
    def target_id(self) -> str:
        return self.relationship.target_node_id

    @property
    def source_anchor(self) -> str:
        return self.relationship.source_anchor

    @property
    def target_anchor(self) -> str:
        return self.relationship.target_anchor

    @property
    def relationship_type(self) -> str:
        return self.relationship.relationship_type

    @property
    def title(self) -> str:
        return self.relationship.title

    @property
    def notes(self) -> str:
        return self.relationship.notes

    @property
    def label(self) -> str:
        lbl = RelationshipRegistry.get_label(self.relationship.relationship_type)
        if self.relationship.title.strip():
            return f"{lbl}: {self.relationship.title.strip()}"
        return lbl

    @property
    def color(self) -> str:
        return RelationshipRegistry.get_color(self.relationship.relationship_type)

    # Legacy attributes for compatibility
    @property
    def width(self) -> int:
        return 2

    @property
    def style(self) -> str:
        return "bezier"

    # -------------------------------------------------------------------------
    # Serialization (Delegates strictly to domain Relationship)
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict:
        return self.relationship.to_dict()

    def from_dict(self, data: dict):
        if isinstance(data, dict):
            self.relationship = Relationship.from_dict(data)
            self.update_path()

    # -------------------------------------------------------------------------
    # Dynamic Bezier Path Calculation
    # -------------------------------------------------------------------------

    def update_path(self):
        """Dynamically recalculate path geometry with Blender/Blueprint dynamic tangent scaling."""
        scene = self.scene()
        if not scene:
            return

        canvas = scene.views()[0] if (scene.views() and hasattr(scene.views()[0], "node")) else None

        source_node = None
        target_node = None

        if canvas:
            source_node = canvas.node(self.source_id)
            target_node = canvas.node(self.target_id)
        else:
            for item in scene.items():
                if hasattr(item, "id"):
                    if item.id == self.source_id:
                        source_node = item
                    elif item.id == self.target_id:
                        target_node = item
                if source_node and target_node:
                    break

        if not source_node or not target_node:
            self._path = QPainterPath()
            self.prepareGeometryChange()
            self.update()
            return

        # Calculate endpoint anchor positions in scene coordinates
        if hasattr(source_node, "get_anchor_scene_pos"):
            src_pt = source_node.get_anchor_scene_pos(self.source_anchor)
        else:
            src_pt = source_node.sceneBoundingRect().center()

        if hasattr(target_node, "get_anchor_scene_pos"):
            tgt_pt = target_node.get_anchor_scene_pos(self.target_anchor)
        else:
            tgt_pt = target_node.sceneBoundingRect().center()

        self.prepareGeometryChange()

        # Dynamic Tangent Length Calculation
        distance = math.hypot(tgt_pt.x() - src_pt.x(), tgt_pt.y() - src_pt.y())
        tangent_len = min(max(distance * 0.35, 40.0), 220.0)

        ctrl1 = self._get_directional_control_point(src_pt, self.source_anchor, tangent_len, is_source=True)
        ctrl2 = self._get_directional_control_point(tgt_pt, self.target_anchor, tangent_len, is_source=False)

        path = QPainterPath()
        path.moveTo(src_pt)
        path.cubicTo(ctrl1, ctrl2, tgt_pt)

        self._path = path
        self._src_pos = src_pt
        self._tgt_pos = tgt_pt
        self.update()

    def _get_directional_control_point(self, point: QPointF, anchor: str, tangent_len: float, is_source: bool) -> QPointF:
        """Compute control point tangent vector based on anchor orientation (top/bottom/left/right)."""
        anchor = anchor.lower()
        if anchor == "right":
            return QPointF(point.x() + tangent_len, point.y())
        elif anchor == "left":
            return QPointF(point.x() - tangent_len, point.y())
        elif anchor == "top":
            return QPointF(point.x(), point.y() - tangent_len)
        elif anchor == "bottom":
            return QPointF(point.x(), point.y() + tangent_len)
        else:
            # Fallback center vector
            sign = 1.0 if is_source else -1.0
            return QPointF(point.x() + tangent_len * sign, point.y())

    # -------------------------------------------------------------------------
    # Hit Testing & Bounding Box
    # -------------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        if self._path.isEmpty():
            return QRectF(0, 0, 0, 0)
        margin = 24.0
        return self._path.boundingRect().adjusted(-margin, -margin, margin, margin)

    def shape(self) -> QPainterPath:
        if self._path.isEmpty():
            return QPainterPath()
        stroker = QPainterPathStroker()
        stroker.setWidth(14.0)
        stroker.setCapStyle(Qt.RoundCap)
        stroker.setJoinStyle(Qt.RoundJoin)
        return stroker.createStroke(self._path)

    # -------------------------------------------------------------------------
    # Rendering Pass
    # -------------------------------------------------------------------------

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        if self._path.isEmpty():
            return

        painter.setRenderHint(QPainter.Antialiasing)
        is_selected = self.isSelected()
        is_directional = RelationshipRegistry.is_directional(self.relationship_type)
        rel_color = QColor(self.color)

        # 1. Selected Glow Outline
        if is_selected:
            glow_pen = QPen(QColor("#6366F1"))
            glow_pen.setWidth(6)
            glow_pen.setCapStyle(Qt.RoundCap)
            glow_pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(glow_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(self._path)

        # 2. Main Curve Stroke
        main_pen = QPen(rel_color if not is_selected else QColor("#818CF8"))
        main_pen.setWidth(2)
        main_pen.setCapStyle(Qt.RoundCap)
        main_pen.setJoinStyle(Qt.RoundJoin)

        painter.setPen(main_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self._path)

        # 3. Arrowhead (Rendered ONLY if directional=True)
        if is_directional and self._path.elementCount() > 1:
            pt2 = self._path.pointAtPercent(1.0)
            pt1 = self._path.pointAtPercent(0.95)
            arrow_color = rel_color if not is_selected else QColor("#818CF8")
            self._draw_arrowhead(painter, pt1, pt2, arrow_color)

        # 4. Centered Pill Label Rendering
        display_label = self.label
        if display_label.strip():
            mid_pt = self._path.pointAtPercent(0.5)
            font = QFont("Segoe UI", 9, QFont.Bold)
            painter.setFont(font)

            font_metrics = painter.fontMetrics()
            txt_w = font_metrics.horizontalAdvance(display_label) + 16
            txt_h = font_metrics.height() + 6

            lbl_rect = QRectF(mid_pt.x() - txt_w / 2, mid_pt.y() - txt_h / 2, txt_w, txt_h)

            # Dark rounded pill badge
            painter.setBrush(QBrush(QColor("#0F172A")))
            border_col = QColor("#6366F1") if is_selected else rel_color
            painter.setPen(QPen(border_col, 1.5))
            painter.drawRoundedRect(lbl_rect, 5.0, 5.0)

            # Text label
            painter.setPen(QPen(QColor("#F8FAFC")))
            painter.drawText(lbl_rect, Qt.AlignCenter, display_label)

    def _draw_arrowhead(self, painter: QPainter, from_pt: QPointF, to_pt: QPointF, color: QColor):
        """Paint a filled triangular arrowhead pointing from from_pt to to_pt."""
        dx = to_pt.x() - from_pt.x()
        dy = to_pt.y() - from_pt.y()
        angle = math.atan2(dy, dx)

        arrow_size = 10.0
        p1 = to_pt - QPointF(arrow_size * math.cos(angle - math.pi / 6), arrow_size * math.sin(angle - math.pi / 6))
        p2 = to_pt - QPointF(arrow_size * math.cos(angle + math.pi / 6), arrow_size * math.sin(angle + math.pi / 6))

        poly = QPolygonF([to_pt, p1, p2])
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(poly)

    # -------------------------------------------------------------------------
    # Context Menu (Routes ALL actions exclusively via ConnectionManager)
    # -------------------------------------------------------------------------

    def contextMenuEvent(self, event):
        event.accept()
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #1E2029;
                color: #E2E8F0;
                border: 1px solid #2E3342;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #313652;
                color: #FFFFFF;
            }
        """)

        edit_act = QAction("✏️ Edit Relationship...", menu)
        type_act = QAction("🔀 Change Type...", menu)
        reverse_act = QAction("🔄 Reverse Relationship", menu)
        dup_act = QAction("📋 Duplicate Relationship", menu)
        src_act = QAction("⬆️ Jump to Source", menu)
        tgt_act = QAction("⬇️ Jump to Target", menu)
        del_act = QAction("🗑️ Delete", menu)

        menu.addAction(edit_act)
        menu.addAction(type_act)
        menu.addAction(reverse_act)
        menu.addAction(dup_act)
        menu.addSeparator()
        menu.addAction(src_act)
        menu.addAction(tgt_act)
        menu.addSeparator()
        menu.addAction(del_act)

        chosen = menu.exec_(event.screenPos())
        if not chosen or not self._manager:
            return

        if chosen == edit_act:
            if hasattr(self.scene(), "views") and self.scene().views():
                canvas = self.scene().views()[0]
                if hasattr(canvas, "set_selected_connectors"):
                    canvas.set_selected_connectors([self])
        elif chosen == type_act:
            if hasattr(self.scene(), "views") and self.scene().views():
                canvas = self.scene().views()[0]
                if hasattr(canvas, "prompt_relationship_type_change"):
                    canvas.prompt_relationship_type_change(self)
        elif chosen == reverse_act:
            self._manager.reverse_relationship(self.id)
        elif chosen == dup_act:
            self._manager.duplicate_relationship(self.id)
        elif chosen == src_act:
            if hasattr(self.scene(), "views") and self.scene().views():
                canvas = self.scene().views()[0]
                node = canvas.node(self.source_id)
                if node:
                    canvas.focus_node(node)
        elif chosen == tgt_act:
            if hasattr(self.scene(), "views") and self.scene().views():
                canvas = self.scene().views()[0]
                node = canvas.node(self.target_id)
                if node:
                    canvas.focus_node(node)
        elif chosen == del_act:
            self._manager.delete_relationship(self.id)
