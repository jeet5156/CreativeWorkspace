from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QScrollArea,
    QGridLayout,
)
from PySide6.QtCore import Qt, Signal

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


class HomeWorkspacePanel(QWidget):
    """Spacious Workspace Home landing screen ('What should I work on today?')."""

    new_project_requested = Signal()
    open_project_requested = Signal()
    open_recent_requested = Signal()
    open_assets_requested = Signal()
    open_recent_project = Signal(object)  # emits Project

    def __init__(self):
        super().__init__()

        self._context = None

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
        self.layout.setSpacing(28)

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

        subtitle = QLabel("What should I work on today?")
        subtitle.setStyleSheet(f"font-size: 14px; color: {TEXT_MUTED};")
        greeting_box.addWidget(subtitle)

        self.layout.addLayout(greeting_box)

        # ---------------------------------------------------------------------
        # Section 2: Continue Working (Recent Projects Grid)
        # ---------------------------------------------------------------------
        cw_box = QVBoxLayout()
        cw_box.setSpacing(12)

        cw_title = QLabel("CONTINUE WORKING")
        cw_title.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        cw_box.addWidget(cw_title)

        self.recent_grid_widget = QWidget()
        self.recent_grid = QGridLayout(self.recent_grid_widget)
        self.recent_grid.setContentsMargins(0, 0, 0, 0)
        self.recent_grid.setSpacing(16)

        cw_box.addWidget(self.recent_grid_widget)
        self.layout.addLayout(cw_box)

        # ---------------------------------------------------------------------
        # Section 3: Pinned Projects
        # ---------------------------------------------------------------------
        pinned_box = QVBoxLayout()
        pinned_box.setSpacing(12)

        pinned_title = QLabel("PINNED PROJECTS")
        pinned_title.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        pinned_box.addWidget(pinned_title)

        self.pinned_grid_widget = QWidget()
        self.pinned_grid = QGridLayout(self.pinned_grid_widget)
        self.pinned_grid.setContentsMargins(0, 0, 0, 0)
        self.pinned_grid.setSpacing(16)

        self.pinned_empty = QLabel("📌 No pinned projects. Click the star icon on any project card for 1-click access.")
        self.pinned_empty.setStyleSheet("color: #64748B; font-size: 12px; padding: 8px 0px;")

        pinned_box.addWidget(self.pinned_grid_widget)
        pinned_box.addWidget(self.pinned_empty)
        self.layout.addLayout(pinned_box)

        # ---------------------------------------------------------------------
        # Section 4: Quick Actions
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
        # Section 5: Recent Activity
        # ---------------------------------------------------------------------
        act_box = QVBoxLayout()
        act_box.setSpacing(12)

        act_title = QLabel("RECENT ACTIVITY")
        act_title.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        act_box.addWidget(act_title)

        act_frame = QFrame()
        act_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 16px;
            }}
        """)
        act_layout = QVBoxLayout(act_frame)
        act_layout.setSpacing(8)

        self.activity_label = QLabel("⚡ No recent activity logged")
        self.activity_label.setStyleSheet("color: #64748B; font-size: 12px;")
        act_layout.addWidget(self.activity_label)

        act_box.addWidget(act_frame)
        self.layout.addLayout(act_box)

        # ---------------------------------------------------------------------
        # Section 6: Creative Insights (Coming Soon Placeholder)
        # ---------------------------------------------------------------------
        insights_box = QVBoxLayout()
        insights_box.setSpacing(12)

        insights_title = QLabel("CREATIVE INSIGHTS")
        insights_title.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        insights_box.addWidget(insights_title)

        insights_frame = QFrame()
        insights_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 16px;
            }}
        """)
        ins_layout = QVBoxLayout(insights_frame)
        ins_layout.setSpacing(4)

        ins_heading = QLabel("📊 Creative telemetry & production workflow health insights coming soon.")
        ins_heading.setStyleSheet("color: #64748B; font-size: 12px; font-weight: bold;")
        ins_layout.addWidget(ins_heading)

        insights_box.addWidget(insights_frame)
        self.layout.addLayout(insights_box)

        self.layout.addStretch()

        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

    def _calc_columns(self) -> int:
        avail_w = max(300, self.width() - 80)
        target_card_w = 260
        cols = max(1, avail_w // target_card_w)
        return min(5, cols)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_context") and self._context:
            try:
                self.set_context(self._context)
            except Exception:
                pass

    def set_context(self, context):
        """Provide AppContext and populate recent/pinned project cards."""
        self._context = context
        if not context or not getattr(context, "project_service", None):
            return

        projects = context.project_service.all_projects()

        # Sort projects by last_opened descending (falling back to created)
        def get_sort_key(p):
            lo = getattr(p, 'last_opened', None)
            cr = getattr(p, 'created', None)
            return lo or cr or datetime.min

        sorted_projects = sorted(projects, key=get_sort_key, reverse=True)

        # Populate Continue Working Grid
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
            card.pin_toggled.connect(self._on_pin_toggled)
            self.recent_grid.addWidget(card, row, col)

        # Populate Pinned Projects Grid
        while self.pinned_grid.count():
            item = self.pinned_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        pinned_projects = [p for p in sorted_projects if getattr(p, 'is_pinned', False)]

        if pinned_projects:
            self.pinned_empty.setVisible(False)
            self.pinned_grid_widget.setVisible(True)
            for idx, proj in enumerate(pinned_projects):
                row = idx // columns
                col = idx % columns
                card = ProjectCard(proj, compact=True)
                card.clicked.connect(self._on_card_clicked)
                card.double_clicked.connect(self._on_card_clicked)
                card.pin_toggled.connect(self._on_pin_toggled)
                self.pinned_grid.addWidget(card, row, col)
        else:
            self.pinned_grid_widget.setVisible(False)
            self.pinned_empty.setVisible(True)

    def _on_card_clicked(self, project: Project):
        if project:
            try:
                self.open_recent_project.emit(project)
            except Exception:
                pass

    def _on_pin_toggled(self, project: Project):
        if project and self._context and getattr(self._context, "project_service", None):
            self._context.project_service.toggle_pin_project(project)
            self.set_context(self._context)

