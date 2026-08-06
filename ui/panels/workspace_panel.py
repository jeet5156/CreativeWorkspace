from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from PySide6.QtCore import Signal

from ui.panels.dashboard_panel import DashboardPanel
from ui.panels.notes_panel import NotesPanel
from ui.panels.asset_workspace_panel import AssetWorkspacePanel
from ui.panels.home_workspace_panel import HomeWorkspacePanel


class WorkspacePanel(QWidget):

    # Emitted after a drop/import completes: report dict
    import_finished = Signal(object)
    # Emitted when Home workspace becomes active (True) or deactivated (False)
    home_active = Signal(bool)
    # Emitted when folder navigation is requested from grid (project, section, rel_path)
    folder_navigation_requested = Signal(object, str, str)

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        self.stack = QStackedWidget()

        # Home workspace shown when no project selected
        self.home = HomeWorkspacePanel()
        self.dashboard = DashboardPanel()
        self.notes = NotesPanel()
        self.asset_workspace = AssetWorkspacePanel()

        # add widgets: home is default (index 0)
        self.stack.addWidget(self.home)
        self.stack.addWidget(self.dashboard)
        self.stack.addWidget(self.notes)
        self.stack.addWidget(self.asset_workspace)

        layout.addWidget(self.stack)

        self._context = None
        self._current_project = None
        self._current_section = None

        # forward asset selection & folder navigation
        try:
            self.asset_workspace.asset_selected.connect(self._on_asset_selected)
        except Exception:
            pass
        try:
            self.asset_workspace.folder_navigation_requested.connect(
                lambda p, s, r: self.folder_navigation_requested.emit(p, s, r)
            )
        except Exception:
            pass

        # enable drop on workspace
        self.setAcceptDrops(True)

    def set_context(self, context):
        """Provide AppContext so panel can listen to asset updates."""
        self._context = context
        # let child panels also receive context (so they can update themselves)
        try:
            self.home.set_context(context)
        except Exception:
            pass
        try:
            self.asset_workspace.set_context(context)
        except Exception:
            pass
        try:
            self.dashboard.set_context(context)
        except Exception:
            pass
        # connect asset change signals
        try:
            context.asset_service.assets_changed.connect(self._on_assets_changed)
        except Exception:
            pass

    def show_home(self):
        """Display the Home workspace (no project selected)."""
        self._current_project = None
        self._current_section = None
        try:
            self.home.set_context(self._context)
        except Exception:
            pass
        self.stack.setCurrentWidget(self.home)
        try:
            self.home_active.emit(True)
        except Exception:
            pass

    def show_section(self, project, section, rel_path=None):
        """Show dashboard when section is 'dashboard'; otherwise the workspace view for that section.
        Reset state when switching projects so dashboard is always shown for project root.
        """

        # If no project provided, show home
        if project is None:
            self.show_home()
            return

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

        # Ensure home is marked inactive
        try:
            self.home_active.emit(False)
        except Exception:
            pass

        if section == "dashboard":
            self.dashboard.show_project(project)
            self.stack.setCurrentWidget(self.dashboard)
            return

        if section == "notes":
            self.notes.show_project(project)
            self.stack.setCurrentWidget(self.notes)
            return

        if section == "lab":
            if getattr(self, "_context", None) and getattr(self._context, "workspace_manager", None):
                wm = self._context.workspace_manager
                if getattr(wm, "lab_panel", None):
                    wm.lab_panel.show_project(project)
                    self.stack.setCurrentWidget(wm.lab_panel)
                    return

        # For assets/references/renders/exports show the asset workspace
        self.asset_workspace.show_project_section(project, section, self._context, rel_path=rel_path)
        self.stack.setCurrentWidget(self.asset_workspace)

    def _on_assets_changed(self, project, category):
        # If the change is for the currently displayed project/section, refresh
        if not self._current_project:
            return
        if project.location != self._current_project.location:
            return
        # Map category names to section keys: category stored as 'Assets' or 'References'
        section = self._current_section
        # If no category filter (None or empty string) or it matches current section, refresh
        if not category or category.lower() == str(section).lower() or (section == 'assets' and category == 'Assets'):
            # refresh current view preserving active relative path subfolder
            active_rel = getattr(self.asset_workspace, '_current_rel_path', None)
            self.show_section(self._current_project, self._current_section, rel_path=active_rel)

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
        target_rel = getattr(self.asset_workspace, '_current_rel_path', None)

        report = self._context.asset_service.import_paths(
            self._current_project, section, paths, target_rel_path=target_rel
        )

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
