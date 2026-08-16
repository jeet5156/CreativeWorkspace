"""Project AI Assistant Widget for CreativeWorkspace (Phase 5B).

Provides a modern, interactive AI assistant panel embedded in the Project Dashboard:
- Grounded conversational Q&A on ProjectContext
- Quick context-aware suggestion chips
- Traceable, clickable Sources Used drawer (Project, Assets, Offline References, Knowledge, Lab)
- Non-blocking asynchronous execution with loading indicators and cancel support
- Navigation signals when source items are clicked
"""

from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QFrame,
    QScrollArea,
    QProgressBar,
    QSizePolicy,
)

from models.project import Project
from models.project_context import ProjectContext
from models.project_assistant import (
    ProjectSourceType,
    TraceableSourceItem,
    ProjectAssistantResponse,
)
from services.project_assistant_service import ProjectAssistantService
from services.ai_service import AIWorker


DARK_BG = "#101216"
CARD_BG = "#181B22"
CARD_BORDER = "#282C38"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_AMBER = "#F59E0B"
ACCENT_RED = "#EF4444"
TEXT_PRIMARY = "#F8FAFC"
TEXT_MUTED = "#94A3B8"


class ClickableSourceChip(QFrame):
    """Clickable pill widget representing a traceable source entity."""

    clicked = Signal(str, str, dict)  # (source_type, target_id_or_path, metadata)

    def __init__(self, source: TraceableSourceItem, parent=None):
        super().__init__(parent)
        self.source = source
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self._setup_ui()

    def _setup_ui(self):
        s_type = self.source.source_type
        status = (self.source.status or "").lower()

        # Choose border/accent based on type/status
        border_color = "#334155"
        bg_color = "#1E293B"
        icon = "🔗"

        if s_type in (ProjectSourceType.PROJECT.value, "project"):
            icon = "📁"
            bg_color = "#172554"
            border_color = "#1E40AF"
        elif s_type in (ProjectSourceType.ASSET.value, "asset"):
            icon = "📦"
            bg_color = "#0F2E28"
            border_color = "#059669"
        elif s_type in (ProjectSourceType.LIBRARY_ASSET.value, "library_asset"):
            if status == "offline":
                icon = "📦"
                bg_color = "#3F2208"
                border_color = "#D97706"
            elif status == "missing":
                icon = "📦"
                bg_color = "#450A0A"
                border_color = "#DC2626"
            else:
                icon = "📦"
                bg_color = "#064E3B"
                border_color = "#10B981"
        elif s_type in (ProjectSourceType.KNOWLEDGE.value, "knowledge"):
            icon = "📄"
            bg_color = "#2E1065"
            border_color = "#7C3AED"
        elif s_type in (ProjectSourceType.LAB_BOARD.value, "lab_board"):
            icon = "🎨"
            bg_color = "#1E1B4B"
            border_color = "#4F46E5"
        elif s_type in (ProjectSourceType.LAB_TASK.value, "lab_task"):
            icon = "☑️"
            bg_color = "#14382B"
            border_color = "#10B981"

        self.setStyleSheet(f"""
            ClickableSourceChip {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 3px 8px;
            }}
            ClickableSourceChip:hover {{
                border: 1px solid #60A5FA;
                background-color: #1E3A8A;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(6)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 11px;")
        layout.addWidget(icon_lbl)

        title_lbl = QLabel(self.source.title)
        title_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 11px; font-weight: 500;")
        layout.addWidget(title_lbl)

        if self.source.badge:
            badge_lbl = QLabel(self.source.badge)
            badge_lbl.setStyleSheet("color: #94A3B8; font-size: 10px; padding: 1px 4px; border-radius: 3px; background-color: rgba(255,255,255,0.08);")
            layout.addWidget(badge_lbl)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            target = self.source.target_id or self.source.target_path or self.source.title
            self.clicked.emit(self.source.source_type, str(target), self.source.metadata)
        super().mousePressEvent(event)


class ProjectAIAssistantWidget(QWidget):
    """Interactive Project AI Assistant Widget."""

    source_clicked = Signal(str, str, dict)  # (source_type, target_id_or_path, metadata)
    open_settings_requested = Signal(str)

    def __init__(
        self,
        assistant_service: Optional[ProjectAssistantService] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.assistant_service = assistant_service
        self._current_project: Optional[Any] = None
        self._active_worker: Optional[AIWorker] = None
        self._is_sources_expanded: bool = True

        self._setup_ui()

    def set_assistant_service(self, service: ProjectAssistantService):
        self.assistant_service = service
        self._update_ai_status()

    def set_project(self, project_or_context: Any):
        """Bind active project and refresh suggestions & clean state if project changed."""
        prev_proj = self._current_project
        self._current_project = project_or_context

        if self.assistant_service:
            self.assistant_service.set_active_project(project_or_context)

        self._update_suggestions()
        self._update_ai_status()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        # 1. Header Bar
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {CARD_BORDER};
                border-radius: 8px;
                padding: 6px 12px;
            }}
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 4, 8, 4)
        h_layout.setSpacing(10)

        ai_title = QLabel("✨ PROJECT AI ASSISTANT")
        ai_title.setStyleSheet(f"color: #93C5FD; font-weight: bold; font-size: 12px; letter-spacing: 0.5px;")
        h_layout.addWidget(ai_title)

        self.status_badge = QLabel("🟢 AI Ready")
        self.status_badge.setStyleSheet("color: #34D399; font-size: 11px; font-weight: 500;")
        h_layout.addWidget(self.status_badge)

        h_layout.addStretch()

        self.clear_btn = QPushButton("🗑 Clear")
        self.clear_btn.setToolTip("Clear conversation history")
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {TEXT_MUTED};
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                color: #EF4444;
                border-color: #EF4444;
                background-color: #2D1515;
            }}
        """)
        self.clear_btn.clicked.connect(self.clear_chat)
        h_layout.addWidget(self.clear_btn)

        self.expand_btn = QPushButton("↕ Expand")
        self.expand_btn.setToolTip("Toggle expand/compact assistant view")
        self.expand_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {TEXT_MUTED};
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                color: #60A5FA;
                border-color: {ACCENT_BLUE};
            }}
        """)
        self.expand_btn.clicked.connect(self._toggle_expand)
        h_layout.addWidget(self.expand_btn)

        self.settings_btn = QPushButton("⚙ Settings")
        self.settings_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {TEXT_MUTED};
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                color: {TEXT_PRIMARY};
                border-color: {ACCENT_BLUE};
            }}
        """)
        self.settings_btn.clicked.connect(lambda: self.open_settings_requested.emit("ai"))
        h_layout.addWidget(self.settings_btn)

        main_layout.addWidget(header)

        # 2. Quick Suggestions Bar
        self.suggestions_container = QFrame()
        self.suggestions_container.setStyleSheet("background: transparent;")
        self.suggestions_layout = QHBoxLayout(self.suggestions_container)
        self.suggestions_layout.setContentsMargins(0, 0, 0, 0)
        self.suggestions_layout.setSpacing(6)
        main_layout.addWidget(self.suggestions_container)

        # 3. Conversation & Response Area (Scrollable)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumHeight(240)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {DARK_BG};
                border: 1px solid {CARD_BORDER};
                border-radius: 8px;
            }}
        """)
        self.chat_container = QWidget()
        self.chat_container.setStyleSheet(f"background-color: {DARK_BG};")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(12, 12, 12, 12)
        self.chat_layout.setSpacing(12)
        self.chat_layout.addStretch()

        self.scroll_area.setWidget(self.chat_container)
        main_layout.addWidget(self.scroll_area, stretch=1)

        # 4. Loading indicator
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 0)  # Indeterminate spinner
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #1E293B;
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {ACCENT_BLUE};
                border-radius: 2px;
            }}
        """)
        self.progress_bar.hide()
        main_layout.addWidget(self.progress_bar)

        # 5. Input Bar
        input_frame = QFrame()
        input_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {CARD_BORDER};
                border-radius: 8px;
                padding: 4px;
            }}
        """)
        in_layout = QHBoxLayout(input_frame)
        in_layout.setContentsMargins(6, 4, 6, 4)
        in_layout.setSpacing(8)

        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Ask about project assets, versions, offline references, knowledge notes, or Lab boards...")
        self.input_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: #12141A;
                color: {TEXT_PRIMARY};
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {ACCENT_BLUE};
            }}
        """)
        self.input_edit.returnPressed.connect(self._on_send_clicked)
        in_layout.addWidget(self.input_edit, stretch=1)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #3F1212;
                color: #F87171;
                border: 1px solid #7F1D1D;
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #7F1D1D;
                color: #FFFFFF;
            }}
        """)
        self.cancel_btn.clicked.connect(self._cancel_active_worker)
        self.cancel_btn.hide()
        in_layout.addWidget(self.cancel_btn)

        self.ask_btn = QPushButton("Ask AI")
        self.ask_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2563EB;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #1D4ED8;
            }}
            QPushButton:disabled {{
                background-color: #334155;
                color: #64748B;
            }}
        """)
        self.ask_btn.clicked.connect(self._on_send_clicked)
        in_layout.addWidget(self.ask_btn)

        main_layout.addWidget(input_frame)

        self._show_initial_welcome()

    def _update_ai_status(self):
        if not self.assistant_service or not self.assistant_service.is_ai_available():
            self.status_badge.setText("⚪ AI Disabled")
            self.status_badge.setStyleSheet("color: #94A3B8; font-size: 11px;")
            self.ask_btn.setEnabled(False)
            self.input_edit.setEnabled(False)
        else:
            self.status_badge.setText("🟢 AI Ready")
            self.status_badge.setStyleSheet("color: #34D399; font-size: 11px; font-weight: bold;")
            self.ask_btn.setEnabled(True)
            self.input_edit.setEnabled(True)

    def _update_suggestions(self):
        # Clear existing suggestion chips
        while self.suggestions_layout.count():
            item = self.suggestions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.assistant_service or not self._current_project:
            return

        suggestions = self.assistant_service.get_quick_suggestions(self._current_project)
        for s_text in suggestions:
            btn = QPushButton(f"💡 {s_text}")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #181C26;
                    color: #93C5FD;
                    border: 1px solid #2A334A;
                    border-radius: 12px;
                    padding: 4px 10px;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background-color: #1E293B;
                    border-color: #3B82F6;
                    color: #FFFFFF;
                }}
            """)
            btn.clicked.connect(lambda checked=False, q=s_text: self.ask_question(q))
            self.suggestions_layout.addWidget(btn)

        self.suggestions_layout.addStretch()

    def _show_initial_welcome(self):
        self._clear_chat_layout()
        welcome_box = QFrame()
        welcome_box.setStyleSheet(f"""
            QFrame {{
                background-color: #141824;
                border: 1px dashed #2A334A;
                border-radius: 8px;
                padding: 14px;
            }}
        """)
        w_lay = QVBoxLayout(welcome_box)
        w_lay.setSpacing(6)

        title = QLabel("🤖 Project AI Grounded Assistant")
        title.setStyleSheet(f"color: #93C5FD; font-size: 13px; font-weight: bold;")
        w_lay.addWidget(title)

        desc = QLabel(
            "Ask questions about this project's indexed assets, version sequences, offline library references, "
            "linked Knowledge notes, or active Creative Lab boards. Every answer cites exact traceable sources."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; line-height: 1.4;")
        w_lay.addWidget(desc)

        self.chat_layout.insertWidget(self.chat_layout.count() - 1, welcome_box)

    def _clear_chat_layout(self):
        # Remove widgets except the bottom stretch
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def clear_chat(self):
        """Clear visible chat messages and reset service conversation history."""
        if self.assistant_service:
            self.assistant_service.clear_history()
        self._show_initial_welcome()

    def _on_send_clicked(self):
        text = self.input_edit.text().strip()
        if not text:
            return
        self.ask_question(text)

    def ask_question(self, question: str):
        """Submit a question to the assistant asynchronously."""
        if not question or not self.assistant_service:
            return

        if not self.assistant_service.is_ai_available():
            self._render_message_bubble("user", question)
            self._render_message_bubble(
                "assistant",
                "⚠️ AI capabilities are currently disabled in Settings. Please enable an AI provider to query this project.",
                sources=[],
            )
            return

        self._render_message_bubble("user", question)
        self.input_edit.clear()

        self._set_loading(True)

        self._active_worker = self.assistant_service.ask_async(
            question=question,
            project_or_id=self._current_project,
            on_finished=self._on_assistant_finished,
            on_error=self._on_assistant_error,
        )

    def _on_assistant_finished(self, question: str, response: ProjectAssistantResponse):
        self._set_loading(False)
        self._render_message_bubble(
            role="assistant",
            content=response.answer,
            sources=response.sources,
        )

    def _on_assistant_error(self, question: str, error_msg: str):
        self._set_loading(False)
        self._render_message_bubble(
            role="assistant",
            content=f"❌ Error generating response: {error_msg}",
            sources=[],
            is_error=True,
        )

    def _cancel_active_worker(self):
        if self._active_worker:
            try:
                self._active_worker.cancel()
            except Exception:
                pass
            self._active_worker = None
        self._set_loading(False)

    def _set_loading(self, loading: bool):
        self.progress_bar.setVisible(loading)
        self.cancel_btn.setVisible(loading)
        self.ask_btn.setVisible(not loading)
        self.input_edit.setEnabled(not loading)

    def _render_message_bubble(
        self,
        role: str,
        content: str,
        sources: Optional[List[TraceableSourceItem]] = None,
        is_error: bool = False,
    ):
        bubble = QFrame()

        if role == "user":
            bubble.setStyleSheet(f"""
                QFrame {{
                    background-color: #1E293B;
                    border: 1px solid #334155;
                    border-radius: 8px;
                    padding: 8px 12px;
                    margin-left: 40px;
                }}
            """)
        else:
            border_c = "#EF4444" if is_error else CARD_BORDER
            bg_c = "#2A1515" if is_error else CARD_BG
            bubble.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_c};
                    border: 1px solid {border_c};
                    border-radius: 8px;
                    padding: 10px 14px;
                    margin-right: 40px;
                }}
            """)

        b_layout = QVBoxLayout(bubble)
        b_layout.setContentsMargins(8, 6, 8, 6)
        b_layout.setSpacing(6)

        # Header role tag
        role_tag = QLabel("👤 You" if role == "user" else "🤖 Project AI")
        role_tag.setStyleSheet("font-size: 11px; font-weight: bold; color: #94A3B8;")
        b_layout.addWidget(role_tag)

        # Content text
        text_lbl = QLabel(content)
        text_lbl.setWordWrap(True)
        text_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        text_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px; line-height: 1.4;")
        b_layout.addWidget(text_lbl)

        # Traceable Sources Container
        if sources:
            sources_box = QFrame()
            sources_box.setStyleSheet("""
                QFrame {
                    background-color: #12141C;
                    border: 1px solid #232738;
                    border-radius: 6px;
                    padding: 6px 8px;
                    margin-top: 4px;
                }
            """)
            s_lay = QVBoxLayout(sources_box)
            s_lay.setContentsMargins(4, 4, 4, 4)
            s_lay.setSpacing(6)

            src_header = QLabel(f"▾ Sources used ({len(sources)})")
            src_header.setStyleSheet("color: #60A5FA; font-size: 11px; font-weight: bold;")
            s_lay.addWidget(src_header)

            chips_flow = QHBoxLayout()
            chips_flow.setSpacing(6)

            for src in sources:
                chip = ClickableSourceChip(src)
                chip.clicked.connect(self._on_source_chip_clicked)
                chips_flow.addWidget(chip)

            chips_flow.addStretch()
            s_lay.addLayout(chips_flow)

            b_layout.addWidget(sources_box)

        # Insert before stretch
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)

        # Smooth scroll to bottom after layout calculation
        from PySide6.QtCore import QTimer
        QTimer.singleShot(40, lambda: self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum()))

    def _toggle_expand(self):
        is_expanded = getattr(self, "_is_expanded", False)
        self._is_expanded = not is_expanded
        if self._is_expanded:
            self.scroll_area.setMinimumHeight(460)
            self.expand_btn.setText("↕ Compact")
        else:
            self.scroll_area.setMinimumHeight(240)
            self.expand_btn.setText("↕ Expand")

    def _on_source_chip_clicked(self, source_type: str, target_id_or_path: str, metadata: dict):
        """Relay source chip click to parent listeners."""
        self.source_clicked.emit(source_type, target_id_or_path, metadata)
