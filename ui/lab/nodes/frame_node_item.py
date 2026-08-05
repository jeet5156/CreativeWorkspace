import os
from typing import List
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget, QInputDialog, QMenu, QLineEdit
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QAction

from ui.lab.nodes.node_item import NodeItem
from ui.lab.nodes.node_definition import NodeDefinition


class FrameNodeItem(NodeItem):
    """Lightweight organizational Frame node item for the Creative Lab canvas.

    Inspired by Unreal Engine Comment Boxes, Figma Sections, and Miro Frames.
    Provides resizable, color-themed, collapse-expand container bounds. Membership is
    determined purely geometrically without child parentage, enabling all current and
    future node types to work seamlessly.
    """

    CORNER_RADIUS = 12.0
    HEADER_HEIGHT = 36.0
    HANDLE_SIZE = 14.0

    COLOR_THEMES = {
        "purple": {
            "accent": "#A855F7",
            "header_bg": "#2E1C48",
            "badge_text": "#C084FC",
            "surface_bg": "#1E1B2E",
            "border": "#A855F7",
        },
        "blue": {
            "accent": "#3B82F6",
            "header_bg": "#1E2E4A",
            "badge_text": "#60A5FA",
            "surface_bg": "#1B2234",
            "border": "#3B82F6",
        },
        "green": {
            "accent": "#22C55E",
            "header_bg": "#14382B",
            "badge_text": "#34D399",
            "surface_bg": "#172922",
            "border": "#22C55E",
        },
        "amber": {
            "accent": "#F59E0B",
            "header_bg": "#3B2D1B",
            "badge_text": "#FBBF24",
            "surface_bg": "#2B251B",
            "border": "#F59E0B",
        },
        "red": {
            "accent": "#EF4444",
            "header_bg": "#3F1D24",
            "badge_text": "#F87171",
            "surface_bg": "#2C1B20",
            "border": "#EF4444",
        },
        "gray": {
            "accent": "#94A3B8",
            "header_bg": "#1E293B",
            "badge_text": "#CBD5E1",
            "surface_bg": "#1C202B",
            "border": "#94A3B8",
        },
    }

    def __init__(self, definition: NodeDefinition, parent=None):
        super().__init__(definition, parent=parent)
        self.z_order = -10
        self.setZValue(-10)  # Render beneath regular spatial nodes
        self.setAcceptHoverEvents(True)

        # Ensure default payload attributes
        if "title" not in self.payload:
            self.payload["title"] = "Section Frame"
        if "color_theme" not in self.payload:
            self.payload["color_theme"] = "purple"
        if "collapsed" not in self.payload:
            self.payload["collapsed"] = False

        self._expanded_height = float(self.height)
        self._is_moving = False
        self._is_resizing = False
        self._is_drag_hovered = False
        self._resize_start_pos = None
        self._resize_start_size = None

    def get_theme_colors(self) -> dict:
        theme_key = str(self.payload.get("color_theme", "purple")).lower()
        return self.COLOR_THEMES.get(theme_key, self.COLOR_THEMES["purple"])

    def contained_nodes(self) -> List[NodeItem]:
        """Geometrically determine member nodes whose scene center falls within frame bounds."""
        if not self.scene():
            return []
        frame_rect = self.sceneBoundingRect()
        members = []
        for item in self.scene().items():
            if isinstance(item, NodeItem) and item is not self and not isinstance(item, FrameNodeItem):
                item_center = item.sceneBoundingRect().center()
                if frame_rect.contains(item_center):
                    members.append(item)
        return members

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.isSelected() and not self._is_moving:
            self._is_moving = True
            try:
                new_pos = value
                current_pos = self.pos()
                delta = new_pos - current_pos

                # Move contained member nodes by matching delta
                for member in self.contained_nodes():
                    if not getattr(member, "is_locked", False):
                        member.setPos(member.pos() + delta)
            finally:
                self._is_moving = False
        return super().itemChange(change, value)

    def set_color_theme(self, theme_name: str):
        if theme_name in self.COLOR_THEMES:
            self.payload["color_theme"] = theme_name
            self._emit_modified()
            self.update()

    def set_collapsed(self, collapsed: bool):
        if bool(self.payload.get("collapsed")) == collapsed:
            return

        self.payload["collapsed"] = collapsed
        if collapsed:
            members = self.contained_nodes()
            self._expanded_height = float(self.height)
            self.height = self.HEADER_HEIGHT
            for member in members:
                member.setVisible(False)
        else:
            self.height = max(self.HEADER_HEIGHT + 40.0, self._expanded_height)
            members = self.contained_nodes()
            for member in members:
                member.setVisible(True)

        self._emit_modified()
        self.update()

    def toggle_collapsed(self):
        self.set_collapsed(not self.payload.get("collapsed", False))

    def start_title_editing(self):
        """Open seamless inline title editor directly over header bar."""
        scene_pos = self.mapToScene(QPointF(14, 4))
        view = self.scene().views()[0] if (self.scene() and self.scene().views()) else None
        if not view:
            self.prompt_rename()
            return

        view_pos = view.mapFromScene(scene_pos)
        edit = QLineEdit(view)
        edit.setText(str(self.payload.get("title", "Section Frame")))
        colors = self.get_theme_colors()
        accent_hex = colors["accent"]
        edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: #1E2029;
                color: #F1F5F9;
                border: 1px solid {accent_hex};
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 12px;
                font-weight: bold;
            }}
        """)
        edit.resize(int(self.width - 28), int(self.HEADER_HEIGHT - 8))
        edit.move(view_pos)
        edit.setFocus()
        edit.selectAll()

        committed = False

        def commit():
            nonlocal committed
            if committed:
                return
            committed = True
            txt = edit.text().strip()
            if txt:
                self.payload["title"] = txt
                self._emit_modified()
                self.update()
            edit.deleteLater()

        edit.returnPressed.connect(commit)
        edit.editingFinished.connect(commit)
        edit.show()

    def prompt_rename(self, parent_widget=None):
        curr_title = str(self.payload.get("title", "Section Frame"))
        new_title, ok = QInputDialog.getText(
            parent_widget,
            "Rename Frame",
            "Enter new Frame title:",
            text=curr_title
        )
        if ok and new_title.strip():
            self.payload["title"] = new_title.strip()
            self._emit_modified()
            self.update()

    def _is_in_resize_handle(self, pos: QPointF) -> bool:
        return (pos.x() >= self.width - self.HANDLE_SIZE) and (pos.y() >= self.height - self.HANDLE_SIZE)

    def hoverMoveEvent(self, event):
        if self._is_in_resize_handle(event.pos()) and not bool(self.payload.get("collapsed", False)):
            self.setCursor(Qt.SizeFDiagCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._is_in_resize_handle(event.pos()) and not bool(self.payload.get("collapsed", False)):
            self._is_resizing = True
            self._resize_start_pos = event.pos()
            self._resize_start_size = (self.width, self.height)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_resizing:
            delta = event.pos() - self._resize_start_pos
            min_w, min_h = self.definition.minimum_size if self.definition else (240.0, 180.0)
            self.width = max(min_w, self._resize_start_size[0] + delta.x())
            self.height = max(min_h, self._resize_start_size[1] + delta.y())
            self._expanded_height = float(self.height)
            self.payload["layout"] = {"width": float(self.width), "height": float(self.height)}
            self._emit_modified()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_resizing:
            self._is_resizing = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.on_double_clicked(event)
        if event.button() == Qt.LeftButton:
            if event.pos().y() <= self.HEADER_HEIGHT:
                self.start_title_editing()
            else:
                self.start_title_editing()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        colors = self.get_theme_colors()
        accent = QColor(colors["accent"])
        header_bg = QColor(colors["header_bg"])
        surface_bg = QColor(colors["surface_bg"])
        surface_bg.setAlpha(30)  # Polished translucent surface fill

        is_collapsed = bool(self.payload.get("collapsed", False))

        # 1. Fill Frame Background Surface
        if not is_collapsed:
            painter.setBrush(QBrush(surface_bg))
            if self._is_drag_hovered:
                border_pen = QPen(accent)
                border_pen.setWidth(3)
            elif self.isSelected():
                border_pen = QPen(QColor("#6366F1"))
                border_pen.setWidth(2)
            else:
                border_pen = QPen(QColor(colors["border"]))
                border_pen.setWidth(1)
            painter.setPen(border_pen)
            painter.drawRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)

        # 2. Draw Header Bar
        header_rect = QRectF(0, 0, self.width, self.HEADER_HEIGHT)
        painter.setBrush(QBrush(header_bg))
        if self._is_drag_hovered:
            header_pen = QPen(accent)
            header_pen.setWidth(3)
        elif self.isSelected():
            header_pen = QPen(QColor("#6366F1"))
            header_pen.setWidth(2)
        else:
            header_pen = QPen(QColor(colors["border"]))
            header_pen.setWidth(1)
        painter.setPen(header_pen)
        painter.drawRoundedRect(header_rect, self.CORNER_RADIUS, self.CORNER_RADIUS)

        # 3. Horizontal Header Divider Line
        divider_pen = QPen(QColor(colors["border"]))
        divider_pen.setWidth(1)
        painter.setPen(divider_pen)
        painter.drawLine(0, int(self.HEADER_HEIGHT), int(self.width), int(self.HEADER_HEIGHT))

        # 4. Top Accent Strip & Header Title Text
        accent_pen = QPen(accent)
        accent_pen.setWidth(3)
        painter.setPen(accent_pen)
        painter.drawLine(4, 4, 4, int(self.HEADER_HEIGHT - 4))

        title_text = str(self.payload.get("title", "Section Frame"))
        icon_str = self.definition.icon if self.definition else "🖼️"
        status_suffix = " (Collapsed)" if is_collapsed else ""
        header_text = f"{icon_str}  {title_text}{status_suffix}"

        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        painter.setPen(QPen(QColor(colors["badge_text"])))
        text_rect = QRectF(14, 0, self.width - 24, self.HEADER_HEIGHT)
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, header_text)

        # 5. Bottom-Right Interactive Resize Handle (◢)
        if not is_collapsed:
            handle_pen = QPen(accent)
            handle_pen.setWidth(2)
            painter.setPen(handle_pen)
            w, h = int(self.width), int(self.height)
            painter.drawLine(w - 12, h - 4, w - 4, h - 12)
            painter.drawLine(w - 8, h - 4, w - 4, h - 8)

        # 6. Selection Outline
        self.draw_selection_outline(painter, rect, self.CORNER_RADIUS)

    def on_context_menu(self, menu: QMenu):
        """Build context menu for Frame node."""
        action_rename = QAction("✏️ Rename Frame...", menu)
        action_rename.triggered.connect(lambda: self.start_title_editing())
        menu.addAction(action_rename)

        # Color Theme Submenu
        color_menu = menu.addMenu("🎨 Change Color Theme")
        for theme_key in ("purple", "blue", "green", "amber", "red", "gray"):
            theme_title = theme_key.capitalize()
            theme_act = QAction(f"● {theme_title}", color_menu)
            theme_act.triggered.connect(lambda checked=False, t=theme_key: self.set_color_theme(t))
            color_menu.addAction(theme_act)

        # Collapse / Expand Action
        is_collapsed = bool(self.payload.get("collapsed", False))
        col_text = "↕️ Expand Frame" if is_collapsed else "↔️ Collapse Frame"
        action_collapse = QAction(col_text, menu)
        action_collapse.triggered.connect(self.toggle_collapsed)
        menu.addAction(action_collapse)
