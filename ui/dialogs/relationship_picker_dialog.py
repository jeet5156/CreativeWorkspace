from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QLabel
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from ui.lab.models.relationship_registry import RelationshipRegistry, RelationshipDefinition


class RelationshipPickerDialog(QDialog):
    """Command palette style popup dialog to search and select a relationship type."""

    definition_selected = Signal(object)

    def __init__(self, parent=None, current_type_id: str = "related_to"):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setFixedSize(320, 280)

        self._selected_definition: Optional[RelationshipDefinition] = None
        self._current_type_id = current_type_id

        self.setStyleSheet("""
            QDialog {
                background-color: #1E2029;
                border: 2px solid #6366F1;
                border-radius: 8px;
            }
            QLineEdit {
                background-color: #0F172A;
                color: #F8FAFC;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
            }
            QListWidget {
                background-color: #0F172A;
                color: #CBD5E1;
                border: 1px solid #1E293B;
                border-radius: 4px;
                outline: none;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #312E81;
                color: #FFFFFF;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header Title Label
        hdr = QLabel("🔗 Select Knowledge Relationship")
        hdr.setFont(QFont("Segoe UI", 9, QFont.Bold))
        hdr.setStyleSheet("color: #94A3B8;")
        layout.addWidget(hdr)

        # Search LineEdit Input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search type (e.g. Depends On, Alternative)...")
        self.search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_input)

        # List Widget Options
        self.list_widget = QListWidget()
        self.list_widget.itemActivated.connect(self._on_item_activated)
        self.list_widget.itemClicked.connect(self._on_item_activated)
        layout.addWidget(self.list_widget)

        # Footer Hint Label
        ftr = QLabel("↑↓ Navigate  •  ↵ Choose  •  Esc Cancel")
        ftr.setStyleSheet("color: #64748B; font-size: 10px;")
        layout.addWidget(ftr)

        self._filter_definitions("")

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self.reject()
            return
        elif key == Qt.Key_Down:
            curr = self.list_widget.currentRow()
            if curr < self.list_widget.count() - 1:
                self.list_widget.setCurrentRow(curr + 1)
            return
        elif key == Qt.Key_Up:
            curr = self.list_widget.currentRow()
            if curr > 0:
                self.list_widget.setCurrentRow(curr - 1)
            return
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            item = self.list_widget.currentItem()
            if item:
                self._on_item_activated(item)
            return
        super().keyPressEvent(event)

    def _on_search_changed(self, text: str):
        self._filter_definitions(text.strip().lower())

    def _filter_definitions(self, query: str):
        self.list_widget.clear()
        defs = RelationshipRegistry.all_definitions()

        matched_defs = []
        for d in defs:
            if not query or query in d.label.lower() or query in d.id.lower() or query in d.description.lower():
                matched_defs.append(d)

        for d in matched_defs:
            arrow = "➔" if d.directional else "⟷"
            txt = f"{d.label}  ({arrow})"
            item = QListWidgetItem(txt)
            item.setData(Qt.UserRole, d.id)

            if d.id == self._current_type_id:
                item.setText(f"{txt}  [current]")

            self.list_widget.addItem(item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _on_item_activated(self, item: QListWidgetItem):
        if not item:
            return
        rel_id = item.data(Qt.UserRole)
        self._selected_definition = RelationshipRegistry.get(rel_id)
        self.accept()

    def selected_definition(self) -> Optional[RelationshipDefinition]:
        return self._selected_definition
