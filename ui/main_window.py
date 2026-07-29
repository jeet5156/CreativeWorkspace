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

        # Show Home Workspace when no project is selected on startup
        if not self.context.current_project:
            try:
                self.workspace.show_home()
            except Exception:
                pass

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

        self.splitter = splitter
        self._saved_splitter_sizes = None

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

        # Set up WorkspaceManager and NavigationService
        try:
            from ui.workspace_manager import WorkspaceManager
            from services.navigation_service import NavigationService
            self.workspace_manager = WorkspaceManager(self.workspace, self.context, None)
            # create navigation service and inject into workspace manager
            self.navigation_service = NavigationService(self.workspace_manager, self.explorer, self.context)
            # give workspace_manager a reference to navigation_service if it needs it
            try:
                self.workspace_manager.set_navigation_service(self.navigation_service)
            except Exception:
                try:
                    self.workspace_manager.navigation_service = self.navigation_service
                except Exception:
                    pass
        except Exception:
            self.workspace_manager = None
            self.navigation_service = None

        # connect explorer navigation signals to the navigation service
        try:
            if self.navigation_service:
                self.explorer.navigation_requested.connect(self.navigation_service.handle_navigation)
                self.explorer.project_selected.connect(lambda p, s: self.navigation_service.navigate_project(p, s))
                # attach Explorer's search services (global search)
                try:
                    self.explorer.set_search_services(self.workspace_manager.find_service, self.navigation_service, self.context.app_state)
                except Exception:
                    pass
        except Exception:
            pass

        # Wire Home workspace quick actions to MainWindow handlers via WorkspaceManager/navigation
        try:
            if self.workspace.home:
                self.workspace.home.new_project_requested.connect(self.new_project)
                self.workspace.home.open_project_requested.connect(self.open_project)
                # double-click recent -> navigate
                self.workspace.home.open_recent_project.connect(lambda proj: self.project_selected(proj, 'dashboard'))
        except Exception:
            pass

        # Global Ctrl+F shortcut to focus Explorer search box
        try:
            from PySide6.QtGui import QShortcut, QKeySequence
            sc = QShortcut(QKeySequence("Ctrl+F"), self)
            sc.activated.connect(lambda: self.explorer.search_edit.setFocus())
        except Exception:
            pass


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

        # Use fixed default splitter sizes on startup (Explorer ≈ 260 px, Inspector ≈ 320 px)
        try:
            splitter.setHandleWidth(8)  # make handle wider for easier resizing
        except Exception:
            pass

        try:
            # Set initial sizes: [Explorer, Workspace, Inspector]
            splitter.setSizes([260, 800, 320])
        except Exception:
            # fallback to stretch factors if setSizes fails
            try:
                splitter.setStretchFactor(0, 1)
                splitter.setStretchFactor(1, 4)
                splitter.setStretchFactor(2, 1)
            except Exception:
                pass

        # Do NOT persist splitter state for now — temporary change per request
        self.setCentralWidget(splitter)

        # Connect Home active event to hide/show inspector while preserving size
        try:
            self.workspace.home_active.connect(self._on_home_active)
        except Exception:
            pass

        # Connect dashboard project reveal to explorer reveal
        try:
            # workspace exposes dashboard instance
            # connect dashboard reveal -> navigation service if available, otherwise fallback to explorer reveal
            try:
                if getattr(self, 'navigation_service', None):
                    self.workspace.dashboard.project_reveal.connect(lambda p: self.navigation_service.navigate_project(p) if p else None)
                else:
                    self.workspace.dashboard.project_reveal.connect(lambda p: self.explorer.reveal_project(p) if p else None)
            except Exception:
                pass
        except Exception:
            pass

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

    def _on_home_active(self, active: bool):
        try:
            if active:
                # remember sizes and hide inspector
                try:
                    self._saved_splitter_sizes = self.splitter.sizes()
                except Exception:
                    self._saved_splitter_sizes = None
                self.inspector.setVisible(False)
            else:
                # show inspector and restore sizes
                self.inspector.setVisible(True)
                if self._saved_splitter_sizes:
                    try:
                        self.splitter.setSizes(self._saved_splitter_sizes)
                    except Exception:
                        pass
        except Exception:
            pass

    def on_asset_selected(self, asset_id):
        # Show asset metadata in inspector
        if not self.context.current_project:
            return
        try:
            self.inspector.show_asset(self.context.current_project, asset_id)
        except Exception:
            pass
        # update canonical app state so services can react (e.g., deletion clears inspector)
        try:
            self.context.app_state.set_current_asset(asset_id)
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
            self.workspace.show_section(project, "dashboard")

        self.status.showMessage(
            f"Snapshot updated for '{project.name}'.",
            5000,
        )

    def remove_snapshot(self, project):

        self.context.project_service.remove_snapshot(project)

        if self.context.current_project == project:
            self.workspace.show_section(project, "dashboard")

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