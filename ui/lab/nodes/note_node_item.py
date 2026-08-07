from PySide6.QtWidgets import (
    QGraphicsTextItem,
    QStyleOptionGraphicsItem,
    QWidget,
    QTextEdit,
    QGraphicsProxyWidget,
    QGraphicsItem,
)
from PySide6.QtCore import Qt, QRectF, QSizeF, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QTextCursor

from ui.lab.nodes.node_item import NodeItem
from ui.lab.nodes.node_definition import NodeDefinition
from ui.lab.nodes.node_capability import NodeCapability
from ui.widgets.markdown_renderer import MarkdownRenderer


class NoteTextEditor(QTextEdit):
    """Embedded dark-themed text widget supporting formatted Markdown preview, raw source editing,

    guaranteed clipping, and internal vertical scrolling when clamped at max height.
    """

    double_clicked = Signal()
    editing_finished = Signal()
    editing_canceled = Signal()
    text_changed_live = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                color: #CBD5E1;
                border: none;
                font-family: 'Segoe UI';
                font-size: 13px;
                selection-background-color: #312E81;
                selection-color: #F1F5F9;
            }
            QScrollBar:vertical {
                background: #1E2029;
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #475569;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #6366F1;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setReadOnly(True)
        self._is_editing = False
        self._last_cursor_position = 0
        self.document().contentsChanged.connect(self._on_contents_changed)

    def _on_contents_changed(self):
        if self._is_editing:
            self.text_changed_live.emit()

    def mouseDoubleClickEvent(self, event):
        if self._is_editing:
            super().mouseDoubleClickEvent(event)
            return
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def start_editing(self, raw_text: str):
        if self._is_editing:
            return
        self._is_editing = True
        self.setReadOnly(False)
        self.setPlainText(raw_text)

        self.setFocus()
        cursor = self.textCursor()
        target_pos = self._last_cursor_position if self._last_cursor_position <= len(raw_text) else len(raw_text)
        cursor.setPosition(target_pos)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def finish_editing(self) -> str:
        if not self._is_editing:
            return self.toPlainText()
        self._last_cursor_position = self.textCursor().position()
        self._is_editing = False
        self.setReadOnly(True)
        return self.toPlainText()

    def cancel_editing(self, original_text: str):
        self._is_editing = False
        self.setReadOnly(True)
        self.setPlainText(original_text)

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()

        if self._is_editing:
            if key in (Qt.Key_Return, Qt.Key_Enter) and (mods & Qt.ControlModifier):
                self.editing_finished.emit()
                event.accept()
                return
            elif key == Qt.Key_Escape:
                self.editing_canceled.emit()
                event.accept()
                return

        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        if self._is_editing:
            try:
                self.editing_finished.emit()
            except Exception:
                pass
        super().focusOutEvent(event)

    # Backward compatibility API matching old QGraphicsTextItem
    def setTextWidth(self, width: float):
        self.document().setTextWidth(max(100.0, float(width)))

    def textWidth(self) -> float:
        return self.document().textWidth()


class NoteNodeItem(NodeItem):
    """Presentation card node for Note cards (Goal, Idea, Task, Problem, Decision, Blank).

    Renders Notion/Linear studio aesthetic with top badge, accent bar, and embedded double-clickable text editor.
    """

    CORNER_RADIUS = 8.0

    def __init__(self, definition: NodeDefinition, parent=None):
        super().__init__(definition, parent=parent)
        self.setFlag(QGraphicsItem.ItemClipsChildrenToShape, True)
        self.setFlag(QGraphicsItem.ItemClipsToShape, True)

        self._pre_edit_content = ""
        self._user_min_height = self.definition.default_size[1] if self.definition else 180.0

        # Embedded Text Editor Proxy Widget
        self.editor = NoteTextEditor()
        self.proxy_widget = QGraphicsProxyWidget(self)
        self.proxy_widget.setWidget(self.editor)
        self.proxy_widget.setPos(12, 34)

        self.editor.double_clicked.connect(self._start_note_editing)
        self.editor.editing_finished.connect(self._commit_note_editing)
        self.editor.editing_canceled.connect(self._cancel_note_editing)
        self.editor.text_changed_live.connect(self._update_card_height)

        # Backward compatibility alias
        self.text_item = self.editor

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

        # 5. Draw Tag Badging (if tags exist)
        self.draw_tag_badges(painter, rect)

        # 6. Draw Selection Ring
        self.draw_selection_outline(painter, rect, self.CORNER_RADIUS)

    def _update_card_height(self):
        """Recalculate card height based on QTextDocument content height to ensure zero text overflow.

        Enforces min height=180px, max height=900px, preserves user manual resize height, and matches preview width.
        Width remains entirely user-controlled. Enables internal vertical scrollbar when clamped at 900px.
        """
        MIN_HEIGHT = 180.0
        MAX_HEIGHT = 900.0

        self.prepareGeometryChange()
        target_w = max(100.0, float(self.width) - 24.0)
        doc = self.editor.document()
        doc.setTextWidth(target_w)

        doc_height = doc.size().height()
        padding = 45.0  # Top header bar (34px) + bottom padding (11px)

        user_min = getattr(self, "_user_min_height", MIN_HEIGHT)
        calculated_height = max(user_min, MIN_HEIGHT, doc_height + padding)

        if calculated_height > MAX_HEIGHT:
            self.height = MAX_HEIGHT
        else:
            self.height = calculated_height

        widget_h = max(30.0, self.height - 45.0)
        self.proxy_widget.setGeometry(QRectF(12, 34, target_w, widget_h))

        if "layout" not in self.payload or not isinstance(self.payload["layout"], dict):
            self.payload["layout"] = {}
        self.payload["layout"]["height"] = self.height

        self.update()

    def mouseDoubleClickEvent(self, event):
        self.on_double_clicked(event)
        if event.button() == Qt.LeftButton:
            self._start_note_editing()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _start_note_editing(self):
        """Canonical single entry point for starting note edit mode."""
        if self.editor._is_editing or not self.has_capability(NodeCapability.CAN_EDIT_TEXT):
            return
        self._pre_edit_content = str(self.payload.get("content", ""))
        self.editor.start_editing(self._pre_edit_content)
        self._update_card_height()

    def _commit_note_editing(self):
        """Canonical single entry point for committing note edits."""
        if not self.editor._is_editing:
            return
        raw_text = self.editor.finish_editing()
        self.payload["content"] = raw_text
        MarkdownRenderer.render_to_document(raw_text, self.editor.document())
        self._update_card_height()
        self._emit_modified()

    # Backward compatibility alias
    _on_editing_finished = _commit_note_editing

    def _cancel_note_editing(self):
        """Canonical single entry point for canceling note edits."""
        if not self.editor._is_editing:
            return
        content = self._pre_edit_content if hasattr(self, "_pre_edit_content") else ""
        self.payload["content"] = content
        self.editor.cancel_editing(content)
        MarkdownRenderer.render_to_document(content, self.editor.document())
        self._update_card_height()
        self._emit_modified()

    # Backward compatibility alias
    _on_editing_canceled = _cancel_note_editing

    def from_dict(self, data: dict):
        super().from_dict(data)

        layout_w = data.get("layout", {}).get("width") if isinstance(data.get("layout"), dict) else None
        if not layout_w and isinstance(data.get("transform"), dict):
            layout_w = data.get("transform", {}).get("width")
        if layout_w:
            self.width = float(layout_w)

        layout_h = data.get("layout", {}).get("height") if isinstance(data.get("layout"), dict) else None
        if not layout_h and isinstance(data.get("transform"), dict):
            layout_h = data.get("transform", {}).get("height")
        if layout_h and float(layout_h) > 180.0:
            self._user_min_height = float(layout_h)

        content = str(self.payload.get("content", ""))
        self.editor.setPlainText(content)
        MarkdownRenderer.render_to_document(content, self.editor.document())
        self._update_card_height()
        self.on_loaded()
        self.update()
