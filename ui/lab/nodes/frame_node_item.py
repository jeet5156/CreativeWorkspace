import os
from typing import List, Union
from datetime import datetime
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget, QInputDialog, QMenu, QLineEdit
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QAction

from ui.lab.nodes.node_item import NodeItem
from ui.lab.nodes.node_definition import NodeDefinition
from services.frame_service import FrameService, FRAME_PADDING, HEADER_HEIGHT, MIN_FRAME_WIDTH, MIN_FRAME_HEIGHT


class FrameNodeItem(NodeItem):
    """Lightweight organizational Frame node container for the Creative Lab canvas.

    Inspired by Miro Section Frames, Unreal Engine Comment Boxes, and Figma Sections.
    Delegates structural graph management to `FrameService` while handling UI rendering,
    header styling, resizing, and user interaction.
    """

    CHEVRON_HIT_WIDTH = 36.0
    CORNER_RADIUS = 12.0
    HEADER_HEIGHT = HEADER_HEIGHT
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
        "yellow": {
            "accent": "#F59E0B",
            "header_bg": "#3B2D1B",
            "badge_text": "#FBBF24",
            "surface_bg": "#2B251B",
            "border": "#F59E0B",
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

        # Standard Future-Proof Payload Attributes
        now = datetime.now().isoformat()
        if "title" not in self.payload:
            self.payload["title"] = "Section Frame"
        if "theme" not in self.payload:
            self.payload["theme"] = self.payload.get("color_theme", "blue")
        if "color_theme" not in self.payload:
            self.payload["color_theme"] = self.payload["theme"]
        if "locked" not in self.payload:
            self.payload["locked"] = False
        if "child_node_ids" not in self.payload or not isinstance(self.payload["child_node_ids"], list):
            self.payload["child_node_ids"] = []
        if "collapsed" not in self.payload:
            self.payload["collapsed"] = False
        if "visible_children" not in self.payload:
            self.payload["visible_children"] = True
        if "created" not in self.payload:
            self.payload["created"] = now
        if "modified" not in self.payload:
            self.payload["modified"] = now

        self._expanded_height = float(self.height)
        self._is_moving = False
        self._is_resizing = False
        self._is_drag_hovered = False
        self._resize_start_pos = None
        self._resize_start_size = None

    def from_dict(self, data: dict):
        if isinstance(data, dict) and "transform" in data and isinstance(data["transform"], dict):
            if "z" not in data["transform"]:
                data["transform"]["z"] = -10
        super().from_dict(data)
        if self.zValue() >= 0:
            self.setZValue(-10)

        # Ensure schema completeness on reload
        if "theme" not in self.payload:
            self.payload["theme"] = self.payload.get("color_theme", "blue")
        if "locked" not in self.payload:
            self.payload["locked"] = False
        if "child_node_ids" not in self.payload or not isinstance(self.payload["child_node_ids"], list):
            self.payload["child_node_ids"] = []
        if "collapsed" not in self.payload:
            self.payload["collapsed"] = False
        if "visible_children" not in self.payload:
            self.payload["visible_children"] = True

    def get_theme_colors(self) -> dict:
        theme_key = str(self.payload.get("theme", self.payload.get("color_theme", "blue"))).lower()
        return self.COLOR_THEMES.get(theme_key, self.COLOR_THEMES["blue"])

    # -------------------------------------------------------------------------
    # Centralized Membership API (Delegated to FrameService)
    # -------------------------------------------------------------------------

    def get_child_ids(self) -> List[str]:
        """Return list of child node UUIDs attached to this frame."""
        return list(self.payload.get("child_node_ids", []))

    def attached_nodes(self) -> List[NodeItem]:
        """Return list of live NodeItem instances attached to this frame via FrameService."""
        return FrameService.get_attached_nodes(self)

    def contained_nodes(self) -> List[NodeItem]:
        """Return attached nodes via FrameService."""
        return self.attached_nodes()

    def attach_node(self, target: Union[NodeItem, str]) -> bool:
        """Attach node to this frame via FrameService."""
        return FrameService.attach_node(self, target)

    def detach_node(self, target: Union[NodeItem, str]) -> bool:
        """Detach node from this frame via FrameService."""
        return FrameService.detach_node(self, target)

    def move_node_to_frame(self, target: Union[NodeItem, str], destination_frame: "FrameNodeItem") -> bool:
        """Transfer node from this frame to destination frame via FrameService."""
        return FrameService.move_node_to_frame(target, self, destination_frame)

    def detach_all(self) -> bool:
        """Detach all child nodes from this frame via FrameService."""
        return FrameService.detach_all(self)

    def select_all_children(self):
        """Select all child nodes attached to this frame in the scene."""
        if not self.scene():
            return
        children = self.attached_nodes()
        self.scene().clearSelection()
        for child in children:
            child.setSelected(True)

    # -------------------------------------------------------------------------
    # Frame Interactions & Capabilities
    # -------------------------------------------------------------------------

    def set_color_theme(self, theme_name: str):
        theme_key = theme_name.lower()
        if theme_key in self.COLOR_THEMES:
            self.payload["theme"] = theme_key
            self.payload["color_theme"] = theme_key
            self._emit_modified()
            self.update()

    def set_locked(self, locked: bool):
        self.payload["locked"] = bool(locked)
        self.is_locked = bool(locked)
        self._emit_modified()
        self.update()

    def toggle_locked(self):
        self.set_locked(not self.payload.get("locked", False))

    def set_collapsed(self, collapsed: bool):
        """Collapse or expand frame via FrameService."""
        return FrameService.set_collapsed(self, collapsed)

    def toggle_collapsed(self):
        """Toggle collapse/expand state."""
        return self.set_collapsed(not bool(self.payload.get("collapsed", False)))

    def fit_to_contents(self):
        """Auto-resize and reposition frame to fit all attached child nodes via FrameService."""
        return FrameService.fit_to_contents(self)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            # Block frame movement if locked
            if self.payload.get("locked", False):
                return self.pos()

            if self.isSelected() and not self._is_moving:
                self._is_moving = True
                try:
                    new_pos = value
                    current_pos = self.pos()
                    delta = new_pos - current_pos

                    # Move attached child nodes by matching position delta
                    for member in self.attached_nodes():
                        if not getattr(member, "is_locked", False):
                            member.setPos(member.pos() + delta)
                finally:
                    self._is_moving = False
        return super().itemChange(change, value)

    def start_title_editing(self):
        """Open seamless inline title editor directly over header bar."""
        scene_pos = self.mapToScene(QPointF(32, 4))
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
        edit.resize(int(self.width - 100), int(self.HEADER_HEIGHT - 8))
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
        if bool(self.payload.get("collapsed", False)):
            return False
        return (pos.x() >= self.width - self.HANDLE_SIZE) and (pos.y() >= self.height - self.HANDLE_SIZE)

    def hoverMoveEvent(self, event):
        if not self.payload.get("locked", False) and self._is_in_resize_handle(event.pos()):
            self.setCursor(Qt.SizeFDiagCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 1. Left chevron hit test toggle
            if event.pos().x() <= self.CHEVRON_HIT_WIDTH and event.pos().y() <= self.HEADER_HEIGHT:
                self.toggle_collapsed()
                event.accept()
                return

            # 2. Resizer handle press
            if not self.payload.get("locked", False) and self._is_in_resize_handle(event.pos()):
                self._is_resizing = True
                self._resize_start_pos = event.pos()
                self._resize_start_size = (self.width, self.height)
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_resizing and not self.payload.get("locked", False) and not bool(self.payload.get("collapsed", False)):
            delta = event.pos() - self._resize_start_pos
            min_w, min_h = self.definition.minimum_size if self.definition else (MIN_FRAME_WIDTH, MIN_FRAME_HEIGHT)
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
            # Double-click header opens inline title editor (deferred camera focus per directive)
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

        is_collapsed = bool(self.payload.get("collapsed", False))
        is_locked = bool(self.payload.get("locked", False))

        surface_bg.setAlpha(15 if is_collapsed else 30)  # Darker surface when collapsed

        # Miro-Style Drag Hover Glow Highlight
        if self._is_drag_hovered:
            glow_bg = QColor(accent)
            glow_bg.setAlpha(25)
            painter.setBrush(QBrush(glow_bg))
            glow_pen = QPen(accent)
            glow_pen.setWidth(3)
            glow_pen.setStyle(Qt.DashLine)
            painter.setPen(glow_pen)
            painter.drawRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)

        # 1. Fill Frame Background Surface
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

        # 3. Horizontal Header Divider Line (only if expanded)
        if not is_collapsed:
            divider_pen = QPen(QColor(colors["border"]))
            divider_pen.setWidth(1)
            painter.setPen(divider_pen)
            painter.drawLine(0, int(self.HEADER_HEIGHT), int(self.width), int(self.HEADER_HEIGHT))

        # 4. Top Accent Strip & Chevron + Header Title Text
        accent_pen = QPen(accent)
        accent_pen.setWidth(3)
        painter.setPen(accent_pen)
        painter.drawLine(4, 4, 4, int(self.HEADER_HEIGHT - 4))

        chevron_str = "▶ " if is_collapsed else "▼ "
        title_text = str(self.payload.get("title", "Section Frame"))
        icon_str = self.definition.icon if self.definition else "🖼️"
        lock_suffix = " 🔒" if is_locked else ""
        header_text = f"{chevron_str}{icon_str}  {title_text}{lock_suffix}"

        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        painter.setPen(QPen(QColor(colors["badge_text"])))
        text_rect = QRectF(14, 0, self.width - 100, self.HEADER_HEIGHT)
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, header_text)

        # Right Pill Badge showing attached child count
        attached_count = len(self.attached_nodes())
        badge_str = f"{attached_count} Nodes"
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.setPen(QPen(QColor(colors["badge_text"]).lighter(120)))
        badge_rect = QRectF(self.width - 95, 0, 85, self.HEADER_HEIGHT)
        painter.drawText(badge_rect, Qt.AlignRight | Qt.AlignVCenter, badge_str)

        # 5. Bottom-Right Interactive Resize Handle (◢) (only if not locked and expanded)
        if not is_locked and not is_collapsed:
            handle_pen = QPen(accent)
            handle_pen.setWidth(2)
            painter.setPen(handle_pen)
            w, h = int(self.width), int(self.height)
            painter.drawLine(w - 12, h - 4, w - 4, h - 12)
            painter.drawLine(w - 8, h - 4, w - 4, h - 8)

        # 6. Membership Selection Visualization (Soft Glow Outline around Member Nodes when expanded)
        if self.isSelected() and not is_collapsed:
            glow_pen = QPen(accent)
            glow_pen.setWidth(2)
            painter.setPen(glow_pen)
            glow_brush = QBrush(QColor(accent))
            glow_brush.setColor(QColor(accent.red(), accent.green(), accent.blue(), 20))
            painter.setBrush(glow_brush)

            for member in self.attached_nodes():
                if hasattr(member, "isVisible") and member.isVisible():
                    member_scene_rect = member.sceneBoundingRect()
                    member_local_rect = self.mapRectFromScene(member_scene_rect)
                    painter.drawRoundedRect(member_local_rect.adjusted(-6, -6, 6, 6), 8, 8)

        # 7. Selection Outline for Frame itself
        self.draw_selection_outline(painter, rect, self.CORNER_RADIUS)

    def on_context_menu(self, menu: QMenu):
        """Build context menu for Frame node."""
        is_locked = bool(self.payload.get("locked", False))
        is_collapsed = bool(self.payload.get("collapsed", False))

        # Focus / Zoom Frame
        action_focus = QAction("🔍 Focus Frame", menu)
        scene_views = self.scene().views() if (self.scene() and self.scene().views()) else []
        if scene_views and hasattr(scene_views[0], "focus_node"):
            action_focus.triggered.connect(lambda: scene_views[0].focus_node(self))
            menu.addAction(action_focus)

        # Collapse / Expand Action
        col_label = "↕️ Expand Frame" if is_collapsed else "↔️ Collapse Frame"
        action_collapse = QAction(col_label, menu)
        action_collapse.triggered.connect(self.toggle_collapsed)
        menu.addAction(action_collapse)

        menu.addSeparator()

        action_rename = QAction("✏️ Rename Frame...", menu)
        action_rename.triggered.connect(lambda: self.start_title_editing())
        menu.addAction(action_rename)

        # Lock / Unlock Action
        lock_label = "🔓 Unlock Frame" if is_locked else "🔒 Lock Frame"
        action_lock = QAction(lock_label, menu)
        action_lock.triggered.connect(self.toggle_locked)
        menu.addAction(action_lock)

        # Fit to Contents
        action_fit = QAction("📐 Fit to Contents", menu)
        action_fit.triggered.connect(self.fit_to_contents)
        menu.addAction(action_fit)

        menu.addSeparator()

        # Color Theme Submenu
        color_menu = menu.addMenu("🎨 Change Theme")
        for theme_key in ("gray", "blue", "green", "yellow", "red", "purple"):
            theme_title = theme_key.capitalize()
            theme_act = QAction(f"● {theme_title}", color_menu)
            theme_act.triggered.connect(lambda checked=False, t=theme_key: self.set_color_theme(t))
            color_menu.addAction(theme_act)

        menu.addSeparator()

        # Children Operations
        action_select_children = QAction("🎯 Select All Children", menu)
        action_select_children.triggered.connect(self.select_all_children)
        menu.addAction(action_select_children)

        action_detach_children = QAction("❌ Detach All Children", menu)
        action_detach_children.triggered.connect(self.detach_all)
        menu.addAction(action_detach_children)

