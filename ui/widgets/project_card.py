from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QSize

from models.project import Project
from ui.widgets.image_preview import ImagePreview
from ui.theme import CARD_BG, CARD_HOVER, BORDER_COLOR, TEXT_PRIMARY, TEXT_MUTED, ACCENT


class ProjectCard(QFrame):
    """Reusable project card component for Workspace Home landing experience.

    Displays cover artwork preview, project title, project type, status indicator,
    last opened timestamp, and a pin toggle button.
    """

    clicked = Signal(object)
    double_clicked = Signal(object)
    pin_toggled = Signal(object)

    def __init__(self, project: Project, compact: bool = False, parent=None):
        super().__init__(parent)
        self.project = project
        self.compact = compact
        self._hovered = False

        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(220)
        self.setMaximumWidth(320)

        self._init_ui()
        self._update_appearance()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        if not self.compact:
            # Cover Artwork Section
            self.cover_preview = ImagePreview()
            self.cover_preview.setFixedHeight(130)
            self.cover_preview.setStyleSheet(f"border-radius: 6px; border: 1px solid {BORDER_COLOR};")
            main_layout.addWidget(self.cover_preview)

        # Header Row: Title & Pin Button
        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        self.title_label = QLabel(self.project.name if self.project else "Untitled")
        self.title_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {TEXT_PRIMARY};")
        header_row.addWidget(self.title_label, stretch=1)

        self.pin_button = QPushButton()
        self.pin_button.setFixedSize(26, 26)
        self.pin_button.setFocusPolicy(Qt.NoFocus)
        self.pin_button.clicked.connect(self._on_pin_clicked)
        header_row.addWidget(self.pin_button)

        main_layout.addLayout(header_row)

        # Subtitle Row: Project Type
        proj_type = (getattr(self.project, 'project_type', None) or 'general').capitalize()
        self.type_label = QLabel(f"📁 {proj_type} Project")
        self.type_label.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
        main_layout.addWidget(self.type_label)

        # Bottom Info Row: Status & Last Opened
        info_row = QHBoxLayout()
        info_row.setSpacing(6)

        self.status_dot = QLabel()
        self.status_dot.setFixedSize(8, 8)
        info_row.addWidget(self.status_dot)

        status_str = (getattr(self.project, 'status', None) or 'active').capitalize()
        self.status_label = QLabel(status_str)
        self.status_label.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
        info_row.addWidget(self.status_label)

        info_row.addStretch()

        last_opened = getattr(self.project, 'last_opened', None) or getattr(self.project, 'created', None)
        time_str = self._format_last_opened(last_opened)
        self.opened_label = QLabel(time_str)
        self.opened_label.setStyleSheet(f"font-size: 10px; color: #64748B;")
        info_row.addWidget(self.opened_label)

        main_layout.addLayout(info_row)

        self.update_project(self.project)

    def update_project(self, project: Project):
        self.project = project
        if not project:
            return

        self.title_label.setText(project.name)
        proj_type = (getattr(project, 'project_type', None) or 'general').capitalize()
        self.type_label.setText(f"📁 {proj_type} Project")

        # Update cover preview if not compact
        if not self.compact and hasattr(self, 'cover_preview'):
            snapshot = Path(project.location) / "snapshot.png" if getattr(project, 'location', None) else None
            if snapshot and snapshot.exists():
                self.cover_preview.load_image(snapshot)
            else:
                self.cover_preview.clear()

        # Update status dot
        status_key = str(getattr(project, 'status', 'active')).lower()
        if status_key == "active":
            self.status_dot.setStyleSheet("background-color: #34D399; border-radius: 4px;")
        elif status_key == "in progress":
            self.status_dot.setStyleSheet("background-color: #60A5FA; border-radius: 4px;")
        else:
            self.status_dot.setStyleSheet("background-color: #94A3B8; border-radius: 4px;")
        self.status_label.setText(status_key.capitalize())

        # Update pin button style
        is_pinned = getattr(project, 'is_pinned', False)
        if is_pinned:
            self.pin_button.setText("★")
            self.pin_button.setStyleSheet("""
                QPushButton {
                    background-color: #3B2D1B;
                    color: #FBBF24;
                    border: 1px solid #F59E0B;
                    border-radius: 4px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #4A3820;
                }
            """)
            self.pin_button.setToolTip("Unpin Project")
        else:
            self.pin_button.setText("☆")
            self.pin_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {TEXT_MUTED};
                    border: 1px solid {BORDER_COLOR};
                    border-radius: 4px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {CARD_HOVER};
                    color: {TEXT_PRIMARY};
                    border: 1px solid {ACCENT};
                }}
            """)
            self.pin_button.setToolTip("Pin Project")

        last_opened = getattr(project, 'last_opened', None) or getattr(project, 'created', None)
        self.opened_label.setText(self._format_last_opened(last_opened))

    def _format_last_opened(self, dt) -> str:
        if not dt or not isinstance(dt, datetime):
            return "Recently"
        diff = datetime.now() - dt
        if diff.days == 0:
            hours = diff.seconds // 3600
            if hours == 0:
                mins = max(1, diff.seconds // 60)
                return f"{mins}m ago"
            return f"{hours}h ago"
        elif diff.days == 1:
            return "Yesterday"
        elif diff.days < 7:
            return f"{diff.days}d ago"
        else:
            return dt.strftime("%d %b")

    def _on_pin_clicked(self):
        try:
            self.pin_toggled.emit(self.project)
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.project)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self.project)
        super().mouseDoubleClickEvent(event)

    def enterEvent(self, event):
        self._hovered = True
        self._update_appearance()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._update_appearance()
        super().leaveEvent(event)

    def _update_appearance(self):
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
