from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QSizePolicy,
    QApplication,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap
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
        '.csv': '📄',
        '.mp3': '🎵',
        '.wav': '🎵',
        '.mp4': '🎞️',
        '.mov': '🎞️',
        '.fbx': '🧩',
        '.obj': '🧩',
    }

    def __init__(self, asset: dict, size: QSize, thumbnail_service=None, project_location: str = None):
        super().__init__()
        self.asset = asset
        self._selected = False
        self.setFixedSize(size)
        self._thumb_service = thumbnail_service
        self._project_location = project_location
        self._size = size

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.thumb = QLabel()
        self.thumb.setFixedSize(size.width() - 12, size.height() - 74)
        self.thumb.setStyleSheet("background:#f0f0f0;border:1px solid #ddd;")
        self.thumb.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.thumb)

        self.name = QLabel(asset.get('filename', ''))
        self.name.setWordWrap(True)
        self.name.setFixedHeight(30)
        layout.addWidget(self.name)

        self.meta = QLabel(f"{asset.get('friendly_type','')} • {asset.get('category','')}")
        self.meta.setStyleSheet("color:#666;font-size:11px;")
        layout.addWidget(self.meta)

        # friendly date label
        self.date_label = QLabel(self._format_friendly_date(asset.get('date_added')))
        self.date_label.setStyleSheet("color:#888;font-size:11px;")
        layout.addWidget(self.date_label)

        # connect to thumbnail ready signal so we can update when generation completes
        try:
            if self._thumb_service:
                self._thumb_service.thumbnail_ready.connect(self._on_thumbnail_ready)
        except Exception:
            pass

        self._load_thumbnail()

    def _format_friendly_date(self, iso_str: str) -> str:
        if not iso_str:
            return ""
        try:
            dt = datetime.fromisoformat(iso_str)
        except Exception:
            return iso_str
        today = datetime.now()
        delta = today.date() - dt.date()
        days = delta.days
        if days == 0:
            return "Today"
        if days == 1:
            return "Yesterday"
        if days < 7:
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
            # Prefer resolving relative paths against the project's canonical root if available.
            if self._project_location:
                abs_path = Path(self._project_location) / (rel_path or '')
            else:
                abs_path = Path(rel_path or '')

        # Ask thumbnail service for cached thumbnail first
        try:
            if self._thumb_service and self._project_location:
                cached = self._thumb_service.get_cached(self._project_location, rel_path, str(abs_path))
                if cached:
                    try:
                        pix = QPixmap(cached)
                        if not pix.isNull():
                            self.thumb.setPixmap(pix.scaled(self.thumb.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                            return
                    except Exception:
                        pass
                # if not cached, request async generation and fall through to placeholder
                try:
                    self._thumb_service.generate_async(self._project_location, rel_path, str(abs_path), self._thumb_size_or_default(), self.asset.get('id'))
                except Exception:
                    pass
        except Exception:
            pass

        # Fallback: image types may still be displayed directly (fast path) if available
        if ext in {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif'}:
            if abs_path.exists():
                try:
                    pix = QPixmap(str(abs_path))
                    if not pix.isNull():
                        self.thumb.setPixmap(pix.scaled(self.thumb.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        return
                except Exception:
                    pass

        # Non-image: show an icon if available, otherwise extension text as placeholder
        icon = self.ICON_MAP.get(ext)
        if icon:
            self.thumb.setText(icon)
            return
        self.thumb.setText(ext.upper().lstrip('.') or 'FILE')

    def _thumb_size_or_default(self):
        try:
            return self._size
        except Exception:
            return QSize(140, 160)

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
            # Let contextMenuEvent handle right-click/context menus to avoid menu dismissal when
            # selection logic triggers UI changes during mouse press.
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
        """Emit context_requested when the OS/context menu is requested. This ensures
        the menu is shown from contextMenuEvent, not mousePressEvent, preventing
        transient menus from closing if selection triggers minor UI updates.
        """
        try:
            self.context_requested.emit(self.asset.get('id'))
        except Exception:
            pass
        # Accept the event so default handling doesn't also run
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
            self.setStyleSheet('background:#e6f0ff;border:1px solid #7aa7ff;')
        else:
            self.setStyleSheet('')
