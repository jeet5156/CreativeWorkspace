from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QSizePolicy,
    QApplication,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QFontMetrics
from pathlib import Path
from datetime import datetime


class AssetCard(QWidget):
    clicked = Signal(str)
    double_clicked = Signal(str)
    context_requested = Signal(str)

    ICON_MAP = {
        '.pdf': '📄',
        '.doc': '📄',
        '.docx': '📄',
        '.txt': '📄',
        '.md': '📝',
        '.csv': '📊',
        '.mp3': '🎵',
        '.wav': '🎵',
        '.flac': '🎵',
        '.mp4': '🎞️',
        '.mov': '🎞️',
        '.avi': '🎞️',
        '.mkv': '🎞️',
        '.fbx': '🧩',
        '.obj': '🧩',
        '.blend': '🧩',
        '.gltf': '🧩',
        '.glb': '🧩',
        '.usd': '🧩',
        '.usda': '🧩',
        '.usdc': '🧩',
        '.usdz': '🧩',
        '.abc': '🧩',
        '.stl': '🧩',
        '.dae': '🧩',
        '.exr': '🎬',
        '.hdr': '🎬',
        '.tga': '🖼️',
        '.tif': '🖼️',
        '.tiff': '🖼️',
        '.sbsar': '🎨',
        '.sbs': '🎨',
        '.zip': '📦',
        '.rar': '📦',
        '.7z': '📦',
    }

    def __init__(self, asset: dict, size: QSize = None, thumbnail_service=None, project_location: str = None):
        super().__init__()
        self.asset = asset
        self._selected = False
        card_size = size or QSize(150, 185)
        self._size = card_size
        self.setFixedSize(card_size)
        self._thumb_service = thumbnail_service
        self._project_location = project_location

        # Default styling
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._default_style = (
            "AssetCard {"
            "  background-color: #1E2130;"
            "  border: 1px solid #2E334D;"
            "  border-radius: 8px;"
            "}"
            "AssetCard:hover {"
            "  background-color: #24293D;"
            "  border: 1px solid #434B70;"
            "}"
            "QToolTip {"
            "  background-color: #202334;"
            "  color: #F1F5F9;"
            "  border: 1px solid #3B4261;"
            "  border-radius: 4px;"
            "  padding: 4px 8px;"
            "  font-size: 11px;"
            "}"
        )
        self._selected_style = (
            "AssetCard {"
            "  background-color: #2B3356;"
            "  border: 2px solid #6366F1;"
            "  border-radius: 8px;"
            "}"
            "AssetCard:hover {"
            "  background-color: #303960;"
            "  border: 2px solid #818CF8;"
            "}"
            "QToolTip {"
            "  background-color: #202334;"
            "  color: #F1F5F9;"
            "  border: 1px solid #3B4261;"
            "  border-radius: 4px;"
            "  padding: 4px 8px;"
            "  font-size: 11px;"
            "}"
        )
        self.setStyleSheet(self._default_style)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # 1. Thumbnail container
        thumb_w = card_size.width() - 16
        thumb_h = max(60, card_size.height() - 85)
        self.thumb = QLabel()
        self.thumb.setFixedSize(thumb_w, thumb_h)
        self.thumb.setStyleSheet(
            "background-color: #141622;"
            "border: 1px solid #24283E;"
            "border-radius: 6px;"
            "color: #94A3B8;"
            "font-size: 24px;"
        )
        self.thumb.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.thumb)

        # 2. Filename (elided text truncation)
        raw_filename = asset.get('filename', '')
        self.name = QLabel()
        self.name.setFixedHeight(20)
        self.name.setStyleSheet("color: #F1F5F9; font-size: 11px; font-weight: 600; background: transparent;")
        self.name.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._full_filename = raw_filename
        self.set_filename(raw_filename)
        layout.addWidget(self.name)

        # 3. Meta info (type / category / version / LOD / sequence)
        friendly_type = asset.get('friendly_type', '')
        category = asset.get('category', '')
        version = asset.get('version')
        lod = asset.get('lod')
        is_sequence = asset.get('is_sequence', False)

        meta_parts = []
        is_lib_ref = bool(asset.get('is_library_reference'))
        if is_lib_ref:
            meta_parts.append("🔗 Library")

        if is_sequence:
            meta_parts.append(f"🎞️ {asset.get('frame_count', 0)} frames")
            if version:
                meta_parts.append(version.upper())
        else:
            if friendly_type:
                meta_parts.append(friendly_type)
            if version:
                meta_parts.append(version.upper())
            if lod:
                meta_parts.append(lod.upper())
            elif category and not version and not is_lib_ref:
                meta_parts.append(category)

        avail = asset.get('availability')
        if avail:
            if avail in ("Offline", "offline"):
                meta_parts.append("⚠️ Offline")
            elif avail in ("Missing", "missing"):
                meta_parts.append("❌ Missing")
            elif avail in ("Possibly Changed", "possibly_changed"):
                meta_parts.append("🔄 Changed")

        meta_str = " • ".join(meta_parts) if meta_parts else (friendly_type or "File")
        self.meta = QLabel(meta_str)
        self.meta.setFixedHeight(16)
        self.meta.setStyleSheet("color: #94A3B8; font-size: 10px; background: transparent;")
        layout.addWidget(self.meta)

        # 4. Friendly date label
        self.date_label = QLabel(self._format_friendly_date(asset.get('date_added') or asset.get('created_at')))
        self.date_label.setFixedHeight(14)
        self.date_label.setStyleSheet("color: #64748B; font-size: 10px; background: transparent;")
        layout.addWidget(self.date_label)

        # Full tooltip
        tooltip_lines = [raw_filename]
        if is_lib_ref:
            tooltip_lines.append("Source: 📚 Global Asset Library Reference")
        if is_sequence:
            tooltip_lines.append(f"Type: {friendly_type} ({asset.get('frame_range', '')})")
            if version:
                tooltip_lines.append(f"Version: {version.upper()}")
        else:
            tooltip_lines.append(f"Type: {friendly_type or 'File'}")
            if version:
                tooltip_lines.append(f"Version: {version.upper()}")
            if lod:
                tooltip_lines.append(f"LOD: {lod.upper()}")
        if category:
            tooltip_lines.append(f"Category: {category}")
        if asset.get('drive_name'):
            tooltip_lines.append(f"Drive: {asset.get('drive_name')}")
        if asset.get('drive_relative_path'):
            tooltip_lines.append(f"Drive Path: {asset.get('drive_relative_path')}")
        if avail:
            tooltip_lines.append(f"Availability: {avail}")
        self.setToolTip("\n".join(tooltip_lines))

        # Connect to thumbnail service
        try:
            if self._thumb_service:
                self._thumb_service.thumbnail_ready.connect(self._on_thumbnail_ready)
        except Exception:
            pass

        self._load_thumbnail()

    def set_filename(self, filename: str):
        """Set filename with middle elision to keep layout strictly fixed."""
        self._full_filename = filename
        fm = QFontMetrics(self.name.font())
        avail_w = max(40, self._size.width() - 20)
        elided = fm.elidedText(filename, Qt.ElideMiddle, avail_w)
        self.name.setText(elided)
        self.name.setToolTip(filename)

    def _format_friendly_date(self, iso_str: str) -> str:
        if not iso_str:
            return ""
        try:
            dt = datetime.fromisoformat(iso_str)
        except Exception:
            return str(iso_str)
        today = datetime.now()
        delta = today.date() - dt.date()
        days = delta.days
        if days == 0:
            return "Today"
        if days == 1:
            return "Yesterday"
        if 0 < days < 7:
            return f"{days} days ago"
        return dt.strftime("%d %b %Y")

    def _load_thumbnail(self):
        # Prefer absolute_path provided by AssetService
        abs_path_str = self.asset.get('absolute_path')
        rel_path = self.asset.get('relative_path')
        ext = Path(rel_path or '').suffix.lower()
        if abs_path_str:
            abs_path = Path(abs_path_str)
        else:
            if self._project_location:
                abs_path = Path(self._project_location) / (rel_path or '')
            else:
                abs_path = Path(rel_path or '')

        # Ask thumbnail service for cached thumbnail first
        try:
            if self._thumb_service:
                proj_loc = self._project_location or "__global_library__"
                thumb_rel_key = rel_path or self.asset.get('drive_relative_path') or self.asset.get('id') or str(abs_path)
                cached = self._thumb_service.get_cached(proj_loc, str(thumb_rel_key), str(abs_path))
                if not cached and self.asset.get('is_library_reference'):
                    cached = self._thumb_service.get_cached("__global_library__", str(self.asset.get('drive_relative_path') or thumb_rel_key), str(abs_path))
                if cached == "FAILED":
                    self._show_fallback_icon(ext)
                    return
                if cached:
                    try:
                        pix = self._thumb_service.get_cached_pixmap(cached) if hasattr(self._thumb_service, "get_cached_pixmap") else QPixmap(cached)
                        if pix and not pix.isNull():
                            self.thumb.setPixmap(pix.scaled(self.thumb.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                            return
                    except Exception:
                        pass
                # if not cached, request async generation and fall through to placeholder
                if abs_path and abs_path.exists():
                    try:
                        self._thumb_service.generate_async(proj_loc, str(thumb_rel_key), str(abs_path), self._thumb_size_or_default(), self.asset.get('id'))
                    except Exception:
                        pass
        except Exception:
            pass

        # Fallback: image types direct display
        if ext in {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif'}:
            if abs_path.exists():
                try:
                    pix = QPixmap(str(abs_path))
                    if not pix.isNull():
                        self.thumb.setPixmap(pix.scaled(self.thumb.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        return
                except Exception:
                    pass

        self._show_fallback_icon(ext)

    def _show_fallback_icon(self, ext: str):
        icon = self.ICON_MAP.get(ext)
        if icon:
            self.thumb.setText(icon)
        else:
            clean_ext = ext.upper().lstrip('.') or 'FILE'
            self.thumb.setText(clean_ext)

    def _thumb_size_or_default(self):
        try:
            return self._size
        except Exception:
            return QSize(150, 185)

    def _on_thumbnail_ready(self, asset_id: str, thumb_path: str):
        try:
            if asset_id != self.asset.get('id'):
                return
            pix = QPixmap(thumb_path)
            if not pix.isNull():
                self.thumb.setPixmap(pix.scaled(self.thumb.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
            self.clicked.emit(self.asset.get('id'))
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        if not hasattr(self, '_drag_start_pos') or self._drag_start_pos is None:
            return
        if (event.pos() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return

        try:
            from PySide6.QtGui import QDrag
            from services.asset_operations_service import AssetOperationsService, MIME_ASSETS

            rel_path = self.asset.get('relative_path') or ''
            parent_dir = str(Path(rel_path).parent).replace('\\', '/')
            if parent_dir == '.':
                parent_dir = ''

            drag = QDrag(self)
            mime_data = AssetOperationsService.create_asset_mime_data(
                project_location=self._project_location or '',
                asset_ids=[self.asset.get('id')],
                source_rel_path=parent_dir,
                operation="move",
            )
            drag.setMimeData(mime_data)

            pixmap = self.grab()
            drag.setPixmap(pixmap.scaled(70, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            drag.exec_(Qt.MoveAction)
        except Exception:
            pass

    def contextMenuEvent(self, event):
        try:
            self.context_requested.emit(self.asset.get('id'))
        except Exception:
            pass
        try:
            event.accept()
        except Exception:
            pass

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self.asset.get('id'))

    def set_selected(self, selected: bool):
        self._selected = selected
        if selected:
            self.setStyleSheet(self._selected_style)
            self.thumb.setStyleSheet(
                "background-color: #1A1E36;"
                "border: 1px solid #6366F1;"
                "border-radius: 6px;"
                "color: #C7D2FE;"
                "font-size: 24px;"
            )
        else:
            self.setStyleSheet(self._default_style)
            self.thumb.setStyleSheet(
                "background-color: #141622;"
                "border: 1px solid #24283E;"
                "border-radius: 6px;"
                "color: #94A3B8;"
                "font-size: 24px;"
            )
