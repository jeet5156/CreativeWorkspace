from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
)
from PySide6.QtCore import Qt, Signal, QSize


class FolderCard(QWidget):
    clicked = Signal(str)
    double_clicked = Signal(str)
    context_requested = Signal(str)
    assets_dropped = Signal(object, str)

    def __init__(
        self,
        folder_name: str,
        rel_path: str,
        size: QSize,
        is_parent_nav: bool = False,
        item_count: int = None,
    ):
        super().__init__()
        self.folder_name = folder_name
        self.rel_path = rel_path
        self.is_parent_nav = is_parent_nav
        self.item_count = item_count
        self._selected = False
        self.setFixedSize(size)
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.thumb = QLabel()
        self.thumb.setFixedSize(size.width() - 12, size.height() - 74)
        self.thumb.setStyleSheet(
            "background:#eef4fc;border:1px solid #cce0ff;border-radius:4px;"
        )
        self.thumb.setAlignment(Qt.AlignCenter)

        if self.is_parent_nav:
            self.thumb.setText("⬆️")
            self.thumb.setStyleSheet(
                "background:#f5f5f5;border:1px dashed #cccccc;border-radius:4px;font-size:28px;"
            )
        else:
            self.thumb.setText("📁")
            self.thumb.setStyleSheet(
                "background:#fff8e6;border:1px solid #ffe0b2;border-radius:4px;font-size:32px;"
            )
        layout.addWidget(self.thumb)

        display_name = ".." if self.is_parent_nav else self.folder_name
        self.name = QLabel(display_name)
        self.name.setWordWrap(True)
        self.name.setFixedHeight(30)
        self.name.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.name)

        if self.is_parent_nav:
            meta_text = "Parent Folder"
        elif self.item_count is not None:
            meta_text = f"Folder • {self.item_count} items"
        else:
            meta_text = "Folder"

        self.meta = QLabel(meta_text)
        self.meta.setStyleSheet("color:#666;font-size:11px;")
        layout.addWidget(self.meta)

        self.date_label = QLabel("")
        self.date_label.setStyleSheet("color:#888;font-size:11px;")
        layout.addWidget(self.date_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.rel_path)
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self.rel_path)

    def contextMenuEvent(self, event):
        try:
            self.context_requested.emit(self.rel_path)
        except Exception:
            pass
        try:
            event.accept()
        except Exception:
            pass

    def set_selected(self, selected: bool):
        self._selected = selected
        if selected:
            self.setStyleSheet(
                "background:#e6f0ff;border:1px solid #7aa7ff;border-radius:4px;"
            )
        else:
            self.setStyleSheet("")

    def dragEnterEvent(self, event):
        try:
            from services.asset_operations_service import MIME_ASSETS
            if event.mimeData().hasFormat(MIME_ASSETS) or event.mimeData().hasUrls():
                event.acceptProposedAction()
                self.setStyleSheet("background:#e6f0ff;border:2px dashed #0066cc;border-radius:4px;")
            else:
                event.ignore()
        except Exception:
            event.ignore()

    def dragLeaveEvent(self, event):
        if not getattr(self, '_selected', False):
            self.setStyleSheet("")
        else:
            self.set_selected(True)

    def dropEvent(self, event):
        try:
            from services.asset_operations_service import MIME_ASSETS
            if event.mimeData().hasFormat(MIME_ASSETS) or event.mimeData().hasUrls():
                event.acceptProposedAction()
                self.dragLeaveEvent(None)
                self.assets_dropped.emit(event.mimeData(), self.rel_path)
            else:
                event.ignore()
        except Exception:
            event.ignore()
