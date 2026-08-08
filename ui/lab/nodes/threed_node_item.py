import os
import time
from pathlib import Path
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget, QFileDialog
from PySide6.QtCore import Qt, QRectF, QUrl, QSize
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QDesktopServices

from enum import Enum, auto
from ui.lab.nodes.node_item import NodeItem
from ui.lab.nodes.node_definition import NodeDefinition


class ThreeDNodeState(Enum):
    EMPTY = auto()
    READY = auto()
    MISSING = auto()
    ERROR = auto()


class ThreeDNodeItem(NodeItem):
    """3D Asset Reference spatial node item for the Lab canvas.

    Renders lightweight document cards displaying 3D asset filename, format indicator,
    cached file size, missing file detection, and locate/relink capabilities.
    Double-clicking performs safe validation without spawning external applications.
    """

    CORNER_RADIUS = 8.0
    VALIDATION_COOLDOWN_SECONDS = 1.5

    FORMAT_LABELS = {
        ".fbx": "FBX 3D Model",
        ".obj": "Wavefront OBJ Model",
        ".glb": "glTF Binary Asset",
        ".gltf": "glTF JSON Asset",
        ".blend": "Blender Project File",
        ".abc": "Alembic Geometry Cache",
        ".usd": "Universal Scene Description",
        ".usda": "USD ASCII Scene",
        ".usdc": "USD Crate Binary",
        ".usdz": "USD Zip Package",
        ".ztl": "ZBrush Tool File",
        ".ma": "Maya ASCII Scene",
        ".mb": "Maya Binary Scene",
        ".max": "3ds Max Scene File",
    }

    def __init__(self, definition: NodeDefinition, parent=None):
        super().__init__(definition, parent=parent)

        self.state = ThreeDNodeState.EMPTY
        self._project_location = None
        self._last_validated_time = 0.0

        # Ensure payload schema defaults
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
        if self.payload.get("asset_path") or self.payload.get("absolute_path") or self.payload.get("image_path"):
            self.validate_reference(force=True)
        else:
            self.state = ThreeDNodeState.EMPTY

    def _format_size_bytes(self, size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def set_asset(self, asset_path: str, project_location: str = None):
        """Programmatic API to set or replace 3D Asset reference."""
        self._last_validated_time = 0.0

        if project_location:
            self._project_location = project_location
            if self.node_context:
                self.node_context.project_location = project_location

        if not asset_path:
            self.payload["asset_path"] = ""
            self.payload["image_path"] = ""
            self.payload["absolute_path"] = ""
            self.payload["filename"] = ""
            self.payload["file_name"] = ""
            self.payload["extension"] = ""
            self.payload["format_label"] = ""
            self.payload["file_size_str"] = ""
            self.state = ThreeDNodeState.EMPTY
            self._emit_modified()
            self.update()
            return

        abs_path = Path(asset_path).resolve()
        ext = abs_path.suffix.lower()
        format_lbl = self.FORMAT_LABELS.get(ext, "3D Model Asset")

        self.payload["absolute_path"] = str(abs_path)
        self.payload["filename"] = abs_path.name
        self.payload["file_name"] = abs_path.name
        self.payload["extension"] = ext
        self.payload["format_label"] = format_lbl

        if not abs_path.exists():
            self.payload["asset_path"] = str(asset_path)
            self.payload["image_path"] = str(asset_path)
            self.payload["file_size_str"] = ""
            self.state = ThreeDNodeState.MISSING
            self._emit_modified()
            self.update()
            return

        # Cache file size string
        try:
            sz = abs_path.stat().st_size
            self.payload["file_size_str"] = self._format_size_bytes(sz)
        except Exception:
            self.payload["file_size_str"] = ""

        # Relative path resolution against project root if applicable
        rel_path = str(abs_path)
        proj_loc = self.project_location
        if proj_loc:
            try:
                proj_root = Path(proj_loc).resolve()
                if proj_root in abs_path.parents or proj_root == abs_path:
                    rel_path = str(abs_path.relative_to(proj_root)).replace("\\", "/")
            except Exception:
                pass

        self.payload["asset_path"] = rel_path
        self.payload["image_path"] = rel_path
        self.state = ThreeDNodeState.READY
        self._emit_modified()
        self.update()

    # Compatibility aliases
    set_pdf = set_asset
    set_image = set_asset
    set_file = set_asset

    def prompt_choose_asset(self, parent_widget=None):
        """Open file dialog to choose, locate, or replace a 3D asset file."""
        filter_str = "3D Asset Files (*.fbx *.obj *.glb *.gltf *.blend *.abc *.usd *.usda *.usdc *.usdz *.ztl *.ma *.mb *.max);;All Files (*)"
        file_path, _ = QFileDialog.getOpenFileName(
            parent_widget,
            "Select 3D Asset Reference",
            "",
            filter_str
        )
        if file_path:
            self.set_asset(file_path)

    prompt_choose_pdf = prompt_choose_asset
    prompt_choose_image = prompt_choose_asset

    def _resolve_abs_path(self) -> Path:
        abs_val = self.payload.get("absolute_path")
        if abs_val:
            p_abs = Path(abs_val)
            if p_abs.exists():
                return p_abs

        rel_or_abs = self.payload.get("asset_path") or self.payload.get("image_path")
        if not rel_or_abs:
            return None

        path = Path(rel_or_abs)
        if path.is_absolute() and path.exists():
            return path

        proj_loc = self.project_location
        if proj_loc:
            proj_abs = Path(proj_loc) / rel_or_abs
            if proj_abs.exists():
                return proj_abs

        if path.exists():
            return path.resolve()

        return None

    def validate_reference(self, force: bool = False) -> bool:
        """Event-driven lazy validation of 3D reference file existence with per-node cooldown throttling."""
        now = time.time()
        if not force and (now - self._last_validated_time) < self.VALIDATION_COOLDOWN_SECONDS:
            return self.state != ThreeDNodeState.MISSING

        self._last_validated_time = now

        asset_path = self.payload.get("asset_path") or self.payload.get("absolute_path") or self.payload.get("image_path")
        if not asset_path:
            if self.state != ThreeDNodeState.EMPTY:
                self.state = ThreeDNodeState.EMPTY
                self.update()
            return False

        abs_path = self._resolve_abs_path()
        exists = abs_path is not None and abs_path.exists() and abs_path.is_file()

        if not exists:
            if self.state != ThreeDNodeState.MISSING:
                self.state = ThreeDNodeState.MISSING
                self.update()
            return False

        # File exists on disk
        if self.state in (ThreeDNodeState.MISSING, ThreeDNodeState.ERROR, ThreeDNodeState.EMPTY):
            # Recovery: File was previously missing/error/empty, now available again!
            try:
                sz = abs_path.stat().st_size
                self.payload["file_size_str"] = self._format_size_bytes(sz)
            except Exception:
                pass
            self.state = ThreeDNodeState.READY
            self.update()

        return True

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        # 1. Fill Card Background
        bg_color = QColor(self.definition.background_color) if self.definition else QColor("#1E2029")
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)

        # 2. Draw Subtle Inner Border
        border_pen = QPen(QColor("#343847"))
        border_pen.setWidth(1)
        painter.setPen(border_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), self.CORNER_RADIUS, self.CORNER_RADIUS)

        # 3. Draw Header Badge Bar (y=0 to 28)
        defn = self.definition
        badge_bg = QColor(defn.badge_bg) if defn else QColor("#13382C")
        badge_text_color = QColor(defn.badge_text) if defn else QColor("#34D399")

        badge_rect = QRectF(0, 0, self.width, 28)
        painter.setBrush(QBrush(badge_bg))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(badge_rect, self.CORNER_RADIUS, self.CORNER_RADIUS)
        painter.drawRect(QRectF(0, 14, self.width, 14))

        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.setPen(QPen(badge_text_color))

        fname = self.payload.get("filename") or self.payload.get("file_name")
        icon = defn.icon if defn else "🧊"
        header_text = f"{icon}  {fname}" if fname else f"{icon}  3D Asset Reference"
        painter.drawText(badge_rect, Qt.AlignCenter, header_text)

        # Content Area below header (y=34 to height-10)
        content_rect = QRectF(10, 34, self.width - 20, self.height - 44)

        # STATE-BASED RENDERING
        if self.state == ThreeDNodeState.EMPTY:
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            painter.setPen(QPen(QColor("#64748B")))
            painter.drawText(content_rect, Qt.AlignCenter, "🧊\nDouble Click\nto Choose 3D Asset")

        elif self.state == ThreeDNodeState.MISSING:
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.setPen(QPen(QColor("#EF4444")))
            filename = self.payload.get("filename") or self.payload.get("file_name") or "3D Asset"
            painter.drawText(content_rect, Qt.AlignCenter, f"⚠️ Missing 3D Asset\n\n{filename}\nFile no longer exists\n\n[ Locate File ]")

        elif self.state == ThreeDNodeState.ERROR:
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            painter.setPen(QPen(QColor("#EF4444")))
            painter.drawText(content_rect, Qt.AlignCenter, "❌\nFailed to Load Asset")

        elif self.state == ThreeDNodeState.READY:
            # Center Area: 3D Asset Vector Card Badge
            icon_box = QRectF(content_rect.left(), content_rect.top() + 10, content_rect.width(), content_rect.height() - 40)

            # Draw 3D asset document icon frame
            doc_rect = QRectF(content_rect.left() + (content_rect.width() - 80) / 2.0, icon_box.top() + 8, 80, 95)
            painter.setBrush(QBrush(QColor("#182C25")))
            painter.setPen(QPen(QColor("#10B981"), 2))
            painter.drawRoundedRect(doc_rect, 6.0, 6.0)

            # Draw "3D" label inside document frame
            painter.setFont(QFont("Segoe UI", 18, QFont.Bold))
            painter.setPen(QPen(QColor("#34D399")))
            painter.drawText(doc_rect, Qt.AlignCenter, "3D")

            # Footer Metadata (EXT • X MB)
            ext_upper = (self.payload.get("extension") or "").replace(".", "").upper() or "3D"
            size_str = self.payload.get("file_size_str", "")
            footer_meta = f"{ext_upper} • {size_str}" if size_str else ext_upper

            title = self.payload.get("title", "")
            caption = self.payload.get("caption", "")

            text_rect = QRectF(content_rect.left(), content_rect.bottom() - 24, content_rect.width(), 24)
            painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
            painter.setPen(QPen(QColor("#94A3B8")))
            disp_text = title if title else (caption if caption else footer_meta)
            painter.drawText(text_rect, Qt.AlignCenter, disp_text)

        # 5. Draw Selection Ring
        self.draw_selection_outline(painter, rect, self.CORNER_RADIUS)

    def on_selected(self):
        super().on_selected()
        self.validate_reference()

    def hoverEnterEvent(self, event):
        self.validate_reference()
        super().hoverEnterEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Perform lazy validation on double click. DO NOT launch external 3D applications!"""
        self.on_double_clicked(event)
        if event.button() == Qt.LeftButton:
            valid = self.validate_reference(force=True)
            if not valid:
                self.prompt_choose_asset()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def on_context_menu(self, menu):
        """Build artist-friendly context menu for 3D Asset Reference nodes."""
        super().on_context_menu(menu)
        from PySide6.QtGui import QAction, QGuiApplication

        abs_path = self._resolve_abs_path()

        if abs_path and abs_path.exists():
            action_reveal = QAction("📍 Reveal in Explorer", menu)
            action_reveal.triggered.connect(lambda: self._reveal_in_explorer(abs_path))
            menu.addAction(action_reveal)

            rel_path = self.payload.get("asset_path") or self.payload.get("image_path", "")
            action_copy = QAction("📋 Copy Path", menu)
            action_copy.triggered.connect(lambda: QGuiApplication.clipboard().setText(rel_path or str(abs_path)))
            menu.addAction(action_copy)

            menu.addSeparator()

        action_relink = QAction("📍 Locate / Relink 3D Asset...", menu)
        action_relink.triggered.connect(lambda: self.prompt_choose_asset())
        menu.addAction(action_relink)

        action_replace = QAction("🔄 Replace 3D Asset...", menu)
        action_replace.triggered.connect(lambda: self.prompt_choose_asset())
        menu.addAction(action_replace)

        if self.payload.get("asset_path") or self.payload.get("absolute_path") or self.payload.get("image_path"):
            action_clear = QAction("❌ Clear 3D Asset", menu)
            action_clear.triggered.connect(lambda: self.set_asset(""))
            menu.addAction(action_clear)

    def _reveal_in_explorer(self, abs_path: Path):
        try:
            if os.name == 'nt':
                os.system(f'explorer /select,"{abs_path}"')
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(abs_path.parent)))
        except Exception:
            pass
