"""Knowledge AI Assist UI Component for CreativeWorkspace with Context Transparency and Ask AI.

Provides asynchronous, non-blocking UI for Knowledge AI actions:
1. Summarize Document (preview -> explicit insert at top/bottom)
2. Generate Tags (selectable suggestion chips -> explicit apply)
3. Key Takeaways (preview -> explicit insert at top/bottom)
4. Ask AI / Knowledge Assistant (free-form Q&A with multi-turn conversation and question-driven context)
5. Context Mode Selector ([ Related ▼ ])
6. Context Transparency Badge & Expander (displays transparent workspace sources & offline status)

Guarantees non-destructive safety: notes and tags remain untouched unless
the user explicitly clicks an action button.
"""

from typing import Any, Dict, List, Optional, Set, Union
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QCursor, QGuiApplication, QKeyEvent
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QLineEdit,
    QComboBox,
    QFrame,
    QScrollArea,
    QProgressBar,
    QSizePolicy,
)

from models.ai import AIResponse
from models.knowledge import KnowledgeDocument
from services.knowledge_ai_service import KnowledgeAIService, KnowledgeAIContextMode
from services.knowledge_assistant_service import KnowledgeAssistantService
from services.ai_service import AIWorker


class KnowledgeAIAssistWidget(QWidget):
    """Modern AI Assist control panel, Ask AI input, and preview area embedded in the Knowledge Editor."""

    insert_content_requested = Signal(str, str)  # (content_to_insert, "top" | "bottom")
    apply_tags_requested = Signal(list)          # (list_of_tags_to_merge)
    open_settings_requested = Signal(str)        # (settings_section, e.g. "ai")

    def __init__(
        self,
        knowledge_ai_service: Optional[KnowledgeAIService] = None,
        knowledge_assistant_service: Optional[KnowledgeAssistantService] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.ai_service = knowledge_ai_service
        self.assistant_service = knowledge_assistant_service

        # Fallback assistant service instantiation if not provided separately
        if not self.assistant_service and self.ai_service:
            self.assistant_service = KnowledgeAssistantService(
                ai_service=getattr(self.ai_service, "ai_service", None),
                knowledge_service=getattr(self.ai_service, "knowledge_service", None),
                context_retrieval_service=getattr(self.ai_service, "context_retrieval_service", None),
            )

        self._current_doc: Optional[KnowledgeDocument] = None
        self._current_project_id: Optional[str] = None
        self._active_worker: Optional[AIWorker] = None
        self._active_action: Optional[str] = None
        self._selected_suggested_tags: Set[str] = set()
        self._is_context_expanded: bool = False

        self._setup_ui()
        self.set_document(None)

    def set_ai_service(self, service: KnowledgeAIService):
        self.ai_service = service
        if not self.assistant_service and service:
            self.assistant_service = KnowledgeAssistantService(
                ai_service=getattr(service, "ai_service", None),
                knowledge_service=getattr(service, "knowledge_service", None),
                context_retrieval_service=getattr(service, "context_retrieval_service", None),
            )
        elif self.assistant_service and service:
            if hasattr(service, "ai_service"):
                self.assistant_service.set_ai_service(service.ai_service)
            if hasattr(service, "context_retrieval_service"):
                self.assistant_service.set_context_retrieval_service(service.context_retrieval_service)

    def set_assistant_service(self, service: KnowledgeAssistantService):
        self.assistant_service = service

    def set_project_id(self, project_id: Optional[str]):
        self._current_project_id = project_id

    def set_document(self, doc: Optional[KnowledgeDocument]):
        """Set active document and reset pending preview / session if document changed."""
        prev_id = self._current_doc.id if self._current_doc else None
        new_id = doc.id if doc else None

        self._current_doc = doc
        if prev_id != new_id:
            self._cancel_active_worker()
            self._hide_preview()
            if self.assistant_service:
                self.assistant_service.set_primary_subject("knowledge", new_id)
            self.ask_input.clear()

        # Update button enable state
        has_doc = bool(doc)
        self.btn_summarize.setEnabled(has_doc)
        self.btn_tags.setEnabled(has_doc)
        self.btn_takeaways.setEnabled(has_doc)
        self.btn_ask.setEnabled(has_doc)
        self.ask_input.setEnabled(has_doc)

    # -------------------------------------------------------------------------
    # UI Setup
    # -------------------------------------------------------------------------

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # 1. Action Buttons & Context Mode Selector Bar
        self.actions_bar = QFrame()
        self.actions_bar.setStyleSheet("""
            QFrame {
                background-color: #161822;
                border: 1px solid #282C40;
                border-radius: 6px;
                padding: 2px 4px;
            }
        """)
        bar_layout = QHBoxLayout(self.actions_bar)
        bar_layout.setContentsMargins(6, 4, 6, 4)
        bar_layout.setSpacing(8)

        ai_label = QLabel("✨ AI ASSIST:")
        ai_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        ai_label.setStyleSheet("color: #818CF8; background: transparent;")
        bar_layout.addWidget(ai_label)

        self.btn_summarize = QPushButton("📝 Summarize")
        self.btn_summarize.setToolTip("Generate a concise overview enriched with related context")
        self.btn_summarize.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_summarize.setStyleSheet(self._action_btn_style())
        self.btn_summarize.clicked.connect(self._on_summarize_clicked)
        bar_layout.addWidget(self.btn_summarize)

        self.btn_tags = QPushButton("🏷️ Suggest Tags")
        self.btn_tags.setToolTip("Suggest relevant tags based on note and project content")
        self.btn_tags.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_tags.setStyleSheet(self._action_btn_style())
        self.btn_tags.clicked.connect(self._on_generate_tags_clicked)
        bar_layout.addWidget(self.btn_tags)

        self.btn_takeaways = QPushButton("💡 Key Takeaways")
        self.btn_takeaways.setToolTip("Extract bullet-point takeaways and action items")
        self.btn_takeaways.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_takeaways.setStyleSheet(self._action_btn_style())
        self.btn_takeaways.clicked.connect(self._on_key_takeaways_clicked)
        bar_layout.addWidget(self.btn_takeaways)

        bar_layout.addSpacing(10)

        # Context Mode Selector
        ctx_mode_label = QLabel("Context:")
        ctx_mode_label.setStyleSheet("color: #64748B; font-size: 11px; font-weight: 500;")
        bar_layout.addWidget(ctx_mode_label)

        self.context_mode_combo = QComboBox()
        self.context_mode_combo.setFont(QFont("Segoe UI", 9))
        self.context_mode_combo.setStyleSheet("""
            QComboBox {
                background-color: #0F111A;
                color: #CBD5E1;
                border: 1px solid #2D334D;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
            }
            QComboBox:hover {
                border-color: #818CF8;
            }
            QComboBox::drop-down {
                border: none;
                width: 14px;
            }
            QComboBox QAbstractItemView {
                background-color: #161822;
                color: #F1F5F9;
                selection-background-color: #4F46E5;
                border: 1px solid #2D334D;
            }
        """)
        self.context_mode_combo.addItem("Current", KnowledgeAIContextMode.CURRENT)
        self.context_mode_combo.addItem("Related", KnowledgeAIContextMode.RELATED)
        self.context_mode_combo.addItem("Project", KnowledgeAIContextMode.PROJECT)
        self.context_mode_combo.addItem("Workspace", KnowledgeAIContextMode.WORKSPACE)
        self.context_mode_combo.setCurrentIndex(1)  # Default: Related
        bar_layout.addWidget(self.context_mode_combo)

        bar_layout.addStretch()

        self.status_pill = QLabel("")
        self.status_pill.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 500;")
        bar_layout.addWidget(self.status_pill)

        main_layout.addWidget(self.actions_bar)

        # 2. Ask AI Question Input Bar
        self.ask_bar = QFrame()
        self.ask_bar.setStyleSheet("""
            QFrame#ask_bar_frame {
                background-color: #161822;
                border: 1px solid #282C40;
                border-radius: 6px;
                padding: 2px 4px;
            }
        """)
        self.ask_bar.setObjectName("ask_bar_frame")
        ask_layout = QHBoxLayout(self.ask_bar)
        ask_layout.setContentsMargins(6, 4, 6, 4)
        ask_layout.setSpacing(6)

        ask_icon = QLabel("💬")
        ask_icon.setStyleSheet("background: transparent; font-size: 12px;")
        ask_layout.addWidget(ask_icon)

        self.ask_input = QLineEdit()
        self.ask_input.setPlaceholderText("Ask AI a question about this note or related workspace assets (Enter to submit)...")
        self.ask_input.setFont(QFont("Segoe UI", 10))
        self.ask_input.setStyleSheet("""
            QLineEdit {
                background-color: #0A0C14;
                color: #F1F5F9;
                border: 1px solid #2D334D;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QLineEdit:focus {
                border-color: #818CF8;
            }
            QLineEdit:disabled {
                background-color: #12141E;
                color: #475569;
            }
        """)
        self.ask_input.returnPressed.connect(self._on_ask_clicked)
        ask_layout.addWidget(self.ask_input, 1)

        self.btn_ask = QPushButton("✨ Ask")
        self.btn_ask.setToolTip("Submit question to AI Assistant using indexed workspace context")
        self.btn_ask.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_ask.setStyleSheet(self._accent_btn_style("#6366F1", "#4F46E5"))
        self.btn_ask.clicked.connect(self._on_ask_clicked)
        ask_layout.addWidget(self.btn_ask)

        self.btn_clear_history = QPushButton("🧹")
        self.btn_clear_history.setToolTip("Clear conversation history")
        self.btn_clear_history.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_clear_history.setStyleSheet(self._action_btn_style())
        self.btn_clear_history.clicked.connect(self._on_clear_history_clicked)
        ask_layout.addWidget(self.btn_clear_history)

        main_layout.addWidget(self.ask_bar)

        # 3. Dynamic Preview & Progress Container Frame
        self.container_frame = QFrame()
        self.container_frame.setStyleSheet("""
            QFrame#ai_container {
                background-color: #12141E;
                border: 1px solid #31374F;
                border-radius: 6px;
            }
        """)
        self.container_frame.setObjectName("ai_container")
        self.container_layout = QVBoxLayout(self.container_frame)
        self.container_layout.setContentsMargins(10, 10, 10, 10)
        self.container_layout.setSpacing(8)

        # --- A. Loading / Progress View ---
        self.loading_widget = QWidget()
        loading_layout = QVBoxLayout(self.loading_widget)
        loading_layout.setContentsMargins(0, 4, 0, 4)
        loading_layout.setSpacing(6)

        loading_header_row = QHBoxLayout()
        self.loading_label = QLabel("✨ Processing AI request...")
        self.loading_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.loading_label.setStyleSheet("color: #818CF8;")
        loading_header_row.addWidget(self.loading_label)
        loading_header_row.addStretch()

        self.btn_cancel_loading = QPushButton("✕ Cancel")
        self.btn_cancel_loading.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_cancel_loading.setStyleSheet(self._action_btn_style())
        self.btn_cancel_loading.clicked.connect(self._on_cancel_clicked)
        loading_header_row.addWidget(self.btn_cancel_loading)

        loading_layout.addLayout(loading_header_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate animation
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1E2235;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #6366F1;
                border-radius: 2px;
            }
        """)
        loading_layout.addWidget(self.progress_bar)

        self.container_layout.addWidget(self.loading_widget)

        # --- B. Error Alert View ---
        self.error_widget = QWidget()
        error_layout = QHBoxLayout(self.error_widget)
        error_layout.setContentsMargins(4, 4, 4, 4)
        error_layout.setSpacing(8)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #F87171; font-size: 12px; font-weight: 500;")
        error_layout.addWidget(self.error_label, 1)

        self.btn_open_settings = QPushButton("⚙️ Open AI Settings")
        self.btn_open_settings.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_open_settings.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4338CA;
            }
        """)
        self.btn_open_settings.clicked.connect(self._on_open_settings_clicked)
        self.btn_open_settings.setVisible(False)
        error_layout.addWidget(self.btn_open_settings)

        self.btn_dismiss_error = QPushButton("✕")
        self.btn_dismiss_error.setFixedSize(24, 24)
        self.btn_dismiss_error.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_dismiss_error.setStyleSheet(self._action_btn_style())
        self.btn_dismiss_error.clicked.connect(self._hide_preview)
        error_layout.addWidget(self.btn_dismiss_error)

        self.container_layout.addWidget(self.error_widget)

        # --- C. Text Result Preview (Summarize, Key Takeaways & Ask AI) ---
        self.text_preview_widget = QWidget()
        text_layout = QVBoxLayout(self.text_preview_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(6)

        text_header_row = QHBoxLayout()
        self.text_preview_title = QLabel("AI Result Preview")
        self.text_preview_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.text_preview_title.setStyleSheet("color: #A5B4FC;")
        text_header_row.addWidget(self.text_preview_title)
        text_header_row.addStretch()

        self.btn_copy_text = QPushButton("📋 Copy")
        self.btn_copy_text.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_copy_text.setStyleSheet(self._action_btn_style())
        self.btn_copy_text.clicked.connect(self._on_copy_text_clicked)
        text_header_row.addWidget(self.btn_copy_text)

        self.btn_dismiss_text = QPushButton("✕ Dismiss")
        self.btn_dismiss_text.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_dismiss_text.setStyleSheet(self._action_btn_style())
        self.btn_dismiss_text.clicked.connect(self._hide_preview)
        text_header_row.addWidget(self.btn_dismiss_text)

        text_layout.addLayout(text_header_row)

        self.text_preview_edit = QTextEdit()
        self.text_preview_edit.setReadOnly(True)
        self.text_preview_edit.setFont(QFont("Segoe UI", 10))
        self.text_preview_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0A0C14;
                color: #F1F5F9;
                border: 1px solid #2D334D;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        self.text_preview_edit.setFixedHeight(110)
        text_layout.addWidget(self.text_preview_edit)

        # Insertion Buttons Row
        self.insert_row_widget = QWidget()
        insert_row = QHBoxLayout(self.insert_row_widget)
        insert_row.setContentsMargins(0, 0, 0, 0)
        insert_row.setSpacing(8)

        insert_hint = QLabel("Insert into note:")
        insert_hint.setStyleSheet("color: #64748B; font-size: 11px;")
        insert_row.addWidget(insert_hint)

        self.btn_insert_top = QPushButton("⬆️ Insert at Top")
        self.btn_insert_top.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_insert_top.setStyleSheet(self._accent_btn_style("#6366F1", "#4F46E5"))
        self.btn_insert_top.clicked.connect(lambda: self._on_insert_clicked("top"))
        insert_row.addWidget(self.btn_insert_top)

        self.btn_insert_bottom = QPushButton("⬇️ Insert at Bottom")
        self.btn_insert_bottom.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_insert_bottom.setStyleSheet(self._accent_btn_style("#6366F1", "#4F46E5"))
        self.btn_insert_bottom.clicked.connect(lambda: self._on_insert_clicked("bottom"))
        insert_row.addWidget(self.btn_insert_bottom)

        insert_row.addStretch()
        text_layout.addWidget(self.insert_row_widget)

        self.container_layout.addWidget(self.text_preview_widget)

        # --- D. Tag Suggestions Preview ---
        self.tags_preview_widget = QWidget()
        tags_layout = QVBoxLayout(self.tags_preview_widget)
        tags_layout.setContentsMargins(0, 0, 0, 0)
        tags_layout.setSpacing(6)

        tags_header_row = QHBoxLayout()
        self.tags_preview_title = QLabel("🏷️ Suggested Tags (Click to select/deselect)")
        self.tags_preview_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.tags_preview_title.setStyleSheet("color: #38BDF8;")
        tags_header_row.addWidget(self.tags_preview_title)
        tags_header_row.addStretch()

        self.btn_toggle_all_tags = QPushButton("Select All")
        self.btn_toggle_all_tags.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_toggle_all_tags.setStyleSheet(self._action_btn_style())
        self.btn_toggle_all_tags.clicked.connect(self._on_toggle_all_tags_clicked)
        tags_header_row.addWidget(self.btn_toggle_all_tags)

        self.btn_dismiss_tags = QPushButton("✕ Dismiss")
        self.btn_dismiss_tags.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_dismiss_tags.setStyleSheet(self._action_btn_style())
        self.btn_dismiss_tags.clicked.connect(self._hide_preview)
        tags_header_row.addWidget(self.btn_dismiss_tags)

        tags_layout.addLayout(tags_header_row)

        # Scrollable chips row
        self.tags_chips_container = QWidget()
        self.tags_chips_container.setStyleSheet("background: transparent;")
        self.tags_chips_layout = QHBoxLayout(self.tags_chips_container)
        self.tags_chips_layout.setContentsMargins(0, 4, 0, 4)
        self.tags_chips_layout.setSpacing(6)
        self.tags_chips_layout.setAlignment(Qt.AlignLeft)

        tags_scroll = QScrollArea()
        tags_scroll.setWidgetResizable(True)
        tags_scroll.setFixedHeight(42)
        tags_scroll.setFrameShape(QFrame.NoFrame)
        tags_scroll.setStyleSheet("background: transparent; border: none;")
        tags_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        tags_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tags_scroll.setWidget(self.tags_chips_container)

        tags_layout.addWidget(tags_scroll)

        # Apply Tags Button Row
        apply_tags_row = QHBoxLayout()
        apply_tags_row.setSpacing(8)

        self.btn_apply_tags = QPushButton("✓ Apply Selected Tags")
        self.btn_apply_tags.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_apply_tags.setStyleSheet(self._accent_btn_style("#0284C7", "#0369A1"))
        self.btn_apply_tags.clicked.connect(self._on_apply_tags_clicked)
        apply_tags_row.addWidget(self.btn_apply_tags)

        apply_tags_row.addStretch()
        tags_layout.addLayout(apply_tags_row)

        self.container_layout.addWidget(self.tags_preview_widget)

        # --- E. Context Used Transparency Badge / Expander ---
        self.context_used_widget = QWidget()
        ctx_layout = QVBoxLayout(self.context_used_widget)
        ctx_layout.setContentsMargins(4, 2, 4, 2)
        ctx_layout.setSpacing(4)

        self.btn_toggle_context = QPushButton("▸ Context used (0)")
        self.btn_toggle_context.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_toggle_context.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #818CF8;
                font-size: 11px;
                font-weight: bold;
                text-align: left;
                padding: 2px 0px;
            }
            QPushButton:hover {
                color: #A5B4FC;
            }
        """)
        self.btn_toggle_context.clicked.connect(self._toggle_context_list)
        ctx_layout.addWidget(self.btn_toggle_context)

        self.context_items_list = QWidget()
        self.context_items_layout = QVBoxLayout(self.context_items_list)
        self.context_items_layout.setContentsMargins(12, 2, 4, 4)
        self.context_items_layout.setSpacing(3)
        self.context_items_list.setVisible(False)
        ctx_layout.addWidget(self.context_items_list)

        self.context_used_widget.setVisible(False)
        self.container_layout.addWidget(self.context_used_widget)

        main_layout.addWidget(self.container_frame)
        self._hide_preview()

    # -------------------------------------------------------------------------
    # Styles
    # -------------------------------------------------------------------------

    def _action_btn_style(self) -> str:
        return """
            QPushButton {
                background-color: #1E2235;
                color: #CBD5E1;
                border: 1px solid #2E3650;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #283556;
                color: #FFFFFF;
                border-color: #6366F1;
            }
            QPushButton:disabled {
                background-color: #12141E;
                color: #475569;
                border-color: #1E2235;
            }
        """

    def _accent_btn_style(self, bg_color: str, hover_color: str) -> str:
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:disabled {{
                background-color: #1E2235;
                color: #64748B;
            }}
        """

    def _tag_chip_style(self, checked: bool) -> str:
        if checked:
            return """
                QPushButton {
                    background-color: #1E3A8A;
                    color: #93C5FD;
                    border: 1px solid #3B82F6;
                    border-radius: 12px;
                    padding: 3px 10px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #2563EB;
                    color: #FFFFFF;
                }
            """
        return """
            QPushButton {
                background-color: #161822;
                color: #64748B;
                border: 1px solid #282C40;
                border-radius: 12px;
                padding: 3px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #283556;
                color: #F1F5F9;
                border-color: #38BDF8;
            }
        """

    # -------------------------------------------------------------------------
    # View State Management
    # -------------------------------------------------------------------------

    def _hide_preview(self):
        self.container_frame.setVisible(False)
        self.loading_widget.setVisible(False)
        self.error_widget.setVisible(False)
        self.text_preview_widget.setVisible(False)
        self.tags_preview_widget.setVisible(False)
        self.context_used_widget.setVisible(False)
        self.status_pill.setText("")
        self._active_action = None

    def _show_loading(self, action_name: str, message: str):
        self._active_action = action_name
        self.container_frame.setVisible(True)
        self.loading_widget.setVisible(True)
        self.error_widget.setVisible(False)
        self.text_preview_widget.setVisible(False)
        self.tags_preview_widget.setVisible(False)
        self.context_used_widget.setVisible(False)
        self.loading_label.setText(message)
        self.status_pill.setText("Generating...")

    def _show_error(self, message: str, show_settings_btn: bool = False):
        self.container_frame.setVisible(True)
        self.loading_widget.setVisible(False)
        self.error_widget.setVisible(True)
        self.text_preview_widget.setVisible(False)
        self.tags_preview_widget.setVisible(False)
        self.context_used_widget.setVisible(False)
        self.error_label.setText(f"⚠️ {message}")
        should_show_btn = show_settings_btn or ("Settings" in message) or ("configured" in message) or ("disabled" in message)
        self.btn_open_settings.setVisible(should_show_btn)
        self.status_pill.setText("Not Configured" if should_show_btn else "Error")

    def _on_open_settings_clicked(self):
        self._hide_preview()
        self.open_settings_requested.emit("ai")
        try:
            win = self.window()
            if hasattr(win, "open_settings"):
                win.open_settings("ai")
            elif hasattr(self, "context") and getattr(self.context, "open_settings", None):
                self.context.open_settings("ai")
        except Exception:
            pass

    def _toggle_context_list(self):
        self._is_context_expanded = not self._is_context_expanded
        self.context_items_list.setVisible(self._is_context_expanded)
        curr_text = self.btn_toggle_context.text()
        if "Context used (" in curr_text:
            num = curr_text.split("Context used (")[-1].rstrip(")")
            self.btn_toggle_context.setText(f"{'▾' if self._is_context_expanded else '▸'} Context used ({num})")

    def _render_context_used(self, resp: Optional[AIResponse]):
        """Render transparent list of workspace context items utilized for this AI result."""
        while self.context_items_layout.count():
            child = self.context_items_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        raw_ctx = resp.raw_response.get("context_result") if (resp and resp.raw_response) else None
        items = raw_ctx.get("items", []) if raw_ctx else []

        if not items:
            self.btn_toggle_context.setText("• Context used: Current document only")
            self.btn_toggle_context.setToolTip("Only the active note was used as the context source.")
            doc_lbl = QLabel(f"📄 {self._current_doc.title if self._current_doc else 'Current Note'}")
            doc_lbl.setStyleSheet("color: #94A3B8; font-size: 11px;")
            self.context_items_layout.addWidget(doc_lbl)
        else:
            self.btn_toggle_context.setText(f"{'▾' if self._is_context_expanded else '▸'} Context used ({len(items)})")
            self.btn_toggle_context.setToolTip("Click to view related workspace entities used by AI.")
            for item in items:
                stype = item.get("source_type", "")
                title = item.get("title", "Untitled")
                avail = item.get("availability", "online")
                is_offline = (avail == "offline" or str(avail).lower() == "offline")

                item_row = QHBoxLayout()
                item_row.setContentsMargins(0, 0, 0, 0)
                item_row.setSpacing(6)

                if stype in ("knowledge", "ContextSource.KNOWLEDGE"):
                    icon_prefix = "📄"
                elif stype in ("project", "ContextSource.PROJECT"):
                    icon_prefix = "📁"
                elif stype in ("library_asset", "ContextSource.LIBRARY_ASSET"):
                    icon_prefix = "📦"
                elif stype in ("project_asset", "ContextSource.PROJECT_ASSET"):
                    icon_prefix = "🖼️"
                elif stype in ("lab_node", "lab_board", "ContextSource.LAB_NODE", "ContextSource.LAB_BOARD"):
                    icon_prefix = "🎨"
                else:
                    icon_prefix = "📌"

                bname = item.get("metadata", {}).get("board_name")
                desc_suffix = f" ({bname})" if bname else ""
                name_lbl = QLabel(f"{icon_prefix} {title}{desc_suffix}")
                name_lbl.setStyleSheet("color: #CBD5E1; font-size: 11px;")
                item_row.addWidget(name_lbl)

                if is_offline:
                    off_badge = QLabel("🟠 Offline")
                    off_badge.setStyleSheet("""
                        background-color: #3B2014;
                        color: #FB923C;
                        font-size: 9px;
                        font-weight: bold;
                        padding: 1px 5px;
                        border-radius: 4px;
                    """)
                    item_row.addWidget(off_badge)

                item_row.addStretch()

                row_widget = QWidget()
                row_widget.setLayout(item_row)
                self.context_items_layout.addWidget(row_widget)

        self.context_used_widget.setVisible(True)
        self.context_items_list.setVisible(self._is_context_expanded)

    def _show_text_result(self, title: str, text: str, action_name: str, resp: Optional[AIResponse] = None):
        self._active_action = action_name
        self.container_frame.setVisible(True)
        self.loading_widget.setVisible(False)
        self.error_widget.setVisible(False)
        self.tags_preview_widget.setVisible(False)
        self.text_preview_widget.setVisible(True)

        self.text_preview_title.setText(title)
        self.text_preview_edit.setPlainText(text)
        self.status_pill.setText("Ready")

        # Show insertion controls only for Summarize & Takeaways (Ask AI uses Copy/Dismiss)
        self.insert_row_widget.setVisible(action_name in ("summarize", "key_takeaways"))

        self._render_context_used(resp)

    def _show_tags_result(self, tags: List[str], resp: Optional[AIResponse] = None):
        self._active_action = "generate_tags"
        self.container_frame.setVisible(True)
        self.loading_widget.setVisible(False)
        self.error_widget.setVisible(False)
        self.text_preview_widget.setVisible(False)
        self.tags_preview_widget.setVisible(True)

        while self.tags_chips_layout.count():
            item = self.tags_chips_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        self._selected_suggested_tags = set(tags)

        if not tags:
            no_tags_lbl = QLabel("No new tags suggested.")
            no_tags_lbl.setStyleSheet("color: #64748B; font-size: 11px; font-style: italic;")
            self.tags_chips_layout.addWidget(no_tags_lbl)
            self.btn_apply_tags.setEnabled(False)
            self.status_pill.setText("No new tags")
        else:
            self.btn_apply_tags.setEnabled(True)
            self.status_pill.setText(f"{len(tags)} suggestions")

            for tag in tags:
                btn_chip = QPushButton(f"✓ {tag}")
                btn_chip.setProperty("tag_val", tag)
                btn_chip.setCheckable(True)
                btn_chip.setChecked(True)
                btn_chip.setCursor(QCursor(Qt.PointingHandCursor))
                btn_chip.setStyleSheet(self._tag_chip_style(True))
                btn_chip.toggled.connect(lambda chk, t=tag, b=btn_chip: self._on_tag_chip_toggled(t, chk, b))
                self.tags_chips_layout.addWidget(btn_chip)

        self._render_context_used(resp)

    def _on_tag_chip_toggled(self, tag: str, checked: bool, button: QPushButton):
        if checked:
            self._selected_suggested_tags.add(tag)
            button.setText(f"✓ {tag}")
            button.setStyleSheet(self._tag_chip_style(True))
        else:
            self._selected_suggested_tags.discard(tag)
            button.setText(f"+ {tag}")
            button.setStyleSheet(self._tag_chip_style(False))

        self.btn_apply_tags.setEnabled(bool(self._selected_suggested_tags))

    def _on_toggle_all_tags_clicked(self):
        all_selected = (len(self._selected_suggested_tags) == self.tags_chips_layout.count())
        target_state = not all_selected

        for i in range(self.tags_chips_layout.count()):
            item = self.tags_chips_layout.itemAt(i)
            btn = item.widget()
            if isinstance(btn, QPushButton):
                btn.setChecked(target_state)

        self.btn_toggle_all_tags.setText("Deselect All" if target_state else "Select All")

    def _cancel_active_worker(self):
        if self._active_worker:
            try:
                self._active_worker.cancel()
            except Exception:
                pass
            self._active_worker = None

    def _on_cancel_clicked(self):
        self._cancel_active_worker()
        self._hide_preview()

    def _get_active_context_mode(self) -> KnowledgeAIContextMode:
        """Get the currently selected context mode from the dropdown."""
        data = self.context_mode_combo.currentData()
        if isinstance(data, KnowledgeAIContextMode):
            return data
        if isinstance(data, str):
            try:
                return KnowledgeAIContextMode(data.lower())
            except ValueError:
                pass
        text = self.context_mode_combo.currentText().strip().lower()
        try:
            return KnowledgeAIContextMode(text)
        except ValueError:
            return KnowledgeAIContextMode.RELATED

    # -------------------------------------------------------------------------
    # Action Triggers with Context Modes
    # -------------------------------------------------------------------------

    def _on_summarize_clicked(self):
        if not self._current_doc or not self.ai_service:
            return

        if not self.ai_service.is_ai_available():
            self._show_error("AI is not configured. Open Settings → AI to connect a provider.", show_settings_btn=True)
            return

        self._cancel_active_worker()
        self._show_loading("summarize", "✨ Summarizing document...")
        mode = self._get_active_context_mode()

        def _on_finished(doc, resp: AIResponse):
            if resp.success:
                self._show_text_result("✨ Document Summary", resp.text.strip(), "summarize", resp=resp)
            else:
                self._show_error(resp.error_message or "Summarization failed.")

        def _on_error(err_msg: str):
            self._show_error(err_msg)

        self._active_worker = self.ai_service.summarize_document_async(
            self._current_doc,
            on_finished=_on_finished,
            on_error=_on_error,
            context_mode=mode,
            project_id=self._current_project_id,
        )

    def _on_generate_tags_clicked(self):
        if not self._current_doc or not self.ai_service:
            return

        if not self.ai_service.is_ai_available():
            self._show_error("AI is not configured. Open Settings → AI to connect a provider.", show_settings_btn=True)
            return

        self._cancel_active_worker()
        self._show_loading("generate_tags", "🏷️ Analyzing document for tag suggestions...")
        mode = self._get_active_context_mode()

        def _on_finished(doc, resp: AIResponse, suggested_tags: List[str]):
            if resp.success:
                self._show_tags_result(suggested_tags, resp=resp)
            else:
                self._show_error(resp.error_message or "Tag generation failed.")

        def _on_error(err_msg: str):
            self._show_error(err_msg)

        self._active_worker = self.ai_service.generate_tags_async(
            self._current_doc,
            on_finished=_on_finished,
            on_error=_on_error,
            context_mode=mode,
            project_id=self._current_project_id,
        )

    def _on_key_takeaways_clicked(self):
        if not self._current_doc or not self.ai_service:
            return

        if not self.ai_service.is_ai_available():
            self._show_error("AI is not configured. Open Settings → AI to connect a provider.", show_settings_btn=True)
            return

        self._cancel_active_worker()
        self._show_loading("key_takeaways", "💡 Extracting key takeaways & action items...")
        mode = self._get_active_context_mode()

        def _on_finished(doc, resp: AIResponse):
            if resp.success:
                self._show_text_result("💡 Key Takeaways", resp.text.strip(), "key_takeaways", resp=resp)
            else:
                self._show_error(resp.error_message or "Takeaways extraction failed.")

        def _on_error(err_msg: str):
            self._show_error(err_msg)

        self._active_worker = self.ai_service.extract_key_takeaways_async(
            self._current_doc,
            on_finished=_on_finished,
            on_error=_on_error,
            context_mode=mode,
            project_id=self._current_project_id,
        )

    # -------------------------------------------------------------------------
    # Ask AI Interactive Q&A
    # -------------------------------------------------------------------------

    def _on_ask_clicked(self):
        """Submit question to Knowledge Assistant Service."""
        question = self.ask_input.text().strip()
        if not question:
            return

        if not self.assistant_service or not self.assistant_service.is_ai_available():
            self._show_error("AI is not configured. Open Settings → AI to connect a provider.", show_settings_btn=True)
            return

        self._cancel_active_worker()
        self._show_loading("ask", f"💬 Thinking: '{question[:40]}...'")
        mode = self._get_active_context_mode()

        def _on_finished(q: str, resp: AIResponse):
            if resp.success:
                self._show_text_result("✨ AI Answer", resp.text.strip(), "ask", resp=resp)
            else:
                self._show_error(resp.error_message or "Ask AI request failed.")

        def _on_error(err_msg: str):
            self._show_error(err_msg)

        self._active_worker = self.assistant_service.ask_async(
            question=question,
            on_finished=_on_finished,
            on_error=_on_error,
            document=self._current_doc,
            project_id=self._current_project_id,
            context_mode=mode,
        )

    def _on_clear_history_clicked(self):
        """Clear assistant conversation history."""
        if self.assistant_service:
            self.assistant_service.clear_history()
        self.status_pill.setText("History cleared")
        def _reset_status():
            try:
                if hasattr(self, "status_pill") and self.status_pill:
                    self.status_pill.setText("")
            except RuntimeError:
                pass
        QTimer.singleShot(1500, _reset_status)

    # -------------------------------------------------------------------------
    # Explicit User Commit Actions
    # -------------------------------------------------------------------------

    def _on_insert_clicked(self, position: str):
        """User explicitly clicked 'Insert at Top' or 'Insert at Bottom'."""
        text = self.text_preview_edit.toPlainText().strip()
        if not text:
            return

        heading = "## Summary" if self._active_action == "summarize" else "## Key Takeaways"
        formatted_block = f"{heading}\n\n{text}"

        self.insert_content_requested.emit(formatted_block, position)
        self._hide_preview()

    def _on_copy_text_clicked(self):
        text = self.text_preview_edit.toPlainText().strip()
        if text:
            clipboard = QGuiApplication.clipboard()
            if clipboard:
                clipboard.setText(text)
                self.btn_copy_text.setText("✓ Copied!")
                def _reset_copy_btn():
                    try:
                        if hasattr(self, "btn_copy_text") and self.btn_copy_text:
                            self.btn_copy_text.setText("📋 Copy")
                    except RuntimeError:
                        pass
                QTimer.singleShot(1500, _reset_copy_btn)

    def _on_apply_tags_clicked(self):
        """User explicitly clicked 'Apply Selected Tags'."""
        tags_to_apply = sorted(list(self._selected_suggested_tags))
        if tags_to_apply:
            self.apply_tags_requested.emit(tags_to_apply)
            self._hide_preview()
