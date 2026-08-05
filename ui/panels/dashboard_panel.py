from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QFrame,
    QScrollArea,
)
from PySide6.QtCore import Qt, Signal

from ui.widgets.image_preview import ImagePreview
from services.status_service import Status
from ui.theme import BG_DARK, CARD_BG, CARD_HOVER, BORDER_COLOR, TEXT_PRIMARY, TEXT_MUTED, ACCENT


class ClickableLabel(QLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, event):
        try:
            if event.button() == Qt.LeftButton:
                self.clicked.emit()
        except Exception:
            pass
        super().mouseReleaseEvent(event)


class DashboardPanel(QWidget):
    """Inspiring Project Overview Home ('What is happening in this project?')."""

    project_reveal = Signal(object)

    def __init__(self):
        super().__init__()

        self._context = None
        self._current_project = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet(f"QScrollArea {{ background-color: {BG_DARK}; border: none; }}")

        container = QWidget()
        container.setStyleSheet(f"QWidget {{ background-color: {BG_DARK}; }}")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)

        # ---------------------------------------------------------------------
        # Hero Header (Open, Breathable Project Identity)
        # ---------------------------------------------------------------------
        hero_layout = QVBoxLayout()
        hero_layout.setSpacing(6)

        top_row = QHBoxLayout()

        self.name_value = ClickableLabel("Project Dashboard")
        self.name_value.setStyleSheet(f"font-size: 26px; font-weight: bold; color: {TEXT_PRIMARY};")
        self.name_value.clicked.connect(lambda: self.project_reveal.emit(self._current_project))
        top_row.addWidget(self.name_value)

        top_row.addStretch()

        self.priority_badge = QLabel("Medium Priority")
        self.priority_badge.setStyleSheet("font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 4px; background-color: #3B2D1B; color: #FBBF24;")
        top_row.addWidget(self.priority_badge)

        self.status_badge = QLabel("Active")
        self.status_badge.setStyleSheet("font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 4px; background-color: #14382B; color: #34D399;")
        top_row.addWidget(self.status_badge)

        hero_layout.addLayout(top_row)

        self.type_value = QLabel("📁 General Project")
        self.type_value.setStyleSheet(f"font-size: 13px; color: {TEXT_MUTED};")
        hero_layout.addWidget(self.type_value)

        layout.addLayout(hero_layout)

        # ---------------------------------------------------------------------
        # Overview Columns: Description (Left) & Cover Image (Right)
        # ---------------------------------------------------------------------
        cols = QHBoxLayout()
        cols.setSpacing(24)

        # Left Column: Description & Metadata
        left_box = QFrame()
        left_box.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 16px;
            }}
            QLabel#section_title {{
                color: {ACCENT};
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }}
        """)
        left_layout = QVBoxLayout(left_box)
        left_layout.setSpacing(12)

        desc_title = QLabel("OVERVIEW & DESCRIPTION")
        desc_title.setObjectName("section_title")
        left_layout.addWidget(desc_title)

        self.description = QTextEdit()
        self.description.setReadOnly(True)
        self.description.setMinimumHeight(140)
        self.description.setStyleSheet(f"background-color: #14161D; color: #CBD5E1; border: 1px solid {BORDER_COLOR}; border-radius: 6px; padding: 8px;")
        left_layout.addWidget(self.description)

        info_form = QFormLayout()
        info_form.setSpacing(8)
        self.location_value = QLabel("-")
        self.created_value = QLabel("-")
        self.modified_value = QLabel("-")
        self.location_value.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        self.created_value.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        self.modified_value.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")

        info_form.addRow("Location:", self.location_value)
        info_form.addRow("Created:", self.created_value)
        info_form.addRow("Modified:", self.modified_value)
        left_layout.addLayout(info_form)

        cols.addWidget(left_box, stretch=3)

        # Right Column: Large Cover Artwork (No title label above it)
        right_box = QFrame()
        right_box.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        right_layout = QVBoxLayout(right_box)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(0)

        self.snapshot = ImagePreview()
        self.snapshot.setFixedHeight(300)
        self.snapshot.setStyleSheet(f"border-radius: 6px; border: 1px solid {BORDER_COLOR};")
        right_layout.addWidget(self.snapshot)

        cols.addWidget(right_box, stretch=2)

        layout.addLayout(cols)

        # ---------------------------------------------------------------------
        # Section 3: Project Health (Compact Horizontal Status Cards)
        # ---------------------------------------------------------------------
        health_container = QVBoxLayout()
        health_container.setSpacing(12)

        stat_header = QLabel("PROJECT HEALTH")
        stat_header.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        health_container.addWidget(stat_header)

        # Horizontal Row of Cards
        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)

        # Card 1: Assets
        self.assets_card, self.assets_status_indicator, self.assets_status_label = self._create_health_card("Assets")
        cards_row.addWidget(self.assets_card)

        # Card 2: References
        self.references_card, self.references_status_indicator, self.references_status_label = self._create_health_card("References")
        cards_row.addWidget(self.references_card)

        # Card 3: Exports
        self.exports_card, self.exports_status_indicator, self.exports_status_label = self._create_health_card("Exports")
        cards_row.addWidget(self.exports_card)

        health_container.addLayout(cards_row)
        layout.addLayout(health_container)

        # ---------------------------------------------------------------------
        # Section 4: Recent Activity & Milestones (Full Width Sections)
        # ---------------------------------------------------------------------
        activity_box = QFrame()
        activity_box.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 16px;
            }}
            QLabel#section_title {{
                color: {ACCENT};
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }}
            QLabel#placeholder_text {{
                color: #64748B;
                font-size: 12px;
            }}
        """)
        act_layout = QVBoxLayout(activity_box)
        act_layout.setSpacing(12)

        recent_act_title = QLabel("RECENT ACTIVITY")
        recent_act_title.setObjectName("section_title")
        act_layout.addWidget(recent_act_title)

        recent_act = QLabel("⚡ No recent events logged")
        recent_act.setObjectName("placeholder_text")
        act_layout.addWidget(recent_act)

        milestones_title = QLabel("MILESTONES & TIMELINE")
        milestones_title.setObjectName("section_title")
        act_layout.addWidget(milestones_title)

        milestones = QLabel("🏁 Phase 1 Foundation Active")
        milestones.setObjectName("placeholder_text")
        act_layout.addWidget(milestones)

        layout.addWidget(activity_box)

        layout.addStretch()

        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

    def _create_health_card(self, title: str):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(8)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; font-weight: bold;")
        c_layout.addWidget(lbl_title)

        status_row = QHBoxLayout()
        status_row.setSpacing(8)

        indicator = QLabel()
        indicator.setFixedSize(10, 10)
        indicator.setStyleSheet("background-color: #64748B; border-radius: 5px;")
        status_row.addWidget(indicator)

        label = QLabel("Empty")
        label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: bold;")
        status_row.addWidget(label)
        status_row.addStretch()

        c_layout.addLayout(status_row)
        return card, indicator, label

    def set_context(self, context):
        self._context = context
        try:
            context.asset_service.assets_changed.connect(self._on_assets_changed)
        except Exception:
            pass
        try:
            context.project_service.project_updated.connect(self._on_project_updated)
        except Exception:
            pass

    def _on_project_updated(self, project):
        if not self._current_project or not project:
            return
        try:
            if str(project.location) == str(self._current_project.location):
                self.show_project(project)
        except Exception:
            pass

    def _on_assets_changed(self, project, category):
        if not self._current_project:
            return
        try:
            if project.location != self._current_project.location:
                return
        except Exception:
            return
        self._update_status_indicators(self._current_project)

    def show_project(self, project):
        self._current_project = project
        if not project:
            return

        self.name_value.setText(project.name)
        proj_type = (getattr(project, 'project_type', None) or 'general').capitalize()
        self.type_value.setText(f"📁 {proj_type} Project")

        self.location_value.setText(str(getattr(project, 'location', '-')))
        if getattr(project, 'created', None):
            self.created_value.setText(project.created.strftime("%d %b %Y"))
        else:
            self.created_value.setText("—")

        if getattr(project, 'modified', None):
            self.modified_value.setText(project.modified.strftime("%d %b %Y"))
        else:
            self.modified_value.setText("—")

        self.description.setPlainText(getattr(project, 'description', ''))

        prio_key = str(getattr(project, 'priority', 'medium')).lower()
        if prio_key in ("high", "urgent"):
            self.priority_badge.setText("High Priority")
            self.priority_badge.setStyleSheet("font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 4px; background-color: #3F1D24; color: #F87171;")
        elif prio_key == "low":
            self.priority_badge.setText("Low Priority")
            self.priority_badge.setStyleSheet("font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 4px; background-color: #14382B; color: #34D399;")
        else:
            self.priority_badge.setText("Medium Priority")
            self.priority_badge.setStyleSheet("font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 4px; background-color: #3B2D1B; color: #FBBF24;")

        status_key = str(getattr(project, 'status', 'active')).lower()
        self.status_badge.setText(status_key.capitalize())
        if status_key == "active":
            self.status_badge.setStyleSheet("font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 4px; background-color: #14382B; color: #34D399;")
        elif status_key == "in progress":
            self.status_badge.setStyleSheet("font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 4px; background-color: #1E2E4A; color: #60A5FA;")
        else:
            self.status_badge.setStyleSheet("font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 4px; background-color: #1E293B; color: #94A3B8;")

        snapshot = Path(project.location) / "snapshot.png" if getattr(project, 'location', None) else None
        if snapshot and snapshot.exists():
            self.snapshot.load_image(snapshot)
        else:
            self.snapshot.clear()

        self._update_status_indicators(project)

    def _update_status_indicators(self, project):
        if not self._context or not project:
            return
        try:
            statuses = self._context.status_service.get_project_statuses(project)
        except Exception:
            statuses = {}

        def render_for(key, indicator, label):
            status = statuses.get(key)
            if status == Status.READY:
                color = "#22C55E"  # emerald
                text = "Ready"
            elif status == Status.EMPTY:
                color = "#64748B"  # slate
                text = "Empty"
            elif status == Status.WARNING:
                color = "#F59E0B"  # amber
                text = "Warning"
            else:
                color = "#64748B"
                text = "Unknown"

            indicator.setStyleSheet(f"background-color: {color}; border-radius: 5px;")
            label.setText(text)

        render_for("assets", self.assets_status_indicator, self.assets_status_label)
        render_for("references", self.references_status_indicator, self.references_status_label)
        render_for("exports", self.exports_status_indicator, self.exports_status_label)

