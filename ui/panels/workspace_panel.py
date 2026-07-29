from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from PySide6.QtCore import Signal

from ui.panels.dashboard_panel import DashboardPanel
from ui.panels.notes_panel import NotesPanel
from ui.panels.asset_workspace_panel import AssetWorkspacePanel


class WorkspacePanel(QWidget):

    # Emitted after a drop/import completes: report dict
    import_finished = Signal(object)

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        self.stack = QStackedWidget()

        self.dashboard = DashboardPanel()
        self.notes = NotesPanel()
        self.asset_workspace = AssetWorkspacePanel()

        self.stack.addWidget(self.dashboard)
        self.stack.addWidget(self.notes)
        self.stack.addWidget(self.asset_workspace)

        layout.addWidget(self.stack)

        self._context = None
        self._current_project = None
        self._current_section = None

        # forward asset selection
        try:
            self.asset_workspace.asset_selected.connect(self._on_asset_selected)
        except Exception:
            pass

        # enable drop on workspace
        self.setAcceptDrops(True)

    def set_context(self, context):
        """Provide AppContext so panel can listen to asset updates."""
        self._context = context
        # connect asset change signals
        try:
            context.asset_service.assets_changed.connect(self._on_assets_changed)
        except Exception:
            pass

    def show_section(self, project, section):
        """Show dashboard when section is 'dashboard'; otherwise the workspace view for that section.
        Reset state when switching projects so dashboard is always shown for project root.
        """
        # Reset state when switching projects
        if not self._current_project or project.location != self._current_project.location:
            # new project -> reset internal state
            self._current_project = project
            self._current_section = None
            try:
                self.asset_workspace.clear()
            except Exception:
                pass

        self._current_project = project
        self._current_section = section

        if section == "dashboard":
            self.dashboard.show_project(project)
            self.stack.setCurrentWidget(self.dashboard)
            return

        if section == "notes":
            self.notes.show_project(project)
            self.stack.setCurrentWidget(self.notes)
            return

        # For assets/references/renders/exports show the asset workspace
        self.asset_workspace.show_project_section(project, section, self._context)
        self.stack.setCurrentWidget(self.asset_workspace)

    def _on_assets_changed(self, project, category):
        # If the change is for the currently displayed project/section, refresh
        if not self._current_project:
            return
        if project.location != self._current_project.location:
            return
        # Map category names to section keys: category stored as 'Assets' or 'References'
        section = self._current_section
        # If no category filter or it matches current section, refresh
        if category is None or category.lower() == section.lower() or (section == 'assets' and category == 'Assets'):
            # refresh current view
            self.show_section(self._current_project, self._current_section)

    # ---------------------
    # Drag & Drop on the workspace
    # ---------------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]

        if not paths:
            event.ignore()
            return

        if not self._current_project:
            event.ignore()
            return

        # Determine target section: use current section, default to assets
        section = self._current_section or 'assets'

        report = self._context.asset_service.import_paths(self._current_project, section, paths)

        # emit finished report for main window to show messages
        try:
            self.import_finished.emit(report)
        except Exception:
            pass

        # rely on AssetService emitting assets_changed to refresh view
        event.acceptProposedAction()

    # forward asset selection to outside
    def _on_asset_selected(self, asset_id):
        # bubble up a selection signal via parent if needed; main window can access asset_workspace directly
        pass

    def clear(self):
        try:
            self.asset_workspace.clear()
        except Exception:
            pass
