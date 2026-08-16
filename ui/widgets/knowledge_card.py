"""Card widget representing a KnowledgeDocument in grid/list views."""

from datetime import datetime
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from models.knowledge import KnowledgeDocument


class KnowledgeCard(QFrame):
    """Visual card representation for a Knowledge Document."""

    clicked = Signal(object)
    favorite_toggled = Signal(str, bool)

    def __init__(self, document: KnowledgeDocument, parent=None):
        super().__init__(parent)
        self.document = document
        self._selected = False

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setFixedHeight(120)
        self.setMinimumWidth(200)
        self.setMaximumWidth(320)
        self.setCursor(Qt.PointingHandCursor)

        self._setup_ui()
        self._update_appearance()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(6)

        # Header: Title + Star Favorite Button
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        self.title_label = QLabel()
        self.title_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.title_label.setStyleSheet("color: #F1F5F9; background: transparent;")
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        header_layout.addWidget(self.title_label)

        self.fav_btn = QPushButton()
        self.fav_btn.setFixedSize(24, 24)
        self.fav_btn.setCursor(Qt.PointingHandCursor)
        self.fav_btn.clicked.connect(self._on_fav_clicked)
        header_layout.addWidget(self.fav_btn)

        main_layout.addLayout(header_layout)

        # Snippet / Content Preview
        self.snippet_label = QLabel()
        self.snippet_label.setFont(QFont("Segoe UI", 9))
        self.snippet_label.setStyleSheet("color: #94A3B8; background: transparent;")
        self.snippet_label.setWordWrap(True)
        self.snippet_label.setMaximumHeight(36)
        self.snippet_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        main_layout.addWidget(self.snippet_label)

        # Footer: Tags + Date
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(8)

        self.tags_label = QLabel()
        self.tags_label.setFont(QFont("Segoe UI", 8))
        self.tags_label.setStyleSheet("color: #38BDF8; background: transparent;")
        self.tags_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        footer_layout.addWidget(self.tags_label)

        self.date_label = QLabel()
        self.date_label.setFont(QFont("Segoe UI", 8))
        self.date_label.setStyleSheet("color: #64748B; background: transparent;")
        footer_layout.addWidget(self.date_label)

        main_layout.addLayout(footer_layout)

        self.update_document(self.document)

    def update_document(self, document: KnowledgeDocument):
        """Update card contents to reflect latest document state."""
        self.document = document

        # Format title with ellipsis if long
        title = document.title or "Untitled Note"
        fm = QFontMetrics(self.title_label.font())
        elided_title = fm.elidedText(title, Qt.ElideRight, 200)
        self.title_label.setText(elided_title)
        self.title_label.setToolTip(title)

        # Format content preview
        content = (document.content or "").strip().replace("\n", " ")
        if not content:
            snippet = "(Empty note)"
        else:
            snippet = content[:120] + ("..." if len(content) > 120 else "")
        self.snippet_label.setText(snippet)

        # Format favorite button
        is_fav = bool(getattr(document, "favorite", False))
        if is_fav:
            self.fav_btn.setText("⭐")
            self.fav_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    font-size: 13px;
                    color: #F59E0B;
                }
                QPushButton:hover {
                    font-size: 15px;
                }
            """)
            self.fav_btn.setToolTip("Unstar note")
        else:
            self.fav_btn.setText("☆")
            self.fav_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    font-size: 14px;
                    color: #64748B;
                }
                QPushButton:hover {
                    color: #F59E0B;
                    font-size: 16px;
                }
            """)
            self.fav_btn.setToolTip("Star note")

        # Format tags
        tags = getattr(document, "tags", [])
        if tags:
            tags_text = " ".join(f"#{t}" for t in tags[:3])
            if len(tags) > 3:
                tags_text += f" +{len(tags) - 3}"
            self.tags_label.setText(tags_text)
            self.tags_label.setToolTip(", ".join(tags))
        else:
            self.tags_label.setText("")
            self.tags_label.setToolTip("")

        # Format date
        mod_raw = getattr(document, "modified", None) or getattr(document, "created", None)
        date_str = ""
        if mod_raw:
            try:
                dt = datetime.fromisoformat(mod_raw)
                now = datetime.now()
                if dt.date() == now.date():
                    date_str = dt.strftime("%H:%M")
                else:
                    date_str = dt.strftime("%d %b")
            except Exception:
                date_str = str(mod_raw)[:10]
        self.date_label.setText(date_str)

    def set_selected(self, selected: bool):
        self._selected = selected
        self._update_appearance()

    def is_selected(self) -> bool:
        return self._selected

    def _update_appearance(self):
        if self._selected:
            self.setStyleSheet("""
                KnowledgeCard {
                    background-color: #1E293B;
                    border: 2px solid #38BDF8;
                    border-radius: 8px;
                }
            """)
        else:
            self.setStyleSheet("""
                KnowledgeCard {
                    background-color: #1E2029;
                    border: 1px solid #2E3342;
                    border-radius: 8px;
                }
                KnowledgeCard:hover {
                    background-color: #252836;
                    border: 1px solid #38BDF8;
                }
            """)

    def _on_fav_clicked(self):
        new_fav = not bool(getattr(self.document, "favorite", False))
        self.favorite_toggled.emit(self.document.id, new_fav)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.document)
        super().mousePressEvent(event)
