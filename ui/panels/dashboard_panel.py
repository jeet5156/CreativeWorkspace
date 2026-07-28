from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
)

from PySide6.QtCore import Qt

from ui.widgets.image_preview import ImagePreview


class DashboardPanel(QWidget):

    def __init__(self):
        super().__init__()

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

        self.name_value = QLabel("-")
        self.type_value = QLabel("-")
        self.location_value = QLabel("-")
        self.created_value = QLabel("-")

        form.addRow("Name:", self.name_value)
        form.addRow("Type:", self.type_value)
        form.addRow("Location:", self.location_value)
        form.addRow("Created:", self.created_value)

        main_layout.addLayout(form)

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

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def show_project(self, project):

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