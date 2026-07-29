from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QSplitter,
    QStatusBar,
    QToolBar,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

from core.app_context import AppContext

from ui.dialogs.new_project_dialog import NewProjectDialog
from ui.panels.explorer_panel import ExplorerPanel
from ui.panels.workspace_panel import WorkspacePanel
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

        self.open_project_action = QAction("Open Project...", self)
        self.open_project_action.triggered.connect(self.open_project)
        file_menu.addAction(self.open_project_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        menubar.addMenu("&Edit")
        menubar.addMenu("&View")
        tools_menu = menubar.addMenu("&Tools")
        menubar.addMenu("&Help")

        # Rebuild Asset Index action
        self.rebuild_index_action = QAction("Rebuild Asset Index", self)
        self.rebuild_index_action.triggered.connect(self.rebuild_asset_index)
        tools_menu.addAction(self.rebuild_index_action)

    def create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        toolbar.addAction(QAction("New", self))
        toolbar.addAction(QAction("Open", self))
        toolbar.addAction(QAction("Save", self))

    def create_central_widget(self):
        splitter = QSplitter(Qt.Horizontal)

        self.explorer = ExplorerPanel()
        self.workspace = WorkspacePanel()
        self.inspector = InspectorPanel()

        self.explorer.project_selected.connect(
            self.project_selected
        )
        self.explorer.set_snapshot_requested.connect(
            self.set_snapshot
        )
        self.explorer.remove_snapshot_requested.connect(
            self.remove_snapshot
        )
        # Handle files dropped from the OS into the explorer tree
        self.explorer.files_dropped.connect(self.on_files_dropped)

        # Provide the workspace panel with app context so it can listen to asset changes
        self.workspace.set_context(self.context)
        # connect workspace import finished to show messages
        try:
            self.workspace.import_finished.connect(self.on_workspace_import_finished)
        except Exception:
            pass
        # connect asset selection from workspace to inspector
        try:
            self.workspace.asset_workspace.asset_selected.connect(self.on_asset_selected)
        except Exception:
            pass

        # give inspector access to context
        try:
            self.inspector.set_context(self.context)
        except Exception:
            pass

        splitter.addWidget(self.explorer)
        splitter.addWidget(self.workspace)
        splitter.addWidget(self.inspector)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 1)

        self.setCentralWidget(splitter)

    def on_workspace_import_finished(self, report):
        parts = []
        if report.get("imported"):
            parts.append(f"Imported {len(report['imported'])} file(s).")
        if report.get("skipped"):
            parts.append(f"Skipped {len(report['skipped'])} duplicate(s).")
        if report.get("errors"):
            parts.append("Errors:\n" + "\n".join(report['errors']))

        if report.get("errors"):
            QMessageBox.warning(self, "Import Results", "\n".join(parts))
        else:
            QMessageBox.information(self, "Import Results", "\n".join(parts) or "Nothing imported.")

        self.status.showMessage("Import complete.", 5000)

    def on_asset_selected(self, asset_id):
        # Show asset metadata in inspector
        if not self.context.current_project:
            return
        try:
            self.inspector.show_asset(self.context.current_project, asset_id)
        except Exception:
            pass

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

    def project_selected(self, project, section):

        self.context.set_current_project(project)

        # If the asset index does not exist, rebuild it automatically for older projects
        try:
            if not self.context.asset_service.has_index(project):
                self.status.showMessage("Building asset index...", 2000)
                self.context.asset_service.rebuild_index(project)
        except Exception:
            pass

        # Delegate to workspace to display the appropriate view
        self.workspace.show_section(project, section)

        print(f"Selected: {project.name} ({section})")

    def new_project(self):

        dialog = NewProjectDialog(self)

        if not dialog.exec():
            return

        project = self.context.project_service.create_project(
            dialog.name_edit.text(),
            dialog.type_combo.currentText(),
            dialog.location_edit.text(),
            dialog.description_edit.toPlainText(),
            dialog.snapshot_path,
        )

        self.context.settings_service.add_recent_project(
            project.location
        )

        self.explorer.load_projects(
            self.context.project_service.all_projects()
        )

        self.project_selected(project, "dashboard")

        self.status.showMessage(
            f"Project '{project.name}' created successfully.",
            5000,
        )

    def set_snapshot(self, project):

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Snapshot",
            project.location,
            "Images (*.png *.jpg *.jpeg *.webp)",
        )

        if not filename:
            return

        self.context.project_service.set_snapshot(project, filename)

        if self.context.current_project == project:
            self.workspace.show_dashboard(project)

        self.status.showMessage(
            f"Snapshot updated for '{project.name}'.",
            5000,
        )

    def remove_snapshot(self, project):

        self.context.project_service.remove_snapshot(project)

        if self.context.current_project == project:
            self.workspace.show_dashboard(project)

        self.status.showMessage(
            f"Snapshot removed for '{project.name}'.",
            5000,
        )

    def open_project(self):

        folder = QFileDialog.getExistingDirectory(
            self,
            "Open Project",
        )

        if not folder:
            return

        if not (Path(folder) / "project.json").exists():
            QMessageBox.warning(
                self,
                "Invalid Project",
                "Selected folder does not contain a project.json file.",
            )
            return

        project = self.context.project_service.load_project(folder)

        if project is None:
            QMessageBox.warning(
                self,
                "Error",
                "Unable to load project.",
            )
            return

        self.context.settings_service.add_recent_project(
            project.location
        )

        self.explorer.load_projects(
            self.context.project_service.all_projects()
        )

        self.project_selected(project, "dashboard")

        self.status.showMessage(
            f"Opened project '{project.name}'.",
            5000,
        )

    def on_files_dropped(self, project, section, paths):
        """Called when the ExplorerPanel reports files/folders were dropped.
        Delegate to AssetService and refresh UI.
        """
        if project is None:
            QMessageBox.warning(
                self,
                "Import Error",
                "Please drop files onto a project or section in the Project Explorer.",
            )
            return

        if not paths:
            QMessageBox.warning(
                self,
                "Import Error",
                "No files or folders detected in drop.",
            )
            return

        report = self.context.asset_service.import_paths(project, section, paths)

        parts = []
        if report.get("imported"):
            parts.append(f"Imported {len(report['imported'])} file(s).")
        if report.get("skipped"):
            parts.append(f"Skipped {len(report['skipped'])} duplicate(s).")
        if report.get("errors"):
            parts.append("Errors:\n" + "\n".join(report['errors']))

        if report.get("errors"):
            QMessageBox.warning(self, "Import Results", "\n".join(parts))
        else:
            QMessageBox.information(self, "Import Results", "\n".join(parts) or "Nothing imported.")

        # Refresh explorer and workspace display
        self.explorer.load_projects(self.context.project_service.all_projects())
        if self.context.current_project == project:
            # Re-show dashboard to refresh any project UI
            self.project_selected(project, "dashboard")

        self.status.showMessage("Import complete.", 5000)

    def rebuild_asset_index(self):
        project = self.context.current_project
        if project is None:
            QMessageBox.warning(self, "Rebuild Asset Index", "No project is currently selected.")
            return

        self.status.showMessage("Rebuilding asset index...", 2000)
        try:
            self.context.asset_service.rebuild_index(project, force=True)
            QMessageBox.information(self, "Rebuild Asset Index", "Asset index rebuilt successfully.")
        except Exception:
            QMessageBox.warning(self, "Rebuild Asset Index", "An error occurred while rebuilding the asset index.")
        finally:
            self.status.showMessage("Ready", 2000)