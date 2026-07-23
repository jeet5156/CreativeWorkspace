from PySide6.QtWidgets import (
    QMainWindow,
    QSplitter,
    QStatusBar,
    QToolBar,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

from ui.explorer import Explorer
from ui.dashboard import Dashboard
from ui.property_panel import PropertyPanel


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Creative Workspace")
        self.resize(1600, 900)

        self.create_menu()
        self.create_toolbar()
        self.create_central_widget()
        self.create_statusbar()

    def create_menu(self):
        menubar = self.menuBar()

        menubar.addMenu("&File")
        menubar.addMenu("&Edit")
        menubar.addMenu("&View")
        menubar.addMenu("&Tools")
        menubar.addMenu("&Help")

    def create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        toolbar.addAction(QAction("New", self))
        toolbar.addAction(QAction("Open", self))
        toolbar.addAction(QAction("Save", self))

    def create_central_widget(self):
        splitter = QSplitter(Qt.Horizontal)

        splitter.addWidget(Explorer())
        splitter.addWidget(Dashboard())
        splitter.addWidget(PropertyPanel())

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 1)

        self.setCentralWidget(splitter)

    def create_statusbar(self):
        status = QStatusBar()
        status.showMessage("Ready")
        self.setStatusBar(status)