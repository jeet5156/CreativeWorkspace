from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout
)
from PySide6.QtCore import Qt


class PropertyPanel(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        label = QLabel("Nothing Selected")
        label.setAlignment(Qt.AlignTop)

        layout.addWidget(label)