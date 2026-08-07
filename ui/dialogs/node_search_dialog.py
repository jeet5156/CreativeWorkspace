from typing import List, Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

from ui.lab.nodes.node_item import NodeItem


class NodeSearchDialog(QDialog):
    """Modern dark-themed Quick Search Palette (Ctrl+K) for spatial Lab nodes."""

    node_selected = Signal(str)

    _recent_queries: List[str] = []

    def __init__(self, nodes: List[NodeItem], parent=None):
        super().__init__(parent)
        self._nodes = nodes or []
        self._filtered_nodes: List[NodeItem] = []

        self.setWindowTitle("Quick Node Search (Ctrl+K)")
        self.setFixedWidth(540)
        self.setFixedHeight(400)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        self.setStyleSheet("""
            QDialog {
                background-color: #171922;
                border: 1px solid #343847;
                border-radius: 8px;
            }
            QLineEdit {
                background-color: #1E2029;
                color: #F1F5F9;
                border: 1px solid #343847;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #6366F1;
            }
            QListWidget {
                background-color: transparent;
                border: none;
                color: #CBD5E1;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 6px;
                margin: 2px 0;
            }
            QListWidget::item:hover {
                background-color: #232736;
                color: #F1F5F9;
            }
            QListWidget::item:selected {
                background-color: #312E81;
                color: #A5B4FC;
            }
            QLabel {
                color: #94A3B8;
                font-size: 11px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header Row
        header_layout = QHBoxLayout()
        title_lbl = QLabel("🔍 <b>Quick Node Search</b> <span style='color: #64748B;'>(Ctrl+K)</span>")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()

        esc_hint = QLabel("Esc to close")
        esc_hint.setStyleSheet("color: #64748B; font-size: 11px;")
        header_layout.addWidget(esc_hint)
        layout.addLayout(header_layout)

        # Search Input LineEdit
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to search title, body, tags (e.g. boss, tag:enemy)...")
        self.search_input.textChanged.connect(self._on_search_text_changed)
        layout.addWidget(self.search_input)

        # Results List Widget
        self.results_list = QListWidget()
        self.results_list.itemActivated.connect(self._on_item_activated)
        self.results_list.itemClicked.connect(self._on_item_activated)
        layout.addWidget(self.results_list)

        # Footer Status Row
        footer_layout = QHBoxLayout()
        self.count_label = QLabel(f"Showing {len(self._nodes)} nodes")
        footer_layout.addWidget(self.count_label)
        footer_layout.addStretch()

        nav_hint = QLabel("↑↓ Navigate  •  ↵ Select")
        nav_hint.setStyleSheet("color: #64748B; font-size: 11px;")
        footer_layout.addWidget(nav_hint)
        layout.addLayout(footer_layout)

        # Perform initial search population
        self._filter_nodes("")

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self.reject()
            return
        elif key == Qt.Key_Down:
            curr_row = self.results_list.currentRow()
            if curr_row < self.results_list.count() - 1:
                self.results_list.setCurrentRow(curr_row + 1)
            return
        elif key == Qt.Key_Up:
            curr_row = self.results_list.currentRow()
            if curr_row > 0:
                self.results_list.setCurrentRow(curr_row - 1)
            return
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            item = self.results_list.currentItem()
            if item:
                self._on_item_activated(item)
            return
        super().keyPressEvent(event)

    def _on_search_text_changed(self, text: str):
        self._filter_nodes(text.strip())

    def _filter_nodes(self, query: str):
        q = query.lower()
        self.results_list.clear()
        self._filtered_nodes = []

        is_tag_query = q.startswith("tag:")
        is_rel_query = q.startswith("relationship:") or q.startswith("rel:")
        is_frame_query = q.startswith("frame:")
        is_type_query = q.startswith("type:")

        val_filter = ""
        if is_tag_query:
            val_filter = q[4:].strip()
        elif is_rel_query:
            val_filter = q.split(":", 1)[1].strip()
        elif is_frame_query:
            val_filter = q[6:].strip()
        elif is_type_query:
            val_filter = q[5:].strip()

        matched = []
        for node in self._nodes:
            if not node:
                continue

            if is_tag_query:
                if any(val_filter in t.lower() for t in node.tags):
                    matched.append(node)
                continue
            elif is_rel_query:
                # Query attached relationships via scene canvas ConnectionManager
                if hasattr(node, "scene") and node.scene() and node.scene().views():
                    cv = node.scene().views()[0]
                    if hasattr(cv, "connection_manager"):
                        rels = cv.connection_manager.get_node_relationships(node.id)
                        if any(val_filter in r.relationship_type.lower() or val_filter in r.title.lower() for r in rels):
                            matched.append(node)
                            continue
                continue
            elif is_frame_query:
                p_id = node.payload.get("parent_frame_id") if isinstance(node.payload, dict) else None
                if p_id and hasattr(node, "scene") and node.scene() and node.scene().views():
                    cv = node.scene().views()[0]
                    if hasattr(cv, "node"):
                        f_node = cv.node(p_id)
                        if f_node and val_filter in str(f_node.payload.get("title", "")).lower():
                            matched.append(node)
                            continue
                continue
            elif is_type_query:
                t_id = node.definition.type_id if node.definition else ""
                if val_filter in t_id.lower():
                    matched.append(node)
                    continue

            # General text query
            if not q:
                matched.append(node)
            else:
                searchable_text = node.get_searchable_text() if hasattr(node, "get_searchable_text") else ""
                if q in searchable_text:
                    matched.append(node)

        # Sort pinned nodes to top
        def _sort_key(n):
            n_meta = getattr(n, "metadata", None)
            pinned = bool(n.payload.get("pinned", False) or (isinstance(n_meta, dict) and n_meta.get("pinned", False)))
            return 0 if pinned else 1

        self._filtered_nodes = sorted(matched, key=_sort_key)

        # Populate ListWidget
        for node in self._filtered_nodes:
            defn = getattr(node, "definition", None)
            n_meta = getattr(node, "metadata", None)
            is_pinned = bool(node.payload.get("pinned", False) or (isinstance(n_meta, dict) and n_meta.get("pinned", False)))
            pin_badge = " ⭐" if is_pinned else ""

            icon = defn.icon if defn else "📝"
            title = defn.title if defn else "Node"
            content_title = node.payload.get("title") if isinstance(node.payload, dict) else None
            if content_title:
                title = f"{title}: {content_title}"

            type_badge = f"[{defn.type_id}]" if defn else "[node]"
            content = str(node.payload.get("content") or "").replace("\n", " ").strip()
            snippet = f" - {content[:45]}..." if content else ""
            tags_str = f"  🏷️ {', '.join(node.tags)}" if node.tags else ""

            display_text = f"{icon}{pin_badge}  <b>{title}</b>  <span style='color: #818CF8; font-size: 11px;'>{type_badge}</span>{snippet} <span style='color: #34D399; font-size: 11px;'>{tags_str}</span>"

            # Highlight matching query text if present
            if q and not is_tag_query:
                try:
                    import re
                    pattern = re.compile(re.escape(q), re.IGNORECASE)
                    display_text = pattern.sub(lambda m: f"<span style='background-color: #3730A3; color: #FDE047; font-weight: bold;'>{m.group(0)}</span>", display_text)
                except Exception:
                    pass

            item = QListWidgetItem()
            item.setData(Qt.UserRole, node.id)
            self.results_list.addItem(item)

            # Create rich widget label for list item
            lbl = QLabel(display_text, self.results_list)
            lbl.setTextFormat(Qt.RichText)
            lbl.setStyleSheet("padding: 4px 6px; color: #E2E8F0;")
            item.setSizeHint(lbl.sizeHint())
            self.results_list.setItemWidget(item, lbl)

        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)

        self.count_label.setText(f"Found {len(self._filtered_nodes)} matching nodes")

    def _on_item_activated(self, item: QListWidgetItem):
        if not item:
            return
        node_id = item.data(Qt.UserRole)
        if node_id:
            query = self.search_input.text().strip()
            if query and query not in NodeSearchDialog._recent_queries:
                NodeSearchDialog._recent_queries.insert(0, query)
                NodeSearchDialog._recent_queries = NodeSearchDialog._recent_queries[:10]

            self.node_selected.emit(node_id)
            self.accept()
