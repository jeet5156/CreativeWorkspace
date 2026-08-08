import os
import time
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget, QFileDialog
from PySide6.QtCore import Qt, QRectF, QUrl, QSize
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QDesktopServices

from enum import Enum, auto
from ui.lab.nodes.node_item import NodeItem
from ui.lab.nodes.node_definition import NodeDefinition


class PdfNodeState(Enum):
    EMPTY = auto()
    READY = auto()
    MISSING = auto()
    ERROR = auto()


class PdfNodeItem(NodeItem):
    """PDF Reference spatial node item for the Lab canvas.

    Renders clean document cards displaying filename, PDF type indicator,
    page count, cached file size, missing file detection, and OS viewer opening.
    """

    CORNER_RADIUS = 8.0
    VALIDATION_COOLDOWN_SECONDS = 1.5

    def __init__(self, definition: NodeDefinition, parent=None):
        super().__init__(definition, parent=parent)

        self.state = PdfNodeState.EMPTY
        self._project_location = None
        self._last_validated_time = 0.0
        self._preview_pixmap = None
        self._cached_preview_size = None

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
        if self.payload.get("pdf_path") or self.payload.get("absolute_path") or self.payload.get("image_path"):
            self.validate_reference(force=True)
        else:
            self.state = PdfNodeState.EMPTY

    def _format_size_bytes(self, size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _detect_page_count(self, abs_path: Path) -> int:
        if not abs_path or not abs_path.exists():
            return 0

        # 1. Try PySide6.QtPdf.QPdfDocument
        try:
            from PySide6.QtPdf import QPdfDocument
            doc = QPdfDocument()
            doc.load(str(abs_path))
            cnt = doc.pageCount()
            if cnt > 0:
                return cnt
        except Exception:
            pass

        # 2. Lightweight binary parsing fallback
        try:
            with open(abs_path, 'rb') as f:
                content = f.read()
            import re
            count_matches = re.findall(rb'/Count\s+(\d+)', content)
            if count_matches:
                return int(count_matches[-1])
            page_matches = re.findall(rb'/Type\s*/Page\b', content)
            if page_matches:
                return len(page_matches)
        except Exception:
            pass

        return 0

    def _request_preview_render(self):
        """Render page 0 of referenced PDF and cache QPixmap result in memory."""
        abs_path = self._resolve_abs_path()
        if not abs_path or not abs_path.exists():
            self._preview_pixmap = None
            self._cached_preview_size = None
            return

        try:
            from PySide6.QtPdf import QPdfDocument
            from PySide6.QtGui import QPixmap
            doc = QPdfDocument()
            doc.load(str(abs_path))
            if doc.pageCount() > 0:
                content_w = max(40, int(self.width - 20))
                content_h = max(40, int(self.height - 44))
                img = doc.render(0, QSize(content_w, content_h))
                if img and not img.isNull():
                    self._preview_pixmap = QPixmap.fromImage(img)
                    self._cached_preview_size = QSize(int(self.width), int(self.height))
                    return
        except Exception:
            pass

        self._preview_pixmap = None
        self._cached_preview_size = None

    def toggle_display_mode(self):
        """Switch display mode between 'icon' and 'preview' without altering node geometry or position."""
        curr = self.payload.get("display_mode", "icon")
        new_mode = "preview" if curr == "icon" else "icon"
        self.payload["display_mode"] = new_mode

        if new_mode == "preview" and self.state == PdfNodeState.READY and self._preview_pixmap is None:
            self._request_preview_render()

        self._emit_modified()
        self.update()

    def set_pdf(self, pdf_path: str, project_location: str = None):
        """Programmatic API to set or replace PDF reference."""
        self._last_validated_time = 0.0
        self._preview_pixmap = None
        self._cached_preview_size = None

        if project_location:
            self._project_location = project_location
            if self.node_context:
                self.node_context.project_location = project_location

        if not pdf_path:
            self.payload["pdf_path"] = ""
            self.payload["image_path"] = ""
            self.payload["absolute_path"] = ""
            self.payload["filename"] = ""
            self.payload["file_name"] = ""
            self.payload["extension"] = ".pdf"
            self.payload["file_size_str"] = ""
            self.payload["page_count"] = 0
            self.state = PdfNodeState.EMPTY
            self._emit_modified()
            self.update()
            return

        abs_path = Path(pdf_path).resolve()
        self.payload["absolute_path"] = str(abs_path)
        self.payload["filename"] = abs_path.name
        self.payload["file_name"] = abs_path.name
        self.payload["extension"] = ".pdf"

        if not abs_path.exists():
            self.payload["pdf_path"] = str(pdf_path)
            self.payload["image_path"] = str(pdf_path)
            self.payload["file_size_str"] = ""
            self.payload["page_count"] = 0
            self.state = PdfNodeState.MISSING
            self._emit_modified()
            self.update()
            return

        # Cache file size string and page count
        try:
            sz = abs_path.stat().st_size
            self.payload["file_size_str"] = self._format_size_bytes(sz)
        except Exception:
            self.payload["file_size_str"] = ""

        self.payload["page_count"] = self._detect_page_count(abs_path)

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

        self.payload["pdf_path"] = rel_path
        self.payload["image_path"] = rel_path
        self.state = PdfNodeState.READY

        if self.payload.get("display_mode") == "preview":
            self._request_preview_render()

        self._emit_modified()
        self.update()

    # Aliases for compatibility
    set_image = set_pdf
    set_file = set_pdf

    def prompt_choose_pdf(self, parent_widget=None):
        """Open file dialog to choose, locate, or replace a PDF file."""
        file_path, _ = QFileDialog.getOpenFileName(
            parent_widget,
            "Select PDF Reference",
            "",
            "PDF Files (*.pdf);;All Files (*)"
        )
        if file_path:
            self.set_pdf(file_path)

    prompt_choose_image = prompt_choose_pdf

    def _resolve_abs_path(self) -> Path:
        abs_val = self.payload.get("absolute_path")
        if abs_val:
            p_abs = Path(abs_val)
            if p_abs.exists():
                return p_abs

        rel_or_abs = self.payload.get("pdf_path") or self.payload.get("image_path")
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
        """Event-driven lazy validation of PDF reference file existence with per-node cooldown throttling."""
        now = time.time()
        if not force and (now - self._last_validated_time) < self.VALIDATION_COOLDOWN_SECONDS:
            return self.state != PdfNodeState.MISSING

        self._last_validated_time = now

        pdf_path = self.payload.get("pdf_path") or self.payload.get("absolute_path") or self.payload.get("image_path")
        if not pdf_path:
            if self.state != PdfNodeState.EMPTY:
                self.state = PdfNodeState.EMPTY
                self._preview_pixmap = None
                self._cached_preview_size = None
                self.update()
            return False

        abs_path = self._resolve_abs_path()
        exists = abs_path is not None and abs_path.exists() and abs_path.is_file()

        if not exists:
            if self.state != PdfNodeState.MISSING:
                self.state = PdfNodeState.MISSING
                self._preview_pixmap = None
                self._cached_preview_size = None
                self.update()
            return False

        # File exists on disk
        if self.state in (PdfNodeState.MISSING, PdfNodeState.ERROR, PdfNodeState.EMPTY):
            # Recovery: File was previously missing/error/empty, now available again!
            try:
                sz = abs_path.stat().st_size
                self.payload["file_size_str"] = self._format_size_bytes(sz)
            except Exception:
                pass
            self.payload["page_count"] = self._detect_page_count(abs_path)
            self.state = PdfNodeState.READY

            if self.payload.get("display_mode") == "preview":
                self._request_preview_render()

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
        badge_bg = QColor(defn.badge_bg) if defn else QColor("#3F1D24")
        badge_text_color = QColor(defn.badge_text) if defn else QColor("#F87171")

        badge_rect = QRectF(0, 0, self.width, 28)
        painter.setBrush(QBrush(badge_bg))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(badge_rect, self.CORNER_RADIUS, self.CORNER_RADIUS)
        painter.drawRect(QRectF(0, 14, self.width, 14))

        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.setPen(QPen(badge_text_color))

        fname = self.payload.get("filename") or self.payload.get("file_name")
        icon = defn.icon if defn else "📄"
        header_text = f"{icon}  {fname}" if fname else f"{icon}  PDF Reference"
        painter.drawText(badge_rect.adjusted(10, 0, -50, 0), Qt.AlignLeft | Qt.AlignVCenter, header_text)

        # 4. Draw Header Toggle Button (x = width - 42, y = 4, w = 34, h = 20)
        curr_mode = self.payload.get("display_mode", "icon")
        btn_rect = QRectF(self.width - 42.0, 4.0, 34.0, 20.0)
        painter.setBrush(QBrush(QColor("#2A171D")))
        painter.setPen(QPen(QColor("#F87171"), 1.0))
        painter.drawRoundedRect(btn_rect, 4.0, 4.0)

        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.setPen(QPen(QColor("#F87171")))
        toggle_icon_str = "▤" if curr_mode == "preview" else "▣"
        painter.drawText(btn_rect, Qt.AlignCenter, toggle_icon_str)

        # Content Area below header (y=34 to height-10)
        content_rect = QRectF(10, 34, self.width - 20, self.height - 44)

        # STATE-BASED RENDERING
        if self.state == PdfNodeState.EMPTY:
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            painter.setPen(QPen(QColor("#64748B")))
            painter.drawText(content_rect, Qt.AlignCenter, "📄\nDouble Click\nto Choose PDF")

        elif self.state == PdfNodeState.MISSING:
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.setPen(QPen(QColor("#EF4444")))
            filename = self.payload.get("filename") or self.payload.get("file_name") or "PDF Document"
            painter.drawText(content_rect, Qt.AlignCenter, f"⚠️ Missing PDF\n\n{filename}\nFile no longer exists\n\n[ Locate File ]")

        elif self.state == PdfNodeState.ERROR:
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            painter.setPen(QPen(QColor("#EF4444")))
            painter.drawText(content_rect, Qt.AlignCenter, "❌\nFailed to Load PDF")

        elif self.state == PdfNodeState.READY:
            # 1. Preview Mode Rendering
            if curr_mode == "preview":
                # Check for resize invalidation
                curr_size = QSize(int(self.width), int(self.height))
                if self._cached_preview_size != curr_size:
                    self._request_preview_render()

                if self._preview_pixmap and not self._preview_pixmap.isNull():
                    preview_box = QRectF(content_rect)
                    annotation_h = 22.0
                    preview_box.setHeight(max(20.0, content_rect.height() - annotation_h))

                    # Scale pixmap preserving aspect ratio
                    mode = Qt.KeepAspectRatio
                    scaled_pix = self._preview_pixmap.scaled(QSize(int(preview_box.width()), int(preview_box.height())), mode, Qt.SmoothTransformation)
                    px_w, px_h = scaled_pix.width(), scaled_pix.height()
                    px_x = preview_box.left() + (preview_box.width() - px_w) / 2.0
                    px_y = preview_box.top() + (preview_box.height() - px_h) / 2.0
                    target_rect = QRectF(px_x, px_y, px_w, px_h).intersected(preview_box)
                    painter.drawPixmap(target_rect.toRect(), scaled_pix)

                    # Footer metadata string
                    page_cnt = self.payload.get("page_count", 0)
                    size_str = self.payload.get("file_size_str", "")
                    pages_str = f"{page_cnt} pages" if page_cnt > 0 else ""
                    meta_parts = ["PDF"]
                    if pages_str:
                        meta_parts.append(pages_str)
                    if size_str:
                        meta_parts.append(size_str)
                    footer_meta = " • ".join(meta_parts)

                    text_rect = QRectF(content_rect.left(), preview_box.bottom() + 2, content_rect.width(), annotation_h - 2)
                    painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
                    painter.setPen(QPen(QColor("#94A3B8")))
                    painter.drawText(text_rect, Qt.AlignCenter, footer_meta)
                else:
                    # Fallback Preview Unavailable Card
                    painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
                    painter.setPen(QPen(QColor("#64748B")))
                    painter.drawText(content_rect, Qt.AlignCenter, "📄\nPreview Unavailable")

            # 2. Icon Mode Rendering (Phase 2 Clean Document Card)
            else:
                icon_box = QRectF(content_rect.left(), content_rect.top() + 10, content_rect.width(), content_rect.height() - 40)
                doc_rect = QRectF(content_rect.left() + (content_rect.width() - 80) / 2.0, icon_box.top() + 8, 80, 95)
                painter.setBrush(QBrush(QColor("#252836")))
                painter.setPen(QPen(QColor("#EF4444"), 2))
                painter.drawRoundedRect(doc_rect, 6.0, 6.0)

                painter.setFont(QFont("Segoe UI", 18, QFont.Bold))
                painter.setPen(QPen(QColor("#EF4444")))
                painter.drawText(doc_rect, Qt.AlignCenter, "PDF")

                page_cnt = self.payload.get("page_count", 0)
                size_str = self.payload.get("file_size_str", "")
                pages_str = f"{page_cnt} pages" if page_cnt > 0 else ""

                meta_parts = ["PDF"]
                if pages_str:
                    meta_parts.append(pages_str)
                if size_str:
                    meta_parts.append(size_str)
                footer_meta = " • ".join(meta_parts)

                title = self.payload.get("title", "")
                caption = self.payload.get("caption", "")

                text_rect = QRectF(content_rect.left(), content_rect.bottom() - 24, content_rect.width(), 24)
                painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
                painter.setPen(QPen(QColor("#94A3B8")))
                disp_text = title if title else (caption if caption else footer_meta)
                painter.drawText(text_rect, Qt.AlignCenter, disp_text)

        # 5. Draw Selection Ring
        self.draw_selection_outline(painter, rect, self.CORNER_RADIUS)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            btn_rect = QRectF(self.width - 42.0, 4.0, 34.0, 20.0)
            if btn_rect.contains(event.pos()):
                self.toggle_display_mode()
                event.accept()
                return
        super().mousePressEvent(event)

    def on_selected(self):
        super().on_selected()
        self.validate_reference()

    def hoverEnterEvent(self, event):
        self.validate_reference()
        super().hoverEnterEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.on_double_clicked(event)
        if event.button() == Qt.LeftButton:
            valid = self.validate_reference(force=True)
            abs_path = self._resolve_abs_path()
            if valid and abs_path and abs_path.exists() and abs_path.is_file():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(abs_path)))
            else:
                self.prompt_choose_pdf()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def on_context_menu(self, menu):
        """Build context menu for PDF Reference nodes."""
        super().on_context_menu(menu)
        from PySide6.QtGui import QAction, QGuiApplication

        abs_path = self._resolve_abs_path()

        if abs_path and abs_path.exists():
            action_open = QAction("📄 Open Original PDF", menu)
            action_open.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(abs_path))))
            menu.addAction(action_open)

            action_reveal = QAction("📍 Reveal in Explorer", menu)
            action_reveal.triggered.connect(lambda: self._reveal_in_explorer(abs_path))
            menu.addAction(action_reveal)

            rel_path = self.payload.get("pdf_path") or self.payload.get("image_path", "")
            action_copy = QAction("📋 Copy Path", menu)
            action_copy.triggered.connect(lambda: QGuiApplication.clipboard().setText(rel_path or str(abs_path)))
            menu.addAction(action_copy)

            menu.addSeparator()

        curr_mode = self.payload.get("display_mode", "icon")
        mode_label = "Display Mode: Icon (Compact)" if curr_mode == "preview" else "Display Mode: Preview (First Page)"
        action_mode = QAction(f"📐 {mode_label}", menu)
        action_mode.triggered.connect(self.toggle_display_mode)
        menu.addAction(action_mode)

        action_relink = QAction("📍 Locate / Relink PDF...", menu)
        action_relink.triggered.connect(lambda: self.prompt_choose_pdf())
        menu.addAction(action_relink)

        action_replace = QAction("🔄 Replace PDF...", menu)
        action_replace.triggered.connect(lambda: self.prompt_choose_pdf())
        menu.addAction(action_replace)

        if self.payload.get("pdf_path") or self.payload.get("absolute_path") or self.payload.get("image_path"):
            action_clear = QAction("❌ Clear PDF", menu)
            action_clear.triggered.connect(lambda: self.set_pdf(""))
            menu.addAction(action_clear)

    def _reveal_in_explorer(self, abs_path: Path):
        try:
            if os.name == 'nt':
                os.system(f'explorer /select,"{abs_path}"')
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(abs_path.parent)))
        except Exception:
            pass

