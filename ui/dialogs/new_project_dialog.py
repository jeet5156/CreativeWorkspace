from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QFileDialog,
)


class NewProjectDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("New Project")
        self.setMinimumWidth(450)

        # Project Name
        self.name_label = QLabel("Project Name")
        self.name_edit = QLineEdit()

        # Project Type
        self.type_label = QLabel("Project Type")
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "Portfolio",
            "Client",
            "Personal",
            "Learning",
        ])

        # Location
        self.location_label = QLabel("Location")
        self.location_edit = QLineEdit()

        self.browse_button = QPushButton("Browse...")

        location_layout = QHBoxLayout()
        location_layout.addWidget(self.location_edit)
        location_layout.addWidget(self.browse_button)

        # Description
        self.description_label = QLabel("Description")
        self.description_edit = QTextEdit()
        self.description_edit.setFixedHeight(80)

        # Buttons
        self.create_button = QPushButton("Create")
        self.cancel_button = QPushButton("Cancel")

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.create_button)
        button_layout.addWidget(self.cancel_button)

        # Main Layout
        layout = QVBoxLayout()

        layout.addWidget(self.name_label)
        layout.addWidget(self.name_edit)

        layout.addWidget(self.type_label)
        layout.addWidget(self.type_combo)

        layout.addWidget(self.location_label)
        layout.addLayout(location_layout)

        layout.addWidget(self.description_label)
        layout.addWidget(self.description_edit)

        layout.addStretch()

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Signals
        self.cancel_button.clicked.connect(self.reject)
        self.create_button.clicked.connect(self.accept)
        self.browse_button.clicked.connect(self.choose_location)

    def choose_location(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Project Location"
        )

        if folder:
            self.location_edit.setText(folder)