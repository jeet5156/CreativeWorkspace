import os
import time
from pathlib import Path
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget, QFileDialog
from PySide6.QtCore import Qt, QRectF, QUrl, QSize
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QDesktopServices

from enum import Enum, auto
from ui.lab.nodes.node_item import NodeItem
from ui.lab.nodes.node_definition import NodeDefinition


class FolderNodeState(Enum):
    EMPTY = auto()
    READY = auto()
    MISSING = auto()
    ERROR = auto()


class FolderNodeItem(NodeItem):
    """Folder Reference spatial node item for the Lab canvas.

    Renders lightweight document cards displaying directory references without copying,
    monitoring, scanning, or enumerating folder contents.
    Double-clicking performs safe validation without spawning external applications.
    """

    CORNER_RADIUS = 8.0
    VALIDATION_COOLDOWN_SECONDS = 1.5

    def __init__(self, definition: NodeDefinition, parent=None):
        super().__init__(definition, parent=parent)

        self.state = FolderNodeState.EMPTY
        self._project_location = None
        self._last_validated_time = 0.0

        if "layout" not in self.payload or not isinstance(self.payload["layout"], dict):
            self.payload["layout"] = {
                "aspect_ratio": 1.23,
                "width": float(self.width),
                "height": float(self.height),
            }
        if "display_mode" not in self.payload:
            self.payload["display_mode"] = "icon"

    @property
    def project_location(self):
        return self._project_location or (self.node_context.project_location if hasattr(self, "node_context") and self.node_context else None)

    def set_context_services(self, thumbnail_service=None, project_location: str = None):
        self._project_location = project_location
        if self.node_context and project_location:
            self.node_context.project_location = project_location
        self.validate_reference(force=True)

    def set_node_context(self, context):
        super().set_node_context(context)
        self.validate_reference(force=True)

    def from_dict(self, data: dict):
        super().from_dict(data)
        if "display_mode" not in self.payload:
            self.payload["display_mode"] = "icon"
        if self.payload.get("folder_path") or self.payload.get("absolute_path") or self.payload.get("image_path"):
            self.validate_reference(force=True)
        else:
            self.state = FolderNodeState.EMPTY

    def set_folder(self, folder_path: str, project_location: str = None):
        """Programmatic API to set or replace Folder reference."""
        self._last_validated_time = 0.0

        if project_location:
            self._project_location = project_location
            if self.node_context:
                self.node_context.project_location = project_location

        if not folder_path:
            self.payload["folder_path"] = ""
            self.payload["image_path"] = ""
            self.payload["absolute_path"] = ""
            self.payload["foldername"] = ""
            self.payload["filename"] = ""
            self.payload["file_name"] = ""
            self.state = FolderNodeState.EMPTY
            self._emit_modified()
            self.update()
            return

        abs_path = Path(folder_path).resolve()
        folder_name = abs_path.name or str(abs_path)

        self.payload["absolute_path"] = str(abs_path)
        self.payload["foldername"] = folder_name
        self.payload["filename"] = folder_name
        self.payload["file_name"] = folder_name

        if not abs_path.exists() or not abs_path.is_dir():
            self.payload["folder_path"] = str(folder_path)
            self.payload["image_path"] = str(folder_path)
            self.state = FolderNodeState.MISSING
            self._emit_modified()
            self.update()
            return

        rel_path = str(abs_path)
        proj_loc = self.project_location
        if proj_loc:
            try:
                proj_root = Path(proj_loc).resolve()
                if proj_root in abs_path.parents or proj_root == abs_path:
                    rel_path = str(abs_path.relative_to(proj_root)).replace("\\", "/")
            except Exception:
                pass

        self.payload["folder_path"] = rel_path
        self.payload["image_path"] = rel_path
        self.state = FolderNodeState.READY
        self._emit_modified()
        self.update()

    set_asset = set_folder
    set_pdf = set_folder
    set_image = set_folder
    set_file = set_folder

    def prompt_choose_folder(self, parent_widget=None):
        folder_path = QFileDialog.getExistingDirectory(
            parent_widget,
            "Select Folder Reference",
            ""
        )
        if folder_path:
            self.set_folder(folder_path)

    prompt_choose_asset = prompt_choose_folder
    prompt_choose_pdf = prompt_choose_folder
    prompt_choose_image = prompt_choose_folder
    prompt_choose_file = prompt_choose_folder

    def _resolve_abs_path(self) -> Path:
        abs_val = self.payload.get("absolute_path")
        if abs_val:
            p_abs = Path(abs_val)
            if p_abs.exists() and p_abs.is_dir():
                return p_abs

        rel_or_abs = self.payload.get("folder_path") or self.payload.get("image_path")
        if not rel_or_abs:
            return None

        path = Path(rel_or_abs)
        if path.is_absolute() and path.exists() and path.is_dir():
            return path

        proj_loc = self.project_location
        if proj_loc:
            proj_abs = Path(proj_loc) / rel_or_abs
            if proj_abs.exists() and proj_abs.is_dir():
                return proj_abs

        if path.exists() and path.is_dir():
            return path.resolve()

        return None

    def validate_reference(self, force: bool = False) -> bool:
        """Validate existence of directory without enumerating folder contents."""
        now = time.time()
        if not force and (now - self._last_validated_time) < self.VALIDATION_COOLDOWN_SECONDS:
            return self.state != FolderNodeState.MISSING

        self._last_validated_time = now

        folder_path = self.payload.get("folder_path") or self.payload.get("absolute_path") or self.payload.get("image_path")
        if not folder_path:
            if self.state != FolderNodeState.EMPTY:
                self.state = FolderNodeState.EMPTY
                self.update()
            return False

        abs_path = self._resolve_abs_path()
        exists = abs_path is not None and abs_path.exists() and abs_path.is_dir()

        if not exists:
            if self.state != FolderNodeState.MISSING:
                self.state = FolderNodeState.MISSING
                self.update()
            return False

        if self.state in (FolderNodeState.MISSING, FolderNodeState.ERROR, FolderNodeState.EMPTY):
            self.state = FolderNodeState.READY
            self.update()

        return True

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        bg_color = QColor(self.definition.background_color) if self.definition else QColor("#1E2029")
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)

        border_pen = QPen(QColor("#343847"))
        border_pen.setWidth(1)
        painter.setPen(border_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), self.CORNER_RADIUS, self.CORNER_RADIUS)

        defn = self.definition
        badge_bg = QColor(defn.badge_bg) if defn else QColor("#3B2D1B")
        badge_text_color = QColor(defn.badge_text) if defn else QColor("#FBBF24")

        badge_rect = QRectF(0, 0, self.width, 28)
        painter.setBrush(QBrush(badge_bg))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(badge_rect, self.CORNER_RADIUS, self.CORNER_RADIUS)
        painter.drawRect(QRectF(0, 14, self.width, 14))

        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.setPen(QPen(badge_text_color))

        fname = self.payload.get("foldername") or self.payload.get("filename") or self.payload.get("file_name")
        icon = defn.icon if defn else "📁"
        header_text = f"{icon}  {fname}" if fname else f"{icon}  Folder Reference"
        painter.drawText(badge_rect, Qt.AlignCenter, header_text)

        content_rect = QRectF(10, 34, self.width - 20, self.height - 44)

        if self.state == FolderNodeState.EMPTY:
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            painter.setPen(QPen(QColor("#64748B")))
            painter.drawText(content_rect, Qt.AlignCenter, "📁\nDouble Click\nto Choose Folder")

        elif self.state == FolderNodeState.MISSING:
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.setPen(QPen(QColor("#EF4444")))
            foldername = self.payload.get("foldername") or self.payload.get("filename") or "Folder"
            painter.drawText(content_rect, Qt.AlignCenter, f"⚠️ Missing Folder\n\n{foldername}\nDirectory no longer exists\n\n[ Locate Folder ]")

        elif self.state == FolderNodeState.ERROR:
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            painter.setPen(QPen(QColor("#EF4444")))
            painter.drawText(content_rect, Qt.AlignCenter, "❌\nFailed to Access Folder")

        elif self.state == FolderNodeState.READY:
            icon_box = QRectF(content_rect.left(), content_rect.top() + 10, content_rect.width(), content_rect.height() - 40)

            folder_rect = QRectF(content_rect.left() + (content_rect.width() - 80) / 2.0, icon_box.top() + 8, 80, 95)
            painter.setBrush(QBrush(QColor("#2C2215")))
            painter.setPen(QPen(QColor("#F59E0B"), 2))
            painter.drawRoundedRect(folder_rect, 6.0, 6.0)

            painter.setFont(QFont("Segoe UI", 22, QFont.Bold))
            painter.setPen(QPen(QColor("#FBBF24")))
            painter.drawText(folder_rect, Qt.AlignCenter, "📁")

            title = self.payload.get("title", "")
            caption = self.payload.get("caption", "")

            text_rect = QRectF(content_rect.left(), content_rect.bottom() - 24, content_rect.width(), 24)
            painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
            painter.setPen(QPen(QColor("#94A3B8")))
            disp_text = title if title else (caption if caption else "Folder")
            painter.drawText(text_rect, Qt.AlignCenter, disp_text)

        self.draw_selection_outline(painter, rect, self.CORNER_RADIUS)

    def on_selected(self):
        super().on_selected()
        self.validate_reference()

    def hoverEnterEvent(self, event):
        self.validate_reference()
        super().hoverEnterEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Perform lazy validation on double click. DO NOT launch external applications or explorer!"""
        self.on_double_clicked(event)
        if event.button() == Qt.LeftButton:
            valid = self.validate_reference(force=True)
            if not valid:
                self.prompt_choose_folder()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def on_context_menu(self, menu):
        super().on_context_menu(menu)
        from PySide6.QtGui import QAction, QGuiApplication

        abs_path = self._resolve_abs_path()

        if abs_path and abs_path.exists():
            action_reveal = QAction("📍 Reveal in Explorer", menu)
            action_reveal.triggered.connect(lambda: self._reveal_in_explorer(abs_path))
            menu.addAction(action_reveal)

            rel_path = self.payload.get("folder_path") or self.payload.get("image_path", "")
            action_copy = QAction("📋 Copy Path", menu)
            action_copy.triggered.connect(lambda: QGuiApplication.clipboard().setText(rel_path or str(abs_path)))
            menu.addAction(action_copy)

            menu.addSeparator()

        action_relink = QAction("📍 Locate / Relink Folder...", menu)
        action_relink.triggered.connect(lambda: self.prompt_choose_folder())
        menu.addAction(action_relink)

        action_replace = QAction("🔄 Replace Folder...", menu)
        action_replace.triggered.connect(lambda: self.prompt_choose_folder())
        menu.addAction(action_replace)

        if self.payload.get("folder_path") or self.payload.get("absolute_path") or self.payload.get("image_path"):
            action_clear = QAction("❌ Clear Folder Reference", menu)
            action_clear.triggered.connect(lambda: self.set_folder(""))
            menu.addAction(action_clear)

    def _reveal_in_explorer(self, abs_path: Path):
        try:
            if os.name == 'nt':
                os.system(f'explorer "{abs_path}"')
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(abs_path)))
        except Exception:
            pass
