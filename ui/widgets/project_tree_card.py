from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QSize
from models.project import Project
from ui.theme import CARD_BG, CARD_HOVER, TEXT_PRIMARY, TEXT_MUTED, ACCENT


class ProjectTreeCard(QWidget):
    """Streamlined 38px IDE project tree row widget for ExplorerPanel.

    Renders a minimal navigation row containing a thin priority accent bar, project title,
    and project type subtitle (VS Code / JetBrains style).
    """

    clicked = Signal(object)
    double_clicked = Signal(object)

    PRIORITY_COLORS = {
        "high": "#EF4444",     # Red
        "urgent": "#EF4444",   # Red
        "medium": "#F59E0B",   # Amber
        "low": "#10B981",      # Green
    }

    FIXED_HEIGHT = 38

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.project = project
        self._selected = False
        self._hovered = False

        self.setFixedHeight(self.FIXED_HEIGHT)
        self.setAttribute(Qt.WA_Hover, True)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 2, 6, 2)
        main_layout.setSpacing(8)

        # ---------------------------------------------------------------------
        # Left Priority Accent Bar
        # ---------------------------------------------------------------------
        self.accent_bar = QFrame()
        self.accent_bar.setFixedWidth(3)
        self.accent_bar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        main_layout.addWidget(self.accent_bar)

        # ---------------------------------------------------------------------
        # Title & Subtitle Stack
        # ---------------------------------------------------------------------
        meta_layout = QVBoxLayout()
        meta_layout.setContentsMargins(2, 1, 4, 1)
        meta_layout.setSpacing(1)

        # Row 1: Project Name
        self.title_label = QLabel(project.name if project else "Untitled Project")
        self.title_label.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {TEXT_PRIMARY};")
        meta_layout.addWidget(self.title_label)

        # Row 2: Project Type Subtitle
        proj_type = (project.project_type if project and getattr(project, 'project_type', None) else "Project").capitalize()
        self.subtitle_label = QLabel(proj_type)
        self.subtitle_label.setStyleSheet(f"font-size: 10px; color: {TEXT_MUTED};")
        meta_layout.addWidget(self.subtitle_label)

        main_layout.addLayout(meta_layout, stretch=1)
        self._update_appearance()

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def sizeHint(self) -> QSize:
        return QSize(0, self.FIXED_HEIGHT)

    def set_expanded(self, expanded: bool):
        # Header height remains fixed 38px whether expanded or collapsed
        pass

    def is_expanded(self) -> bool:
        return False

    def set_selected(self, selected: bool):
        self._selected = selected
        self._update_appearance()

    def is_selected(self) -> bool:
        return self._selected

    def update_project(self, project: Project):
        self.project = project
        if not project:
            return
        self.title_label.setText(project.name)
        proj_type = (project.project_type if getattr(project, 'project_type', None) else "Project").capitalize()
        self.subtitle_label.setText(proj_type)
        self._update_appearance()

    # -------------------------------------------------------------------------
    # Mouse & Event Handling
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # Styling Helper
    # -------------------------------------------------------------------------

    def _update_appearance(self):
        prio_key = str(getattr(self.project, 'priority', 'medium')).lower() if self.project else "medium"
        prio_color = self.PRIORITY_COLORS.get(prio_key, self.PRIORITY_COLORS["medium"])

        if self._selected:
            self.accent_bar.setStyleSheet(f"background-color: {ACCENT}; border-radius: 1px;")
            self.setStyleSheet(f"""
                QWidget {{
                    background-color: {CARD_BG};
                    border-radius: 4px;
                }}
            """)
            self.title_label.setStyleSheet(f"font-size: 12px; font-weight: bold; color: #FFFFFF;")
        elif self._hovered:
            self.accent_bar.setStyleSheet(f"background-color: {prio_color}; border-radius: 1px;")
            self.setStyleSheet(f"""
                QWidget {{
                    background-color: {CARD_HOVER};
                    border-radius: 4px;
                }}
            """)
            self.title_label.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {TEXT_PRIMARY};")
        else:
            self.accent_bar.setStyleSheet(f"background-color: {prio_color}; border-radius: 1px;")
            self.setStyleSheet("""
                QWidget {
                    background-color: transparent;
                }
            """)
            self.title_label.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {TEXT_PRIMARY};")

    def sizeHint(self):
        return QSize(200, self.FIXED_HEIGHT)

