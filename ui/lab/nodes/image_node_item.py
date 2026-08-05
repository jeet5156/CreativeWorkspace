import os
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget, QFileDialog
from PySide6.QtCore import Qt, QRectF, QUrl, QSize
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QPixmap, QDesktopServices, QImageReader

from enum import Enum, auto

from ui.lab.nodes.node_item import NodeItem
from ui.lab.nodes.node_definition import NodeDefinition
from ui.lab.nodes.node_capability import NodeCapability

DEBUG_LOGGING = False


def log_debug(msg: str):
    if DEBUG_LOGGING:
        print(msg)


class ImageNodeState(Enum):
    EMPTY = auto()
    LOADING = auto()
    READY = auto()
    MISSING = auto()
    ERROR = auto()


class ImageNodeItem(NodeItem):
    """Reference Image spatial node item for the Lab canvas.

    Renders visual reference cards with thumbnail caching via ThumbnailService,
    artist title/caption annotations, aspect-ratio preserving resizing, and fit/fill modes.
    """

    CORNER_RADIUS = 8.0

    def __init__(self, definition: NodeDefinition, parent=None):
        super().__init__(definition, parent=parent)

        self.state = ImageNodeState.EMPTY
        self._pixmap = None
        self._thumb_service = None
        self._project_location = None

        # Ensure layout dict in payload schema
        if "layout" not in self.payload or not isinstance(self.payload["layout"], dict):
            self.payload["layout"] = {
                "aspect_ratio": 1.33,
                "width": float(self.width),
                "height": float(self.height),
            }

    @property
    def thumb_service(self):
        return self._thumb_service or (self.node_context.thumbnail_service if hasattr(self, "node_context") and self.node_context else None)

    @property
    def project_location(self):
        return self._project_location or (self.node_context.project_location if hasattr(self, "node_context") and self.node_context else None)

    def set_node_context(self, context):
        super().set_node_context(context)
        if self.thumb_service and not getattr(self, "_connected_thumb_signal", False):
            try:
                self.thumb_service.thumbnail_ready.connect(self._on_thumbnail_ready)
                self._connected_thumb_signal = True
            except Exception:
                pass
        self._request_thumbnail()

    def set_context_services(self, thumbnail_service=None, project_location: str = None):
        self._thumb_service = thumbnail_service
        self._project_location = project_location
        if self.node_context:
            if thumbnail_service:
                self.node_context.thumbnail_service = thumbnail_service
            if project_location:
                self.node_context.project_location = project_location
        if self.thumb_service and not getattr(self, "_connected_thumb_signal", False):
            try:
                self.thumb_service.thumbnail_ready.connect(self._on_thumbnail_ready)
                self._connected_thumb_signal = True
            except Exception:
                pass
        self._request_thumbnail()

    def from_dict(self, data: dict):
        super().from_dict(data)
        if self.payload.get("image_path"):
            self._request_thumbnail()
        else:
            self.state = ImageNodeState.EMPTY
            self._pixmap = None

    def set_image(self, image_path: str, project_location: str = None):
        """Programmatic API to set or replace image. Computes relative path and aspect ratio."""
        self._log_state(f"BEFORE set_image({image_path})")
        log_debug(f"[SET_IMAGE] self.id={self.id}, old_path={self.payload.get('image_path')}, new_path={image_path}")
        if project_location:
            self._project_location = project_location
            if self.node_context:
                self.node_context.project_location = project_location

        if not image_path:
            self.payload["image_path"] = ""
            self.payload["filename"] = ""
            self.state = ImageNodeState.EMPTY
            self._pixmap = None
            self._emit_modified()
            self.update()
            self._log_state("AFTER set_image(empty)")
            return

        abs_path = Path(image_path).resolve()
        if not abs_path.exists():
            self.payload["image_path"] = str(image_path)
            self.payload["filename"] = abs_path.name
            self.state = ImageNodeState.MISSING
            self._pixmap = None
            self._emit_modified()
            self.update()
            self._log_state("AFTER set_image(missing)")
            return

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

        self.payload["image_path"] = rel_path
        self.payload["filename"] = abs_path.name
        self.state = ImageNodeState.LOADING

        # Calculate image dimensions and aspect ratio via QImageReader header
        reader = QImageReader(str(abs_path))
        img_size = reader.size()
        if img_size.isValid() and img_size.height() > 0:
            w, h = img_size.width(), img_size.height()
            aspect = float(w) / float(h)
            self.payload["layout"] = {
                "aspect_ratio": round(aspect, 3),
                "width": round(self.width, 2),
                "height": round(self.height, 2),
                "raw_width": w,
                "raw_height": h,
            }
            # Adjust node height based on aspect ratio
            if aspect > 0:
                self.height = round(self.width / aspect, 2)
                self.payload["layout"]["height"] = float(self.height)

        self._request_thumbnail()
        self._emit_modified()
        self.update()
        self._log_state(f"AFTER set_image({image_path})")

    def prompt_choose_image(self, parent_widget=None):
        """Open file dialog to choose or replace an image file."""
        file_path, _ = QFileDialog.getOpenFileName(
            parent_widget,
            "Select Reference Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*)"
        )
        if file_path:
            self.set_image(file_path)

    def _resolve_abs_path(self) -> Path:
        rel_or_abs = self.payload.get("image_path")
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

    def _request_thumbnail(self):
        abs_path = self._resolve_abs_path()
        if not abs_path or not abs_path.exists():
            if self.payload.get("image_path"):
                self.state = ImageNodeState.MISSING
            else:
                self.state = ImageNodeState.EMPTY
            self._pixmap = None
            self.update()
            return

        rel_path = self.payload.get("image_path") or str(abs_path)
        proj_loc = self.project_location or str(abs_path.parent)
        target_size = QSize(int(self.width), int(self.height))

        svc = self.thumb_service
        if svc:
            if not getattr(self, "_connected_thumb_signal", False):
                try:
                    svc.thumbnail_ready.connect(self._on_thumbnail_ready)
                    self._connected_thumb_signal = True
                except Exception:
                    pass

            cached = svc.get_cached(proj_loc, rel_path, str(abs_path))
            if cached == "FAILED":
                self.state = ImageNodeState.ERROR
                self._pixmap = None
                self.update()
                return
            if cached:
                pix = svc.get_cached_pixmap(cached)
                if pix and not pix.isNull():
                    self._pixmap = pix
                    self.state = ImageNodeState.READY
                    self.update()
                    return
            # Request async generation
            self.state = ImageNodeState.LOADING
            log_debug(f"[IMGNODE_REQ] self.id={self.id}, image_path={rel_path}")
            log_debug(f"[THUMB] generate_async requested: asset_id={self.id}, src={abs_path}")
            svc.generate_async(proj_loc, rel_path, str(abs_path), target_size, self.id)
        else:
            # Fallback direct image load if ThumbnailService context service is unavailable
            pix = QPixmap(str(abs_path))
            if not pix.isNull():
                self._pixmap = pix
                self.state = ImageNodeState.READY
            else:
                self.state = ImageNodeState.ERROR
                self._pixmap = None
            self.update()

    def _on_thumbnail_ready(self, asset_id: str, thumb_path: str):
        match = asset_id == self.id
        log_debug(f"[CALLBACK_PATH] self.id={self.id}, asset_id={asset_id}, match={match}, image_path={self.payload.get('image_path')}, id(_pixmap)={id(self._pixmap)}")
        if not asset_id or not match:
            log_debug(f"[CALLBACK_PATH] REJECTED callback: self.id={self.id} != asset_id={asset_id}")
            return  # Strictly ignore None or mismatched asset IDs

        svc = self.thumb_service
        pix = svc.get_cached_pixmap(thumb_path) if svc else QPixmap(thumb_path)
        is_null = pix.isNull() if hasattr(pix, "isNull") else True

        if pix and not is_null:
            log_debug(f"[PIXMAP_ASSIGNED] self.id={self.id}, image_path={self.payload.get('image_path')}, old_pixmap_id={id(self._pixmap)}, new_pixmap_id={id(pix)}")
            self._pixmap = pix
            self.state = ImageNodeState.READY
        else:
            self._pixmap = None
            self.state = ImageNodeState.ERROR

        self.update()

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
        badge_bg = QColor(defn.badge_bg) if defn else QColor("#13374A")
        badge_text_color = QColor(defn.badge_text) if defn else QColor("#38BDF8")

        badge_rect = QRectF(0, 0, self.width, 28)
        painter.setBrush(QBrush(badge_bg))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(badge_rect, self.CORNER_RADIUS, self.CORNER_RADIUS)
        painter.drawRect(QRectF(0, 14, self.width, 14))

        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.setPen(QPen(badge_text_color))
        header_text = f"{defn.icon}  Reference" if defn else "🖼 Reference"
        painter.drawText(badge_rect, Qt.AlignCenter, header_text)

        # Content Area below header (y=34 to height-10)
        content_rect = QRectF(10, 34, self.width - 20, self.height - 44)

        # STATE-BASED RENDERING
        if self.state == ImageNodeState.EMPTY:
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            painter.setPen(QPen(QColor("#64748B")))
            painter.drawText(content_rect, Qt.AlignCenter, "🖼\nDouble Click\nto Choose Image")

        elif self.state == ImageNodeState.MISSING:
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            painter.setPen(QPen(QColor("#EF4444")))
            filename = self.payload.get("filename") or "Image"
            painter.drawText(content_rect, Qt.AlignCenter, f"⚠️\nImage Missing\n{filename}")

        elif self.state == ImageNodeState.LOADING:
            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(QPen(QColor("#94A3B8")))
            painter.drawText(content_rect, Qt.AlignCenter, "⏳\nLoading Preview...")

        elif self.state == ImageNodeState.ERROR:
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            painter.setPen(QPen(QColor("#EF4444")))
            painter.drawText(content_rect, Qt.AlignCenter, "❌\nFailed to Load")

        elif self.state == ImageNodeState.READY and self._pixmap:
            preview_rect = QRectF(content_rect)
            title = self.payload.get("title", "")
            caption = self.payload.get("caption", "")

            if title or caption:
                annotation_h = 32.0
                preview_rect.setHeight(max(20.0, content_rect.height() - annotation_h))
                text_rect = QRectF(content_rect.left(), preview_rect.bottom() + 4, content_rect.width(), annotation_h - 4)

                painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
                painter.setPen(QPen(QColor("#F1F5F9")))
                disp_text = title if title else caption
                painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, disp_text)

            fit_mode = self.payload.get("fit_mode", "fit")
            mode = Qt.KeepAspectRatioByExpanding if fit_mode == "fill" else Qt.KeepAspectRatio

            if isinstance(self._pixmap, QPixmap):
                scaled_pix = self._pixmap.scaled(QSize(int(preview_rect.width()), int(preview_rect.height())), mode, Qt.SmoothTransformation)
                px_w, px_h = scaled_pix.width(), scaled_pix.height()
                px_x = preview_rect.left() + (preview_rect.width() - px_w) / 2.0
                px_y = preview_rect.top() + (preview_rect.height() - px_h) / 2.0
                target_rect = QRectF(px_x, px_y, px_w, px_h).intersected(preview_rect)
                painter.drawPixmap(target_rect.toRect(), scaled_pix)
            elif isinstance(self._pixmap, QImage):
                scaled_img = self._pixmap.scaled(QSize(int(preview_rect.width()), int(preview_rect.height())), mode, Qt.SmoothTransformation)
                px_w, px_h = scaled_img.width(), scaled_img.height()
                px_x = preview_rect.left() + (preview_rect.width() - px_w) / 2.0
                px_y = preview_rect.top() + (preview_rect.height() - px_h) / 2.0
                target_rect = QRectF(px_x, px_y, px_w, px_h).intersected(preview_rect)
                painter.drawImage(target_rect.toRect(), scaled_img)

        # 5. Draw Selection Ring
        self.draw_selection_outline(painter, rect, self.CORNER_RADIUS)

    def mouseDoubleClickEvent(self, event):
        self.on_double_clicked(event)
        if event.button() == Qt.LeftButton:
            self.prompt_choose_image()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def on_context_menu(self, menu):
        """Build artist-friendly context menu for Reference Image nodes."""
        from PySide6.QtGui import QAction, QGuiApplication

        abs_path = self._resolve_abs_path()

        if abs_path and abs_path.exists():
            action_open = QAction("🖼 Open Original Image", menu)
            action_open.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(abs_path))))
            menu.addAction(action_open)

            action_reveal = QAction("📍 Reveal in Explorer", menu)
            action_reveal.triggered.connect(lambda: self._reveal_in_explorer(abs_path))
            menu.addAction(action_reveal)

            rel_path = self.payload.get("image_path", "")
            action_copy = QAction("📋 Copy Relative Path", menu)
            action_copy.triggered.connect(lambda: QGuiApplication.clipboard().setText(rel_path))
            menu.addAction(action_copy)

            menu.addSeparator()

        action_replace = QAction("🔄 Replace Image...", menu)
        action_replace.triggered.connect(lambda: self.prompt_choose_image())
        menu.addAction(action_replace)

        if self.payload.get("image_path"):
            action_clear = QAction("❌ Clear Image", menu)
            action_clear.triggered.connect(lambda: self.set_image(""))
            menu.addAction(action_clear)

        menu.addSeparator()

        current_fit = self.payload.get("fit_mode", "fit")
        fit_label = "Fit Mode: Fill (Crop)" if current_fit == "fit" else "Fit Mode: Fit (Entire)"
        action_fit = QAction(f"📐 {fit_label}", menu)
        action_fit.triggered.connect(self._toggle_fit_mode)
        menu.addAction(action_fit)

    def _toggle_fit_mode(self):
        curr = self.payload.get("fit_mode", "fit")
        self.payload["fit_mode"] = "fill" if curr == "fit" else "fit"
        self._emit_modified()
        self.update()

    def _reveal_in_explorer(self, abs_path: Path):
        try:
            if os.name == 'nt':
                os.system(f'explorer /select,"{abs_path}"')
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(abs_path.parent)))
        except Exception:
            pass
