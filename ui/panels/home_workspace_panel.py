from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
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
    QComboBox,
    QMenu,
    QApplication,
)
from PySide6.QtCore import Qt, Signal, QMimeData, QPoint
from PySide6.QtGui import QDrag

from models.project import Project
from ui.widgets.project_card import ProjectCard
from ui.theme import BG_DARK, CARD_BG, CARD_HOVER, BORDER_COLOR, TEXT_PRIMARY, TEXT_MUTED, ACCENT


class QuickTaskDatePickerBtn(QPushButton):
    """Compact Quick Task due-date picker button with preset options and a custom Qt QCalendarWidget picker."""

    date_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self._selected_date = None
        self._update_button_text()

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: #14161D;
                color: #CBD5E1;
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                min-width: 110px;
                text-align: left;
            }}
            QPushButton:hover {{
                border-color: {ACCENT};
                color: #F1F5F9;
            }}
        """)
        self.clicked.connect(self._show_menu)

    def get_selected_date(self) -> Optional[str]:
        return self._selected_date

    def set_selected_date(self, due_date_str: Optional[str]):
        self._selected_date = due_date_str
        self._update_button_text()
        if due_date_str:
            self.date_changed.emit(due_date_str)

    def clear_date(self):
        self._selected_date = None
        self._update_button_text()
        self.date_changed.emit("")

    def _update_button_text(self):
        if not self._selected_date:
            self.setText("📅 Due Date ▼")
        else:
            self.setText(f"📅 {self._selected_date} ▼")

    def _show_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: #1E2029;
                color: #CBD5E1;
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 11px;
            }}
            QMenu::item:selected {{
                background-color: #312E81;
                color: #F1F5F9;
            }}
        """)

        act_none = menu.addAction("🚫 No date")
        act_none.triggered.connect(self.clear_date)

        today = datetime.now().date()

        act_today = menu.addAction(f"⏰ Today ({today.strftime('%b %d')})")
        act_today.triggered.connect(lambda: self.set_selected_date(today.isoformat()))

        tomorrow = today + timedelta(days=1)
        act_tom = menu.addAction(f"🌅 Tomorrow ({tomorrow.strftime('%b %d')})")
        act_tom.triggered.connect(lambda: self.set_selected_date(tomorrow.isoformat()))

        this_week = today + timedelta(days=7)
        act_week = menu.addAction(f"🗓️ This week ({this_week.strftime('%b %d')})")
        act_week.triggered.connect(lambda: self.set_selected_date(this_week.isoformat()))

        menu.addSeparator()
        act_custom = menu.addAction("📅 Custom date...")
        act_custom.triggered.connect(self._open_calendar_dialog)

        menu.exec_(self.mapToGlobal(QPoint(0, self.height())))

    def _open_calendar_dialog(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QCalendarWidget, QPushButton
        from PySide6.QtCore import QDate

        dlg = QDialog(self)
        dlg.setWindowTitle("Select Task Due Date")
        dlg.setFixedSize(300, 260)
        dlg.setStyleSheet(f"""
            QDialog {{
                background-color: #1E2029;
            }}
            QCalendarWidget {{
                background-color: #14161D;
                color: #F1F5F9;
            }}
            QCalendarWidget QWidget#qt_calendar_navigationbar {{
                background-color: #1E2029;
            }}
            QPushButton {{
                background-color: {ACCENT};
                color: #FFFFFF;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }}
        """)

        layout = QVBoxLayout(dlg)
        cal = QCalendarWidget()
        cal.setGridVisible(True)
        if self._selected_date:
            try:
                parts = [int(p) for p in self._selected_date.split("-")]
                cal.setSelectedDate(QDate(parts[0], parts[1], parts[2]))
            except Exception:
                pass
        layout.addWidget(cal)

        btn_row = QHBoxLayout()
        btn_clear = QPushButton("Clear")
        btn_clear.setStyleSheet("background-color: #374151; color: #CBD5E1;")
        btn_clear.clicked.connect(lambda: (self.clear_date(), dlg.accept()))
        btn_row.addWidget(btn_clear)

        btn_row.addStretch()

        btn_ok = QPushButton("Set Date")
        btn_ok.clicked.connect(lambda: (self.set_selected_date(cal.selectedDate().toString("yyyy-MM-dd")), dlg.accept()))
        btn_row.addWidget(btn_ok)

        layout.addLayout(btn_row)
        dlg.exec_()


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

        if item_data.get("type") == "project":
            loc_str = str(p_obj.location) if p_obj else "unknown"
            self.key = f"proj::{loc_str}"
        else:
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

        icon_prefix = "★ " if t_id == "project" else "📌 "
        title_lbl = QLabel(f"{icon_prefix}{title}")
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
        if t_id == "project":
            badge_str = f"⭐ Favorite Project"
        else:
            b_name = item_data.get("_board_name", "Main")
            if p_obj:
                badge_str = f"📁 {p_obj.name} · {b_name}"
            else:
                badge_str = f"🛠️ Workbench · {b_name}"

        badge_lbl = QLabel(badge_str)
        badge_lbl.setStyleSheet(f"font-size: 10px; color: #64748B; margin-top: 2px;")
        layout.addWidget(badge_lbl)

    def mousePressEvent(self, event):
        if event:
            if event.button() == Qt.LeftButton:
                self._drag_start_pos = event.pos()
            super().mousePressEvent(event)
        else:
            p_obj = self.item_data.get("project")
            if self.item_data.get("type") == "project":
                self.card_clicked.emit(p_obj, None, None)
            else:
                b_id = self.item_data.get("_board_id") or self.item_data.get("_board_name", "Main")
                n_id = self.item_data.get("id")
                self.card_clicked.emit(p_obj, b_id, n_id)

    def mouseMoveEvent(self, event):
        if not event or not (event.buttons() & Qt.LeftButton) or not self._drag_start_pos:
            return super().mouseMoveEvent(event) if event else None

        threshold = QApplication.startDragDistance() if QApplication.instance() else 10
        if (event.pos() - self._drag_start_pos).manhattanLength() < threshold:
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
        if self.item_data.get("type") == "project":
            b_id = None
            n_id = None
        else:
            b_id = self.item_data.get("_board_id") or self.item_data.get("_board_name", "Main")
            n_id = self.item_data.get("id")
        threshold = QApplication.startDragDistance() if QApplication.instance() else 10
        if not event or (event.button() == Qt.LeftButton and self._drag_start_pos and (event.pos() - self._drag_start_pos).manhattanLength() < threshold):
            self.card_clicked.emit(p_obj, b_id, n_id)
        elif not event:
            self.card_clicked.emit(p_obj, b_id, n_id)
        if event:
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
        self._sorted_projects = []

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
        # Section 1: Hero Greeting Header
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

        # ---------------------------------------------------------------------
        # 1. Quick Capture Bar (Near Top)
        # ---------------------------------------------------------------------
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

        self.qc_dest_cb = QComboBox()
        self.qc_dest_cb.setCursor(Qt.PointingHandCursor)
        self.qc_dest_cb.setToolTip("Target Destination (Default: Workbench Inbox)")
        self.qc_dest_cb.addItem("📥 Workbench Inbox", (None, "Main"))
        self.qc_dest_cb.setStyleSheet(f"""
            QComboBox {{
                background-color: #14161D;
                color: #F1F5F9;
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                min-width: 170px;
            }}
            QComboBox:focus {{
                border-color: {ACCENT};
            }}
        """)
        qc_row.addWidget(self.qc_dest_cb)

        self.qc_btn = QPushButton("🛠️ Capture")
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
        # 2. Quick Actions Toolbar (Below Quick Capture)
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

        # ---------------------------------------------------------------------
        # 3. Needs Attention & Pinned References (Horizontal Row)
        # ---------------------------------------------------------------------
        attn_pins_row = QHBoxLayout()
        attn_pins_row.setSpacing(16)

        # Left: Needs Attention Box
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
        attn_pins_row.addLayout(attention_box, stretch=1)

        # Right: Pinned References & Favorites Box
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

        attn_pins_row.addLayout(pins_box, stretch=1)

        self.layout.addLayout(attn_pins_row)

        # ---------------------------------------------------------------------
        # 4. Quick Task Control Block (Directly Below Needs Attention/Pinned Row)
        # ---------------------------------------------------------------------
        qt_frame = QFrame()
        qt_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 14px;
            }}
            QLabel#qt_title {{
                color: {ACCENT};
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }}
        """)
        qt_layout = QVBoxLayout(qt_frame)
        qt_layout.setSpacing(8)

        qt_title = QLabel("QUICK TASK")
        qt_title.setObjectName("qt_title")
        qt_layout.addWidget(qt_title)

        qt_row = QHBoxLayout()
        qt_row.setSpacing(8)

        self.qt_input = QLineEdit()
        self.qt_input.setPlaceholderText("+ Add a quick task (e.g. 'Review audio assets')...")
        self.qt_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #14161D;
                color: #F1F5F9;
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {ACCENT};
            }}
        """)
        self.qt_input.returnPressed.connect(self._on_quick_task_submitted)
        qt_row.addWidget(self.qt_input)

        self.qt_attn_cb = QComboBox()
        self.qt_attn_cb.setCursor(Qt.PointingHandCursor)
        self.qt_attn_cb.addItems(["Normal", "Important", "Urgent"])
        self.qt_attn_cb.setStyleSheet(f"""
            QComboBox {{
                background-color: #14161D;
                color: #F1F5F9;
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                min-width: 90px;
            }}
        """)
        qt_row.addWidget(self.qt_attn_cb)

        self.qt_due_btn = QuickTaskDatePickerBtn()
        qt_row.addWidget(self.qt_due_btn)

        self.qt_dest_cb = QComboBox()
        self.qt_dest_cb.setCursor(Qt.PointingHandCursor)
        self.qt_dest_cb.addItem("📥 Workbench Inbox", (None, "Main"))
        self.qt_dest_cb.setStyleSheet(f"""
            QComboBox {{
                background-color: #14161D;
                color: #F1F5F9;
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                min-width: 150px;
            }}
        """)
        qt_row.addWidget(self.qt_dest_cb)

        self.qt_btn = QPushButton("+ Quick Task")
        self.qt_btn.setCursor(Qt.PointingHandCursor)
        self.qt_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: #FFFFFF;
                font-weight: bold;
                font-size: 11px;
                padding: 6px 12px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #3B82F6;
            }}
        """)
        self.qt_btn.clicked.connect(self._on_quick_task_submitted)
        qt_row.addWidget(self.qt_btn)

        qt_layout.addLayout(qt_row)

        self.qt_feedback_lbl = QLabel("")
        self.qt_feedback_lbl.setStyleSheet("color: #34D399; font-size: 11px;")
        self.qt_feedback_lbl.setVisible(False)
        qt_layout.addWidget(self.qt_feedback_lbl)

        self.layout.addWidget(qt_frame)

        # ---------------------------------------------------------------------
        # 5. Tasks & Checklist and Recent Activity (Horizontal Row, Directly Below Quick Task)
        # Tasks ~60%, Recent Activity ~40% with internal scrolling
        # ---------------------------------------------------------------------
        tasks_activity_row = QHBoxLayout()
        tasks_activity_row.setSpacing(16)

        # Left: Tasks & Checklists Summary (~60% width)
        tasks_box = QVBoxLayout()
        tasks_box.setSpacing(12)

        tasks_hdr_row = QHBoxLayout()
        tasks_header = QLabel("☑ TASKS & CHECKLISTS")
        tasks_header.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        tasks_hdr_row.addWidget(tasks_header)

        tasks_hdr_row.addStretch()

        # Task filter buttons
        self.task_filter_btns = {}
        for f_name in ("All", "Active", "Attention", "Due Soon", "Completed"):
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
        tasks_activity_row.addLayout(tasks_box, stretch=6)

        # Right: Recent Activity (~40% width, constrained height with internal scrolling)
        activity_box = QVBoxLayout()
        activity_box.setSpacing(12)

        activity_header = QLabel("⚡ RECENT ACTIVITY")
        activity_header.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        activity_box.addWidget(activity_header)

        self.activity_frame = QFrame()
        self.activity_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 12px;
            }}
        """)

        activity_container = QWidget()
        self.activity_layout = QVBoxLayout(activity_container)
        self.activity_layout.setContentsMargins(0, 0, 0, 0)
        self.activity_layout.setSpacing(6)

        self.activity_scroll = QScrollArea()
        self.activity_scroll.setWidgetResizable(True)
        self.activity_scroll.setFrameShape(QFrame.NoFrame)
        self.activity_scroll.setMaximumHeight(320)
        self.activity_scroll.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        self.activity_scroll.setWidget(activity_container)

        activity_frame_layout = QVBoxLayout(self.activity_frame)
        activity_frame_layout.setContentsMargins(12, 12, 12, 12)
        activity_frame_layout.addWidget(self.activity_scroll)

        activity_box.addWidget(self.activity_frame)
        tasks_activity_row.addLayout(activity_box, stretch=4)

        self.layout.addLayout(tasks_activity_row)

        # ---------------------------------------------------------------------
        # 6. Project Overview (Continue Working) — At the Bottom of Home Page
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

        dest_tuple = self.qc_dest_cb.currentData() if hasattr(self, "qc_dest_cb") else (None, "Main")
        p_target, b_id_target = dest_tuple if isinstance(dest_tuple, tuple) else (None, "Main")

        if self._context and hasattr(self._context, "lab_service") and self._context.lab_service:
            lab_svc = self._context.lab_service
            item = lab_svc.add_quick_capture_note(text, project=p_target, board_id=b_id_target)
            if item:
                self.qc_input.clear()

                dest_name = "Workbench Inbox"
                if p_target:
                    b_entry = lab_svc.get_board_entry(p_target, b_id_target)
                    b_name = b_entry.get("name") if isinstance(b_entry, dict) and b_entry.get("name") else b_id_target
                    dest_name = f"{p_target.name} · {b_name}"
                elif b_id_target and b_id_target.lower() not in ("main", "inbox"):
                    b_entry = lab_svc.get_board_entry(None, b_id_target)
                    b_name = b_entry.get("name") if isinstance(b_entry, dict) and b_entry.get("name") else b_id_target
                    dest_name = f"Workbench · {b_name}"

                self.qc_feedback_lbl.setText(f"✓ Added note to {dest_name}!")
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

    def _on_pinned_card_clicked(self, proj, board_id, node_id):
        if proj and board_id is None and node_id is None:
            self.open_recent_project.emit(proj)
        else:
            self.open_board_requested.emit(proj, board_id, node_id)

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

        # Apply persisted custom project order if present
        if hasattr(self._context, "lab_service") and self._context.lab_service:
            try:
                saved_p_order = self._context.lab_service.get_project_order()
                if saved_p_order:
                    p_map = {str(p.location): p for p in sorted_projects if getattr(p, "location", None)}
                    ordered_projects = []
                    for loc in saved_p_order:
                        if loc in p_map:
                            ordered_projects.append(p_map.pop(loc))
                    ordered_projects.extend(p_map.values())
                    sorted_projects = ordered_projects
            except Exception:
                pass

        self._sorted_projects = sorted_projects

        # Populate Destination Selector Dropdown (Lightweight Metadata)
        if hasattr(self, "qc_dest_cb"):
            curr_dest = self.qc_dest_cb.currentData()
            curr_qt_dest = self.qt_dest_cb.currentData() if hasattr(self, "qt_dest_cb") else None
            self.qc_dest_cb.clear()
            if hasattr(self, "qt_dest_cb"):
                self.qt_dest_cb.clear()

            # 1. Default Option: Workbench Inbox
            self.qc_dest_cb.addItem("📥 Workbench Inbox", (None, "Main"))
            if hasattr(self, "qt_dest_cb"):
                self.qt_dest_cb.addItem("📥 Workbench Inbox", (None, "Main"))

            if hasattr(self._context, "lab_service") and self._context.lab_service:
                lab_svc = self._context.lab_service

                # 2. Other Workbench boards
                try:
                    wb_boards = lab_svc.list_boards(None)
                    for b in wb_boards:
                        if isinstance(b, dict):
                            b_id = b.get("id")
                            b_name = b.get("name", "Main")
                            if b_id and b_name.lower() not in ("main", "inbox") and b_id != "Main":
                                self.qc_dest_cb.addItem(f"🛠️ Workbench · {b_name}", (None, b_id))
                                if hasattr(self, "qt_dest_cb"):
                                    self.qt_dest_cb.addItem(f"🛠️ Workbench · {b_name}", (None, b_id))
                except Exception:
                    pass

                # 3. Project Lab boards
                for p in sorted_projects:
                    try:
                        p_boards = lab_svc.list_boards(p)
                        for b in p_boards:
                            if isinstance(b, dict):
                                b_id = b.get("id")
                                b_name = b.get("name", "Main")
                                if b_id:
                                    self.qc_dest_cb.addItem(f"📁 {p.name} · {b_name}", (p, b_id))
                                    if hasattr(self, "qt_dest_cb"):
                                        self.qt_dest_cb.addItem(f"📁 {p.name} · {b_name}", (p, b_id))
                    except Exception:
                        pass

            if curr_dest:
                for idx in range(self.qc_dest_cb.count()):
                    if self.qc_dest_cb.itemData(idx) == curr_dest:
                        self.qc_dest_cb.setCurrentIndex(idx)
                        break

            if curr_qt_dest and hasattr(self, "qt_dest_cb"):
                for idx in range(self.qt_dest_cb.count()):
                    if self.qt_dest_cb.itemData(idx) == curr_qt_dest:
                        self.qt_dest_cb.setCurrentIndex(idx)
                        break

        all_tasks = []
        all_pinned = []
        all_attention = []

        # Include Projects marked favorite=True / is_pinned=True in Pinned References & Favorites
        for p in projects:
            if getattr(p, "is_pinned", False):
                all_pinned.append({
                    "id": f"proj_fav_{p.location}",
                    "type": "project",
                    "project": p,
                    "payload": {
                        "title": p.name,
                        "content": f"📁 {(getattr(p, 'project_type', None) or 'general').capitalize()} Project · Favorite",
                    },
                    "_board_id": None,
                    "_board_name": None,
                })

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
                        if pin.get("type") == "project":
                            k = f"proj::{p_obj.location}" if p_obj else "proj::unknown"
                        else:
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
                card.card_clicked.connect(self._on_pinned_card_clicked)
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
            card.card_reordered.connect(self._on_project_card_reordered)
            self.recent_grid.addWidget(card, row, col)

        # Render Recent Activity Section
        self._render_recent_activity(sorted_projects)

    def _render_recent_activity(self, sorted_projects):
        if not hasattr(self, "activity_layout"):
            return

        while self.activity_layout.count():
            item = self.activity_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        activity_items = []
        if self._context and getattr(self._context, "activity_service", None):
            try:
                activity_items = self._context.activity_service.recent(limit=10)
            except Exception:
                activity_items = []

        if not activity_items:
            no_act_lbl = QLabel("⚡ No recent activity recorded yet")
            no_act_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
            self.activity_layout.addWidget(no_act_lbl)
        else:
            for act_data in activity_items:
                if not isinstance(act_data, dict):
                    continue
                row = QHBoxLayout()
                row.setSpacing(8)

                ts_raw = act_data.get("timestamp", "")
                ts_str = ""
                if ts_raw:
                    try:
                        dt = datetime.fromisoformat(ts_raw)
                        ts_str = dt.strftime("%H:%M")
                    except Exception:
                        ts_str = str(ts_raw)[:10]

                if ts_str:
                    time_lbl = QLabel(ts_str)
                    time_lbl.setStyleSheet("color: #64748B; font-size: 10px; font-weight: bold; font-family: monospace;")
                    row.addWidget(time_lbl)

                ev_type = act_data.get("event_type") or act_data.get("action", "")
                icon_str = "⚡"
                if ev_type == "quick_capture":
                    icon_str = "💡"
                elif ev_type == "quick_task":
                    icon_str = "📌"
                elif ev_type == "task_complete":
                    icon_str = "✅"
                elif ev_type == "task_incomplete":
                    icon_str = "☐"
                elif ev_type == "move_nodes":
                    icon_str = "📁"
                elif ev_type == "copy_nodes":
                    icon_str = "📋"

                icon_lbl = QLabel(icon_str)
                icon_lbl.setStyleSheet("font-size: 11px;")
                row.addWidget(icon_lbl)

                desc_text = act_data.get("description") or act_data.get("action", "Activity")
                desc_lbl = QLabel(desc_text)
                desc_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
                row.addWidget(desc_lbl)

                row.addStretch()

                p_loc = act_data.get("project_location")
                p_name = act_data.get("project_name")
                b_id = act_data.get("board_id") or "Main"
                n_id = act_data.get("node_id")

                p_obj = None
                if p_loc or p_name:
                    for p in sorted_projects:
                        if p_loc and getattr(p, "location", None) == p_loc:
                            p_obj = p
                            break
                        if p_name and getattr(p, "name", None) == p_name:
                            p_obj = p
                            break

                if p_obj:
                    src_str = f"📁 {p_obj.name} · {b_id}"
                else:
                    src_str = f"🛠️ Workbench · {b_id}"

                src_lbl = QLabel(src_str)
                src_lbl.setStyleSheet("color: #64748B; font-size: 10px;")
                row.addWidget(src_lbl)

                row_w = QWidget()
                row_w.setCursor(Qt.PointingHandCursor)
                row_w.setLayout(row)
                row_w.mousePressEvent = lambda _, proj=p_obj, b=b_id, nid=n_id: self.open_board_requested.emit(proj, b, nid)
                self.activity_layout.addWidget(row_w)

    def _on_quick_task_submitted(self):
        text = self.qt_input.text().strip()
        if not text:
            return

        attn = self.qt_attn_cb.currentText().lower()
        due_date = self.qt_due_btn.get_selected_date() if hasattr(self, "qt_due_btn") else None

        dest_tuple = self.qt_dest_cb.currentData() if hasattr(self, "qt_dest_cb") else (None, "Main")
        p_target, b_id_target = dest_tuple if isinstance(dest_tuple, tuple) else (None, "Main")

        if self._context and hasattr(self._context, "lab_service") and self._context.lab_service:
            lab_svc = self._context.lab_service
            item = lab_svc.add_quick_task_note(text, attention=attn, due_date=due_date, project=p_target, board_id=b_id_target)
            if item:
                self.qt_input.clear()
                if hasattr(self, "qt_due_btn"):
                    self.qt_due_btn.clear_date()

                dest_name = "Workbench Inbox"
                if p_target:
                    b_entry = lab_svc.get_board_entry(p_target, b_id_target)
                    b_name = b_entry.get("name") if isinstance(b_entry, dict) and b_entry.get("name") else b_id_target
                    dest_name = f"{p_target.name} · {b_name}"
                elif b_id_target and b_id_target.lower() not in ("main", "inbox"):
                    b_entry = lab_svc.get_board_entry(None, b_id_target)
                    b_name = b_entry.get("name") if isinstance(b_entry, dict) and b_entry.get("name") else b_id_target
                    dest_name = f"Workbench · {b_name}"

                self.qt_feedback_lbl.setText(f"✓ Task added to {dest_name}!")
                self.qt_feedback_lbl.setVisible(True)
                from PySide6.QtCore import QTimer
                QTimer.singleShot(3000, lambda: self.qt_feedback_lbl.setVisible(False))
                self.set_context(self._context)

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
            due_stat = t.get("due_status", "none")

            if self._current_task_filter == "Active" and is_comp:
                continue
            if self._current_task_filter == "Completed" and not is_comp:
                continue
            if self._current_task_filter == "Attention" and (attn not in ("urgent", "important") and due_stat not in ("overdue", "due_today", "due_soon")):
                continue
            if self._current_task_filter == "Due Soon" and due_stat not in ("overdue", "due_today", "due_soon"):
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

            for t_item in filtered_tasks[:12]:
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
                attn = t_item.get("attention", "normal")
                due_date = t_item.get("due_date")
                due_stat = t_item.get("due_status", "none")

                chk_btn.clicked.connect(lambda _, proj=p_obj, b=b_id, nid=n_id, txt=t_text, cur=is_comp: self._on_task_toggled(proj, b, nid, txt, not cur))
                t_row.addWidget(chk_btn)

                # Task text label
                txt_lbl = QLabel(t_text)
                txt_lbl.setStyleSheet(f"color: {TEXT_PRIMARY if not is_comp else TEXT_MUTED}; font-size: 12px;")
                t_row.addWidget(txt_lbl)

                # Attention badge
                if attn == "urgent":
                    attn_lbl = QLabel("🔴 URGENT")
                    attn_lbl.setStyleSheet("font-size: 9px; font-weight: bold; color: #EF4444; background: rgba(239,68,68,0.15); border-radius: 4px; padding: 2px 5px;")
                    t_row.addWidget(attn_lbl)
                elif attn == "important":
                    attn_lbl = QLabel("🟡 IMPORTANT")
                    attn_lbl.setStyleSheet("font-size: 9px; font-weight: bold; color: #F59E0B; background: rgba(245,158,11,0.15); border-radius: 4px; padding: 2px 5px;")
                    t_row.addWidget(attn_lbl)

                # Due date badge (Visually distinguishable!)
                if due_stat == "overdue":
                    due_lbl = QLabel(f"⚠️ OVERDUE: {due_date}")
                    due_lbl.setStyleSheet("font-size: 9px; font-weight: bold; color: #EF4444; background: rgba(239,68,68,0.18); border: 1px solid #EF4444; border-radius: 4px; padding: 1px 5px;")
                    t_row.addWidget(due_lbl)
                elif due_stat == "due_today":
                    due_lbl = QLabel(f"⏰ DUE TODAY")
                    due_lbl.setStyleSheet("font-size: 9px; font-weight: bold; color: #F59E0B; background: rgba(245,158,11,0.18); border: 1px solid #F59E0B; border-radius: 4px; padding: 1px 5px;")
                    t_row.addWidget(due_lbl)
                elif due_stat == "due_soon":
                    due_lbl = QLabel(f"📅 DUE: {due_date}")
                    due_lbl.setStyleSheet("font-size: 9px; font-weight: bold; color: #60A5FA; background: rgba(96,165,250,0.15); border-radius: 4px; padding: 2px 5px;")
                    t_row.addWidget(due_lbl)
                elif due_date:
                    due_lbl = QLabel(f"📅 {due_date}")
                    due_lbl.setStyleSheet("font-size: 9px; color: #94A3B8; background: rgba(148,163,184,0.1); border-radius: 4px; padding: 2px 5px;")
                    t_row.addWidget(due_lbl)

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
            if pin.get("type") == "project":
                loc_str = str(p_obj.location) if p_obj else "unknown"
                current_keys.append(f"proj::{loc_str}")
            else:
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

    def _on_project_card_reordered(self, source_loc: str, target_loc: str):
        """Reorder Project Overview cards and persist custom order to home_config.json."""
        if not self._context or not hasattr(self._context, "lab_service") or not self._context.lab_service:
            return

        lab_svc = self._context.lab_service
        current_locs = [str(p.location) for p in getattr(self, "_sorted_projects", []) if getattr(p, "location", None)]
        if source_loc in current_locs and target_loc in current_locs:
            current_locs.remove(source_loc)
            target_idx = current_locs.index(target_loc)
            current_locs.insert(target_idx, source_loc)
            lab_svc.save_project_order(current_locs)
            self.set_context(self._context)
