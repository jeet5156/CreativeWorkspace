"""Reusable Visual Markup Canvas Widget.

Provides high-performance image display with mouse-centric zoom, pan,
reliable normalized coordinate mapping, interactive pin/note placement,
vector arrow creation, freehand stroke drawing, drag-to-move repositioning,
keyboard deletion, undo/redo command history, annotation overlay rendering,
and selection infrastructure.
"""

import copy
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, QSizeF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QImageReader,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from models.markup import MarkupDocument


# -----------------------------------------------------------------------------
# Tool Modes
# -----------------------------------------------------------------------------

class MarkupTool:
    """Supported interactive tool modes for MarkupCanvas."""
    SELECT = "select"
    PIN = "pin"
    ADD_NOTE = "pin"
    ARROW = "arrow"
    FREEHAND = "freehand"
    DRAW = "freehand"


# -----------------------------------------------------------------------------
# Undo / Redo Command Architecture
# -----------------------------------------------------------------------------

class MarkupCommand:
    """Abstract base command for undoable visual markup operations."""

    def execute(self):
        raise NotImplementedError

    def undo(self):
        raise NotImplementedError

    def redo(self):
        self.execute()


class CreateAnnotationCommand(MarkupCommand):
    """Command encapsulating creating a new visual annotation."""

    def __init__(self, view, doc_id: str, annotation_data: Dict[str, Any]):
        self.view = view
        self.doc_id = doc_id
        self.annotation_data = copy.deepcopy(annotation_data)

    def execute(self):
        doc = self.view.document()
        if not doc:
            return

        svc = self.view.markup_service()
        ann_id = self.annotation_data.get("id")

        if svc and doc.id:
            svc.add_annotation(doc.id, self.annotation_data)
            loaded = svc.get_markup(doc.id)
            if loaded:
                self.view._document = loaded
        else:
            if not any(a.get("id") == ann_id for a in doc.annotations):
                doc.annotations.append(copy.deepcopy(self.annotation_data))

        self.view._rebuild_annotations()
        self.view.select_annotation(ann_id)
        try:
            self.view.annotation_created.emit(ann_id)
        except Exception:
            pass

    def undo(self):
        doc = self.view.document()
        if not doc:
            return

        ann_id = self.annotation_data.get("id")
        svc = self.view.markup_service()

        if svc and doc.id:
            svc.remove_annotation(doc.id, ann_id)
            loaded = svc.get_markup(doc.id)
            if loaded:
                self.view._document = loaded
        else:
            doc.annotations = [a for a in doc.annotations if a.get("id") != ann_id]

        if self.view.selected_annotation_id() == ann_id:
            self.view.select_annotation(None)

        self.view._rebuild_annotations()


class MoveAnnotationCommand(MarkupCommand):
    """Command encapsulating moving an annotation (pin, arrow, or freehand) to a new position."""

    def __init__(self, view, doc_id: str, annotation_id: str, old_geom: Dict[str, Any], new_geom: Dict[str, Any]):
        self.view = view
        self.doc_id = doc_id
        self.annotation_id = annotation_id
        self.old_geom = copy.deepcopy(old_geom)
        self.new_geom = copy.deepcopy(new_geom)

    def _apply_geom(self, geom: Dict[str, Any]):
        doc = self.view.document()
        if not doc:
            return

        svc = self.view.markup_service()
        if svc and doc.id:
            svc.update_annotation(doc.id, self.annotation_id, copy.deepcopy(geom))
            loaded = svc.get_markup(doc.id)
            if loaded:
                self.view._document = loaded
        else:
            for a in doc.annotations:
                if a.get("id") == self.annotation_id:
                    a.update(copy.deepcopy(geom))
                    break

        self.view._rebuild_annotations()
        if self.view.selected_annotation_id() == self.annotation_id:
            self.view.select_annotation(self.annotation_id)

    def execute(self):
        self._apply_geom(self.new_geom)

    def undo(self):
        self._apply_geom(self.old_geom)


class EditTextAnnotationCommand(MarkupCommand):
    """Command encapsulating modifying text of an existing annotation."""

    def __init__(self, view, doc_id: str, annotation_id: str, old_text: str, new_text: str):
        self.view = view
        self.doc_id = doc_id
        self.annotation_id = annotation_id
        self.old_text = old_text
        self.new_text = new_text

    def _apply_text(self, text: str):
        doc = self.view.document()
        if not doc:
            return

        svc = self.view.markup_service()
        if svc and doc.id:
            svc.update_annotation(doc.id, self.annotation_id, {"text": text})
            loaded = svc.get_markup(doc.id)
            if loaded:
                self.view._document = loaded
        else:
            for a in doc.annotations:
                if a.get("id") == self.annotation_id:
                    a["text"] = text
                    break

        if self.annotation_id in self.view._annotation_items:
            item = self.view._annotation_items[self.annotation_id]
            if isinstance(item, MarkupTextItem):
                item.set_text(text)
        else:
            self.view._rebuild_annotations()

    def execute(self):
        self._apply_text(self.new_text)

    def undo(self):
        self._apply_text(self.old_text)


class DeleteAnnotationCommand(MarkupCommand):
    """Command encapsulating deleting an existing visual annotation."""

    def __init__(self, view, doc_id: str, annotation_data: Dict[str, Any]):
        self.view = view
        self.doc_id = doc_id
        self.annotation_data = copy.deepcopy(annotation_data)

    def execute(self):
        doc = self.view.document()
        if not doc:
            return

        ann_id = self.annotation_data.get("id")
        svc = self.view.markup_service()

        if svc and doc.id:
            svc.remove_annotation(doc.id, ann_id)
            loaded = svc.get_markup(doc.id)
            if loaded:
                self.view._document = loaded
        else:
            doc.annotations = [a for a in doc.annotations if a.get("id") != ann_id]

        if self.view.selected_annotation_id() == ann_id:
            self.view.select_annotation(None)

        self.view._rebuild_annotations()

    def undo(self):
        doc = self.view.document()
        if not doc:
            return

        ann_id = self.annotation_data.get("id")
        svc = self.view.markup_service()

        if svc and doc.id:
            svc.add_annotation(doc.id, self.annotation_data)
            loaded = svc.get_markup(doc.id)
            if loaded:
                self.view._document = loaded
        else:
            if not any(a.get("id") == ann_id for a in doc.annotations):
                doc.annotations.append(copy.deepcopy(self.annotation_data))

        self.view._rebuild_annotations()
        self.view.select_annotation(ann_id)


class MarkupUndoStack:
    """Bounded history stack managing undo/redo execution and memory bounds."""

    MAX_HISTORY = 50

    def __init__(self):
        self._undo_stack: List[MarkupCommand] = []
        self._redo_stack: List[MarkupCommand] = []

    def push(self, cmd: MarkupCommand):
        self._undo_stack.append(cmd)
        if len(self._undo_stack) > self.MAX_HISTORY:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def undo(self) -> bool:
        if not self.can_undo():
            return False
        cmd = self._undo_stack.pop()
        cmd.undo()
        self._redo_stack.append(cmd)
        return True

    def redo(self) -> bool:
        if not self.can_redo():
            return False
        cmd = self._redo_stack.pop()
        cmd.redo()
        self._undo_stack.append(cmd)
        return True

    def clear(self):
        self._undo_stack.clear()
        self._redo_stack.clear()


# -----------------------------------------------------------------------------
# Dialog for Note Input & Editing
# -----------------------------------------------------------------------------

class NoteInputDialog(QDialog):
    """Compact dark-theme dialog for entering or editing pin note text."""

    def __init__(self, initial_text: str = "", title: str = "Add Note", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedWidth(360)
        self.setModal(True)

        self.setStyleSheet("""
            QDialog {
                background-color: #141620;
                color: #F1F5F9;
                border: 1px solid #282C40;
                border-radius: 8px;
            }
            QLabel {
                color: #CBD5E1;
                font-size: 12px;
                font-weight: 600;
            }
            QTextEdit {
                background-color: #1E2029;
                color: #F1F5F9;
                border: 1px solid #2E3342;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
                line-height: 1.4;
            }
            QTextEdit:focus {
                border-color: #38BDF8;
            }
            QPushButton {
                background-color: #1E2029;
                color: #CBD5E1;
                border: 1px solid #2E3342;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #283556;
                color: #FFFFFF;
                border-color: #38BDF8;
            }
            QPushButton#btnSave {
                background-color: #2563EB;
                color: #FFFFFF;
                border: 1px solid #3B82F6;
            }
            QPushButton#btnSave:hover {
                background-color: #1D4ED8;
                border-color: #60A5FA;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header Label
        header_lbl = QLabel(f"📍 {title}")
        layout.addWidget(header_lbl)

        # Text Edit
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Type your note or comment here...")
        self.text_edit.setPlainText(initial_text)
        self.text_edit.setFixedHeight(90)
        layout.addWidget(self.text_edit)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Save Note" if initial_text else "Add Note")
        self.btn_save.setObjectName("btnSave")
        self.btn_save.clicked.connect(self._on_save_clicked)
        btn_row.addWidget(self.btn_save)

        layout.addLayout(btn_row)
        self.text_edit.setFocus()

    def _on_save_clicked(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            self.reject()
            return
        self.accept()

    def get_text(self) -> str:
        return self.text_edit.toPlainText().strip()


# -----------------------------------------------------------------------------
# Annotation Graphics Items
# -----------------------------------------------------------------------------

class MarkupPathItem(QGraphicsPathItem):
    """Render a freehand vector stroke or path with forgiving hit detection."""

    def __init__(self, annotation_id: str, path: QPainterPath, pen: QPen, parent=None):
        super().__init__(path, parent)
        self.annotation_id = annotation_id
        self._is_selected = False
        self.setPen(pen)
        self.setZValue(10)
        self.setAcceptHoverEvents(True)

    def set_markup_selected(self, selected: bool):
        self._is_selected = selected
        self.update()

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(max(14.0, self.pen().widthF() + 10.0))
        stroker.setCapStyle(Qt.RoundCap)
        stroker.setJoinStyle(Qt.RoundJoin)
        return stroker.createStroke(self.path()).united(self.path())

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing, True)
        if self._is_selected:
            glow_pen = QPen(QColor("#38BDF8"), self.pen().widthF() + 6.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(glow_pen)
            painter.drawPath(self.path())

        super().paint(painter, option, widget)


class MarkupArrowItem(QGraphicsPathItem):
    """Render a vector arrow with arrowhead and forgiving hit-testing."""

    def __init__(self, annotation_id: str, path: QPainterPath, pen: QPen, brush: QBrush, parent=None):
        super().__init__(path, parent)
        self.annotation_id = annotation_id
        self._is_selected = False
        self.setPen(pen)
        self.setBrush(brush)
        self.setZValue(10)
        self.setAcceptHoverEvents(True)

    def set_markup_selected(self, selected: bool):
        self._is_selected = selected
        self.update()

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(max(14.0, self.pen().widthF() + 10.0))
        stroker.setCapStyle(Qt.RoundCap)
        stroker.setJoinStyle(Qt.RoundJoin)
        return stroker.createStroke(self.path()).united(self.path())

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing, True)
        if self._is_selected:
            glow_pen = QPen(QColor("#38BDF8"), self.pen().widthF() + 6.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(glow_pen)
            painter.setBrush(QBrush(QColor("#38BDF8")))
            painter.drawPath(self.path())

        super().paint(painter, option, widget)


class MarkupRectItem(QGraphicsRectItem):
    """Render a rectangle annotation."""

    def __init__(self, annotation_id: str, rect: QRectF, pen: QPen, brush: QBrush, parent=None):
        super().__init__(rect, parent)
        self.annotation_id = annotation_id
        self._is_selected = False
        self.setPen(pen)
        self.setBrush(brush)
        self.setZValue(10)
        self.setAcceptHoverEvents(True)

    def set_markup_selected(self, selected: bool):
        self._is_selected = selected
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        if self._is_selected:
            glow_pen = QPen(QColor("#38BDF8"), self.pen().widthF() + 5.0, Qt.DashLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(glow_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.rect())

        super().paint(painter, option, widget)


class MarkupEllipseItem(QGraphicsEllipseItem):
    """Render an ellipse / circle annotation."""

    def __init__(self, annotation_id: str, rect: QRectF, pen: QPen, brush: QBrush, parent=None):
        super().__init__(rect, parent)
        self.annotation_id = annotation_id
        self._is_selected = False
        self.setPen(pen)
        self.setBrush(brush)
        self.setZValue(10)
        self.setAcceptHoverEvents(True)

    def set_markup_selected(self, selected: bool):
        self._is_selected = selected
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        if self._is_selected:
            glow_pen = QPen(QColor("#38BDF8"), self.pen().widthF() + 5.0, Qt.DashLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(glow_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(self.rect())

        super().paint(painter, option, widget)


class MarkupTextItem(QGraphicsItem):
    """Render an interactive visual pin marker and text callout."""

    PIN_RADIUS = 5.0
    LEADER_OFFSET_X = 14.0
    LEADER_OFFSET_Y = -18.0

    def __init__(
        self,
        annotation_id: str,
        text: str,
        anchor_pos: QPointF,
        font: QFont,
        color: QColor,
        bg_color: Optional[QColor] = None,
        parent=None,
    ):
        super().__init__(parent=parent)
        self.annotation_id = annotation_id
        self._is_selected = False
        self._text = text
        self._font = font
        self._color = color
        self._bg_color = bg_color or QColor(18, 20, 28, 230)
        self.setPos(anchor_pos)
        self.setZValue(20)
        self.setAcceptHoverEvents(True)

    def set_text(self, text: str):
        self.prepareGeometryChange()
        self._text = text
        self.update()

    def text(self) -> str:
        return self._text

    def set_markup_selected(self, selected: bool):
        self._is_selected = selected
        self.update()

    def _callout_rect(self) -> QRectF:
        fm = QFontMetricsF(self._font)
        lines = self._text.split("\n")
        w = max(fm.horizontalAdvance(l) for l in lines) if lines else 60.0
        h = max(22.0, len(lines) * fm.lineSpacing() + 6.0)

        box_x = self.LEADER_OFFSET_X
        box_y = self.LEADER_OFFSET_Y - h / 2.0
        return QRectF(box_x, box_y, w + 16.0, h)

    def boundingRect(self) -> QRectF:
        box = self._callout_rect()
        min_x = min(-self.PIN_RADIUS - 2, box.left() - 4)
        min_y = min(-self.PIN_RADIUS - 2, box.top() - 4)
        max_x = max(self.PIN_RADIUS + 2, box.right() + 4)
        max_y = max(self.PIN_RADIUS + 2, box.bottom() + 4)
        return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing, True)
        box = self._callout_rect()
        pin_color = QColor("#38BDF8") if self._is_selected else self._color

        # 1. Leader Line
        leader_pen = QPen(QColor("#38BDF8") if self._is_selected else QColor("#64748B"), 1.5, Qt.SolidLine)
        painter.setPen(leader_pen)
        box_anchor = QPointF(box.left(), box.center().y())
        painter.drawLine(QPointF(0, 0), box_anchor)

        # 2. Anchor Pin Dot
        if self._is_selected:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(56, 189, 248, 80)))
            painter.drawEllipse(QPointF(0, 0), self.PIN_RADIUS + 4, self.PIN_RADIUS + 4)

        painter.setPen(QPen(QColor("#0F172A"), 1.5))
        painter.setBrush(QBrush(pin_color))
        painter.drawEllipse(QPointF(0, 0), self.PIN_RADIUS, self.PIN_RADIUS)

        # Inner dot
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.drawEllipse(QPointF(0, 0), 1.5, 1.5)

        # 3. Callout Box
        border_pen = QPen(QColor("#38BDF8") if self._is_selected else QColor("#334155"), 1.5 if self._is_selected else 1.0)
        painter.setPen(border_pen)
        painter.setBrush(QBrush(self._bg_color))
        painter.drawRoundedRect(box, 5.0, 5.0)

        # 4. Text
        painter.setFont(self._font)
        painter.setPen(QPen(QColor("#F8FAFC")))
        text_rect = QRectF(box.x() + 8, box.y() + 3, box.width() - 16, box.height() - 6)
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, self._text)


# -----------------------------------------------------------------------------
# Core MarkupCanvasView
# -----------------------------------------------------------------------------

class MarkupCanvasView(QGraphicsView):
    """QGraphicsView responsible for 2D pan, zoom, coordinate mapping, and annotation rendering."""

    image_loaded = Signal(str)
    annotation_selected = Signal(str)
    annotation_created = Signal(str)
    canvas_view_changed = Signal(float)
    normalized_point_clicked = Signal(float, float)
    tool_changed = Signal(str)
    undo_stack_changed = Signal()

    MIN_ZOOM = 0.05
    MAX_ZOOM = 20.0
    ZOOM_STEP = 1.15

    def __init__(self, parent=None):
        super().__init__(parent)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # Undo / Redo Command History Stack
        self.undo_stack = MarkupUndoStack()

        # Background & Viewport Flags
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setBackgroundBrush(QBrush(QColor("#14161F")))

        # Image, Document, and Service state
        self._image_path: Optional[str] = None
        self._pixmap_item: Optional[QGraphicsPixmapItem] = None
        self._image_size = QSizeF(0, 0)
        self._document: Optional[MarkupDocument] = None
        self._markup_service = None
        self._annotation_items: Dict[str, QGraphicsItem] = {}
        self._selected_annotation_id: Optional[str] = None

        # Interactive state & Active tool
        self._current_tool = MarkupTool.SELECT
        self._is_panning = False
        self._pan_start = QPoint()
        self._space_pressed = False
        self._zoom_level = 1.0

        # Drag-to-move repositioning state
        self._dragged_item: Optional[QGraphicsItem] = None
        self._drag_start_scene_pos = QPointF()
        self._drag_item_orig_pos = QPointF()
        self._drag_orig_geom: Dict[str, Any] = {}
        self._has_dragged = False

        # Arrow creation state
        self._is_drawing_arrow = False
        self._arrow_start_scene = QPointF()
        self._arrow_start_norm = QPointF()
        self._temp_arrow_item: Optional[QGraphicsPathItem] = None

        # Freehand creation state
        self._is_drawing_freehand = False
        self._freehand_pts_scene: List[QPointF] = []
        self._freehand_pts_norm: List[Dict[str, float]] = []
        self._freehand_path = QPainterPath()
        self._temp_stroke_item: Optional[QGraphicsPathItem] = None

        # Placeholder label when no image is loaded
        self._placeholder_text = "No Image Loaded"

    # -------------------------------------------------------------------------
    # Undo / Redo Public API
    # -------------------------------------------------------------------------

    def can_undo(self) -> bool:
        return self.undo_stack.can_undo()

    def can_redo(self) -> bool:
        return self.undo_stack.can_redo()

    def undo(self) -> bool:
        success = self.undo_stack.undo()
        if success:
            self.undo_stack_changed.emit()
        return success

    def redo(self) -> bool:
        success = self.undo_stack.redo()
        if success:
            self.undo_stack_changed.emit()
        return success

    # -------------------------------------------------------------------------
    # Tool Modes API
    # -------------------------------------------------------------------------

    def set_tool(self, tool_name: str):
        """Set active interaction mode ('select', 'pin', 'arrow', or 'freehand')."""
        if tool_name in (MarkupTool.FREEHAND, "freehand", "draw"):
            tool = MarkupTool.FREEHAND
        elif tool_name in (MarkupTool.ARROW, "arrow"):
            tool = MarkupTool.ARROW
        elif tool_name in (MarkupTool.PIN, "pin", "add_note"):
            tool = MarkupTool.PIN
        else:
            tool = MarkupTool.SELECT

        if self._current_tool == tool:
            return

        # Cancel any active in-progress drawing
        self._cleanup_temp_drawing()

        self._current_tool = tool
        self._update_cursor()
        try:
            self.tool_changed.emit(self._current_tool)
        except Exception:
            pass

    def current_tool(self) -> str:
        """Return the currently active tool name."""
        return self._current_tool

    def _cleanup_temp_drawing(self):
        if self._is_drawing_arrow:
            self._is_drawing_arrow = False
            if self._temp_arrow_item:
                if self._temp_arrow_item.scene() == self._scene:
                    self._scene.removeItem(self._temp_arrow_item)
                self._temp_arrow_item = None

        if self._is_drawing_freehand:
            self._is_drawing_freehand = False
            if self._temp_stroke_item:
                if self._temp_stroke_item.scene() == self._scene:
                    self._scene.removeItem(self._temp_stroke_item)
                self._temp_stroke_item = None
            self._freehand_pts_scene.clear()
            self._freehand_pts_norm.clear()

    def _update_cursor(self):
        if self._is_panning:
            self.setCursor(Qt.ClosedHandCursor)
        elif self._space_pressed:
            self.setCursor(Qt.OpenHandCursor)
        elif self._current_tool in (MarkupTool.PIN, MarkupTool.ARROW, MarkupTool.FREEHAND) and self.has_image():
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    # -------------------------------------------------------------------------
    # Image Loading & Management
    # -------------------------------------------------------------------------

    def set_image(self, image_source: Union[str, Path, QImage, QPixmap]) -> bool:
        """Load and display an image from a filepath, QImage, or QPixmap."""
        pixmap = None
        path_str = ""

        if isinstance(image_source, (str, Path)):
            path = Path(image_source)
            path_str = str(path)
            if not path.exists():
                self.clear_image()
                self._placeholder_text = f"Image Not Found: {path.name}"
                self.viewport().update()
                return False

            reader = QImageReader(str(path))
            reader.setAutoTransform(True)
            img = reader.read()
            if img.isNull():
                self.clear_image()
                self._placeholder_text = f"Failed to decode: {path.name}"
                self.viewport().update()
                return False

            pixmap = QPixmap.fromImage(img)

        elif isinstance(image_source, QImage):
            pixmap = QPixmap.fromImage(image_source)
        elif isinstance(image_source, QPixmap):
            pixmap = image_source

        if not pixmap or pixmap.isNull():
            self.clear_image()
            return False

        self._image_path = path_str
        self._image_size = QSizeF(pixmap.width(), pixmap.height())

        # Clear existing scene items & undo stack
        self._cleanup_temp_drawing()
        self._scene.clear()
        self._annotation_items.clear()
        self._selected_annotation_id = None
        self.undo_stack.clear()
        self.undo_stack_changed.emit()

        # Setup Image in Scene: Top-left at (0, 0), dimensions (W, H)
        self._pixmap_item = QGraphicsPixmapItem(pixmap)
        self._pixmap_item.setTransformationMode(Qt.SmoothTransformation)
        self._pixmap_item.setZValue(0)
        self._scene.addItem(self._pixmap_item)
        self._scene.setSceneRect(0, 0, self._image_size.width(), self._image_size.height())

        # Re-render annotations if document is attached
        if self._document:
            self._rebuild_annotations()

        # Zoom to fit image on initial load
        self.zoom_to_fit()
        self._update_cursor()

        try:
            self.image_loaded.emit(self._image_path or "")
        except Exception:
            pass

        return True

    def clear_image(self):
        """Clear the current image and scene."""
        self._image_path = None
        self._pixmap_item = None
        self._image_size = QSizeF(0, 0)
        self._cleanup_temp_drawing()
        self._annotation_items.clear()
        self._selected_annotation_id = None
        self.undo_stack.clear()
        self.undo_stack_changed.emit()
        self._scene.clear()
        self._placeholder_text = "No Image Loaded"
        self._update_cursor()
        self.viewport().update()

    def has_image(self) -> bool:
        """Return True if an image is currently loaded."""
        return self._pixmap_item is not None and not self._image_size.isEmpty()

    @property
    def image_size(self) -> QSizeF:
        return self._image_size

    # -------------------------------------------------------------------------
    # Document & Service Delegation
    # -------------------------------------------------------------------------

    def set_document(self, document: Optional[MarkupDocument]):
        """Attach a MarkupDocument and render its annotations."""
        self._document = document
        self.undo_stack.clear()
        self.undo_stack_changed.emit()
        self._rebuild_annotations()

    def document(self) -> Optional[MarkupDocument]:
        return self._document

    def set_markup_service(self, service):
        """Attach a MarkupService for atomic persistence delegation."""
        self._markup_service = service

    def markup_service(self):
        return self._markup_service

    def _rebuild_annotations(self):
        """Re-render all annotations from the active MarkupDocument."""
        for item in list(self._annotation_items.values()):
            if item.scene() == self._scene:
                self._scene.removeItem(item)
        self._annotation_items.clear()

        if not self._document or not self.has_image():
            return

        w = self._image_size.width()
        h = self._image_size.height()

        for ann in self._document.annotations:
            if not isinstance(ann, dict):
                continue

            ann_id = str(ann.get("id") or "")
            ann_type = str(ann.get("type") or "text").lower()
            style = ann.get("style") or {}
            color_str = style.get("color") or style.get("stroke_color") or "#EF4444"
            width_val = float(style.get("width") or style.get("stroke_width") or 3.0)
            fill_str = style.get("fill") or style.get("fill_color") or "transparent"

            pen = QPen(QColor(color_str), width_val, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            brush = QBrush(QColor(fill_str)) if fill_str != "transparent" else QBrush(Qt.NoBrush)

            item = None

            if ann_type in ("freehand", "draw", "stroke"):
                pts = ann.get("points") or []
                if len(pts) >= 2:
                    path = QPainterPath()
                    p0 = pts[0]
                    p0_x = float(p0.get("x", 0.0) if isinstance(p0, dict) else p0[0]) * w
                    p0_y = float(p0.get("y", 0.0) if isinstance(p0, dict) else p0[1]) * h
                    path.moveTo(p0_x, p0_y)
                    for pt in pts[1:]:
                        px = float(pt.get("x", 0.0) if isinstance(pt, dict) else pt[0]) * w
                        py = float(pt.get("y", 0.0) if isinstance(pt, dict) else pt[1]) * h
                        path.lineTo(px, py)
                    item = MarkupPathItem(ann_id, path, pen)

            elif ann_type == "arrow":
                start = ann.get("start") or {"x": 0, "y": 0}
                end = ann.get("end") or {"x": 0, "y": 0}
                sx = float(start.get("x", 0.0) if isinstance(start, dict) else start[0]) * w
                sy = float(start.get("y", 0.0) if isinstance(start, dict) else start[1]) * h
                ex = float(end.get("x", 0.0) if isinstance(end, dict) else end[0]) * w
                ey = float(end.get("y", 0.0) if isinstance(end, dict) else end[1]) * h

                path = self._build_arrow_path(sx, sy, ex, ey, width_val)
                item = MarkupArrowItem(ann_id, path, pen, QBrush(QColor(color_str)))

            elif ann_type in ("rectangle", "rect", "box"):
                rect_data = ann.get("rect")
                if isinstance(rect_data, (list, tuple)) and len(rect_data) >= 4:
                    rx, ry, rw, rh = [float(v) for v in rect_data[:4]]
                    rect = QRectF(rx * w, ry * h, rw * w, rh * h)
                elif isinstance(rect_data, dict):
                    rx = float(rect_data.get("x", 0.0)) * w
                    ry = float(rect_data.get("y", 0.0)) * h
                    rw = float(rect_data.get("width", 0.0)) * w
                    rh = float(rect_data.get("height", 0.0)) * h
                    rect = QRectF(rx, ry, rw, rh)
                else:
                    start = ann.get("start") or {"x": 0, "y": 0}
                    end = ann.get("end") or {"x": 0, "y": 0}
                    sx = float(start.get("x", 0.0) if isinstance(start, dict) else start[0]) * w
                    sy = float(start.get("y", 0.0) if isinstance(start, dict) else start[1]) * h
                    ex = float(end.get("x", 0.0) if isinstance(end, dict) else end[0]) * w
                    ey = float(end.get("y", 0.0) if isinstance(end, dict) else end[1]) * h
                    rect = QRectF(min(sx, ex), min(sy, ey), abs(ex - sx), abs(ey - sy))

                item = MarkupRectItem(ann_id, rect, pen, brush)

            elif ann_type in ("ellipse", "circle"):
                rect_data = ann.get("rect")
                if isinstance(rect_data, (list, tuple)) and len(rect_data) >= 4:
                    rx, ry, rw, rh = [float(v) for v in rect_data[:4]]
                    rect = QRectF(rx * w, ry * h, rw * w, rh * h)
                elif isinstance(rect_data, dict):
                    rx = float(rect_data.get("x", 0.0)) * w
                    ry = float(rect_data.get("y", 0.0)) * h
                    rw = float(rect_data.get("width", 0.0)) * w
                    rh = float(rect_data.get("height", 0.0)) * h
                    rect = QRectF(rx, ry, rw, rh)
                else:
                    start = ann.get("start") or {"x": 0, "y": 0}
                    end = ann.get("end") or {"x": 0, "y": 0}
                    sx = float(start.get("x", 0.0) if isinstance(start, dict) else start[0]) * w
                    sy = float(start.get("y", 0.0) if isinstance(start, dict) else start[1]) * h
                    ex = float(end.get("x", 0.0) if isinstance(end, dict) else end[0]) * w
                    ey = float(end.get("y", 0.0) if isinstance(end, dict) else end[1]) * h
                    rect = QRectF(min(sx, ex), min(sy, ey), abs(ex - sx), abs(ey - sy))

                item = MarkupEllipseItem(ann_id, rect, pen, brush)

            elif ann_type in ("text", "callout", "pin"):
                pos_data = ann.get("position") or ann.get("start") or {"x": 0, "y": 0}
                px = float(pos_data.get("x", 0.0) if isinstance(pos_data, dict) else pos_data[0]) * w
                py = float(pos_data.get("y", 0.0) if isinstance(pos_data, dict) else pos_data[1]) * h
                text_content = str(ann.get("text") or "Note")
                font_sz = int(style.get("font_size") or 10)
                font = QFont("Segoe UI", font_sz, QFont.Bold)
                item = MarkupTextItem(ann_id, text_content, QPointF(px, py), font, QColor(color_str))

            if item:
                if ann_id == self._selected_annotation_id and hasattr(item, "set_markup_selected"):
                    item.set_markup_selected(True)
                self._scene.addItem(item)
                self._annotation_items[ann_id] = item

    def _build_arrow_path(self, sx: float, sy: float, ex: float, ey: float, stroke_width: float) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(sx, sy)
        path.lineTo(ex, ey)

        dx = ex - sx
        dy = ey - sy
        length = math.hypot(dx, dy)
        if length > 0.001:
            head_len = max(14.0, stroke_width * 3.5)
            head_angle = math.radians(26.0)
            angle = math.atan2(dy, dx)

            p1_x = ex - head_len * math.cos(angle - head_angle)
            p1_y = ey - head_len * math.sin(angle - head_angle)
            p2_x = ex - head_len * math.cos(angle + head_angle)
            p2_y = ey - head_len * math.sin(angle + head_angle)

            path.moveTo(ex, ey)
            path.lineTo(p1_x, p1_y)
            path.lineTo(p2_x, p2_y)
            path.closeSubpath()

        return path

    # -------------------------------------------------------------------------
    # Coordinate Mapping API (CRITICAL)
    # -------------------------------------------------------------------------

    def view_to_normalized(self, point: Union[QPointF, QPoint, Tuple[float, float]]) -> Optional[QPointF]:
        """Convert a Viewport pixel point to normalized image coordinates [0.0, 1.0]."""
        if not self.has_image():
            return None

        vx = float(point[0] if isinstance(point, (tuple, list)) else point.x())
        vy = float(point[1] if isinstance(point, (tuple, list)) else point.y())

        inv_trans, invertible = self.viewportTransform().inverted()
        if invertible:
            scene_pt = inv_trans.map(QPointF(vx, vy))
        else:
            scene_pt = self.mapToScene(QPoint(int(round(vx)), int(round(vy))))

        w = self._image_size.width()
        h = self._image_size.height()
        if w <= 0 or h <= 0:
            return None

        u = scene_pt.x() / w
        v = scene_pt.y() / h
        return QPointF(u, v)

    def normalized_to_view(self, point: Union[QPointF, Tuple[float, float]]) -> Optional[QPointF]:
        """Convert normalized image coordinates [0.0, 1.0] to Viewport pixel coordinates."""
        if not self.has_image():
            return None

        u = float(point[0] if isinstance(point, (tuple, list)) else point.x())
        v = float(point[1] if isinstance(point, (tuple, list)) else point.y())

        w = self._image_size.width()
        h = self._image_size.height()
        scene_pt = QPointF(u * w, v * h)
        view_pt = self.viewportTransform().map(scene_pt)
        return QPointF(view_pt.x(), view_pt.y())

    def image_to_normalized(self, point: Union[QPointF, Tuple[float, float]]) -> Optional[QPointF]:
        """Convert native image pixel coordinates to normalized [0.0, 1.0] coordinates."""
        if not self.has_image():
            return None

        x = float(point[0] if isinstance(point, (tuple, list)) else point.x())
        y = float(point[1] if isinstance(point, (tuple, list)) else point.y())

        w = self._image_size.width()
        h = self._image_size.height()
        return QPointF(x / w, y / h)

    def normalized_to_image(self, point: Union[QPointF, Tuple[float, float]]) -> Optional[QPointF]:
        """Convert normalized [0.0, 1.0] coordinates to native image pixel coordinates."""
        if not self.has_image():
            return None

        u = float(point[0] if isinstance(point, (tuple, list)) else point.x())
        v = float(point[1] if isinstance(point, (tuple, list)) else point.y())

        w = self._image_size.width()
        h = self._image_size.height()
        return QPointF(u * w, v * h)

    def view_to_image(self, point: Union[QPointF, QPoint, Tuple[float, float]]) -> Optional[QPointF]:
        """Convert Viewport pixel point to native image pixel coordinates."""
        if not self.has_image():
            return None

        vx = float(point[0] if isinstance(point, (tuple, list)) else point.x())
        vy = float(point[1] if isinstance(point, (tuple, list)) else point.y())

        inv_trans, invertible = self.viewportTransform().inverted()
        if invertible:
            return inv_trans.map(QPointF(vx, vy))
        return self.mapToScene(QPoint(int(round(vx)), int(round(vy))))

    def image_to_view(self, point: Union[QPointF, Tuple[float, float]]) -> Optional[QPointF]:
        """Convert native image pixel coordinates to Viewport pixel point."""
        if not self.has_image():
            return None

        x = float(point[0] if isinstance(point, (tuple, list)) else point.x())
        y = float(point[1] if isinstance(point, (tuple, list)) else point.y())
        view_pt = self.viewportTransform().map(QPointF(x, y))
        return QPointF(view_pt.x(), view_pt.y())

    # -------------------------------------------------------------------------
    # Zoom & Pan Controls
    # -------------------------------------------------------------------------

    def zoom_in(self, factor: float = ZOOM_STEP):
        """Zoom in relative to current scale."""
        self._apply_zoom(factor)

    def zoom_out(self, factor: float = ZOOM_STEP):
        """Zoom out relative to current scale."""
        self._apply_zoom(1.0 / factor)

    def zoom_to_fit(self):
        """Fit entire image into available viewport while preserving aspect ratio."""
        if not self.has_image():
            return

        self.resetTransform()
        rect = QRectF(0, 0, self._image_size.width(), self._image_size.height())
        self.fitInView(rect, Qt.KeepAspectRatio)
        self._zoom_level = self.transform().m11()
        self._emit_view_changed()

    def zoom_to_actual(self):
        """Set zoom to 100% (1:1 native image pixels to screen pixels)."""
        if not self.has_image():
            return

        self.resetTransform()
        self._zoom_level = 1.0
        self.centerOn(self._image_size.width() / 2.0, self._image_size.height() / 2.0)
        self._emit_view_changed()

    def set_zoom_level(self, level: float):
        """Explicitly set absolute zoom level."""
        level = max(self.MIN_ZOOM, min(self.MAX_ZOOM, float(level)))
        factor = level / self._zoom_level
        self.scale(factor, factor)
        self._zoom_level = level
        self._emit_view_changed()

    def get_zoom_level(self) -> float:
        """Return current zoom scale factor (1.0 = 100%)."""
        return self._zoom_level

    def _apply_zoom(self, factor: float):
        """Apply incremental zoom factor clamped to limits."""
        new_zoom = self._zoom_level * factor
        if new_zoom < self.MIN_ZOOM:
            factor = self.MIN_ZOOM / self._zoom_level
            new_zoom = self.MIN_ZOOM
        elif new_zoom > self.MAX_ZOOM:
            factor = self.MAX_ZOOM / self._zoom_level
            new_zoom = self.MAX_ZOOM

        self.scale(factor, factor)
        self._zoom_level = new_zoom
        self._emit_view_changed()

    def _emit_view_changed(self):
        try:
            self.canvas_view_changed.emit(self._zoom_level)
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Annotation Mutation, Deletion, and Undo/Redo Integration
    # -------------------------------------------------------------------------

    def create_pin_annotation(self, norm_pos: QPointF, note_text: str, color: str = "#EF4444") -> Optional[str]:
        """Create, persist, and render a new pin note at normalized coordinates with Undo support."""
        if not self.has_image() or not note_text or not note_text.strip():
            return None

        u = max(0.0, min(1.0, float(norm_pos.x())))
        v = max(0.0, min(1.0, float(norm_pos.y())))

        import uuid
        ann_id = f"ann_{uuid.uuid4().hex[:8]}"

        ann_data = {
            "id": ann_id,
            "type": "text",
            "position": {"x": round(u, 4), "y": round(v, 4)},
            "text": note_text.strip(),
            "style": {
                "color": color,
                "font_size": 10,
            },
        }

        if not self._document:
            self._document = MarkupDocument(
                name="Visual Markup",
                source_reference={"source_type": "project_asset", "relative_path": self._image_path or ""},
            )

        cmd = CreateAnnotationCommand(self, self._document.id, ann_data)
        cmd.execute()
        self.undo_stack.push(cmd)
        self.undo_stack_changed.emit()

        return ann_id

    def create_arrow_annotation(
        self,
        start_norm: QPointF,
        end_norm: QPointF,
        color: str = "#EF4444",
        stroke_width: float = 3.0,
    ) -> Optional[str]:
        """Create, persist, and render a new vector arrow annotation with Undo support."""
        if not self.has_image():
            return None

        sx = max(0.0, min(1.0, float(start_norm.x())))
        sy = max(0.0, min(1.0, float(start_norm.y())))
        ex = max(0.0, min(1.0, float(end_norm.x())))
        ey = max(0.0, min(1.0, float(end_norm.y())))

        import uuid
        ann_id = f"ann_{uuid.uuid4().hex[:8]}"

        ann_data = {
            "id": ann_id,
            "type": "arrow",
            "start": {"x": round(sx, 4), "y": round(sy, 4)},
            "end": {"x": round(ex, 4), "y": round(ey, 4)},
            "style": {
                "color": color,
                "width": stroke_width,
            },
        }

        if not self._document:
            self._document = MarkupDocument(
                name="Visual Markup",
                source_reference={"source_type": "project_asset", "relative_path": self._image_path or ""},
            )

        cmd = CreateAnnotationCommand(self, self._document.id, ann_data)
        cmd.execute()
        self.undo_stack.push(cmd)
        self.undo_stack_changed.emit()

        return ann_id

    def create_freehand_annotation(
        self,
        points_norm: List[Dict[str, float]],
        color: str = "#EF4444",
        stroke_width: float = 3.0,
    ) -> Optional[str]:
        """Create, persist, and render a new freehand stroke annotation with Undo support."""
        if not self.has_image() or len(points_norm) < 2:
            return None

        clean_pts = []
        for pt in points_norm:
            x = max(0.0, min(1.0, float(pt.get("x", 0.0) if isinstance(pt, dict) else pt[0])))
            y = max(0.0, min(1.0, float(pt.get("y", 0.0) if isinstance(pt, dict) else pt[1])))
            if not clean_pts or abs(clean_pts[-1]["x"] - x) > 0.0005 or abs(clean_pts[-1]["y"] - y) > 0.0005:
                clean_pts.append({"x": round(x, 4), "y": round(y, 4)})

        if len(clean_pts) < 2:
            return None

        import uuid
        ann_id = f"ann_{uuid.uuid4().hex[:8]}"

        ann_data = {
            "id": ann_id,
            "type": "freehand",
            "points": clean_pts,
            "style": {
                "color": color,
                "width": stroke_width,
            },
        }

        if not self._document:
            self._document = MarkupDocument(
                name="Visual Markup",
                source_reference={"source_type": "project_asset", "relative_path": self._image_path or ""},
            )

        cmd = CreateAnnotationCommand(self, self._document.id, ann_data)
        cmd.execute()
        self.undo_stack.push(cmd)
        self.undo_stack_changed.emit()

        return ann_id

    def edit_annotation_text(self, annotation_id: str, new_text: str) -> bool:
        """Update existing note text and persist with Undo support."""
        if not self._document or not annotation_id or not new_text or not new_text.strip():
            return False

        old_text = ""
        for a in self._document.annotations:
            if a.get("id") == annotation_id:
                old_text = a.get("text", "")
                break

        if old_text == new_text.strip():
            return True

        cmd = EditTextAnnotationCommand(self, self._document.id, annotation_id, old_text, new_text.strip())
        cmd.execute()
        self.undo_stack.push(cmd)
        self.undo_stack_changed.emit()
        return True

    def delete_selected_annotation(self) -> bool:
        """Delete currently selected annotation with Undo support."""
        if not self._selected_annotation_id or not self._document:
            return False

        target_id = self._selected_annotation_id
        target_ann = None
        for a in self._document.annotations:
            if a.get("id") == target_id:
                target_ann = copy.deepcopy(a)
                break

        if not target_ann:
            return False

        cmd = DeleteAnnotationCommand(self, self._document.id, target_ann)
        cmd.execute()
        self.undo_stack.push(cmd)
        self.undo_stack_changed.emit()
        return True

    def delete_annotation(self, annotation_id: str) -> bool:
        """Delete specific annotation by ID with Undo support."""
        if not annotation_id or not self._document:
            return False

        target_ann = None
        for a in self._document.annotations:
            if a.get("id") == annotation_id:
                target_ann = copy.deepcopy(a)
                break

        if not target_ann:
            return False

        cmd = DeleteAnnotationCommand(self, self._document.id, target_ann)
        cmd.execute()
        self.undo_stack.push(cmd)
        self.undo_stack_changed.emit()
        return True

    def select_annotation(self, annotation_id: Optional[str]):
        """Select an annotation by ID, updating visual highlights."""
        if self._selected_annotation_id == annotation_id:
            return

        # Deselect old
        if self._selected_annotation_id in self._annotation_items:
            item = self._annotation_items[self._selected_annotation_id]
            if hasattr(item, "set_markup_selected"):
                item.set_markup_selected(False)

        self._selected_annotation_id = annotation_id

        # Select new
        if annotation_id in self._annotation_items:
            item = self._annotation_items[annotation_id]
            if hasattr(item, "set_markup_selected"):
                item.set_markup_selected(True)

        try:
            self.annotation_selected.emit(annotation_id or "")
        except Exception:
            pass

    def selected_annotation_id(self) -> Optional[str]:
        return self._selected_annotation_id

    def get_annotation_data(self, annotation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve annotation dictionary by ID."""
        if not self._document:
            return None
        for a in self._document.annotations:
            if a.get("id") == annotation_id:
                return a
        return None

    # -------------------------------------------------------------------------
    # Event Handlers (Wheel, Mouse Pan, Drag Move, Click, Key Events)
    # -------------------------------------------------------------------------

    def wheelEvent(self, event):
        angle = event.angleDelta().y()
        if angle > 0:
            self.zoom_in()
        elif angle < 0:
            self.zoom_out()
        event.accept()

    def keyPressEvent(self, event):
        # 1. Escape Key -> Deselect annotation OR exit Pin / Arrow / Freehand mode
        if event.key() == Qt.Key_Escape:
            self._cleanup_temp_drawing()

            if self._current_tool in (MarkupTool.PIN, MarkupTool.ARROW, MarkupTool.FREEHAND):
                self.set_tool(MarkupTool.SELECT)
            if self._selected_annotation_id:
                self.select_annotation(None)
            event.accept()
            return

        # 2. Delete / Backspace -> Delete selected annotation
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            if self._selected_annotation_id:
                self.delete_selected_annotation()
                event.accept()
                return

        # 3. Undo / Redo Shortcuts
        if event.matches(QKeySequence.Undo) or (event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_Z and not (event.modifiers() & Qt.ShiftModifier)):
            if self.undo():
                event.accept()
                return
        if event.matches(QKeySequence.Redo) or (event.modifiers() & Qt.ControlModifier and (event.key() == Qt.Key_Y or (event.key() == Qt.Key_Z and event.modifiers() & Qt.ShiftModifier))):
            if self.redo():
                event.accept()
                return

        # 4. Space Bar Panning
        if event.key() == Qt.Key_Space and not self._space_pressed:
            self._space_pressed = True
            self._update_cursor()
            event.accept()
            return

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space:
            self._space_pressed = False
            self._update_cursor()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def _event_pos(self, event) -> QPoint:
        if hasattr(event, "position"):
            return event.position().toPoint()
        return event.pos()

    def mousePressEvent(self, event):
        pos = self._event_pos(event)

        # 1. Panning Trigger (Middle Click OR Space + Left Click)
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and self._space_pressed):
            self._is_panning = True
            self._pan_start = pos
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        # 2. Left Click in PIN Mode -> Prompt for Note Text and Place Pin
        if event.button() == Qt.LeftButton and self._current_tool == MarkupTool.PIN and self.has_image():
            norm_pt = self.view_to_normalized(pos)
            if norm_pt:
                dlg = NoteInputDialog(title="Add Pin Note", parent=self)
                if dlg.exec() == QDialog.Accepted:
                    text = dlg.get_text()
                    if text:
                        self.create_pin_annotation(norm_pt, text)
                        self.set_tool(MarkupTool.SELECT)
            event.accept()
            return

        # 3. Left Click in ARROW Mode -> Capture Start Point and Init Preview
        if event.button() == Qt.LeftButton and self._current_tool == MarkupTool.ARROW and self.has_image():
            norm_pt = self.view_to_normalized(pos)
            scene_pt = self.mapToScene(pos)
            if norm_pt:
                self._is_drawing_arrow = True
                self._arrow_start_norm = norm_pt
                self._arrow_start_scene = scene_pt

                if self._temp_arrow_item and self._temp_arrow_item.scene() == self._scene:
                    self._scene.removeItem(self._temp_arrow_item)

                pen = QPen(QColor("#EF4444"), 3.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                brush = QBrush(QColor("#EF4444"))
                self._temp_arrow_item = QGraphicsPathItem()
                self._temp_arrow_item.setPen(pen)
                self._temp_arrow_item.setBrush(brush)
                self._temp_arrow_item.setZValue(100)
                self._scene.addItem(self._temp_arrow_item)

            event.accept()
            return

        # 4. Left Click in FREEHAND Mode -> Start Freehand Stroke
        if event.button() == Qt.LeftButton and self._current_tool == MarkupTool.FREEHAND and self.has_image():
            norm_pt = self.view_to_normalized(pos)
            scene_pt = self.mapToScene(pos)
            if norm_pt:
                self._is_drawing_freehand = True
                self._freehand_pts_norm = [{"x": round(norm_pt.x(), 4), "y": round(norm_pt.y(), 4)}]
                self._freehand_pts_scene = [scene_pt]
                self._freehand_path = QPainterPath()
                self._freehand_path.moveTo(scene_pt)

                if self._temp_stroke_item and self._temp_stroke_item.scene() == self._scene:
                    self._scene.removeItem(self._temp_stroke_item)

                pen = QPen(QColor("#EF4444"), 3.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                self._temp_stroke_item = QGraphicsPathItem()
                self._temp_stroke_item.setPen(pen)
                self._temp_stroke_item.setPath(self._freehand_path)
                self._temp_stroke_item.setZValue(100)
                self._scene.addItem(self._temp_stroke_item)

            event.accept()
            return

        # 5. Left Click in SELECT Mode -> Selection, Drag-To-Move Setup, & Normalized Click Signal
        if event.button() == Qt.LeftButton and self._current_tool == MarkupTool.SELECT:
            scene_pos = self.mapToScene(pos)
            norm_pt = self.view_to_normalized(pos)
            if norm_pt:
                self.normalized_point_clicked.emit(norm_pt.x(), norm_pt.y())

            items_at_pos = self.scene().items(scene_pos)
            hit_ann_id = None
            hit_item = None
            for it in items_at_pos:
                if hasattr(it, "annotation_id"):
                    hit_ann_id = it.annotation_id
                    hit_item = it
                    break

            self.select_annotation(hit_ann_id)

            if hit_item and hit_ann_id:
                self._dragged_item = hit_item
                self._drag_start_scene_pos = scene_pos
                self._drag_item_orig_pos = hit_item.pos()
                ann_data = self.get_annotation_data(hit_ann_id) or {}
                self._drag_orig_geom = copy.deepcopy(ann_data)
                self._has_dragged = False

            event.accept()
            return

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        pos = self._event_pos(event)
        if event.button() == Qt.LeftButton and self._current_tool == MarkupTool.SELECT:
            scene_pos = self.mapToScene(pos)
            items_at_pos = self.scene().items(scene_pos)
            for it in items_at_pos:
                if isinstance(it, MarkupTextItem) and hasattr(it, "annotation_id"):
                    dlg = NoteInputDialog(initial_text=it.text(), title="Edit Note", parent=self)
                    if dlg.exec() == QDialog.Accepted:
                        new_txt = dlg.get_text()
                        if new_txt:
                            self.edit_annotation_text(it.annotation_id, new_txt)
                    event.accept()
                    return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        pos = self._event_pos(event)
        if self._is_panning:
            delta = pos - self._pan_start
            self._pan_start = pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return

        # Live Arrow Drawing Preview
        if self._is_drawing_arrow and self._temp_arrow_item:
            current_scene = self.mapToScene(pos)
            sx = self._arrow_start_scene.x()
            sy = self._arrow_start_scene.y()
            ex = current_scene.x()
            ey = current_scene.y()
            path = self._build_arrow_path(sx, sy, ex, ey, 3.0)
            self._temp_arrow_item.setPath(path)
            event.accept()
            return

        # Live Freehand Drawing Preview
        if self._is_drawing_freehand and self._temp_stroke_item and self._freehand_pts_scene:
            current_scene = self.mapToScene(pos)
            last_scene = self._freehand_pts_scene[-1]
            dist = math.hypot(current_scene.x() - last_scene.x(), current_scene.y() - last_scene.y())
            if dist >= 3.0:
                norm_pt = self.view_to_normalized(pos)
                if norm_pt:
                    self._freehand_pts_scene.append(current_scene)
                    self._freehand_pts_norm.append({"x": round(norm_pt.x(), 4), "y": round(norm_pt.y(), 4)})
                    self._freehand_path.lineTo(current_scene)
                    self._temp_stroke_item.setPath(self._freehand_path)
            event.accept()
            return

        # Real-time Drag-To-Move Repositioning
        if self._dragged_item is not None and (event.buttons() & Qt.LeftButton):
            scene_pos = self.mapToScene(pos)
            delta = scene_pos - self._drag_start_scene_pos
            if delta.manhattanLength() > 2.0:
                self._has_dragged = True

            new_x = self._drag_item_orig_pos.x() + delta.x()
            new_y = self._drag_item_orig_pos.y() + delta.y()
            self._dragged_item.setPos(QPointF(new_x, new_y))
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        pos = self._event_pos(event)
        if self._is_panning:
            self._is_panning = False
            self._update_cursor()
            event.accept()
            return

        # Finalize Arrow Creation
        if self._is_drawing_arrow:
            self._is_drawing_arrow = False
            if self._temp_arrow_item:
                if self._temp_arrow_item.scene() == self._scene:
                    self._scene.removeItem(self._temp_arrow_item)
                self._temp_arrow_item = None

            end_scene = self.mapToScene(pos)
            end_norm = self.view_to_normalized(pos)

            dist = math.hypot(end_scene.x() - self._arrow_start_scene.x(), end_scene.y() - self._arrow_start_scene.y())
            if dist >= 6.0 and self._arrow_start_norm and end_norm:
                sx = max(0.0, min(1.0, float(self._arrow_start_norm.x())))
                sy = max(0.0, min(1.0, float(self._arrow_start_norm.y())))
                ex = max(0.0, min(1.0, float(end_norm.x())))
                ey = max(0.0, min(1.0, float(end_norm.y())))

                self.create_arrow_annotation(QPointF(sx, sy), QPointF(ex, ey))
                self.set_tool(MarkupTool.SELECT)

            event.accept()
            return

        # Finalize Freehand Creation
        if self._is_drawing_freehand:
            self._is_drawing_freehand = False
            if self._temp_stroke_item:
                if self._temp_stroke_item.scene() == self._scene:
                    self._scene.removeItem(self._temp_stroke_item)
                self._temp_stroke_item = None

            if len(self._freehand_pts_norm) >= 2:
                self.create_freehand_annotation(self._freehand_pts_norm)
                self.set_tool(MarkupTool.SELECT)

            self._freehand_pts_scene.clear()
            self._freehand_pts_norm.clear()
            event.accept()
            return

        # Finalize Drag-To-Move Repositioning
        if self._dragged_item is not None:
            ann_id = getattr(self._dragged_item, "annotation_id", None)
            if ann_id and self._has_dragged and self._document:
                w = self._image_size.width()
                h = self._image_size.height()
                if w > 0 and h > 0:
                    delta_scene_x = self._dragged_item.pos().x() - self._drag_item_orig_pos.x()
                    delta_scene_y = self._dragged_item.pos().y() - self._drag_item_orig_pos.y()
                    delta_u = delta_scene_x / w
                    delta_v = delta_scene_y / h

                    ann_type = str(self._drag_orig_geom.get("type", "text")).lower()

                    if ann_type in ("freehand", "draw", "stroke"):
                        old_pts = self._drag_orig_geom.get("points", [])
                        new_pts = []
                        for pt in old_pts:
                            px = float(pt.get("x", 0.0) if isinstance(pt, dict) else pt[0])
                            py = float(pt.get("y", 0.0) if isinstance(pt, dict) else pt[1])
                            nx = max(0.0, min(1.0, px + delta_u))
                            ny = max(0.0, min(1.0, py + delta_v))
                            new_pts.append({"x": round(nx, 4), "y": round(ny, 4)})

                        old_geom = {"points": copy.deepcopy(old_pts)}
                        new_geom = {"points": new_pts}

                        if abs(delta_u) > 0.0001 or abs(delta_v) > 0.0001:
                            cmd = MoveAnnotationCommand(self, self._document.id, ann_id, old_geom, new_geom)
                            cmd.execute()
                            self.undo_stack.push(cmd)
                            self.undo_stack_changed.emit()

                    elif ann_type == "arrow":
                        old_s = self._drag_orig_geom.get("start", {"x": 0.0, "y": 0.0})
                        old_e = self._drag_orig_geom.get("end", {"x": 0.0, "y": 0.0})
                        old_sx = float(old_s.get("x", 0.0) if isinstance(old_s, dict) else old_s[0])
                        old_sy = float(old_s.get("y", 0.0) if isinstance(old_s, dict) else old_s[1])
                        old_ex = float(old_e.get("x", 0.0) if isinstance(old_e, dict) else old_e[0])
                        old_ey = float(old_e.get("y", 0.0) if isinstance(old_e, dict) else old_e[1])

                        new_sx = max(0.0, min(1.0, old_sx + delta_u))
                        new_sy = max(0.0, min(1.0, old_sy + delta_v))
                        new_ex = max(0.0, min(1.0, old_ex + delta_u))
                        new_ey = max(0.0, min(1.0, old_ey + delta_v))

                        old_geom = {"start": {"x": old_sx, "y": old_sy}, "end": {"x": old_ex, "y": old_ey}}
                        new_geom = {"start": {"x": round(new_sx, 4), "y": round(new_sy, 4)}, "end": {"x": round(new_ex, 4), "y": round(new_ey, 4)}}

                        if abs(delta_u) > 0.0001 or abs(delta_v) > 0.0001:
                            cmd = MoveAnnotationCommand(self, self._document.id, ann_id, old_geom, new_geom)
                            cmd.execute()
                            self.undo_stack.push(cmd)
                            self.undo_stack_changed.emit()

                    else:
                        # Default / text / pin translation
                        old_pos = self._drag_orig_geom.get("position", {"x": 0.0, "y": 0.0})
                        old_x = float(old_pos.get("x", 0.0) if isinstance(old_pos, dict) else old_pos[0])
                        old_y = float(old_pos.get("y", 0.0) if isinstance(old_pos, dict) else old_pos[1])

                        new_u = max(0.0, min(1.0, old_x + delta_u))
                        new_v = max(0.0, min(1.0, old_y + delta_v))

                        old_geom = {"position": {"x": old_x, "y": old_y}}
                        new_geom = {"position": {"x": round(new_u, 4), "y": round(new_v, 4)}}

                        if abs(delta_u) > 0.0001 or abs(delta_v) > 0.0001:
                            cmd = MoveAnnotationCommand(self, self._document.id, ann_id, old_geom, new_geom)
                            cmd.execute()
                            self.undo_stack.push(cmd)
                            self.undo_stack_changed.emit()

            self._dragged_item = None
            self._has_dragged = False
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._emit_view_changed()

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect)
        if not self.has_image():
            painter.save()
            painter.setPen(QColor("#64748B"))
            painter.setFont(QFont("Segoe UI", 13, QFont.Bold))
            painter.drawText(self.viewport().rect(), Qt.AlignCenter, self._placeholder_text)
            painter.restore()


# -----------------------------------------------------------------------------
# Compact Canvas Toolbar
# -----------------------------------------------------------------------------

class MarkupCanvasToolbar(QFrame):
    """Compact dark-theme toolbar with tool selectors, undo/redo controls, and zoom percentage readout."""

    tool_selected = Signal(str)
    undo_requested = Signal()
    redo_requested = Signal()
    zoom_in_requested = Signal()
    zoom_out_requested = Signal()
    fit_requested = Signal()
    actual_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self._active_tool = MarkupTool.SELECT

        self.setStyleSheet("""
            MarkupCanvasToolbar {
                background-color: #12141C;
                border-bottom: 1px solid #282C40;
                padding: 2px 8px;
            }
            QPushButton {
                background-color: #1E2029;
                color: #CBD5E1;
                border: 1px solid #2E3342;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
                min-width: 24px;
            }
            QPushButton:hover {
                background-color: #283556;
                color: #38BDF8;
                border-color: #38BDF8;
            }
            QPushButton:disabled {
                background-color: #161822;
                color: #475569;
                border-color: #202330;
            }
            QPushButton[active="true"] {
                background-color: #1E3A8A;
                color: #60A5FA;
                border: 1px solid #3B82F6;
            }
            QLabel {
                color: #94A3B8;
                font-size: 11px;
                font-weight: 600;
                padding: 0 4px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # 1. Tool Selection Group
        self.btn_select = QPushButton("🖱 Select")
        self.btn_select.setToolTip("Select / Move Annotations (S)")
        self.btn_select.clicked.connect(lambda: self.set_active_tool(MarkupTool.SELECT))
        layout.addWidget(self.btn_select)

        self.btn_pin = QPushButton("📍 Add Note")
        self.btn_pin.setToolTip("Place a Pin Callout Note on the Image (N)")
        self.btn_pin.clicked.connect(lambda: self.set_active_tool(MarkupTool.PIN))
        layout.addWidget(self.btn_pin)

        self.btn_arrow = QPushButton("↗ Arrow")
        self.btn_arrow.setToolTip("Draw a Directional Vector Arrow (A)")
        self.btn_arrow.clicked.connect(lambda: self.set_active_tool(MarkupTool.ARROW))
        layout.addWidget(self.btn_arrow)

        self.btn_draw = QPushButton("✏ Draw")
        self.btn_draw.setToolTip("Freehand Drawing Stroke (D)")
        self.btn_draw.clicked.connect(lambda: self.set_active_tool(MarkupTool.FREEHAND))
        layout.addWidget(self.btn_draw)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet("background-color: #282C40; max-width: 1px; margin: 4px 4px;")
        layout.addWidget(sep1)

        # 2. Undo / Redo Group
        self.btn_undo = QPushButton("↶ Undo")
        self.btn_undo.setToolTip("Undo (Ctrl+Z)")
        self.btn_undo.setEnabled(False)
        self.btn_undo.clicked.connect(self.undo_requested.emit)
        layout.addWidget(self.btn_undo)

        self.btn_redo = QPushButton("↷ Redo")
        self.btn_redo.setToolTip("Redo (Ctrl+Y)")
        self.btn_redo.setEnabled(False)
        self.btn_redo.clicked.connect(self.redo_requested.emit)
        layout.addWidget(self.btn_redo)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet("background-color: #282C40; max-width: 1px; margin: 4px 4px;")
        layout.addWidget(sep2)

        # 3. Zoom Group
        self.btn_zoom_out = QPushButton("−")
        self.btn_zoom_out.setToolTip("Zoom Out (Ctrl+- or Wheel Down)")
        self.btn_zoom_out.clicked.connect(self.zoom_out_requested.emit)
        layout.addWidget(self.btn_zoom_out)

        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setAlignment(Qt.AlignCenter)
        self.lbl_zoom.setFixedWidth(46)
        layout.addWidget(self.lbl_zoom)

        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setToolTip("Zoom In (Ctrl++ or Wheel Up)")
        self.btn_zoom_in.clicked.connect(self.zoom_in_requested.emit)
        layout.addWidget(self.btn_zoom_in)

        # Separator
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.VLine)
        sep3.setStyleSheet("background-color: #282C40; max-width: 1px; margin: 4px 4px;")
        layout.addWidget(sep3)

        # Fit Button
        self.btn_fit = QPushButton("Fit")
        self.btn_fit.setToolTip("Fit Image to Viewport")
        self.btn_fit.clicked.connect(self.fit_requested.emit)
        layout.addWidget(self.btn_fit)

        # 100% Button
        self.btn_actual = QPushButton("100%")
        self.btn_actual.setToolTip("1:1 Pixel Scale")
        self.btn_actual.clicked.connect(self.actual_requested.emit)
        layout.addWidget(self.btn_actual)

        layout.addStretch()
        self._update_tool_buttons()

    def set_active_tool(self, tool_name: str):
        if tool_name in (MarkupTool.FREEHAND, "freehand", "draw"):
            tool = MarkupTool.FREEHAND
        elif tool_name in (MarkupTool.ARROW, "arrow"):
            tool = MarkupTool.ARROW
        elif tool_name in (MarkupTool.PIN, "pin", "add_note"):
            tool = MarkupTool.PIN
        else:
            tool = MarkupTool.SELECT

        if self._active_tool == tool:
            return
        self._active_tool = tool
        self._update_tool_buttons()
        try:
            self.tool_selected.emit(self._active_tool)
        except Exception:
            pass

    def _update_tool_buttons(self):
        self.btn_select.setProperty("active", "true" if self._active_tool == MarkupTool.SELECT else "false")
        self.btn_pin.setProperty("active", "true" if self._active_tool == MarkupTool.PIN else "false")
        self.btn_arrow.setProperty("active", "true" if self._active_tool == MarkupTool.ARROW else "false")
        self.btn_draw.setProperty("active", "true" if self._active_tool == MarkupTool.FREEHAND else "false")
        self.btn_select.style().unpolish(self.btn_select)
        self.btn_select.style().polish(self.btn_select)
        self.btn_pin.style().unpolish(self.btn_pin)
        self.btn_pin.style().polish(self.btn_pin)
        self.btn_arrow.style().unpolish(self.btn_arrow)
        self.btn_arrow.style().polish(self.btn_arrow)
        self.btn_draw.style().unpolish(self.btn_draw)
        self.btn_draw.style().polish(self.btn_draw)

    def set_zoom_level(self, level: float):
        pct = int(round(level * 100))
        self.lbl_zoom.setText(f"{pct}%")

    def update_undo_redo_state(self, can_undo: bool, can_redo: bool):
        self.btn_undo.setEnabled(can_undo)
        self.btn_redo.setEnabled(can_redo)


# -----------------------------------------------------------------------------
# Composite MarkupCanvas Component
# -----------------------------------------------------------------------------

class MarkupCanvas(QWidget):
    """Reusable Composite Visual Markup Canvas Widget with integrated toolbar and view."""

    image_loaded = Signal(str)
    annotation_selected = Signal(str)
    annotation_created = Signal(str)
    canvas_view_changed = Signal(float)
    normalized_point_clicked = Signal(float, float)
    tool_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top Toolbar
        self.toolbar = MarkupCanvasToolbar(self)
        main_layout.addWidget(self.toolbar)

        # 2. Center Graphics View
        self.view = MarkupCanvasView(self)
        main_layout.addWidget(self.view, 1)

        # Connect toolbar to view
        self.toolbar.tool_selected.connect(self.view.set_tool)
        self.toolbar.undo_requested.connect(self.view.undo)
        self.toolbar.redo_requested.connect(self.view.redo)
        self.toolbar.zoom_in_requested.connect(self.view.zoom_in)
        self.toolbar.zoom_out_requested.connect(self.view.zoom_out)
        self.toolbar.fit_requested.connect(self.view.zoom_to_fit)
        self.toolbar.actual_requested.connect(self.view.zoom_to_actual)

        # Connect view updates to toolbar and parent signals
        self.view.tool_changed.connect(self._on_tool_changed)
        self.view.undo_stack_changed.connect(self._on_undo_stack_changed)
        self.view.canvas_view_changed.connect(self._on_view_changed)
        self.view.image_loaded.connect(self.image_loaded.emit)
        self.view.annotation_selected.connect(self.annotation_selected.emit)
        self.view.annotation_created.connect(self.annotation_created.emit)
        self.view.normalized_point_clicked.connect(self.normalized_point_clicked.emit)

    def _on_tool_changed(self, tool_name: str):
        self.toolbar.set_active_tool(tool_name)
        self.tool_changed.emit(tool_name)

    def _on_view_changed(self, zoom_level: float):
        self.toolbar.set_zoom_level(zoom_level)
        self.canvas_view_changed.emit(zoom_level)

    def _on_undo_stack_changed(self):
        self.toolbar.update_undo_redo_state(self.view.can_undo(), self.view.can_redo())

    # -------------------------------------------------------------------------
    # Public API Delegation
    # -------------------------------------------------------------------------

    def set_tool(self, tool_name: str):
        self.view.set_tool(tool_name)

    def current_tool(self) -> str:
        return self.view.current_tool()

    def set_image(self, image_source: Union[str, Path, QImage, QPixmap]) -> bool:
        return self.view.set_image(image_source)

    def clear_image(self):
        self.view.clear_image()

    def has_image(self) -> bool:
        return self.view.has_image()

    def set_document(self, document: Optional[MarkupDocument]):
        self.view.set_document(document)

    def document(self) -> Optional[MarkupDocument]:
        return self.view.document()

    def set_markup_service(self, service):
        self.view.set_markup_service(service)

    def markup_service(self):
        return self.view.markup_service()

    def can_undo(self) -> bool:
        return self.view.can_undo()

    def can_redo(self) -> bool:
        return self.view.can_redo()

    def undo(self) -> bool:
        return self.view.undo()

    def redo(self) -> bool:
        return self.view.redo()

    def create_pin_annotation(self, norm_pos: QPointF, note_text: str, color: str = "#EF4444") -> Optional[str]:
        return self.view.create_pin_annotation(norm_pos, note_text, color=color)

    def create_arrow_annotation(
        self,
        start_norm: QPointF,
        end_norm: QPointF,
        color: str = "#EF4444",
        stroke_width: float = 3.0,
    ) -> Optional[str]:
        return self.view.create_arrow_annotation(start_norm, end_norm, color=color, stroke_width=stroke_width)

    def create_freehand_annotation(
        self,
        points_norm: List[Dict[str, float]],
        color: str = "#EF4444",
        stroke_width: float = 3.0,
    ) -> Optional[str]:
        return self.view.create_freehand_annotation(points_norm, color=color, stroke_width=stroke_width)

    def edit_annotation_text(self, annotation_id: str, new_text: str) -> bool:
        return self.view.edit_annotation_text(annotation_id, new_text)

    def delete_selected_annotation(self) -> bool:
        return self.view.delete_selected_annotation()

    def delete_annotation(self, annotation_id: str) -> bool:
        return self.view.delete_annotation(annotation_id)

    def zoom_in(self):
        self.view.zoom_in()

    def zoom_out(self):
        self.view.zoom_out()

    def zoom_to_fit(self):
        self.view.zoom_to_fit()

    def zoom_to_actual(self):
        self.view.zoom_to_actual()

    def set_zoom_level(self, level: float):
        self.view.set_zoom_level(level)

    def get_zoom_level(self) -> float:
        return self.view.get_zoom_level()

    def select_annotation(self, annotation_id: Optional[str]):
        self.view.select_annotation(annotation_id)

    def selected_annotation_id(self) -> Optional[str]:
        return self.view.selected_annotation_id()

    # Coordinate Mapping
    def view_to_normalized(self, point: Union[QPointF, QPoint, Tuple[float, float]]) -> Optional[QPointF]:
        return self.view.view_to_normalized(point)

    def normalized_to_view(self, point: Union[QPointF, Tuple[float, float]]) -> Optional[QPointF]:
        return self.view.normalized_to_view(point)

    def image_to_normalized(self, point: Union[QPointF, Tuple[float, float]]) -> Optional[QPointF]:
        return self.view.image_to_normalized(point)

    def normalized_to_image(self, point: Union[QPointF, Tuple[float, float]]) -> Optional[QPointF]:
        return self.view.normalized_to_image(point)

    def view_to_image(self, point: Union[QPointF, QPoint, Tuple[float, float]]) -> Optional[QPointF]:
        return self.view.view_to_image(point)

    def image_to_view(self, point: Union[QPointF, Tuple[float, float]]) -> Optional[QPointF]:
        return self.view.image_to_view(point)
