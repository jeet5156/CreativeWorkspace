"""Project Dashboard Panel for CreativeWorkspace (Phase 5A).

Aggregates and displays live project context:
- Project Metadata & Identity
- High-level metric cards (Knowledge, Assets, Library, Lab)
- Library references availability breakdown (Available, Offline, Missing, Changed)
- Recent Knowledge documentation with direct navigation
- Active Creative Lab boards with node counts
- Asset version groups & LOD summaries
- Project tasks & checklist progress derived from Lab nodes
"""

from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QTextEdit,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFormLayout,
    QFrame,
    QScrollArea,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal

from ui.widgets.image_preview import ImagePreview
from ui.widgets.project_summary_card import ProjectMetricCard, ProjectAvailabilityCard
from ui.widgets.project_ai_assistant_widget import ProjectAIAssistantWidget
from models.project import Project
from models.project_context import ProjectContext
from ui.theme import (
    BG_DARK,
    CARD_BG,
    CARD_HOVER,
    BORDER_COLOR,
    TEXT_PRIMARY,
    TEXT_MUTED,
    ACCENT,
)


class ClickableFrame(QFrame):
    """Clickable row/card widget emitting clicked signal."""
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class DashboardPanel(QWidget):
    """Inspiring, native Project Overview & Context Dashboard."""

    project_reveal = Signal(object)
    open_lab_requested = Signal(object, str)
    open_knowledge_requested = Signal(object, str)
    navigate_section_requested = Signal(object, str, str)

    def __init__(self):
        super().__init__()

        self._context = None
        self._current_project: Optional[Project] = None
        self._current_project_context: Optional[ProjectContext] = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet(f"QScrollArea {{ background-color: {BG_DARK}; border: none; }}")

        container = QWidget()
        container.setStyleSheet(f"QWidget {{ background-color: {BG_DARK}; }}")
        self.layout = QVBoxLayout(container)
        self.layout.setContentsMargins(24, 24, 24, 24)
        self.layout.setSpacing(20)

        # ---------------------------------------------------------------------
        # 1. Hero Header (Project Identity, Badges & Action Buttons)
        # ---------------------------------------------------------------------
        hero_layout = QVBoxLayout()
        hero_layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self.name_value = QLabel("Project Dashboard")
        self.name_value.setCursor(Qt.PointingHandCursor)
        self.name_value.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {TEXT_PRIMARY};")
        self.name_value.mouseReleaseEvent = lambda e: self._on_title_clicked(e)
        top_row.addWidget(self.name_value)

        top_row.addStretch()

        self.priority_badge = QLabel("Medium")
        self.priority_badge.setStyleSheet(
            "font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 4px; "
            "background-color: #3B2D1B; color: #FBBF24;"
        )
        top_row.addWidget(self.priority_badge)

        self.status_badge = QLabel("Active")
        self.status_badge.setStyleSheet(
            "font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 4px; "
            "background-color: #14382B; color: #34D399;"
        )
        top_row.addWidget(self.status_badge)

        # Refresh button
        self.refresh_btn = QPushButton("↻ Refresh")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setToolTip("Re-aggregate project context and live availability")
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {CARD_BG};
                color: {TEXT_PRIMARY};
                font-size: 12px;
                font-weight: 500;
                padding: 6px 12px;
                border-radius: 6px;
                border: 1px solid {BORDER_COLOR};
            }}
            QPushButton:hover {{
                background-color: {CARD_HOVER};
                border: 1px solid {ACCENT};
            }}
        """)
        self.refresh_btn.clicked.connect(self.refresh)
        top_row.addWidget(self.refresh_btn)

        # Open Creative Lab button
        self.open_lab_btn = QPushButton("🎨 Open Creative Lab")
        self.open_lab_btn.setCursor(Qt.PointingHandCursor)
        self.open_lab_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: #FFFFFF;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #3B82F6;
            }}
        """)
        self.open_lab_btn.clicked.connect(self._on_open_lab_clicked)
        top_row.addWidget(self.open_lab_btn)

        hero_layout.addLayout(top_row)

        sub_row = QHBoxLayout()
        self.type_value = QLabel("📁 General Project")
        self.type_value.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED};")
        sub_row.addWidget(self.type_value)

        self.path_value = QLabel("")
        self.path_value.setStyleSheet(f"font-size: 11px; color: #64748B; font-family: monospace;")
        sub_row.addWidget(self.path_value)
        sub_row.addStretch()

        hero_layout.addLayout(sub_row)
        self.layout.addLayout(hero_layout)

        # ---------------------------------------------------------------------
        # 2. Top Metric Cards Row (Knowledge, Assets, Library, Lab)
        # ---------------------------------------------------------------------
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(14)

        self.card_knowledge = ProjectMetricCard("Knowledge", icon="📖", count=0, subtitle="Documentation notes")
        self.card_knowledge.clicked.connect(lambda: self._navigate_to("knowledge"))
        metrics_row.addWidget(self.card_knowledge)

        self.card_assets = ProjectMetricCard("Assets", icon="🧊", count=0, subtitle="Project-local files")
        self.card_assets.clicked.connect(lambda: self._navigate_to("assets"))
        metrics_row.addWidget(self.card_assets)

        self.card_library = ProjectMetricCard("Library", icon="📚", count=0, subtitle="Global references")
        self.card_library.clicked.connect(lambda: self._navigate_to("library_references"))
        metrics_row.addWidget(self.card_library)

        self.card_lab = ProjectMetricCard("Lab", icon="🎨", count=0, subtitle="Spatial boards")
        self.card_lab.clicked.connect(lambda: self._navigate_to("lab"))
        metrics_row.addWidget(self.card_lab)

        self.layout.addLayout(metrics_row)

        # ---------------------------------------------------------------------
        # 3. Two-Column Dashboard Content Layout
        # ---------------------------------------------------------------------
        content_cols = QHBoxLayout()
        content_cols.setSpacing(16)

        # Left Column: Library Availability & Recent Knowledge
        left_col = QVBoxLayout()
        left_col.setSpacing(16)

        # 3A. Library Availability Card
        self.availability_card = ProjectAvailabilityCard()
        self.availability_card.filter_requested.connect(self._on_availability_filter_clicked)
        left_col.addWidget(self.availability_card)

        # 3B. Recent Knowledge Section
        self.knowledge_box = self._create_section_box("RECENT KNOWLEDGE", "📄 View All Notes", lambda: self._navigate_to("knowledge"))
        self.knowledge_list_layout = QVBoxLayout()
        self.knowledge_list_layout.setSpacing(6)
        self.knowledge_box.layout().addLayout(self.knowledge_list_layout)
        left_col.addWidget(self.knowledge_box)

        # 3C. Overview & Metadata Box
        self.meta_box = self._create_section_box("PROJECT OVERVIEW & DETAILS")
        self.desc_edit = QTextEdit()
        self.desc_edit.setReadOnly(True)
        self.desc_edit.setMaximumHeight(48)
        self.desc_edit.setStyleSheet(f"background-color: #14161D; color: #CBD5E1; border: 1px solid {BORDER_COLOR}; border-radius: 6px; padding: 6px; font-size: 11px;")
        self.meta_box.layout().addWidget(self.desc_edit)

        self.meta_form = QFormLayout()
        self.meta_form.setSpacing(4)
        self.client_val = QLabel("-")
        self.client_val.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        self.created_val = QLabel("-")
        self.created_val.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        self.modified_val = QLabel("-")
        self.modified_val.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        self.meta_form.addRow("Client:", self.client_val)
        self.meta_form.addRow("Created:", self.created_val)
        self.meta_form.addRow("Modified:", self.modified_val)
        self.meta_box.layout().addLayout(self.meta_form)
        left_col.addWidget(self.meta_box)

        content_cols.addLayout(left_col, stretch=1)

        # Right Column: Lab Boards & Asset Version Summaries & Tasks
        right_col = QVBoxLayout()
        right_col.setSpacing(18)

        # 3D. Recent / Active Lab Boards
        self.lab_box = self._create_section_box("RECENT / ACTIVE LAB BOARDS", "🎨 Open Lab", self._on_open_lab_clicked)
        self.lab_list_layout = QVBoxLayout()
        self.lab_list_layout.setSpacing(6)
        self.lab_box.layout().addLayout(self.lab_list_layout)
        right_col.addWidget(self.lab_box)

        # 3E. Project Assets & Version Overview
        self.assets_box = self._create_section_box("PROJECT ASSETS & VERSIONS", "🧊 View Assets", lambda: self._navigate_to("assets"))
        self.versions_list_layout = QVBoxLayout()
        self.versions_list_layout.setSpacing(6)
        self.assets_box.layout().addLayout(self.versions_list_layout)
        right_col.addWidget(self.assets_box)

        # 3F. Tasks & Checklists Section
        self.tasks_box = self._create_section_box("TASKS & CHECKLISTS")
        self.task_summary_lbl = QLabel("0 tasks total")
        self.task_summary_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: bold;")
        self.tasks_box.layout().addWidget(self.task_summary_lbl)

        self.task_progress_bar = QProgressBar()
        self.task_progress = self.task_progress_bar
        self.task_progress_bar.setFixedHeight(6)
        self.task_progress_bar.setTextVisible(False)
        self.task_progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #1E293B;
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: #34D399;
                border-radius: 3px;
            }}
        """)
        self.tasks_box.layout().addWidget(self.task_progress_bar)

        self.task_items_layout = QVBoxLayout()
        self.task_items_layout.setSpacing(4)
        self.tasks_box.layout().addLayout(self.task_items_layout)
        right_col.addWidget(self.tasks_box)

        content_cols.addLayout(right_col, stretch=1)

        self.layout.addLayout(content_cols)

        # ---------------------------------------------------------------------
        # 4. Project AI Assistant (Phase 5B)
        # ---------------------------------------------------------------------
        self.ai_assistant_widget = ProjectAIAssistantWidget()
        self.ai_assistant_widget.source_clicked.connect(self._on_assistant_source_clicked)
        self.ai_assistant_widget.open_settings_requested.connect(self._on_open_settings_requested)
        self.layout.addWidget(self.ai_assistant_widget)

        self.layout.addStretch()

        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

    # -------------------------------------------------------------------------
    # Context & Signal Wiring
    # -------------------------------------------------------------------------

    def set_context(self, context):
        """Provide AppContext and hook into signals."""
        self._context = context
        if context and getattr(context, "project_context_service", None):
            try:
                context.project_context_service.context_updated.connect(self._on_context_updated)
            except Exception:
                pass
        if context and getattr(context, "project_assistant_service", None):
            try:
                self.ai_assistant_widget.set_assistant_service(context.project_assistant_service)
            except Exception:
                pass
        if context and getattr(context, "lab_service", None):
            try:
                context.lab_service.board_updated.connect(lambda *args: self.refresh())
                context.lab_service.manifest_updated.connect(lambda *args: self.refresh())
            except Exception:
                pass
        if context and getattr(context, "asset_service", None):
            try:
                context.asset_service.assets_changed.connect(lambda *args: self.refresh())
            except Exception:
                pass
        if context and getattr(context, "project_service", None):
            try:
                context.project_service.project_updated.connect(lambda *args: self.refresh())
            except Exception:
                pass

    def _on_context_updated(self, project_context: ProjectContext):
        if not self._current_project:
            return
        if project_context.project_path == getattr(self._current_project, "location", "") or project_context.project_name == self._current_project.name:
            self._render_context(project_context)

    # -------------------------------------------------------------------------
    # Public Display & Refresh API
    # -------------------------------------------------------------------------

    def show_project(self, project: Project):
        """Display dashboard for the specified project."""
        if not project:
            self.clear()
            return

        self._current_project = project
        self.refresh()

    def refresh(self):
        """Re-aggregate project context and re-render dashboard."""
        if not self._current_project:
            self.clear()
            return

        if self._context and getattr(self._context, "project_context_service", None):
            ctx = self._context.project_context_service.get_project_context(self._current_project)
        else:
            from services.project_context_service import ProjectContextService
            pcs = ProjectContextService(
                context=self._context,
                project_service=getattr(self._context, "project_service", None) if self._context else None,
                asset_service=getattr(self._context, "asset_service", None) if self._context else None,
                library_service=getattr(self._context, "library_service", None) if self._context else None,
                knowledge_service=getattr(self._context, "knowledge_service", None) if self._context else None,
                lab_service=getattr(self._context, "lab_service", None) if self._context else None,
            )
            ctx = pcs.get_project_context(self._current_project)

        self._render_context(ctx)

    def clear(self):
        """Cleanly reset all displayed metrics and sections."""
        self._current_project = None
        self._current_project_context = None

        self.name_value.setText("Project Dashboard")
        self.type_value.setText("No project selected")
        self.path_value.setText("")
        self.priority_badge.setText("Medium")
        self.status_badge.setText("Inactive")

        self.card_knowledge.set_count(0)
        self.card_assets.set_count(0)
        self.card_library.set_count(0)
        self.card_lab.set_count(0)

        self.availability_card.update_counts(0, 0, 0, 0)
        self.desc_edit.setText("")
        self.client_val.setText("-")
        self.created_val.setText("-")
        self.modified_val.setText("-")

        self._clear_layout(self.knowledge_list_layout)
        self._clear_layout(self.lab_list_layout)
        self._clear_layout(self.versions_list_layout)
        self._clear_layout(self.task_items_layout)

        self.task_summary_lbl.setText("0 tasks total")
        self.task_progress.setValue(0)
        if hasattr(self, "ai_assistant_widget"):
            self.ai_assistant_widget.clear_chat()

    # -------------------------------------------------------------------------
    # Render Implementation
    # -------------------------------------------------------------------------

    def _render_context(self, ctx: ProjectContext):
        self._current_project_context = ctx

        # 1. Header Information
        self.name_value.setText(ctx.project_name or "Untitled Project")
        p_type = (ctx.project_type or "general").capitalize()
        self.type_value.setText(f"📁 {p_type} Project")
        self.path_value.setText(ctx.project_path)

        p_priority = str(ctx.metadata.get("priority", "medium")).capitalize()
        self.priority_badge.setText(p_priority)
        if p_priority == "High":
            self.priority_badge.setStyleSheet("font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 4px; background-color: #3F1D24; color: #F87171;")
        else:
            self.priority_badge.setStyleSheet("font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 4px; background-color: #3B2D1B; color: #FBBF24;")

        p_status = str(ctx.metadata.get("status", "active")).capitalize()
        self.status_badge.setText(p_status)

        # 2. Metric Cards
        k_count = ctx.knowledge_summary.total_notes
        k_fav = ctx.knowledge_summary.favorite_notes
        self.card_knowledge.set_count(k_count, f"{k_fav} favorite{'s' if k_fav != 1 else ''}" if k_fav else "Documentation notes")

        a_count = ctx.asset_summary.total_assets
        self.card_assets.set_count(a_count, f"{len(ctx.asset_summary.by_category)} categories")

        lib_count = ctx.library_summary.total_linked_assets
        self.card_library.set_count(lib_count, f"{ctx.library_summary.available_assets} online")

        lab_count = ctx.lab_summary.total_boards
        self.card_lab.set_count(lab_count, f"{ctx.lab_summary.total_nodes} spatial nodes")

        # 3. Library Availability Card
        avail = ctx.availability_summary
        self.availability_card.update_counts(
            available=avail.online_library_assets,
            offline=avail.offline_library_assets,
            missing=avail.missing_library_assets,
            changed=avail.possibly_changed_assets,
        )

        # 4. Overview & Metadata
        self.desc_edit.setText(ctx.metadata.get("description", "") or "No description provided.")
        self.client_val.setText(ctx.metadata.get("client", "") or "None")
        self.created_val.setText(ctx.created[:10] if ctx.created else "-")
        self.modified_val.setText(ctx.modified[:10] if ctx.modified else "-")

        # 5. Recent Knowledge Section
        self._render_recent_knowledge(ctx.knowledge_summary.recent_notes)

        # 6. Recent Lab Boards Section
        self._render_recent_lab(ctx.lab_summary.recent_boards)

        # 7. Asset Versions Section
        self._render_versions(ctx.asset_summary)

        # 8. Tasks Section
        self._render_tasks(ctx.lab_summary.task_status)

        # 9. Project AI Assistant (Phase 5B)
        if hasattr(self, "ai_assistant_widget"):
            self.ai_assistant_widget.set_project(ctx)

    def _render_recent_knowledge(self, notes: List[Dict[str, Any]]):
        self._clear_layout(self.knowledge_list_layout)
        if not notes:
            placeholder = QLabel("📄 No Knowledge documents explicitly linked yet.")
            placeholder.setStyleSheet("color: #64748B; font-size: 11px; padding: 6px 0;")
            self.knowledge_list_layout.addWidget(placeholder)
            return

        for note in notes[:5]:
            row = ClickableFrame()
            row.setStyleSheet(f"""
                ClickableFrame {{
                    background-color: #14161D;
                    border: 1px solid {BORDER_COLOR};
                    border-radius: 6px;
                    padding: 6px 10px;
                }}
                ClickableFrame:hover {{
                    background-color: {CARD_HOVER};
                    border: 1px solid {ACCENT};
                }}
            """)
            r_lay = QHBoxLayout(row)
            r_lay.setContentsMargins(8, 6, 8, 6)
            r_lay.setSpacing(8)

            doc_id = note.get("id")
            title = note.get("title", "Untitled Note")
            fav = bool(note.get("is_favorite"))

            icon_txt = "⭐ 📄" if fav else "📄"
            icon_lbl = QLabel(icon_txt)
            icon_lbl.setStyleSheet("font-size: 12px;")
            r_lay.addWidget(icon_lbl)

            title_lbl = QLabel(title)
            title_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 500;")
            r_lay.addWidget(title_lbl)

            r_lay.addStretch()

            mod_str = str(note.get("modified", ""))[:10]
            if mod_str:
                date_lbl = QLabel(mod_str)
                date_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
                r_lay.addWidget(date_lbl)

            row.clicked.connect(lambda d_id=doc_id: self._on_knowledge_item_clicked(d_id))
            self.knowledge_list_layout.addWidget(row)

    def _render_recent_lab(self, boards: List[Dict[str, Any]]):
        self._clear_layout(self.lab_list_layout)
        if not boards:
            placeholder = QLabel("🎨 No Lab boards found.")
            placeholder.setStyleSheet("color: #64748B; font-size: 11px; padding: 6px 0;")
            self.lab_list_layout.addWidget(placeholder)
            return

        for b in boards[:5]:
            row = ClickableFrame()
            row.setStyleSheet(f"""
                ClickableFrame {{
                    background-color: #14161D;
                    border: 1px solid {BORDER_COLOR};
                    border-radius: 6px;
                    padding: 6px 10px;
                }}
                ClickableFrame:hover {{
                    background-color: {CARD_HOVER};
                    border: 1px solid {ACCENT};
                }}
            """)
            r_lay = QHBoxLayout(row)
            r_lay.setContentsMargins(8, 6, 8, 6)
            r_lay.setSpacing(8)

            b_name = b.get("name", "Main")
            node_cnt = b.get("node_count", 0)

            icon_lbl = QLabel("🎨")
            icon_lbl.setStyleSheet("font-size: 12px;")
            r_lay.addWidget(icon_lbl)

            name_lbl = QLabel(b_name)
            name_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 500;")
            r_lay.addWidget(name_lbl)

            r_lay.addStretch()

            cnt_lbl = QLabel(f"{node_cnt} node{'s' if node_cnt != 1 else ''}")
            cnt_lbl.setStyleSheet("font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 3px; background-color: #1E2E4A; color: #60A5FA;")
            r_lay.addWidget(cnt_lbl)

            row.clicked.connect(lambda b_n=b_name: self._on_lab_board_clicked(b_n))
            self.lab_list_layout.addWidget(row)

    def _render_versions(self, asset_summary):
        self._clear_layout(self.versions_list_layout)
        version_groups = asset_summary.version_groups
        if not version_groups:
            # Show category distribution fallback
            cats = asset_summary.by_category
            if not cats:
                placeholder = QLabel("🧊 No project assets indexed yet.")
                placeholder.setStyleSheet("color: #64748B; font-size: 11px; padding: 6px 0;")
                self.versions_list_layout.addWidget(placeholder)
                return

            for cat, count in list(cats.items())[:4]:
                row = QFrame()
                row.setStyleSheet(f"background-color: #14161D; border: 1px solid {BORDER_COLOR}; border-radius: 6px; padding: 4px 8px;")
                r_lay = QHBoxLayout(row)
                r_lay.setContentsMargins(6, 4, 6, 4)
                lbl = QLabel(f"📁 {cat}")
                lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 11px;")
                cnt = QLabel(f"{count} files")
                cnt.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
                r_lay.addWidget(lbl)
                r_lay.addStretch()
                r_lay.addWidget(cnt)
                self.versions_list_layout.addWidget(row)
            return

        for grp in version_groups[:4]:
            row = ClickableFrame()
            row.setStyleSheet(f"""
                ClickableFrame {{
                    background-color: #14161D;
                    border: 1px solid {BORDER_COLOR};
                    border-radius: 6px;
                    padding: 6px 10px;
                }}
                ClickableFrame:hover {{
                    background-color: {CARD_HOVER};
                    border: 1px solid {ACCENT};
                }}
            """)
            r_lay = QHBoxLayout(row)
            r_lay.setContentsMargins(8, 6, 8, 6)
            r_lay.setSpacing(8)

            name = grp.get("logical_name", "Asset")
            latest = grp.get("latest", "v001")
            cnt = grp.get("count", 1)

            lbl = QLabel(f"📦 {name}")
            lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 500;")
            r_lay.addWidget(lbl)

            r_lay.addStretch()

            v_badge = QLabel(f"Latest: {latest} ({cnt} versions)")
            v_badge.setStyleSheet("font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 3px; background-color: #14382B; color: #34D399;")
            r_lay.addWidget(v_badge)

            row.clicked.connect(lambda: self._navigate_to("assets"))
            self.versions_list_layout.addWidget(row)

    def _render_tasks(self, task_status: Dict[str, int]):
        self._clear_layout(self.task_items_layout)
        total = task_status.get("total", 0)
        completed = task_status.get("completed", 0)
        pending = task_status.get("pending", 0)

        if total > 0:
            pct = int((completed / total) * 100)
            self.task_progress.setValue(pct)
            self.task_summary_lbl.setText(f"{completed} / {total} Tasks Completed ({pct}%)")

            # Quick summary badges
            row = QHBoxLayout()
            row.setSpacing(8)

            comp_badge = QLabel(f"🟢 Completed: {completed}")
            comp_badge.setStyleSheet("font-size: 11px; color: #34D399; font-weight: bold;")
            row.addWidget(comp_badge)

            pend_badge = QLabel(f"⚪ Pending: {pending}")
            pend_badge.setStyleSheet("font-size: 11px; color: #94A3B8; font-weight: bold;")
            row.addWidget(pend_badge)
            row.addStretch()

            self.task_items_layout.addLayout(row)
        else:
            self.task_progress.setValue(0)
            self.task_summary_lbl.setText("No checklist tasks logged in Lab notes")

    # -------------------------------------------------------------------------
    # Helper Layout Creators
    # -------------------------------------------------------------------------

    def _create_section_box(self, title: str, action_text: str = None, action_callback = None) -> QFrame:
        box = QFrame()
        box.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 14px;
            }}
            QLabel#box_title {{
                color: {ACCENT};
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }}
        """)
        b_lay = QVBoxLayout(box)
        b_lay.setContentsMargins(14, 12, 14, 12)
        b_lay.setSpacing(10)

        header_row = QHBoxLayout()
        t_lbl = QLabel(title)
        t_lbl.setObjectName("box_title")
        header_row.addWidget(t_lbl)
        header_row.addStretch()

        if action_text and action_callback:
            act_btn = QPushButton(action_text)
            act_btn.setCursor(Qt.PointingHandCursor)
            act_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {ACCENT};
                    font-size: 11px;
                    font-weight: bold;
                    border: none;
                    padding: 0;
                }}
                QPushButton:hover {{
                    color: #60A5FA;
                    text-decoration: underline;
                }}
            """)
            act_btn.clicked.connect(action_callback)
            header_row.addWidget(act_btn)

        b_lay.addLayout(header_row)
        return box

    def _clear_layout(self, layout):
        if not layout:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    # -------------------------------------------------------------------------
    # Navigation Action Handlers
    # -------------------------------------------------------------------------

    def _on_title_clicked(self, event):
        if event.button() == Qt.LeftButton and self._current_project:
            self.project_reveal.emit(self._current_project)

    def _on_open_lab_clicked(self):
        if self._current_project:
            self.open_lab_requested.emit(self._current_project, "Main")
            if self._context and hasattr(self._context, "workspace_manager") and self._context.workspace_manager:
                self._context.workspace_manager.show_project(self._current_project, section="lab")

    def _on_lab_board_clicked(self, board_name: str):
        if self._current_project:
            self.open_lab_requested.emit(self._current_project, board_name)
            if self._context and hasattr(self._context, "workspace_manager") and self._context.workspace_manager:
                wm = self._context.workspace_manager
                if getattr(wm, "lab_panel", None):
                    wm.lab_panel.show_project(self._current_project, board_name=board_name)
                wm.show_project(self._current_project, section="lab")

    def _on_knowledge_item_clicked(self, doc_id: str):
        if self._current_project:
            self.open_knowledge_requested.emit(self._current_project, doc_id)
            if self._context and hasattr(self._context, "workspace_manager") and self._context.workspace_manager:
                wm = self._context.workspace_manager
                wm.show_module("knowledge")
                if getattr(wm, "knowledge_panel", None) and hasattr(wm.knowledge_panel, "select_document"):
                    try:
                        wm.knowledge_panel.select_document(doc_id)
                    except Exception:
                        pass

    def _on_availability_filter_clicked(self, status_key: str):
        if self._current_project:
            self._navigate_to("library_references")

    def _navigate_to(self, section: str):
        if not self._current_project:
            return
        self.navigate_section_requested.emit(self._current_project, section, "")
        if self._context and hasattr(self._context, "workspace_manager") and self._context.workspace_manager:
            wm = self._context.workspace_manager
            if section in ("knowledge",):
                wm.show_module("knowledge")
            elif section in ("lab",):
                wm.show_project(self._current_project, section="lab")
            else:
                wm.show_project(self._current_project, section=section)

    def _on_assistant_source_clicked(self, source_type: str, target: str, metadata: dict):
        if not self._current_project:
            return
        wm = getattr(self._context, "workspace_manager", None) if self._context else None

        from core.navigation import NavigationPayload
        if source_type in ("knowledge",):
            if wm:
                wm.navigate(NavigationPayload.for_knowledge_doc(target, metadata=metadata))
            else:
                self._on_knowledge_item_clicked(target)
        elif source_type in ("lab_board", "lab_task", "lab_node"):
            board_id = metadata.get("board_id") or (target if source_type == "lab_board" else "Main")
            node_id = target if source_type in ("lab_task", "lab_node") else None
            if wm:
                wm.navigate(NavigationPayload.for_lab_node(node_id, board_id=board_id, project_or_name=self._current_project, metadata=metadata))
            else:
                self._on_lab_board_clicked(board_id)
        elif source_type in ("asset",):
            rel_p = metadata.get("relative_path")
            if wm:
                wm.navigate(NavigationPayload.for_project_asset(self._current_project, target, rel_path=rel_p, metadata=metadata))
            else:
                self._navigate_to("assets")
        elif source_type in ("library_asset",):
            if wm:
                wm.navigate(NavigationPayload.for_library_asset(target, metadata=metadata))
            else:
                self._navigate_to("library_references")
        elif source_type in ("project",):
            if wm:
                wm.navigate(NavigationPayload.for_project(self._current_project))

    def _on_open_settings_requested(self, section: str):
        if self._context and hasattr(self._context, "settings_dialog") and self._context.settings_dialog:
            try:
                self._context.settings_dialog.show()
            except Exception:
                pass
