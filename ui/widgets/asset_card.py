from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QSizePolicy,
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

    def __init__(self, asset: dict, size: QSize):
        super().__init__()
        self.asset = asset
        self._selected = False
        self.setFixedSize(size)

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
        ext = Path(self.asset.get('relative_path','')).suffix.lower()
        if abs_path_str:
            abs_path = Path(abs_path_str)
        else:
            abs_path = Path.cwd() / self.asset.get('relative_path','')

        if ext in {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif'}:
            if abs_path.exists():
                try:
                    pix = QPixmap(str(abs_path))
                    if not pix.isNull():
                        self.thumb.setPixmap(pix.scaled(self.thumb.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        return
                except Exception:
                    pass
        # Non-image: show an icon if available, otherwise extension text
        icon = self.ICON_MAP.get(ext)
        if icon:
            self.thumb.setText(icon)
            return
        self.thumb.setText(ext.upper().lstrip('.') or 'FILE')

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.asset.get('id'))
        elif event.button() == Qt.RightButton:
            self.context_requested.emit(self.asset.get('id'))

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self.asset.get('id'))

    def set_selected(self, selected: bool):
        self._selected = selected
        if selected:
            self.setStyleSheet('background:#e6f0ff;border:1px solid #7aa7ff;')
        else:
            self.setStyleSheet('')
