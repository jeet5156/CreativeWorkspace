from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Qt


class ModulePlaceholder(QWidget):
    def __init__(self, title: str, description: str):
        super().__init__()
        layout = QVBoxLayout(self)
        t = QLabel(title)
        t.setStyleSheet("font-weight:bold; font-size:16px; padding:6px;")
        layout.addWidget(t)
        d = QLabel(description)
        d.setWordWrap(True)
        d.setStyleSheet("color:#6c757d; padding:6px;")
        layout.addWidget(d)
        layout.addStretch()
