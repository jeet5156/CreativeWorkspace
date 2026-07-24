from PySide6.QtWidgets import (
    QMainWindow,
    QSplitter,
    QStatusBar,
    QToolBar,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

from ui.dialogs.new_project_dialog import NewProjectDialog
from ui.panels.explorer_panel import ExplorerPanel
from ui.panels.dashboard_panel import DashboardPanel
from ui.panels.inspector_panel import InspectorPanel


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

        file_menu = menubar.addMenu("&File")

        self.new_project_action = QAction("New Project", self)
        file_menu.addAction(self.new_project_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        file_menu.addAction(exit_action)

        self.new_project_action.triggered.connect(self.new_project)
        exit_action.triggered.connect(self.close)

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

        splitter.addWidget(ExplorerPanel())
        splitter.addWidget(DashboardPanel())
        splitter.addWidget(InspectorPanel())

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 1)

        self.setCentralWidget(splitter)

    def create_statusbar(self):
        status = QStatusBar()
        status.showMessage("Ready")
        self.setStatusBar(status)

    def new_project(self):
        dialog = NewProjectDialog(self)

        if dialog.exec():
            print("Project Name :", dialog.name_edit.text())
            print("Project Type :", dialog.type_combo.currentText())
            print("Location     :", dialog.location_edit.text())
            print("Description  :", dialog.description_edit.toPlainText())