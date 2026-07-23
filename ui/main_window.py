from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QLabel,
    QHBoxLayout,
    QStatusBar,
    QToolBar
)

from PySide6.QtCore import Qt


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Creative Workspace")
        self.resize(1600, 900)

        self.setup_ui()

    def setup_ui(self):

        # ---------- Toolbar ----------
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        # ---------- Central Widget ----------
        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout()
        central.setLayout(layout)

        # ---------- Explorer ----------
        explorer = QLabel("Explorer")
        explorer.setAlignment(Qt.AlignCenter)

        # ---------- Workspace ----------
        workspace = QLabel("Workspace")
        workspace.setAlignment(Qt.AlignCenter)

        # ---------- Properties ----------
        properties = QLabel("Properties")
        properties.setAlignment(Qt.AlignCenter)

        layout.addWidget(explorer, 1)
        layout.addWidget(workspace, 3)
        layout.addWidget(properties, 1)

        # ---------- Status Bar ----------
        status = QStatusBar()
        status.showMessage("Ready")
        self.setStatusBar(status)