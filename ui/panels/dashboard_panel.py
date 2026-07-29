from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
)

from PySide6.QtCore import Qt, Signal

from ui.widgets.image_preview import ImagePreview
from services.status_service import Status


class ClickableLabel(QLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, event):
        try:
            if event.button() == Qt.LeftButton:
                self.clicked.emit()
        except Exception:
            # fallback for PySide differences
            try:
                self.clicked.emit()
            except Exception:
                pass
        super().mouseReleaseEvent(event)


class DashboardPanel(QWidget):
    # Signal emitted when user clicks project name: (project)
    project_reveal = Signal(object)

    def __init__(self):
        super().__init__()

        self._context = None
        self._current_project = None

        main_layout = QVBoxLayout(self)

        # --------------------------------------------------
        # Title
        # --------------------------------------------------

        title = QLabel("Project Dashboard")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            QLabel{
                font-size:18px;
                font-weight:bold;
                padding:8px;
            }
        """)

        main_layout.addWidget(title)

        # --------------------------------------------------
        # Project Information
        # --------------------------------------------------

        form = QFormLayout()

        # Project fields; make name clickable to reveal in Explorer
        self.name_value = ClickableLabel("-")
        self.type_value = QLabel("-")
        self.location_value = QLabel("-")
        self.created_value = QLabel("-")

        form.addRow("Name:", self.name_value)
        form.addRow("Type:", self.type_value)
        form.addRow("Location:", self.location_value)
        form.addRow("Created:", self.created_value)

        # connect click to emit reveal signal
        try:
            self.name_value.clicked.connect(lambda: self.project_reveal.emit(self._current_project))
        except Exception:
            pass

        main_layout.addLayout(form)

        # --------------------------------------------------
        # Status Indicators (data-driven)
        # --------------------------------------------------

        status_layout = QFormLayout()

        # Each status has a small colored indicator label and a text label
        self.assets_status_indicator = QLabel()
        self.assets_status_indicator.setFixedSize(12, 12)
        self.assets_status_label = QLabel("-")
        status_layout.addRow("Assets:", self._wrap_indicator(self.assets_status_indicator, self.assets_status_label))

        self.references_status_indicator = QLabel()
        self.references_status_indicator.setFixedSize(12, 12)
        self.references_status_label = QLabel("-")
        status_layout.addRow("References:", self._wrap_indicator(self.references_status_indicator, self.references_status_label))

        self.exports_status_indicator = QLabel()
        self.exports_status_indicator.setFixedSize(12, 12)
        self.exports_status_label = QLabel("-")
        status_layout.addRow("Exports:", self._wrap_indicator(self.exports_status_indicator, self.exports_status_label))

        main_layout.addLayout(status_layout)

        # --------------------------------------------------
        # Description
        # --------------------------------------------------

        description_layout = QVBoxLayout()

        description_layout.addWidget(QLabel("Description"))

        self.description = QTextEdit()
        self.description.setReadOnly(True)
        self.description.setMinimumHeight(220)

        description_layout.addWidget(self.description)

        # --------------------------------------------------
        # Snapshot
        # --------------------------------------------------

        snapshot_layout = QVBoxLayout()

        snapshot_layout.addWidget(QLabel("Project Snapshot"))

        self.snapshot = ImagePreview()

        snapshot_layout.addWidget(self.snapshot)

        # --------------------------------------------------
        # Bottom Area
        # --------------------------------------------------

        bottom_layout = QHBoxLayout()
        bottom_layout.addLayout(description_layout, 2)
        bottom_layout.addSpacing(12)
        bottom_layout.addLayout(snapshot_layout, 1)

        main_layout.addLayout(bottom_layout)

        main_layout.addStretch()

    def _wrap_indicator(self, indicator_label: QLabel, text_label: QLabel):
        container = QHBoxLayout()
        container.addWidget(indicator_label)
        container.addSpacing(8)
        container.addWidget(text_label)
        w = QWidget()
        w.setLayout(container)
        return w

    def set_context(self, context):
        """Allow service layer access and listen for changes."""
        self._context = context
        try:
            context.asset_service.assets_changed.connect(self._on_assets_changed)
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
        # update statuses when asset/service reports changes
        self._update_status_indicators(self._current_project)

    def show_project(self, project):
        self._current_project = project

        self.name_value.setText(project.name)
        self.type_value.setText(project.project_type)
        self.location_value.setText(project.location)
        self.created_value.setText(
            project.created.strftime("%d %b %Y")
        )

        self.description.setPlainText(project.description)

        snapshot = (
            Path(project.location) / "snapshot.png"
        )

        if snapshot.exists():
            self.snapshot.load_image(snapshot)
        else:
            self.snapshot.clear()

        # update status indicators via service layer
        self._update_status_indicators(project)

    def _update_status_indicators(self, project):
        if not self._context or not project:
            return
        try:
            statuses = self._context.status_service.get_project_statuses(project)
        except Exception:
            statuses = {}

        # helper to render status
        def render_for(key, indicator, label):
            status = statuses.get(key)
            if status == Status.READY:
                color = "#28a745"  # green
                text = "Ready"
            elif status == Status.EMPTY:
                color = "#6c757d"  # gray
                text = "Empty"
            elif status == Status.WARNING:
                color = "#ffc107"  # amber
                text = "Warning"
            else:
                color = "#6c757d"
                text = "Unknown"

            indicator.setStyleSheet(f"background-color: {color}; border-radius: 6px;")
            label.setText(text)

        render_for("assets", self.assets_status_indicator, self.assets_status_label)
        render_for("references", self.references_status_indicator, self.references_status_label)
        render_for("exports", self.exports_status_indicator, self.exports_status_label)
