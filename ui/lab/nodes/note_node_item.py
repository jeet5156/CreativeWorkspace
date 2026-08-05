from PySide6.QtWidgets import QGraphicsTextItem, QStyleOptionGraphicsItem, QWidget
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QTextCursor

from ui.lab.nodes.node_item import NodeItem
from ui.lab.nodes.node_definition import NodeDefinition
from ui.lab.nodes.node_capability import NodeCapability


class NoteTextItem(QGraphicsTextItem):
    """Child text editor item for NoteNodeItem with focus-out auto-save signal."""

    editing_finished = Signal()

    def focusOutEvent(self, event):
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        super().focusOutEvent(event)
        try:
            self.editing_finished.emit()
        except Exception:
            pass


class NoteNodeItem(NodeItem):
    """Presentation card node for Note cards (Goal, Idea, Task, Problem, Decision, Blank).

    Renders Notion/Linear studio aesthetic with top badge, accent bar, and embedded double-clickable text editor.
    """

    CORNER_RADIUS = 8.0

    def __init__(self, definition: NodeDefinition, parent=None):
        super().__init__(definition, parent=parent)

        # Embedded Text Editor Child
        self.text_item = NoteTextItem(self)
        self.text_item.setPos(12, 34)
        self.text_item.setTextWidth(self.width - 24)

        font = QFont("Segoe UI", 10)
        self.text_item.setFont(font)
        self.text_item.setDefaultTextColor(QColor("#CBD5E1"))
        self.text_item.setTextInteractionFlags(Qt.NoTextInteraction)
        self.text_item.editing_finished.connect(self._on_editing_finished)

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        defn = self.definition
        accent_color = QColor(defn.accent_color if defn else "#94A3B8")

        # 1. Fill card background surface
        bg_color = QColor(self.background_color)
        painter.setBrush(QBrush(bg_color))

        border_pen = QPen(QColor("#6366F1") if self.isSelected() else QColor("#2E3342"))
        border_pen.setWidth(2 if self.isSelected() else 1)
        painter.setPen(border_pen)

        painter.drawRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)

        # 2. Draw Left Accent Bar
        accent_pen = QPen(accent_color)
        accent_pen.setWidth(4)
        painter.setPen(accent_pen)
        painter.drawLine(4, 10, 4, int(self.height - 10))

        # 3. Draw Header Divider Line
        divider_pen = QPen(QColor("#2E3342"))
        divider_pen.setWidth(1)
        painter.setPen(divider_pen)
        painter.drawLine(10, 30, int(self.width - 10), 30)

        # 4. Draw Header Icon & Label Badge
        badge_bg = QColor(defn.badge_bg if defn else "#1E293B")
        badge_text_color = QColor(defn.badge_text if defn else "#94A3B8")

        badge_rect = QRectF(12, 6, 110, 18)
        painter.setBrush(QBrush(badge_bg))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(badge_rect, 4.0, 4.0)

        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.setPen(QPen(badge_text_color))
        header_text = f"{defn.icon}  {defn.title}" if defn else "Note"
        painter.drawText(badge_rect, Qt.AlignCenter, header_text)

        # 5. Draw Selection Ring
        self.draw_selection_outline(painter, rect, self.CORNER_RADIUS)

    def mouseDoubleClickEvent(self, event):
        self.on_double_clicked(event)
        if event.button() == Qt.LeftButton and self.has_capability(NodeCapability.CAN_EDIT_TEXT):
            self.text_item.setTextInteractionFlags(Qt.TextEditorInteraction)
            self.text_item.setFocus()
            cursor = self.text_item.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.text_item.setTextCursor(cursor)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
        super().mouseDoubleClickEvent(event)

    def _on_editing_finished(self):
        self.payload["content"] = self.text_item.toPlainText()
        self._emit_modified()

    def from_dict(self, data: dict):
        super().from_dict(data)
        content = str(self.payload.get("content", ""))
        self.text_item.setPlainText(content)
        self.on_loaded()
        self.update()
