from PySide6.QtWidgets import (
    QMainWindow,
    QSplitter,
    QStatusBar,
    QToolBar,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

from core.app_context import AppContext

from ui.dialogs.new_project_dialog import NewProjectDialog
from ui.panels.explorer_panel import ExplorerPanel
from ui.panels.dashboard_panel import DashboardPanel
from ui.panels.inspector_panel import InspectorPanel


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.context = AppContext()

        self.setWindowTitle("Creative Workspace")
        self.resize(1600, 900)

        self.create_menu()
        self.create_toolbar()
        self.create_central_widget()
        self.create_statusbar()

        self.load_recent_projects()

    def create_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")

        self.new_project_action = QAction("New Project", self)
        self.new_project_action.triggered.connect(self.new_project)
        file_menu.addAction(self.new_project_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

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

        self.explorer = ExplorerPanel()
        self.dashboard = DashboardPanel()
        self.inspector = InspectorPanel()
        self.explorer.project_selected.connect(
        self.project_selected
        )

        splitter.addWidget(self.explorer)
        splitter.addWidget(self.dashboard)
        splitter.addWidget(self.inspector)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 1)

        self.setCentralWidget(splitter)

    def create_statusbar(self):
        self.status = QStatusBar()
        self.status.showMessage("Ready")
        self.setStatusBar(self.status)

    def load_recent_projects(self):

        self.context.project_service.clear()

        recent = self.context.settings_service.recent_projects()

        for project_path in recent:
            project = self.context.project_service.load_project(project_path)

            if project is None:
                self.context.settings_service.remove_recent_project(project_path)

        self.explorer.load_projects(
            self.context.project_service.all_projects()
        )
    def project_selected(self, project):

        self.context.set_current_project(project)

        self.dashboard.show_project(project)

        print(f"Selected: {project.name}")
    
    def new_project(self):

        dialog = NewProjectDialog(self)

        if not dialog.exec():
            return

        project = self.context.project_service.create_project(
            dialog.name_edit.text(),
            dialog.type_combo.currentText(),
            dialog.location_edit.text(),
            dialog.description_edit.toPlainText(),
        )

        self.context.settings_service.add_recent_project(
            project.location
        )

        self.explorer.load_projects(
            self.context.project_service.all_projects()
        )

        self.status.showMessage(
            f"Project '{project.name}' created successfully.",
            5000,
        )