from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QScrollArea,
    QGridLayout,
)
from PySide6.QtCore import Qt, Signal, QMimeData, QPoint
from PySide6.QtGui import QDrag

from models.project import Project
from ui.widgets.project_card import ProjectCard
from ui.theme import BG_DARK, CARD_BG, CARD_HOVER, BORDER_COLOR, TEXT_PRIMARY, TEXT_MUTED, ACCENT


class ActionTile(QFrame):
    """Clean interactive tile for Quick Actions."""

    clicked = Signal()

    def __init__(self, icon_str: str, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self._hovered = False
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_Hover, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(4)

        icon_lbl = QLabel(icon_str)
        icon_lbl.setStyleSheet(f"font-size: 20px; color: {ACCENT};")
        layout.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {TEXT_PRIMARY};")
        layout.addWidget(title_lbl)

        sub_lbl = QLabel(subtitle)
        sub_lbl.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
        layout.addWidget(sub_lbl)

        self._update_style()

    def enterEvent(self, event):
        self._hovered = True
        self._update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._update_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def _update_style(self):
        if self._hovered:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {CARD_HOVER};
                    border: 1px solid {ACCENT};
                    border-radius: 8px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {CARD_BG};
                    border: 1px solid {BORDER_COLOR};
                    border-radius: 8px;
                }}
            """)


class PinnedCard(QFrame):
    """Reorderable Home Pinned Card featuring content previews and drag & drop reordering."""

    card_clicked = Signal(object, str, str)  # (project, board_id, node_id)
    card_reordered = Signal(str, str)  # (source_key, target_key)

    def __init__(self, item_data: dict, parent=None):
        super().__init__(parent)
        self.item_data = item_data
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self._drag_start_pos = None

        p_obj = item_data.get("project")
        b_id = item_data.get("_board_id") or item_data.get("_board_name", "Main")
        n_id = item_data.get("id")
        loc_str = str(p_obj.location) if p_obj else "__workbench__"
        self.key = f"{loc_str}::{b_id}::{n_id}"

        self._hovered = False
        self.setAttribute(Qt.WA_Hover, True)

        attn = item_data.get("_attention", "normal").lower()

        # Border color based on attention priority
        border_col = BORDER_COLOR
        if attn == "urgent":
            border_col = "#EF4444"
        elif attn == "important":
            border_col = "#F59E0B"

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {border_col};
                border-radius: 8px;
                padding: 10px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # Header Row: Icon/Title & Attention indicator
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(6)

        payload = item_data.get("payload", {}) if isinstance(item_data.get("payload"), dict) else {}
        t_id = item_data.get("type", "node")
        title = payload.get("title") or payload.get("filename") or t_id

        title_lbl = QLabel(f"📌 {title}")
        title_lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {TEXT_PRIMARY};")
        hdr_row.addWidget(title_lbl)

        hdr_row.addStretch()

        if attn == "urgent":
            attn_badge = QLabel("🔴 URGENT")
            attn_badge.setStyleSheet("font-size: 9px; font-weight: bold; color: #EF4444; background: rgba(239,68,68,0.15); border-radius: 4px; padding: 2px 4px;")
            hdr_row.addWidget(attn_badge)
        elif attn == "important":
            attn_badge = QLabel("🟡 IMPORTANT")
            attn_badge.setStyleSheet("font-size: 9px; font-weight: bold; color: #F59E0B; background: rgba(245,158,11,0.15); border-radius: 4px; padding: 2px 4px;")
            hdr_row.addWidget(attn_badge)

        layout.addLayout(hdr_row)

        # Body: Content Preview (1-3 lines snippet)
        content = payload.get("content") or payload.get("text") or payload.get("caption") or ""
        preview_str = ""
        if content and isinstance(content, str):
            lines = [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith("- [")]
            preview_str = " ".join(lines[:3])
            if len(preview_str) > 130:
                preview_str = preview_str[:127] + "..."

        if preview_str:
            prev_lbl = QLabel(preview_str)
            prev_lbl.setWordWrap(True)
            prev_lbl.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED}; line-height: 1.3;")
            layout.addWidget(prev_lbl)

        # Footer Badge: Source indicator
        b_name = item_data.get("_board_name", "Main")
        if p_obj:
            badge_str = f"📁 {p_obj.name} · {b_name}"
        else:
            badge_str = f"🛠️ Workbench · {b_name}"

        badge_lbl = QLabel(badge_str)
        badge_lbl.setStyleSheet(f"font-size: 10px; color: #64748B; margin-top: 2px;")
        layout.addWidget(badge_lbl)

    def mousePressEvent(self, event):
        if event and event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not event or not (event.buttons() & Qt.LeftButton) or not self._drag_start_pos:
            return super().mouseMoveEvent(event)

        if (event.pos() - self._drag_start_pos).manhattanLength() < 10:
            return super().mouseMoveEvent(event)

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.key)
        drag.setMimeData(mime_data)
        drag.exec_(Qt.MoveAction)

    def dragEnterEvent(self, event):
        if event and event.mimeData() and event.mimeData().hasText():
            event.acceptProposedAction()
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {CARD_HOVER};
                    border: 2px dashed {ACCENT};
                    border-radius: 8px;
                    padding: 9px;
                }}
            """)

    def dragLeaveEvent(self, event):
        attn = self.item_data.get("_attention", "normal").lower()
        border_col = "#EF4444" if attn == "urgent" else ("#F59E0B" if attn == "important" else BORDER_COLOR)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {border_col};
                border-radius: 8px;
                padding: 10px;
            }}
        """)

    def dropEvent(self, event):
        if event and event.mimeData():
            source_key = event.mimeData().text()
            if source_key and source_key != self.key:
                self.card_reordered.emit(source_key, self.key)
            event.acceptProposedAction()
        self.dragLeaveEvent(event)

    def mouseReleaseEvent(self, event):
        p_obj = self.item_data.get("project")
        b_id = self.item_data.get("_board_id") or self.item_data.get("_board_name", "Main")
        n_id = self.item_data.get("id")
        if not event or (event.button() == Qt.LeftButton and self._drag_start_pos and (event.pos() - self._drag_start_pos).manhattanLength() < 6):
            self.card_clicked.emit(p_obj, b_id, n_id)
        elif not event:
            self.card_clicked.emit(p_obj, b_id, n_id)
        super().mouseReleaseEvent(event)


class HomeWorkspacePanel(QWidget):
    """Spacious Workspace Home landing screen & Daily Command Center ('What needs my attention?')."""

    new_project_requested = Signal()
    open_project_requested = Signal()
    open_recent_requested = Signal()
    open_assets_requested = Signal()
    open_recent_project = Signal(object)  # emits Project
    open_workbench_requested = Signal()
    open_board_requested = Signal(object, str, object)  # emits (project, board_name, target_node_id)

    def __init__(self):
        super().__init__()

        self._context = None
        self._current_task_filter = "All"
        self._cached_pinned_items = []
        self._cached_task_items = []

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
        self.layout.setContentsMargins(28, 28, 28, 28)
        self.layout.setSpacing(24)

        # ---------------------------------------------------------------------
        # Section 1: Hero Greeting Header & Quick Capture
        # ---------------------------------------------------------------------
        greeting_box = QVBoxLayout()
        greeting_box.setSpacing(4)

        hour = datetime.now().hour
        if hour < 12:
            greet_str = "Good Morning"
        elif hour < 18:
            greet_str = "Good Afternoon"
        else:
            greet_str = "Good Evening"

        self.greeting_title = QLabel(greet_str)
        self.greeting_title.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {TEXT_PRIMARY};")
        greeting_box.addWidget(self.greeting_title)

        subtitle = QLabel("Daily Command Center — What needs your attention today?")
        subtitle.setStyleSheet(f"font-size: 14px; color: {TEXT_MUTED};")
        greeting_box.addWidget(subtitle)

        self.layout.addLayout(greeting_box)

        # Quick Capture Bar
        qc_frame = QFrame()
        qc_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 14px;
            }}
            QLabel#qc_title {{
                color: {ACCENT};
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }}
        """)
        qc_layout = QVBoxLayout(qc_frame)
        qc_layout.setSpacing(8)

        qc_title = QLabel("QUICK CAPTURE")
        qc_title.setObjectName("qc_title")
        qc_layout.addWidget(qc_title)

        qc_row = QHBoxLayout()
        qc_row.setSpacing(10)

        self.qc_input = QLineEdit()
        self.qc_input.setPlaceholderText("What are you thinking about? (Capture an unassigned idea, task, or research note...)")
        self.qc_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #14161D;
                color: #F1F5F9;
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {ACCENT};
            }}
        """)
        self.qc_input.returnPressed.connect(self._on_quick_capture_submitted)
        qc_row.addWidget(self.qc_input)

        self.qc_btn = QPushButton("🛠️ Add to Workbench")
        self.qc_btn.setCursor(Qt.PointingHandCursor)
        self.qc_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: #FFFFFF;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 16px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #3B82F6;
            }}
        """)
        self.qc_btn.clicked.connect(self._on_quick_capture_submitted)
        qc_row.addWidget(self.qc_btn)

        qc_layout.addLayout(qc_row)

        self.qc_feedback_lbl = QLabel("")
        self.qc_feedback_lbl.setStyleSheet("color: #34D399; font-size: 11px;")
        self.qc_feedback_lbl.setVisible(False)
        qc_layout.addWidget(self.qc_feedback_lbl)

        self.layout.addWidget(qc_frame)

        # ---------------------------------------------------------------------
        # Section 2: Needs Attention & Urgent Items
        # ---------------------------------------------------------------------
        attention_box = QVBoxLayout()
        attention_box.setSpacing(12)

        attn_header = QLabel("🔴/🟡 NEEDS ATTENTION")
        attn_header.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        attention_box.addWidget(attn_header)

        self.attn_frame = QFrame()
        self.attn_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        self.attn_layout = QVBoxLayout(self.attn_frame)
        self.attn_layout.setSpacing(8)

        self.attn_lbl = QLabel("✅ All project task pipelines & Workbench operating normally")
        self.attn_lbl.setStyleSheet("color: #64748B; font-size: 12px;")
        self.attn_layout.addWidget(self.attn_lbl)

        attention_box.addWidget(self.attn_frame)
        self.layout.addLayout(attention_box)

        # ---------------------------------------------------------------------
        # Section 3: Continue Working (Recent Projects Grid)
        # ---------------------------------------------------------------------
        cw_box = QVBoxLayout()
        cw_box.setSpacing(12)

        cw_title = QLabel("PROJECT OVERVIEW (CONTINUE WORKING)")
        cw_title.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        cw_box.addWidget(cw_title)

        self.recent_grid_widget = QWidget()
        self.recent_grid = QGridLayout(self.recent_grid_widget)
        self.recent_grid.setContentsMargins(0, 0, 0, 0)
        self.recent_grid.setSpacing(16)

        cw_box.addWidget(self.recent_grid_widget)
        self.layout.addLayout(cw_box)

        # ---------------------------------------------------------------------
        # Section 4: Pinned References & Visual Cards (Reorderable)
        # ---------------------------------------------------------------------
        pins_box = QVBoxLayout()
        pins_box.setSpacing(12)

        pins_hdr_row = QHBoxLayout()
        pins_header = QLabel("📌 PINNED REFERENCES & FAVORITES")
        pins_header.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        pins_hdr_row.addWidget(pins_header)

        pins_hdr_row.addStretch()

        pins_hint = QLabel("💡 Drag cards to reorder Home view")
        pins_hint.setStyleSheet("font-size: 10px; color: #64748B;")
        pins_hdr_row.addWidget(pins_hint)

        pins_box.addLayout(pins_hdr_row)

        self.pins_grid_widget = QWidget()
        self.pins_grid = QGridLayout(self.pins_grid_widget)
        self.pins_grid.setContentsMargins(0, 0, 0, 0)
        self.pins_grid.setSpacing(12)
        pins_box.addWidget(self.pins_grid_widget)

        self.layout.addLayout(pins_box)

        # ---------------------------------------------------------------------
        # Section 5: Tasks & Checklists Summary (With Filter Controls)
        # ---------------------------------------------------------------------
        tasks_box = QVBoxLayout()
        tasks_box.setSpacing(12)

        tasks_hdr_row = QHBoxLayout()
        tasks_header = QLabel("☑ TASKS & CHECKLISTS")
        tasks_header.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        tasks_hdr_row.addWidget(tasks_header)

        tasks_hdr_row.addStretch()

        # Task filter buttons
        self.task_filter_btns = {}
        for f_name in ("All", "Active", "Attention", "Completed"):
            btn = QPushButton(f_name)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("filter_name", f_name)
            btn.clicked.connect(lambda _, name=f_name: self._on_task_filter_clicked(name))
            tasks_hdr_row.addWidget(btn)
            self.task_filter_btns[f_name] = btn

        self._update_task_filter_styles()

        tasks_box.addLayout(tasks_hdr_row)

        self.tasks_frame = QFrame()
        self.tasks_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 14px;
            }}
        """)
        self.tasks_layout = QVBoxLayout(self.tasks_frame)
        self.tasks_layout.setSpacing(8)

        self.tasks_summary_lbl = QLabel("No active checklist tasks")
        self.tasks_summary_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: bold;")
        self.tasks_layout.addWidget(self.tasks_summary_lbl)

        self.tasks_list_widget = QWidget()
        self.tasks_list_layout = QVBoxLayout(self.tasks_list_widget)
        self.tasks_list_layout.setContentsMargins(0, 0, 0, 0)
        self.tasks_list_layout.setSpacing(6)
        self.tasks_layout.addWidget(self.tasks_list_widget)

        tasks_box.addWidget(self.tasks_frame)
        self.layout.addLayout(tasks_box)

        # ---------------------------------------------------------------------
        # Section 6: Quick Actions
        # ---------------------------------------------------------------------
        qa_box = QVBoxLayout()
        qa_box.setSpacing(12)

        qa_title = QLabel("QUICK ACTIONS")
        qa_title.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        qa_box.addWidget(qa_title)

        qa_row = QHBoxLayout()
        qa_row.setSpacing(16)

        tile_new = ActionTile("➕", "New Project", "Initialize new creative workspace")
        tile_new.clicked.connect(lambda: self.new_project_requested.emit())
        qa_row.addWidget(tile_new)

        tile_wb = ActionTile("🛠️", "Open Workbench", "Global ideas & study notes space")
        tile_wb.clicked.connect(lambda: self.open_workbench_requested.emit())
        qa_row.addWidget(tile_wb)

        tile_open = ActionTile("📂", "Open Project", "Browse location from disk")
        tile_open.clicked.connect(lambda: self.open_project_requested.emit())
        qa_row.addWidget(tile_open)

        tile_recent = ActionTile("🕒", "Open Recent", "Jump into recently active project")
        tile_recent.clicked.connect(lambda: self.open_recent_requested.emit())
        qa_row.addWidget(tile_recent)

        tile_assets = ActionTile("📚", "Asset Library", "Explore creative asset collection")
        tile_assets.clicked.connect(lambda: self.open_assets_requested.emit())
        qa_row.addWidget(tile_assets)

        qa_box.addLayout(qa_row)
        self.layout.addLayout(qa_box)

        self.layout.addStretch()

        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

    def _update_task_filter_styles(self):
        for f_name, btn in self.task_filter_btns.items():
            if f_name == self._current_task_filter:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {ACCENT};
                        color: #FFFFFF;
                        font-weight: bold;
                        font-size: 10px;
                        padding: 3px 8px;
                        border-radius: 4px;
                        border: none;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #1E2029;
                        color: {TEXT_MUTED};
                        font-size: 10px;
                        padding: 3px 8px;
                        border-radius: 4px;
                        border: 1px solid {BORDER_COLOR};
                    }}
                    QPushButton:hover {{
                        color: {TEXT_PRIMARY};
                    }}
                """)

    def _on_task_filter_clicked(self, filter_name: str):
        self._current_task_filter = filter_name
        self._update_task_filter_styles()
        self._render_tasks_list()

    def _calc_columns(self) -> int:
        avail_w = max(300, self.width() - 80)
        target_card_w = 260
        cols = max(1, avail_w // target_card_w)
        return min(5, cols)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_cols = self._calc_columns()
        if getattr(self, "_last_cols", None) != new_cols:
            self._last_cols = new_cols
            self._regrid_cards()

    def _regrid_cards(self):
        """Rearrange existing grid widgets without re-querying disk or context."""
        cols = getattr(self, "_last_cols", 3)
        for grid in (self.recent_grid, self.pins_grid):
            widgets = []
            while grid.count():
                item = grid.takeAt(0)
                if item.widget():
                    widgets.append(item.widget())
            for idx, w in enumerate(widgets):
                row = idx // cols
                col = idx % cols
                grid.addWidget(w, row, col)

    def _on_quick_capture_submitted(self):
        text = self.qc_input.text().strip()
        if not text:
            return

        if self._context and hasattr(self._context, "lab_service") and self._context.lab_service:
            item = self._context.lab_service.add_quick_capture_note(text)
            if item:
                self.qc_input.clear()
                self.qc_feedback_lbl.setText("✓ Added note to Workbench!")
                self.qc_feedback_lbl.setVisible(True)
                from PySide6.QtCore import QTimer
                QTimer.singleShot(3000, lambda: self.qc_feedback_lbl.setVisible(False))
                self.set_context(self._context)

    def _on_card_clicked(self, project: Project):
        if project:
            try:
                self.open_recent_project.emit(project)
            except Exception:
                pass

    def _on_project_pin_toggled(self, project: Project):
        if not project or not self._context or not getattr(self._context, "project_service", None):
            return
        self._context.project_service.toggle_pin_project(project)
        if hasattr(self._context, "inspector_panel") and self._context.inspector_panel:
            curr = getattr(self._context.inspector_panel, "_current_inspectable", None)
            if curr and getattr(curr, "project", None) and getattr(curr.project, "location", None) == project.location:
                self._context.inspector_panel.show_project(project)
        self.set_context(self._context)

    def set_context(self, context):
        """Provide AppContext and populate recent/pinned project cards, attention items, tasks, and references."""
        self._context = context
        if not context or not getattr(context, "project_service", None):
            return

        if not getattr(self, "_project_updated_connected", False):
            try:
                context.project_service.project_updated.connect(lambda p: self.set_context(self._context))
                self._project_updated_connected = True
            except Exception:
                pass

        projects = context.project_service.all_projects()

        def get_sort_key(p):
            is_fav = 1 if getattr(p, 'is_pinned', False) else 0
            lo = getattr(p, 'last_opened', None)
            cr = getattr(p, 'created', None)
            return (is_fav, lo or cr or datetime.min)

        sorted_projects = sorted(projects, key=get_sort_key, reverse=True)

        all_tasks = []
        all_pinned = []
        all_attention = []

        if hasattr(self._context, "lab_service") and self._context.lab_service:
            lab_svc = self._context.lab_service

            for p in sorted_projects:
                try:
                    summary = lab_svc.get_project_summary_metadata(p)
                    for t in summary.get("task_stats", {}).get("items", []):
                        t_copy = dict(t)
                        t_copy["project"] = p
                        all_tasks.append(t_copy)
                    for pin in summary.get("pinned_nodes", []):
                        pin_copy = dict(pin)
                        pin_copy["project"] = p
                        all_pinned.append(pin_copy)
                except Exception:
                    pass

            # Fetch global Workbench summary metadata
            try:
                wb_summary = lab_svc.get_project_summary_metadata(None)
                for t in wb_summary.get("task_stats", {}).get("items", []):
                    t_copy = dict(t)
                    t_copy["project"] = None
                    all_tasks.append(t_copy)
                for pin in wb_summary.get("pinned_nodes", []):
                    pin_copy = dict(pin)
                    pin_copy["project"] = None
                    all_pinned.append(pin_copy)
            except Exception:
                pass

            # Collect Attention items (Urgent 🔴 & Important 🟡) across pinned & unpinned items
            for p in list(sorted_projects) + [None]:
                try:
                    boards = lab_svc.list_boards(p)
                    for b in boards:
                        b_id = b.get("id")
                        b_name = b.get("name", "Main")
                        if not b_id:
                            continue
                        board_data = lab_svc.load_board(p, b_id)
                        for item in board_data.get("items", []):
                            if not isinstance(item, dict):
                                continue
                            payload = item.get("payload", {}) if isinstance(item.get("payload"), dict) else {}
                            attn = (item.get("attention") or payload.get("attention") or item.get("metadata", {}).get("attention") or "normal").lower()
                            if attn in ("urgent", "important"):
                                it_copy = dict(item)
                                it_copy["project"] = p
                                it_copy["_board_name"] = b_name
                                it_copy["_board_id"] = b_id
                                it_copy["_attention"] = attn
                                all_attention.append(it_copy)
                except Exception:
                    pass

            # Sort Needs Attention items: Urgent first, then Important
            all_attention.sort(key=lambda x: 0 if x.get("_attention") == "urgent" else 1)

            # Reorder pinned nodes based on saved Home presentation preferences
            try:
                saved_order = lab_svc.get_pinned_order()
                if saved_order:
                    key_map = {}
                    for pin in all_pinned:
                        p_obj = pin.get("project")
                        b_id = pin.get("_board_id") or pin.get("_board_name", "Main")
                        n_id = pin.get("id")
                        loc_str = str(p_obj.location) if p_obj else "__workbench__"
                        k = f"{loc_str}::{b_id}::{n_id}"
                        key_map[k] = pin

                    ordered_pinned = []
                    for k in saved_order:
                        if k in key_map:
                            ordered_pinned.append(key_map.pop(k))

                    # Append any newly pinned items not yet in saved_order
                    ordered_pinned.extend(key_map.values())
                    all_pinned = ordered_pinned
            except Exception:
                pass

        self._cached_pinned_items = all_pinned
        self._cached_task_items = all_tasks

        # ---------------------------------------------------------------------
        # Render Needs Attention Section
        # ---------------------------------------------------------------------
        while self.attn_layout.count():
            item = self.attn_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not all_attention:
            self.attn_lbl = QLabel("✅ All project task pipelines & Workbench operating normally")
            self.attn_lbl.setStyleSheet("color: #64748B; font-size: 12px;")
            self.attn_layout.addWidget(self.attn_lbl)
        else:
            for item_data in all_attention[:6]:
                row = QHBoxLayout()
                row.setSpacing(8)

                attn = item_data.get("_attention", "normal")
                badge_lbl = QLabel("🔴 URGENT" if attn == "urgent" else "🟡 IMPORTANT")
                badge_lbl.setStyleSheet(f"font-size: 10px; font-weight: bold; color: {'#EF4444' if attn == 'urgent' else '#F59E0B'}; background: rgba({'239,68,68' if attn == 'urgent' else '245,158,11'}, 0.15); border-radius: 4px; padding: 2px 6px;")
                row.addWidget(badge_lbl)

                payload = item_data.get("payload", {}) if isinstance(item_data.get("payload"), dict) else {}
                title = payload.get("title") or payload.get("filename") or item_data.get("type", "Item")
                txt_lbl = QLabel(title)
                txt_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: bold;")
                row.addWidget(txt_lbl)

                row.addStretch()

                p_obj = item_data.get("project")
                b_name = item_data.get("_board_name", "Main")
                b_id = item_data.get("_board_id") or b_name
                n_id = item_data.get("id")

                source_str = f"📁 {p_obj.name} · {b_name}" if p_obj else f"🛠️ Workbench · {b_name}"
                src_lbl = QLabel(source_str)
                src_lbl.setStyleSheet("color: #64748B; font-size: 10px;")
                row.addWidget(src_lbl)

                w = QWidget()
                w.setCursor(Qt.PointingHandCursor)
                w.setLayout(row)
                w.mousePressEvent = lambda _, proj=p_obj, b=b_id, nid=n_id: self.open_board_requested.emit(proj, b, nid)
                self.attn_layout.addWidget(w)

        # Render Tasks List
        self._render_tasks_list()

        # ---------------------------------------------------------------------
        # Render Reorderable Pinned Grid
        # ---------------------------------------------------------------------
        while self.pins_grid.count():
            item = self.pins_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not all_pinned:
            lbl = QLabel("📌 No pinned reference items across projects or Workbench yet")
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
            self.pins_grid.addWidget(lbl, 0, 0)
        else:
            cols = self._calc_columns()
            for idx, p_item in enumerate(all_pinned[:6]):
                col = idx % cols
                row = idx // cols

                card = PinnedCard(p_item)
                card.card_clicked.connect(lambda proj, b, nid: self.open_board_requested.emit(proj, b, nid))
                card.card_reordered.connect(self._on_pinned_card_reordered)
                self.pins_grid.addWidget(card, row, col)

        # ---------------------------------------------------------------------
        # Populate Continue Working Grid
        # ---------------------------------------------------------------------
        while self.recent_grid.count():
            item = self.recent_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        columns = self._calc_columns()
        for idx, proj in enumerate(sorted_projects):
            row = idx // columns
            col = idx % columns
            card = ProjectCard(proj, compact=False)
            card.clicked.connect(self._on_card_clicked)
            card.double_clicked.connect(self._on_card_clicked)
            card.pin_toggled.connect(self._on_project_pin_toggled)
            self.recent_grid.addWidget(card, row, col)

    def _render_tasks_list(self):
        """Render Tasks section matching active filter without re-querying disk."""
        while self.tasks_list_layout.count():
            item = self.tasks_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        all_tasks = getattr(self, "_cached_task_items", [])

        filtered_tasks = []
        for t in all_tasks:
            is_comp = t.get("completed", False)
            attn = t.get("attention", "normal")
            if self._current_task_filter == "Active" and is_comp:
                continue
            if self._current_task_filter == "Completed" and not is_comp:
                continue
            if self._current_task_filter == "Attention" and attn not in ("urgent", "important"):
                continue
            filtered_tasks.append(t)

        if not filtered_tasks:
            self.tasks_summary_lbl.setText(f"No {self._current_task_filter.lower()} checklist tasks")
            lbl = QLabel("Create note nodes with '- [ ] Task' inside project Labs or Workbench to track production checklists.")
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
            self.tasks_list_layout.addWidget(lbl)
        else:
            completed_cnt = sum(1 for t in all_tasks if t.get("completed"))
            self.tasks_summary_lbl.setText(f"{completed_cnt} / {len(all_tasks)} Tasks Completed across projects & Workbench")

            for t_item in filtered_tasks[:8]:
                t_row = QHBoxLayout()
                t_row.setSpacing(8)

                is_comp = t_item.get("completed", False)
                chk_btn = QPushButton("☑" if is_comp else "☐")
                chk_btn.setCursor(Qt.PointingHandCursor)
                chk_btn.setStyleSheet(f"color: {'#34D399' if is_comp else TEXT_MUTED}; font-size: 13px; background: none; border: none; padding: 0px;")

                p_obj = t_item.get("project")
                b_name = t_item.get("board_name", "Main")
                b_id = t_item.get("board_id") or b_name
                n_id = t_item.get("node_id")
                t_text = t_item.get("text", "")

                chk_btn.clicked.connect(lambda _, proj=p_obj, b=b_id, nid=n_id, txt=t_text, cur=is_comp: self._on_task_toggled(proj, b, nid, txt, not cur))
                t_row.addWidget(chk_btn)

                txt_lbl = QLabel(t_text)
                txt_lbl.setStyleSheet(f"color: {TEXT_PRIMARY if not is_comp else TEXT_MUTED}; font-size: 12px;")
                t_row.addWidget(txt_lbl)

                t_row.addStretch()

                if p_obj:
                    badge_str = f"📁 {p_obj.name} · {b_name}"
                else:
                    badge_str = f"🛠️ Workbench · {b_name}"
                b_lbl = QLabel(badge_str)
                b_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
                t_row.addWidget(b_lbl)

                t_widget = QWidget()
                t_widget.setCursor(Qt.PointingHandCursor)
                t_widget.setLayout(t_row)
                t_widget.mousePressEvent = lambda _, proj=p_obj, b=b_id, nid=n_id: self.open_board_requested.emit(proj, b, nid)
                self.tasks_list_layout.addWidget(t_widget)

    def _on_task_toggled(self, project, board_id: str, node_id: str, task_text: str, target_completed: bool):
        if self._context and hasattr(self._context, "lab_service") and self._context.lab_service:
            updated = self._context.lab_service.toggle_task_completion(project, board_id, node_id, task_text, target_completed)
            if updated:
                self.set_context(self._context)

    def _on_pinned_card_reordered(self, source_key: str, target_key: str):
        """Reorder presentation list pinned_order without modifying canvas spatial coordinates."""
        if not self._context or not hasattr(self._context, "lab_service") or not self._context.lab_service:
            return

        lab_svc = self._context.lab_service
        current_keys = []
        for pin in self._cached_pinned_items:
            p_obj = pin.get("project")
            b_id = pin.get("_board_id") or pin.get("_board_name", "Main")
            n_id = pin.get("id")
            loc_str = str(p_obj.location) if p_obj else "__workbench__"
            current_keys.append(f"{loc_str}::{b_id}::{n_id}")

        if source_key in current_keys and target_key in current_keys:
            current_keys.remove(source_key)
            target_idx = current_keys.index(target_key)
            current_keys.insert(target_idx, source_key)
            lab_svc.save_pinned_order(current_keys)
            self.set_context(self._context)
