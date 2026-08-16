from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFontMetrics


class FolderCard(QWidget):
    clicked = Signal(str)
    double_clicked = Signal(str)
    context_requested = Signal(str)
    assets_dropped = Signal(object, str)

    def __init__(
        self,
        folder_name: str,
        rel_path: str,
        size: QSize = None,
        is_parent_nav: bool = False,
        item_count: int = None,
        availability: str = None,
        is_favorite: bool = False,
    ):
        super().__init__()
        self.folder_name = folder_name
        self.rel_path = rel_path
        self.is_parent_nav = is_parent_nav
        self.item_count = item_count
        self.availability = availability
        self.is_favorite = is_favorite
        self._selected = False
        card_size = size or QSize(150, 185)
        self._size = card_size
        self.setFixedSize(card_size)
        self.setAcceptDrops(True)

        # Style definitions (distinguished from asset files by warm folder tones)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._default_style = (
            "FolderCard {"
            "  background-color: #1F2232;"
            "  border: 1px solid #3E382A;"
            "  border-radius: 8px;"
            "}"
            "FolderCard:hover {"
            "  background-color: #262B40;"
            "  border: 1px solid #785A1D;"
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
            "FolderCard {"
            "  background-color: #362F20;"
            "  border: 2px solid #F59E0B;"
            "  border-radius: 8px;"
            "}"
            "FolderCard:hover {"
            "  background-color: #3D3524;"
            "  border: 2px solid #FBBF24;"
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
        self._drop_hover_style = (
            "FolderCard {"
            "  background-color: #292E46;"
            "  border: 2px dashed #F59E0B;"
            "  border-radius: 8px;"
            "}"
        )
        self.setStyleSheet(self._default_style)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # 1. Folder thumbnail container
        thumb_w = card_size.width() - 16
        thumb_h = max(60, card_size.height() - 85)
        self.thumb = QLabel()
        self.thumb.setFixedSize(thumb_w, thumb_h)
        self.thumb.setAlignment(Qt.AlignCenter)

        if self.is_parent_nav:
            self.thumb.setText("⬆️")
            self.thumb.setStyleSheet(
                "background-color: #1A1D2A;"
                "border: 1px dashed #475569;"
                "border-radius: 6px;"
                "font-size: 24px;"
            )
        else:
            icon_char = "⭐📁" if self.is_favorite else "📁"
            self.thumb.setText(icon_char)
            self.thumb.setStyleSheet(
                "background-color: #2A2215;"
                "border: 1px solid #523F17;"
                "border-radius: 6px;"
                "font-size: 28px;"
            )
        layout.addWidget(self.thumb)

        # 2. Folder name with text elision to prevent layout shifts
        display_name = ".." if self.is_parent_nav else self.folder_name
        self.name = QLabel()
        self.name.setFixedHeight(20)
        self.name.setStyleSheet(
            "color: #FCD34D; font-size: 11px; font-weight: bold; background: transparent;"
        )
        self.name.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.set_folder_name(display_name)
        layout.addWidget(self.name)

        # 3. Meta info
        meta_parts = []
        if self.is_parent_nav:
            meta_parts.append("Parent Folder")
        else:
            if self.item_count is not None:
                meta_parts.append(f"{self.item_count} items")
            else:
                meta_parts.append("Folder")

            if self.availability in ("Offline", "offline"):
                meta_parts.append("⚠️ Offline")
            elif self.availability in ("Missing", "missing"):
                meta_parts.append("❌ Missing")

        meta_text = " • ".join(meta_parts)
        self.meta = QLabel(meta_text)
        self.meta.setFixedHeight(16)
        self.meta.setStyleSheet("color: #D97706; font-size: 10px; font-weight: 500; background: transparent;")
        layout.addWidget(self.meta)

        # 4. Status / spacing label
        self.date_label = QLabel("")
        self.date_label.setFixedHeight(14)
        self.date_label.setStyleSheet("color: #64748B; font-size: 10px; background: transparent;")
        layout.addWidget(self.date_label)

        # Full tooltip
        tooltip_lines = [display_name, f"Type: {meta_text}"]
        if self.availability:
            tooltip_lines.append(f"Availability: {self.availability}")
        if self.is_favorite:
            tooltip_lines.append("Favorite: Yes")
        self.setToolTip("\n".join(tooltip_lines))

    def set_folder_name(self, name: str):
        """Set folder display name with middle elision to keep layout strictly fixed."""
        fm = QFontMetrics(self.name.font())
        avail_w = max(40, self._size.width() - 20)
        elided = fm.elidedText(name, Qt.ElideMiddle, avail_w)
        self.name.setText(elided)
        self.name.setToolTip(name)

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
            self.setStyleSheet(self._selected_style)
            if self.is_parent_nav:
                self.thumb.setStyleSheet(
                    "background-color: #25293A;"
                    "border: 1px dashed #F59E0B;"
                    "border-radius: 6px;"
                    "font-size: 24px;"
                )
            else:
                self.thumb.setStyleSheet(
                    "background-color: #382C18;"
                    "border: 1px solid #F59E0B;"
                    "border-radius: 6px;"
                    "font-size: 28px;"
                )
        else:
            self.setStyleSheet(self._default_style)
            if self.is_parent_nav:
                self.thumb.setStyleSheet(
                    "background-color: #1A1D2A;"
                    "border: 1px dashed #475569;"
                    "border-radius: 6px;"
                    "font-size: 24px;"
                )
            else:
                self.thumb.setStyleSheet(
                    "background-color: #2A2215;"
                    "border: 1px solid #523F17;"
                    "border-radius: 6px;"
                    "font-size: 28px;"
                )

    def dragEnterEvent(self, event):
        try:
            from services.asset_operations_service import MIME_ASSETS
            if event.mimeData().hasFormat(MIME_ASSETS) or event.mimeData().hasUrls():
                event.acceptProposedAction()
                self.setStyleSheet(self._drop_hover_style)
            else:
                event.ignore()
        except Exception:
            event.ignore()

    def dragLeaveEvent(self, event):
        if not getattr(self, '_selected', False):
            self.setStyleSheet(self._default_style)
        else:
            self.setStyleSheet(self._selected_style)

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
