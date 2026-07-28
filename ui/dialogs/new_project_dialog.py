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

from ui.widgets.image_preview import ImagePreview


class NewProjectDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("New Project")
        self.resize(760, 520)

        self.snapshot_path = ""

        # --------------------------------------------------
        # Project Name
        # --------------------------------------------------

        self.name_label = QLabel("Project Name")
        self.name_edit = QLineEdit()

        # --------------------------------------------------
        # Project Type
        # --------------------------------------------------

        self.type_label = QLabel("Project Type")

        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "Portfolio",
            "Client",
            "Personal",
            "Learning",
        ])

        # --------------------------------------------------
        # Location
        # --------------------------------------------------

        self.location_label = QLabel("Location")
        self.location_edit = QLineEdit()

        self.browse_button = QPushButton("Browse...")

        location_layout = QHBoxLayout()
        location_layout.addWidget(self.location_edit)
        location_layout.addWidget(self.browse_button)

        # --------------------------------------------------
        # Description
        # --------------------------------------------------

        self.description_label = QLabel("Description")

        self.description_edit = QTextEdit()
        self.description_edit.setMinimumHeight(180)

        # --------------------------------------------------
        # Snapshot
        # --------------------------------------------------

        self.snapshot_label = QLabel("Project Snapshot")

        self.snapshot_preview = ImagePreview()

        self.choose_snapshot_button = QPushButton("Choose Image...")
        self.clear_snapshot_button = QPushButton("Clear")

        snapshot_buttons = QHBoxLayout()
        snapshot_buttons.addWidget(self.choose_snapshot_button)
        snapshot_buttons.addWidget(self.clear_snapshot_button)

        snapshot_layout = QVBoxLayout()
        snapshot_layout.addWidget(self.snapshot_label)
        snapshot_layout.addWidget(self.snapshot_preview)
        snapshot_layout.addLayout(snapshot_buttons)

        # --------------------------------------------------
        # Left Side
        # --------------------------------------------------

        left_layout = QVBoxLayout()

        left_layout.addWidget(self.name_label)
        left_layout.addWidget(self.name_edit)

        left_layout.addWidget(self.type_label)
        left_layout.addWidget(self.type_combo)

        left_layout.addWidget(self.location_label)
        left_layout.addLayout(location_layout)

        left_layout.addWidget(self.description_label)
        left_layout.addWidget(self.description_edit)

        # --------------------------------------------------
        # Middle Layout
        # --------------------------------------------------

        content_layout = QHBoxLayout()
        content_layout.addLayout(left_layout, 2)
        content_layout.addLayout(snapshot_layout, 1)

        # --------------------------------------------------
        # Buttons
        # --------------------------------------------------

        self.create_button = QPushButton("Create")
        self.cancel_button = QPushButton("Cancel")

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.create_button)

        # --------------------------------------------------
        # Main Layout
        # --------------------------------------------------

        layout = QVBoxLayout(self)

        layout.addLayout(content_layout)
        layout.addSpacing(10)
        layout.addLayout(button_layout)

        # --------------------------------------------------
        # Signals
        # --------------------------------------------------

        self.cancel_button.clicked.connect(self.reject)
        self.create_button.clicked.connect(self.accept)

        self.browse_button.clicked.connect(self.choose_location)

        self.choose_snapshot_button.clicked.connect(
            self.choose_snapshot
        )

        self.clear_snapshot_button.clicked.connect(
            self.clear_snapshot
        )

    # --------------------------------------------------
    # Location
    # --------------------------------------------------

    def choose_location(self):

        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Project Location",
        )

        if folder:
            self.location_edit.setText(folder)

    # --------------------------------------------------
    # Snapshot
    # --------------------------------------------------

    def choose_snapshot(self):

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Project Snapshot",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)",
        )

        if not filename:
            return

        self.snapshot_path = filename
        self.snapshot_preview.load_image(filename)

    def clear_snapshot(self):

        self.snapshot_path = ""
        self.snapshot_preview.clear()