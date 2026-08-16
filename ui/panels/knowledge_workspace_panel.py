"""Global Knowledge Workspace Panel for CreativeWorkspace.

Provides a structured local-first knowledge manager with folder hierarchy,
document card listings, search, tags, favorites, and embedded document editing.
"""

from typing import Dict, List, Optional
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QScrollArea,
    QSplitter,
    QFrame,
    QTreeWidget,
    QTreeWidgetItem,
    QComboBox,
    QInputDialog,
    QMessageBox,
    QMenu,
    QSizePolicy,
)

from models.knowledge import KnowledgeDocument, KnowledgeFolder
from services.knowledge_service import KnowledgeService, _UNSET
from services.knowledge_ai_service import KnowledgeAIService
from ui.widgets.knowledge_card import KnowledgeCard
from ui.widgets.relationship_chip import RelationshipChip
from ui.widgets.knowledge_ai_assist_widget import KnowledgeAIAssistWidget
from ui.dialogs.add_knowledge_relationship_dialog import AddKnowledgeRelationshipDialog


class KnowledgeWorkspacePanel(QWidget):
    """Full-featured Knowledge workspace panel with sidebar navigation, document grid, and live editor."""

    document_selected = Signal(object)

    def __init__(self, context=None, parent=None):
        super().__init__(parent)
        self._context = context
        self.knowledge_service: Optional[KnowledgeService] = getattr(context, "knowledge_service", None) if context else None
        
        self.knowledge_ai_service: Optional[KnowledgeAIService] = getattr(context, "knowledge_ai_service", None) if context else None
        self.knowledge_assistant_service: Optional[KnowledgeAssistantService] = getattr(context, "knowledge_assistant_service", None) if context else None
        if not self.knowledge_ai_service and context and getattr(context, "ai_service", None):
            self.knowledge_ai_service = KnowledgeAIService(getattr(context, "ai_service", None), self.knowledge_service)

        # State
        self._current_category = "all"  # "all", "favorites", "recent", "folder"
        self._current_folder_id: Optional[str] = None
        self._current_doc_id: Optional[str] = None
        self._search_query: str = ""

        self._cards: Dict[str, KnowledgeCard] = {}
        self._folder_tree_items: Dict[str, QTreeWidgetItem] = {}
        self._is_updating_editor = False

        # Autosave debounce timer for editor
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(300)
        self._autosave_timer.timeout.connect(self._save_active_document)

        self._setup_ui()

        # Connect to service signals if available
        if self.knowledge_service:
            try:
                self.knowledge_service.document_created.connect(self._on_service_doc_created)
                self.knowledge_service.document_updated.connect(self._on_service_doc_updated)
                self.knowledge_service.document_deleted.connect(self._on_service_doc_deleted)
                self.knowledge_service.folder_created.connect(self._on_service_folder_changed)
                self.knowledge_service.folder_updated.connect(self._on_service_folder_changed)
                self.knowledge_service.folder_deleted.connect(self._on_service_folder_changed)
                self.knowledge_service.knowledge_reloaded.connect(self.refresh)
            except Exception:
                pass

        self.refresh()

    def set_context(self, context):
        self._context = context
        self.knowledge_service = getattr(context, "knowledge_service", None) if context else None
        self.knowledge_ai_service = getattr(context, "knowledge_ai_service", None) if context else None
        self.knowledge_assistant_service = getattr(context, "knowledge_assistant_service", None) if context else None
        if not self.knowledge_ai_service and context and getattr(context, "ai_service", None):
            self.knowledge_ai_service = KnowledgeAIService(getattr(context, "ai_service", None), self.knowledge_service)
        if hasattr(self, "ai_assist_widget") and self.ai_assist_widget:
            self.ai_assist_widget.set_ai_service(self.knowledge_ai_service)
            if self.knowledge_assistant_service:
                self.ai_assist_widget.set_assistant_service(self.knowledge_assistant_service)
        self.refresh()

    # -------------------------------------------------------------------------
    # UI Setup
    # -------------------------------------------------------------------------

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Left Navigation Sidebar
        self.sidebar = self._create_sidebar()
        main_layout.addWidget(self.sidebar)

        # 2. Main Content Splitter (Cards List on Left, Editor on Right)
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #282C40;
                width: 1px;
            }
        """)

        # Left Sub-Pane: Header + Document Cards
        self.cards_pane = self._create_cards_pane()
        self.main_splitter.addWidget(self.cards_pane)

        # Right Sub-Pane: Embedded Document Editor
        self.editor_pane = self._create_editor_pane()
        self.main_splitter.addWidget(self.editor_pane)

        self.main_splitter.setSizes([340, 560])
        main_layout.addWidget(self.main_splitter, 1)

    def _create_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #12141C;
                border-right: 1px solid #282C40;
            }
        """)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(8)

        # Title / Header
        title_lbl = QLabel("📖 Knowledge")
        title_lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title_lbl.setStyleSheet("color: #F1F5F9; background: transparent;")
        layout.addWidget(title_lbl)

        layout.addSpacing(8)

        # Quick Views
        self.btn_all_notes = QPushButton("📝  All Notes")
        self.btn_favorites = QPushButton("⭐  Favorites")
        self.btn_recent = QPushButton("🕒  Recent")

        for btn in (self.btn_all_notes, self.btn_favorites, self.btn_recent):
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._sidebar_btn_style())
            layout.addWidget(btn)

        self.btn_all_notes.setChecked(True)
        self.btn_all_notes.clicked.connect(lambda: self._select_category("all"))
        self.btn_favorites.clicked.connect(lambda: self._select_category("favorites"))
        self.btn_recent.clicked.connect(lambda: self._select_category("recent"))

        layout.addSpacing(12)

        # Folders Header Row
        folders_header = QHBoxLayout()
        folders_lbl = QLabel("FOLDERS")
        folders_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        folders_lbl.setStyleSheet("color: #64748B; background: transparent;")
        folders_header.addWidget(folders_lbl)
        folders_header.addStretch()

        self.btn_add_folder = QPushButton("➕")
        self.btn_add_folder.setFixedSize(22, 22)
        self.btn_add_folder.setToolTip("Create Root Folder")
        self.btn_add_folder.setCursor(Qt.PointingHandCursor)
        self.btn_add_folder.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94A3B8;
                border: none;
                font-size: 11px;
            }
            QPushButton:hover {
                color: #38BDF8;
                background-color: #1E2235;
                border-radius: 4px;
            }
        """)
        self.btn_add_folder.clicked.connect(self._prompt_create_folder)
        folders_header.addWidget(self.btn_add_folder)
        layout.addLayout(folders_header)

        # Folders Tree
        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setStyleSheet("""
            QTreeWidget {
                background-color: transparent;
                border: none;
                color: #CBD5E1;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 4px 6px;
                border-radius: 4px;
            }
            QTreeWidget::item:hover {
                background-color: #1E2235;
                color: #F1F5F9;
            }
            QTreeWidget::item:selected {
                background-color: #283556;
                color: #38BDF8;
                font-weight: bold;
            }
        """)
        self.folder_tree.itemClicked.connect(self._on_folder_tree_clicked)
        self.folder_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.folder_tree.customContextMenuRequested.connect(self._on_folder_context_menu)
        layout.addWidget(self.folder_tree, 1)

        return sidebar

    def _sidebar_btn_style(self) -> str:
        return """
            QPushButton {
                text-align: left;
                padding: 7px 10px;
                background-color: transparent;
                color: #94A3B8;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #1E2235;
                color: #F1F5F9;
            }
            QPushButton:checked {
                background-color: #283556;
                color: #38BDF8;
                font-weight: bold;
            }
        """

    def _create_cards_pane(self) -> QWidget:
        pane = QWidget()
        pane.setStyleSheet("background-color: #141620;")
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # Header Bar: View Title + "+ New Note" Button
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        self.view_title_label = QLabel("All Notes")
        self.view_title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.view_title_label.setStyleSheet("color: #F1F5F9;")
        header_row.addWidget(self.view_title_label)

        self.count_badge = QLabel("0")
        self.count_badge.setStyleSheet("""
            background-color: #1E2235;
            color: #94A3B8;
            font-size: 11px;
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 10px;
        """)
        header_row.addWidget(self.count_badge)

        header_row.addStretch()

        self.btn_new_note = QPushButton("➕  New Note")
        self.btn_new_note.setCursor(Qt.PointingHandCursor)
        self.btn_new_note.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
        """)
        self.btn_new_note.clicked.connect(self.create_new_note)
        header_row.addWidget(self.btn_new_note)

        layout.addLayout(header_row)

        # Search Bar
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search title, content, tags...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #1E2029;
                color: #F1F5F9;
                border: 1px solid #2E3342;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #38BDF8;
            }
        """)
        self.search_edit.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_edit)

        # Scroll Area with Card Stack / Flow
        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setFrameShape(QFrame.NoFrame)
        self.cards_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 4, 4, 4)
        self.cards_layout.setSpacing(8)
        self.cards_layout.setAlignment(Qt.AlignTop)

        # Empty State Label
        self.empty_state_label = QLabel("No notes found.")
        self.empty_state_label.setAlignment(Qt.AlignCenter)
        self.empty_state_label.setWordWrap(True)
        self.empty_state_label.setStyleSheet("color: #64748B; font-size: 13px; padding: 40px 16px;")
        self.cards_layout.addWidget(self.empty_state_label)

        self.cards_scroll.setWidget(self.cards_container)
        layout.addWidget(self.cards_scroll, 1)

        return pane

    def _create_editor_pane(self) -> QWidget:
        pane = QWidget()
        pane.setStyleSheet("background-color: #0F1117;")
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Editor Stack: Placeholder (when no doc selected) or Active Editor
        self.editor_controls_widget = QWidget()
        editor_layout = QVBoxLayout(self.editor_controls_widget)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(10)

        # Top Bar: Title + Star + Folder Picker + Delete Button
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(8)

        self.editor_title = QLineEdit()
        self.editor_title.setPlaceholderText("Note Title...")
        self.editor_title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        self.editor_title.setStyleSheet("""
            QLineEdit {
                background: transparent;
                color: #F1F5F9;
                border: none;
                padding: 4px 0;
            }
            QLineEdit:focus {
                border-bottom: 1px solid #38BDF8;
            }
        """)
        self.editor_title.textChanged.connect(self._on_editor_content_modified)
        top_bar.addWidget(self.editor_title, 1)

        self.editor_fav_btn = QPushButton("☆")
        self.editor_fav_btn.setFixedSize(30, 30)
        self.editor_fav_btn.setCursor(Qt.PointingHandCursor)
        self.editor_fav_btn.setToolTip("Toggle Favorite")
        self.editor_fav_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #282C40;
                border-radius: 6px;
                color: #64748B;
                font-size: 15px;
            }
            QPushButton:hover {
                border-color: #F59E0B;
                color: #F59E0B;
            }
        """)
        self.editor_fav_btn.clicked.connect(self._toggle_active_favorite)
        top_bar.addWidget(self.editor_fav_btn)

        self.editor_folder_cb = QComboBox()
        self.editor_folder_cb.setStyleSheet("""
            QComboBox {
                background-color: #1E2029;
                color: #CBD5E1;
                border: 1px solid #2E3342;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
            }
        """)
        self.editor_folder_cb.currentIndexChanged.connect(self._on_editor_folder_changed)
        top_bar.addWidget(self.editor_folder_cb)

        self.editor_delete_btn = QPushButton("🗑️")
        self.editor_delete_btn.setFixedSize(30, 30)
        self.editor_delete_btn.setCursor(Qt.PointingHandCursor)
        self.editor_delete_btn.setToolTip("Delete Note")
        self.editor_delete_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #282C40;
                border-radius: 6px;
                color: #EF4444;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #EF4444;
                color: #FFFFFF;
            }
        """)
        self.editor_delete_btn.clicked.connect(self._delete_active_document)
        top_bar.addWidget(self.editor_delete_btn)

        editor_layout.addLayout(top_bar)

        # Tags Input
        tags_row = QHBoxLayout()
        tags_row.setSpacing(6)
        tags_icon = QLabel("🏷️")
        tags_icon.setStyleSheet("background: transparent; font-size: 12px;")
        tags_row.addWidget(tags_icon)

        self.editor_tags = QLineEdit()
        self.editor_tags.setPlaceholderText("Add tags separated by comma (e.g. gameplay, lore, vfx)...")
        self.editor_tags.setStyleSheet("""
            QLineEdit {
                background-color: #161822;
                color: #38BDF8;
                border: 1px solid #282C40;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #38BDF8;
            }
        """)
        self.editor_tags.textChanged.connect(self._on_editor_content_modified)
        tags_row.addWidget(self.editor_tags, 1)
        editor_layout.addLayout(tags_row)

        # Relationships Section (Linked Projects, Assets, Lab Nodes)
        self.rel_section = QFrame()
        self.rel_section.setStyleSheet("""
            QFrame {
                background-color: #161822;
                border: 1px solid #232738;
                border-radius: 6px;
                padding: 2px;
            }
        """)
        rel_layout = QVBoxLayout(self.rel_section)
        rel_layout.setContentsMargins(6, 6, 6, 6)
        rel_layout.setSpacing(6)

        rel_header_row = QHBoxLayout()
        rel_title_icon = QLabel("🔗")
        rel_title_icon.setStyleSheet("background: transparent; font-size: 11px;")
        rel_header_row.addWidget(rel_title_icon)

        rel_title = QLabel("Relationships")
        rel_title.setFont(QFont("Segoe UI", 9, QFont.Bold))
        rel_title.setStyleSheet("color: #94A3B8; background: transparent;")
        rel_header_row.addWidget(rel_title)

        self.rel_count_badge = QLabel("0")
        self.rel_count_badge.setStyleSheet("""
            background-color: #283556;
            color: #38BDF8;
            border-radius: 8px;
            padding: 1px 6px;
            font-size: 10px;
            font-weight: bold;
        """)
        rel_header_row.addWidget(self.rel_count_badge)

        rel_header_row.addStretch()

        self.btn_add_rel = QPushButton("➕ Link Item")
        self.btn_add_rel.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_add_rel.setStyleSheet("""
            QPushButton {
                background-color: #1E2235;
                color: #38BDF8;
                border: 1px solid #2E3650;
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #283556;
                color: #FFFFFF;
                border-color: #38BDF8;
            }
        """)
        self.btn_add_rel.clicked.connect(self._on_add_relationship_clicked)
        rel_header_row.addWidget(self.btn_add_rel)
        rel_layout.addLayout(rel_header_row)

        # Chips container
        self.rel_chips_widget = QWidget()
        self.rel_chips_widget.setStyleSheet("background: transparent;")
        self.rel_chips_layout = QHBoxLayout(self.rel_chips_widget)
        self.rel_chips_layout.setContentsMargins(0, 0, 0, 0)
        self.rel_chips_layout.setSpacing(6)
        self.rel_chips_layout.setAlignment(Qt.AlignLeft)

        # Placeholder label when no relationships linked
        self.rel_placeholder_label = QLabel("No linked projects, assets, or lab nodes.")
        self.rel_placeholder_label.setStyleSheet("color: #475569; font-size: 11px; font-style: italic; background: transparent;")
        self.rel_chips_layout.addWidget(self.rel_placeholder_label)

        # Scroll area for chips if many
        self.rel_scroll = QScrollArea()
        self.rel_scroll.setWidgetResizable(True)
        self.rel_scroll.setFixedHeight(36)
        self.rel_scroll.setFrameShape(QFrame.NoFrame)
        self.rel_scroll.setStyleSheet("background: transparent; border: none; padding: 0;")
        self.rel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.rel_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.rel_scroll.setWidget(self.rel_chips_widget)

        rel_layout.addWidget(self.rel_scroll)
        editor_layout.addWidget(self.rel_section)

        # AI Assist Widget
        self.ai_assist_widget = KnowledgeAIAssistWidget(
            self.knowledge_ai_service,
            knowledge_assistant_service=self.knowledge_assistant_service,
        )
        self.ai_assist_widget.insert_content_requested.connect(self._on_ai_insert_content_requested)
        self.ai_assist_widget.apply_tags_requested.connect(self._on_ai_apply_tags_requested)
        self.ai_assist_widget.open_settings_requested.connect(self._on_ai_open_settings_requested)
        editor_layout.addWidget(self.ai_assist_widget)

        # Content Text Editor
        self.editor_content = QTextEdit()
        self.editor_content.setPlaceholderText("Start writing your note here in plain text or markdown...")
        self.editor_content.setFont(QFont("Segoe UI", 11))
        self.editor_content.setStyleSheet("""
            QTextEdit {
                background-color: #12141C;
                color: #F1F5F9;
                border: 1px solid #282C40;
                border-radius: 6px;
                padding: 12px;
                line-height: 1.5;
            }
            QTextEdit:focus {
                border: 1px solid #38BDF8;
            }
        """)
        self.editor_content.textChanged.connect(self._on_editor_content_modified)
        editor_layout.addWidget(self.editor_content, 1)

        # Footer Bar: Word count + Last modified
        footer_row = QHBoxLayout()
        self.editor_stats_label = QLabel("0 words  •  0 chars")
        self.editor_stats_label.setStyleSheet("color: #64748B; font-size: 11px;")
        footer_row.addWidget(self.editor_stats_label)

        footer_row.addStretch()

        self.editor_status_label = QLabel("Saved")
        self.editor_status_label.setStyleSheet("color: #10B981; font-size: 11px;")
        footer_row.addWidget(self.editor_status_label)

        editor_layout.addLayout(footer_row)
        layout.addWidget(self.editor_controls_widget)

        # Placeholder label when no doc is selected
        self.editor_placeholder = QLabel("Select a note from the list to view and edit,\nor click '+ New Note' to create a new one.")
        self.editor_placeholder.setAlignment(Qt.AlignCenter)
        self.editor_placeholder.setStyleSheet("color: #64748B; font-size: 13px;")
        layout.addWidget(self.editor_placeholder)

        self.editor_controls_widget.setVisible(False)
        self.editor_placeholder.setVisible(True)

        return pane

    # -------------------------------------------------------------------------
    # Data Loading & Rendering
    # -------------------------------------------------------------------------

    def refresh(self):
        """Refresh the entire Knowledge workspace UI (folders, categories, document cards)."""
        if not self.knowledge_service:
            return

        self._refresh_folders_tree()
        self._refresh_folder_picker()
        self._refresh_documents_list()

    def _refresh_folders_tree(self):
        """Populate hierarchical folders in the left sidebar tree."""
        if not self.knowledge_service:
            return

        self.folder_tree.blockSignals(True)
        self.folder_tree.clear()
        self._folder_tree_items.clear()

        all_folders = self.knowledge_service.list_folders()
        # Build hierarchy
        folder_map = {f.id: f for f in all_folders}
        children_map: Dict[Optional[str], List[KnowledgeFolder]] = {}
        for f in all_folders:
            p_id = f.parent_id if f.parent_id in folder_map else None
            children_map.setdefault(p_id, []).append(f)

        def add_nodes(parent_id: Optional[str], parent_item: Optional[QTreeWidgetItem]):
            for folder in children_map.get(parent_id, []):
                doc_count = len(self.knowledge_service.list_documents(folder_id=folder.id, recursive=False))
                display_text = f"📁  {folder.name} ({doc_count})"
                item = QTreeWidgetItem([display_text])
                item.setData(0, Qt.UserRole, folder.id)
                self._folder_tree_items[folder.id] = item

                if parent_item:
                    parent_item.addChild(item)
                else:
                    self.folder_tree.addTopLevelItem(item)

                item.setExpanded(True)
                add_nodes(folder.id, item)

        add_nodes(None, None)
        self.folder_tree.blockSignals(False)

        # Restore selection
        if self._current_category == "folder" and self._current_folder_id in self._folder_tree_items:
            self.folder_tree.setCurrentItem(self._folder_tree_items[self._current_folder_id])

    def _refresh_folder_picker(self):
        """Update the folder picker in the editor pane."""
        if not self.knowledge_service:
            return

        self.editor_folder_cb.blockSignals(True)
        self.editor_folder_cb.clear()
        self.editor_folder_cb.addItem("📁 Root (No Folder)", None)

        all_folders = self.knowledge_service.list_folders()
        for f in all_folders:
            path = self.knowledge_service.get_folder_path(f.id)
            path_str = " / ".join(p.name for p in path)
            self.editor_folder_cb.addItem(f"📁 {path_str}", f.id)

        self.editor_folder_cb.blockSignals(False)

    def _refresh_documents_list(self):
        """Fetch and render document cards matching the active category/folder and search query."""
        if not self.knowledge_service:
            return

        # Fetch matching documents
        if self._search_query:
            search_folder = self._current_folder_id if self._current_category == "folder" else _UNSET
            docs = self.knowledge_service.search(
                self._search_query,
                folder_id=search_folder,
                favorite_only=(self._current_category == "favorites"),
            )
        elif self._current_category == "favorites":
            docs = self.knowledge_service.list_documents(favorite_only=True)
        elif self._current_category == "recent":
            docs = self.knowledge_service.list_documents()
            docs.sort(key=lambda d: getattr(d, "modified", "") or getattr(d, "created", ""), reverse=True)
        elif self._current_category == "folder" and self._current_folder_id:
            docs = self.knowledge_service.list_documents(folder_id=self._current_folder_id, recursive=False)
        else:
            docs = self.knowledge_service.list_documents()

        # Update view title & badge
        if self._search_query:
            self.view_title_label.setText(f"Search: '{self._search_query}'")
        elif self._current_category == "favorites":
            self.view_title_label.setText("⭐ Favorites")
        elif self._current_category == "recent":
            self.view_title_label.setText("🕒 Recent Notes")
        elif self._current_category == "folder" and self._current_folder_id:
            fld = self.knowledge_service.get_folder(self._current_folder_id)
            self.view_title_label.setText(f"📁 {fld.name if fld else 'Folder'}")
        else:
            self.view_title_label.setText("📝 All Notes")

        self.count_badge.setText(str(len(docs)))

        # Clear existing cards from layout
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w and w != self.empty_state_label:
                w.setParent(None)
                w.deleteLater()

        self._cards.clear()

        if not docs:
            # Show empty state
            if self._search_query:
                self.empty_state_label.setText(f"No search results for '{self._search_query}'.")
            elif self._current_category == "favorites":
                self.empty_state_label.setText("No favorites yet.\nStar any note to add it here.")
            elif self._current_category == "folder":
                self.empty_state_label.setText("No notes in this folder.\nClick '+ New Note' to create one.")
            else:
                self.empty_state_label.setText("No notes yet.\nClick '+ New Note' to start writing.")
            self.cards_layout.addWidget(self.empty_state_label)
            self.empty_state_label.setVisible(True)

            # If current doc is not in docs, clear editor
            if self._current_doc_id:
                self._load_document_into_editor(None)
            return

        self.empty_state_label.setVisible(False)

        # Create cards
        for doc in docs:
            card = KnowledgeCard(doc)
            card.clicked.connect(self._on_card_clicked)
            card.favorite_toggled.connect(self._on_card_favorite_toggled)
            self._cards[doc.id] = card
            self.cards_layout.addWidget(card)

        # Restore selection
        if self._current_doc_id and self._current_doc_id in self._cards:
            self._select_document(self._current_doc_id, emit_signal=False)
        elif docs:
            self._select_document(docs[0].id, emit_signal=True)

    # -------------------------------------------------------------------------
    # Document Selection & Editor Population
    # -------------------------------------------------------------------------

    def show_document(self, doc_id: str) -> bool:
        """Select, highlight, and display an exact Knowledge document in the editor."""
        if not self.knowledge_service or not doc_id:
            return False

        doc = self.knowledge_service.get_document(doc_id)
        if not doc:
            return False

        # Reset search filter
        self._search_query = ""
        if hasattr(self, "search_input") and self.search_input:
            self.search_input.blockSignals(True)
            self.search_input.clear()
            self.search_input.blockSignals(False)

        # Set category or folder
        if doc.folder_id:
            self._current_category = "folder"
            self._current_folder_id = doc.folder_id
        else:
            self._current_category = "all"
            self._current_folder_id = None

        self.refresh()
        self._select_document(doc_id, emit_signal=True)
        return True

    def _select_document(self, doc_id: str, emit_signal: bool = True):
        """Select a document card, highlight it, and load it into the editor."""
        self._current_doc_id = doc_id
        for cid, card in self._cards.items():
            card.set_selected(cid == doc_id)

        if not self.knowledge_service:
            return

        doc = self.knowledge_service.get_document(doc_id)
        self._load_document_into_editor(doc)

        if emit_signal and doc:
            try:
                self.document_selected.emit(doc)
            except Exception:
                pass

    def _load_document_into_editor(self, doc: Optional[KnowledgeDocument]):
        """Load document into the editor fields without triggering change events."""
        self._is_updating_editor = True
        if not doc:
            self._current_doc_id = None
            self.editor_controls_widget.setVisible(False)
            self.editor_placeholder.setVisible(True)
            if hasattr(self, "ai_assist_widget"):
                self.ai_assist_widget.set_document(None)
            self._is_updating_editor = False
            return

        self.editor_placeholder.setVisible(False)
        self.editor_controls_widget.setVisible(True)
        if hasattr(self, "ai_assist_widget"):
            self.ai_assist_widget.set_document(doc)
            curr_proj = getattr(self._context, "current_project", None) if self._context else None
            proj_id = getattr(curr_proj, "name", None) or (doc.project_ids[0] if getattr(doc, "project_ids", None) else None)
            self.ai_assist_widget.set_project_id(proj_id)

        self.editor_title.setText(doc.title or "")
        self.editor_content.setPlainText(doc.content or "")
        self.editor_tags.setText(", ".join(doc.tags) if doc.tags else "")

        # Favorite button
        if getattr(doc, "favorite", False):
            self.editor_fav_btn.setText("⭐")
            self.editor_fav_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: 1px solid #F59E0B;
                    border-radius: 6px;
                    color: #F59E0B;
                    font-size: 15px;
                }
            """)
        else:
            self.editor_fav_btn.setText("☆")
            self.editor_fav_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: 1px solid #282C40;
                    border-radius: 6px;
                    color: #64748B;
                    font-size: 15px;
                }
            """)

        # Folder dropdown
        self.editor_folder_cb.blockSignals(True)
        idx = 0
        for i in range(self.editor_folder_cb.count()):
            if self.editor_folder_cb.itemData(i) == doc.folder_id:
                idx = i
                break
        self.editor_folder_cb.setCurrentIndex(idx)
        self.editor_folder_cb.blockSignals(False)

        self._update_editor_stats(doc.content or "")
        self._refresh_relationships_display(doc)
        self.editor_status_label.setText("Saved")
        self.editor_status_label.setStyleSheet("color: #10B981; font-size: 11px;")
        self._is_updating_editor = False

    def _on_ai_insert_content_requested(self, text: str, position: str):
        """Insert AI generated text at top or bottom of current document content."""
        if not self._current_doc_id:
            return
        curr_text = self.editor_content.toPlainText().strip()
        if not curr_text:
            new_text = text.strip()
        elif position == "top":
            new_text = f"{text.strip()}\n\n{curr_text}"
        else:
            new_text = f"{curr_text}\n\n{text.strip()}"
        self.editor_content.setPlainText(new_text)
        self._save_active_document()

    def _on_ai_apply_tags_requested(self, tags: List[str]):
        """Merge AI suggested tags into current document tags."""
        if not self._current_doc_id or not tags:
            return
        raw_existing = self.editor_tags.text()
        existing_tags = [t.strip() for t in raw_existing.split(",") if t.strip()]
        existing_lower = set(t.lower() for t in existing_tags)
        for tag in tags:
            if tag.lower() not in existing_lower:
                existing_tags.append(tag)
                existing_lower.add(tag.lower())
        self.editor_tags.setText(", ".join(existing_tags))
        self._save_active_document()

    def _on_ai_open_settings_requested(self, section: str = "ai"):
        """Handle request to open Settings dialog from AI Assist widget."""
        try:
            if self.context and getattr(self.context, "open_settings", None):
                self.context.open_settings(section)
            else:
                win = self.window()
                if hasattr(win, "open_settings"):
                    win.open_settings(section)
        except Exception:
            pass

    def _update_editor_stats(self, content: str):
        words = len(content.split()) if content.strip() else 0
        chars = len(content)
        self.editor_stats_label.setText(f"{words} words  •  {chars} chars")

    def _refresh_relationships_display(self, doc: Optional[KnowledgeDocument]):
        """Render relationship chips for active document."""
        # Clear existing chips (except placeholder)
        while self.rel_chips_layout.count():
            item = self.rel_chips_layout.takeAt(0)
            w = item.widget()
            if w and w != self.rel_placeholder_label:
                w.setParent(None)
                w.deleteLater()

        if not doc:
            self.rel_placeholder_label.setVisible(True)
            self.rel_chips_layout.addWidget(self.rel_placeholder_label)
            self.rel_count_badge.setText("0")
            return

        total_count = (
            len(getattr(doc, "project_ids", [])) +
            len(getattr(doc, "library_asset_ids", [])) +
            len(getattr(doc, "project_asset_refs", [])) +
            len(getattr(doc, "lab_node_ids", []))
        )
        self.rel_count_badge.setText(str(total_count))

        if total_count == 0:
            self.rel_placeholder_label.setVisible(True)
            self.rel_chips_layout.addWidget(self.rel_placeholder_label)
            return

        self.rel_placeholder_label.setVisible(False)

        # 1. Projects
        for proj_id in getattr(doc, "project_ids", []):
            chip = RelationshipChip("project", {"project_id": proj_id}, context=self._context)
            chip.clicked.connect(self._on_relationship_chip_clicked)
            chip.remove_requested.connect(self._on_relationship_chip_removed)
            self.rel_chips_layout.addWidget(chip)

        # 2. Library Assets
        for asset_id in getattr(doc, "library_asset_ids", []):
            chip = RelationshipChip("library_asset", {"asset_id": asset_id}, context=self._context)
            chip.clicked.connect(self._on_relationship_chip_clicked)
            chip.remove_requested.connect(self._on_relationship_chip_removed)
            self.rel_chips_layout.addWidget(chip)

        # 3. Project Assets
        for ref in getattr(doc, "project_asset_refs", []):
            chip = RelationshipChip("project_asset", ref, context=self._context)
            chip.clicked.connect(self._on_relationship_chip_clicked)
            chip.remove_requested.connect(self._on_relationship_chip_removed)
            self.rel_chips_layout.addWidget(chip)

        # 4. Lab Nodes
        for node_id in getattr(doc, "lab_node_ids", []):
            chip = RelationshipChip("lab_node", {"node_id": node_id}, context=self._context)
            chip.clicked.connect(self._on_relationship_chip_clicked)
            chip.remove_requested.connect(self._on_relationship_chip_removed)
            self.rel_chips_layout.addWidget(chip)

    def _on_add_relationship_clicked(self):
        """Open the Add Knowledge Relationship Dialog and associate selected target."""
        if not self.knowledge_service or not self._current_doc_id:
            return

        doc = self.knowledge_service.get_document(self._current_doc_id)
        if not doc:
            return

        dlg = AddKnowledgeRelationshipDialog(self._context, self, current_doc=doc)
        if dlg.exec() == AddKnowledgeRelationshipDialog.Accepted:
            result = dlg.get_selected_relationship()
            if result:
                rel_type, target_data = result
                updated_doc = None
                if rel_type == "project":
                    updated_doc = self.knowledge_service.add_project_relationship(
                        self._current_doc_id, target_data.get("project_id", "")
                    )
                elif rel_type == "library_asset":
                    updated_doc = self.knowledge_service.add_library_asset_relationship(
                        self._current_doc_id, target_data.get("asset_id", "")
                    )
                elif rel_type == "project_asset":
                    updated_doc = self.knowledge_service.add_project_asset_relationship(
                        self._current_doc_id,
                        target_data.get("project_id", ""),
                        target_data.get("asset_id", ""),
                        target_data.get("relative_path", ""),
                        category=target_data.get("category"),
                    )
                elif rel_type == "lab_node":
                    updated_doc = self.knowledge_service.add_lab_node_relationship(
                        self._current_doc_id,
                        target_data.get("node_id", ""),
                        target_data.get("board_id"),
                        target_data.get("project_id")
                    )

                if updated_doc:
                    self._refresh_relationships_display(updated_doc)
                    try:
                        self.document_selected.emit(updated_doc)
                    except Exception:
                        pass

    def _on_relationship_chip_clicked(self, rel_type: str, data: dict):
        """Navigate to the source workspace or entity represented by the clicked chip via unified payload."""
        if not self._context:
            return

        from core.navigation import NavigationPayload, NavigationTargetType
        wm = getattr(self._context, "workspace_manager", None)
        if not wm:
            return

        if rel_type == "project":
            payload = NavigationPayload.for_project(data.get("project_id", ""))
            wm.navigate(payload)

        elif rel_type == "library_asset":
            payload = NavigationPayload.for_library_asset(data.get("asset_id", ""), metadata=data)
            wm.navigate(payload)

        elif rel_type == "project_asset":
            payload = NavigationPayload.for_project_asset(
                data.get("project_id", ""),
                data.get("asset_id", "") or data.get("relative_path", ""),
                rel_path=data.get("relative_path"),
                category=data.get("category"),
                metadata=data,
            )
            wm.navigate(payload)

        elif rel_type == "lab_node":
            payload = NavigationPayload.for_lab_node(
                data.get("node_id", ""),
                board_id=data.get("board_id"),
                project_or_name=data.get("project_id"),
                metadata=data,
            )
            wm.navigate(payload)

    def _on_relationship_chip_removed(self, rel_type: str, data: dict):
        """Remove relationship from active document and refresh UI."""
        if not self.knowledge_service or not self._current_doc_id:
            return

        updated_doc = None
        if rel_type == "project":
            updated_doc = self.knowledge_service.remove_project_relationship(
                self._current_doc_id, data.get("project_id", "")
            )
        elif rel_type == "library_asset":
            updated_doc = self.knowledge_service.remove_library_asset_relationship(
                self._current_doc_id, data.get("asset_id", "")
            )
        elif rel_type == "project_asset":
            updated_doc = self.knowledge_service.remove_project_asset_relationship(
                self._current_doc_id, data.get("project_id", ""), data.get("asset_id", "")
            )
        elif rel_type == "lab_node":
            updated_doc = self.knowledge_service.remove_lab_node_relationship(
                self._current_doc_id, data.get("node_id", "")
            )

        if updated_doc:
            self._refresh_relationships_display(updated_doc)
            try:
                self.document_selected.emit(updated_doc)
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Editor Autosave & Field Updates
    # -------------------------------------------------------------------------

    def _on_editor_content_modified(self):
        if self._is_updating_editor or not self._current_doc_id:
            return

        self.editor_status_label.setText("Saving...")
        self.editor_status_label.setStyleSheet("color: #F59E0B; font-size: 11px;")
        self._update_editor_stats(self.editor_content.toPlainText())
        self._autosave_timer.start()

    def _save_active_document(self):
        """Persist changes in the active document to KnowledgeService."""
        if not self.knowledge_service or not self._current_doc_id:
            return

        new_title = self.editor_title.text().strip() or "Untitled Note"
        new_content = self.editor_content.toPlainText()
        raw_tags = self.editor_tags.text()
        tags_list = [t.strip() for t in raw_tags.split(",") if t.strip()]

        updated_doc = self.knowledge_service.update_document(
            self._current_doc_id,
            title=new_title,
            content=new_content,
            tags=tags_list,
        )

        if updated_doc:
            self.editor_status_label.setText("Saved")
            self.editor_status_label.setStyleSheet("color: #10B981; font-size: 11px;")

            # Update corresponding card preview immediately
            if updated_doc.id in self._cards:
                self._cards[updated_doc.id].update_document(updated_doc)

            # Notify Inspector
            try:
                self.document_selected.emit(updated_doc)
            except Exception:
                pass

    def _toggle_active_favorite(self):
        if not self.knowledge_service or not self._current_doc_id:
            return

        doc = self.knowledge_service.get_document(self._current_doc_id)
        if not doc:
            return

        new_fav = not bool(getattr(doc, "favorite", False))
        updated = self.knowledge_service.update_document(doc.id, favorite=new_fav)
        if updated:
            self._load_document_into_editor(updated)
            if updated.id in self._cards:
                self._cards[updated.id].update_document(updated)
            if self._current_category == "favorites" and not new_fav:
                self._refresh_documents_list()
            try:
                self.document_selected.emit(updated)
            except Exception:
                pass

    def _on_editor_folder_changed(self, index: int):
        if self._is_updating_editor or not self.knowledge_service or not self._current_doc_id:
            return

        target_folder_id = self.editor_folder_cb.itemData(index)
        updated = self.knowledge_service.move_document(self._current_doc_id, target_folder_id)
        if updated:
            self._refresh_folders_tree()
            if self._current_category == "folder" and self._current_folder_id != target_folder_id:
                self._refresh_documents_list()
            try:
                self.document_selected.emit(updated)
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Actions: Document Creation, Deletion & Category Navigation
    # -------------------------------------------------------------------------

    def create_new_note(self):
        """Create a new note in active folder or root and focus editor."""
        if not self.knowledge_service:
            return

        folder_id = self._current_folder_id if self._current_category == "folder" else None
        doc = self.knowledge_service.create_document(
            title="Untitled Note",
            content="",
            folder_id=folder_id,
        )

        self._refresh_folders_tree()
        self._refresh_documents_list()
        self._select_document(doc.id, emit_signal=True)

        # Focus title input for immediate typing
        self.editor_title.setFocus()
        self.editor_title.selectAll()

    def _delete_active_document(self):
        """Delete active note with confirmation."""
        if not self.knowledge_service or not self._current_doc_id:
            return

        doc = self.knowledge_service.get_document(self._current_doc_id)
        if not doc:
            return

        reply = QMessageBox.question(
            self,
            "Delete Note",
            f"Are you sure you want to delete '{doc.title}'?\n\nThis will only delete the note and will not affect any referenced project files.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            doc_id = self._current_doc_id
            self.knowledge_service.delete_document(doc_id)
            self._current_doc_id = None
            self._load_document_into_editor(None)
            self._refresh_folders_tree()
            self._refresh_documents_list()
            try:
                self.document_selected.emit(None)
            except Exception:
                pass

    def _select_category(self, category: str):
        """Switch active category (all, favorites, recent)."""
        self._current_category = category
        self._current_folder_id = None

        self.btn_all_notes.setChecked(category == "all")
        self.btn_favorites.setChecked(category == "favorites")
        self.btn_recent.setChecked(category == "recent")
        self.folder_tree.clearSelection()

        self._refresh_documents_list()

    def _on_folder_tree_clicked(self, item: QTreeWidgetItem, column: int):
        """Switch active category to selected folder."""
        folder_id = item.data(0, Qt.UserRole)
        self._current_category = "folder"
        self._current_folder_id = folder_id

        self.btn_all_notes.setChecked(False)
        self.btn_favorites.setChecked(False)
        self.btn_recent.setChecked(False)

        self._refresh_documents_list()

    def _on_card_clicked(self, doc: KnowledgeDocument):
        self._select_document(doc.id, emit_signal=True)

    def _on_card_favorite_toggled(self, doc_id: str, new_fav: bool):
        if not self.knowledge_service:
            return
        updated = self.knowledge_service.set_favorite(doc_id, new_fav)
        if updated:
            if updated.id in self._cards:
                self._cards[updated.id].update_document(updated)
            if self._current_doc_id == doc_id:
                self._load_document_into_editor(updated)
            if self._current_category == "favorites" and not new_fav:
                self._refresh_documents_list()
            try:
                self.document_selected.emit(updated)
            except Exception:
                pass

    def _on_search_changed(self, text: str):
        if self._autosave_timer.isActive():
            self._autosave_timer.stop()
            self._save_active_document()
        self._search_query = text.strip()
        self._refresh_documents_list()

    # -------------------------------------------------------------------------
    # Folder Management Actions
    # -------------------------------------------------------------------------

    def _prompt_create_folder(self, parent_id: Optional[str] = None):
        if not self.knowledge_service:
            return

        name, ok = QInputDialog.getText(self, "New Folder", "Folder Name:")
        if ok and name.strip():
            fld = self.knowledge_service.create_folder(name=name.strip(), parent_id=parent_id)
            self._refresh_folders_tree()
            self._refresh_folder_picker()
            # Navigate to newly created folder
            self._current_category = "folder"
            self._current_folder_id = fld.id
            self.btn_all_notes.setChecked(False)
            self.btn_favorites.setChecked(False)
            self.btn_recent.setChecked(False)
            if fld.id in self._folder_tree_items:
                self.folder_tree.setCurrentItem(self._folder_tree_items[fld.id])
            self._refresh_documents_list()

    def _on_folder_context_menu(self, pos):
        item = self.folder_tree.itemAt(pos)
        if not item or not self.knowledge_service:
            return

        folder_id = item.data(0, Qt.UserRole)
        folder = self.knowledge_service.get_folder(folder_id)
        if not folder:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1E2029;
                color: #F1F5F9;
                border: 1px solid #343847;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #38BDF8;
                color: #0F172A;
            }
        """)

        action_new_sub = menu.addAction("➕ New Subfolder")
        action_rename = menu.addAction("✏️ Rename Folder")
        action_delete = menu.addAction("🗑️ Delete Folder")

        chosen = menu.exec_(self.folder_tree.viewport().mapToGlobal(pos))
        if chosen == action_new_sub:
            self._prompt_create_folder(parent_id=folder.id)
        elif chosen == action_rename:
            new_name, ok = QInputDialog.getText(self, "Rename Folder", "New Name:", text=folder.name)
            if ok and new_name.strip():
                self.knowledge_service.rename_folder(folder.id, new_name.strip())
                self._refresh_folders_tree()
                self._refresh_folder_picker()
                if self._current_folder_id == folder.id:
                    self.view_title_label.setText(f"📁 {new_name.strip()}")
        elif chosen == action_delete:
            self._prompt_delete_folder(folder)

    def _prompt_delete_folder(self, folder: KnowledgeFolder):
        child_docs = self.knowledge_service.list_documents(folder_id=folder.id, recursive=False)
        child_folders = [f for f in self.knowledge_service.list_folders() if f.parent_id == folder.id]

        if child_docs or child_folders:
            reply = QMessageBox.question(
                self,
                "Delete Folder",
                f"Folder '{folder.name}' contains {len(child_folders)} subfolders and {len(child_docs)} notes.\n\n"
                "Do you want to move its contents to the parent folder before deleting?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                self.knowledge_service.delete_folder(folder.id, safe_mode=True, reparent_children=True)
            elif reply == QMessageBox.No:
                # Force cascade delete within knowledge catalog only
                self.knowledge_service.delete_folder(folder.id, safe_mode=False, reparent_children=False)
            else:
                return
        else:
            self.knowledge_service.delete_folder(folder.id, safe_mode=True)

        if self._current_folder_id == folder.id:
            self._select_category("all")
        else:
            self._refresh_folders_tree()
            self._refresh_folder_picker()
            self._refresh_documents_list()

    # -------------------------------------------------------------------------
    # Service Signal Handlers (Live Cross-Component Reactivity)
    # -------------------------------------------------------------------------

    def _on_service_doc_created(self, doc):
        pass  # Handled directly in create_new_note

    def _on_service_doc_updated(self, doc):
        if not doc:
            return
        if doc.id in self._cards:
            self._cards[doc.id].update_document(doc)
        if self._current_doc_id == doc.id and not self._is_updating_editor:
            # Sync editor if updated externally (e.g. from Inspector)
            if self.editor_title.text() != doc.title:
                self.editor_title.setText(doc.title)
            if self.editor_tags.text() != ", ".join(doc.tags):
                self.editor_tags.setText(", ".join(doc.tags))

    def _on_service_doc_deleted(self, doc_id: str):
        if self._current_doc_id == doc_id:
            self._load_document_into_editor(None)
        self._refresh_documents_list()

    def _on_service_folder_changed(self, *args):
        self._refresh_folders_tree()
        self._refresh_folder_picker()
