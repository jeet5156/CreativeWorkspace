from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QFormLayout,
    QTextEdit,
)

from PySide6.QtCore import Qt


class DashboardPanel(QWidget):

    def __init__(self):
        super().__init__()

        main_layout = QVBoxLayout(self)

        title = QLabel("Project Dashboard")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size:18px;font-weight:bold;padding:8px;"
        )

        main_layout.addWidget(title)

        form = QFormLayout()

        self.name_value = QLabel("-")
        self.type_value = QLabel("-")
        self.location_value = QLabel("-")
        self.created_value = QLabel("-")

        self.description = QTextEdit()
        self.description.setReadOnly(True)
        self.description.setMinimumHeight(120)

        form.addRow("Name:", self.name_value)
        form.addRow("Type:", self.type_value)
        form.addRow("Location:", self.location_value)
        form.addRow("Created:", self.created_value)

        main_layout.addLayout(form)

        main_layout.addWidget(QLabel("Description"))
        main_layout.addWidget(self.description)

        main_layout.addStretch()

    def show_project(self, project):

        self.name_value.setText(project.name)
        self.type_value.setText(project.project_type)
        self.location_value.setText(project.location)
        self.created_value.setText(
            project.created.strftime("%d %b %Y")
        )
        self.description.setPlainText(project.description)