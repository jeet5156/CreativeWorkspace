from PySide6.QtWidgets import QGraphicsTextItem, QGraphicsItem, QStyleOptionGraphicsItem, QWidget
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont

from ui.lab.items.card_item import CardItem
from ui.lab.items.card_types import CardType, NoteType, NOTE_TYPE_CONFIGS


class NoteTextItem(QGraphicsTextItem):
    """Child text item for NoteCardItem with focus-out auto-save signal."""

    editing_finished = Signal()

    def focusOutEvent(self, event):
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        super().focusOutEvent(event)
        try:
            self.editing_finished.emit()
        except Exception:
            pass


class NoteCardItem(CardItem):
    """Semantic NoteCard canvas object with Notion/Linear studio aesthetic.

    Renders a dark slate paper card with a left accent bar, semantic icon badge (Goal, Idea, Task, Problem, Decision),
    and an embedded double-clickable text editor.
    """

    WIDTH = 260.0
    HEIGHT = 180.0
    CORNER_RADIUS = 8.0

    def __init__(self, note_type: NoteType = NoteType.BLANK, parent=None):
        super().__init__(card_type=CardType.NOTE, parent=parent)
        self.note_type = note_type
        self.content = ""
        self.background_color = "#1E2029"

        # Embedded Text Editor Child
        self.text_item = NoteTextItem(self)
        self.text_item.setPos(12, 34)
        self.text_item.setTextWidth(self.WIDTH - 24)

        font = QFont("Segoe UI", 10)
        self.text_item.setFont(font)
        self.text_item.setDefaultTextColor(QColor("#CBD5E1"))
        self.text_item.setTextInteractionFlags(Qt.NoTextInteraction)
        self.text_item.editing_finished.connect(self._on_editing_finished)

    # -------------------------------------------------------------------------
    # QGraphicsItem Geometry & Rendering
    # -------------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.WIDTH, self.HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        config = NOTE_TYPE_CONFIGS.get(self.note_type, NOTE_TYPE_CONFIGS[NoteType.BLANK])
        accent_color = QColor(config["accent"])

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
        painter.drawLine(4, 10, 4, int(self.HEIGHT - 10))

        # 3. Draw Header Divider Line
        divider_pen = QPen(QColor("#2E3342"))
        divider_pen.setWidth(1)
        painter.setPen(divider_pen)
        painter.drawLine(10, 30, int(self.WIDTH - 10), 30)

        # 4. Draw Header Icon & Label Badge
        badge_bg = QColor(config["badge_bg"])
        badge_text_color = QColor(config["badge_text"])

        badge_rect = QRectF(12, 6, 110, 18)
        painter.setBrush(QBrush(badge_bg))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(badge_rect, 4.0, 4.0)

        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.setPen(QPen(badge_text_color))
        header_text = f"{config['icon']}  {config['label']}"
        painter.drawText(badge_rect, Qt.AlignCenter, header_text)

        # 5. Draw Selection Ring
        self.draw_selection_outline(painter, rect, self.CORNER_RADIUS)

    # -------------------------------------------------------------------------
    # Interaction Handling
    # -------------------------------------------------------------------------

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.text_item.setTextInteractionFlags(Qt.TextEditorInteraction)
            self.text_item.setFocus()
            # Set cursor at end
            cursor = self.text_item.textCursor()
            cursor.movePosition(cursor.End)
            self.text_item.setTextCursor(cursor)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _on_editing_finished(self):
        self.content = self.text_item.toPlainText()
        self._emit_modified()

    # -------------------------------------------------------------------------
    # Serialization Interface
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["payload"] = {
            "note_type": self.note_type.value if isinstance(self.note_type, NoteType) else str(self.note_type),
            "content": self.text_item.toPlainText(),
        }
        return d

    def from_dict(self, data: dict):
        super().from_dict(data)
        payload = data.get("payload", {})
        if isinstance(payload, dict):
            raw_type = str(payload.get("note_type", "blank")).lower()
            try:
                self.note_type = NoteType(raw_type)
            except Exception:
                self.note_type = NoteType.BLANK

            self.content = str(payload.get("content", ""))
            self.text_item.setPlainText(self.content)

        self.update()
