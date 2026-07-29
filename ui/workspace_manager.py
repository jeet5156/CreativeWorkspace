from typing import Dict

from ui.panels.module_placeholder import ModulePlaceholder
from ui.panels.home_workspace_panel import HomeWorkspacePanel
from ui.panels.dashboard_panel import DashboardPanel
from ui.panels.projects_dashboard import ProjectsDashboard
from services.find_service import FindService


class WorkspaceManager:
    """Controller that orchestrates which workspace view is shown.

    Keeps MainWindow simple: call show_home(), show_project(project, section), or show_module(key).
    """

    def __init__(self, workspace_panel, context, navigation_service=None):
        self.workspace = workspace_panel
        self.context = context
        self.navigation_service = navigation_service

        # Create placeholder module panels and register them in the workspace stack
        self._modules: Dict[str, object] = {}

        # Home is already part of the workspace stack as index 0
        # Register Projects dashboard
        self.projects_dashboard = ProjectsDashboard(self.context)
        self._register_module("projects_dashboard", self.projects_dashboard)

        # register placeholder modules first
        self._register_module("clients", ModulePlaceholder("Clients", "Manage client records, contacts, and deliverables."))
        self._register_module("assets_lib", ModulePlaceholder("Asset Library", "Global asset repository and tagging."))
        self._register_module("knowledge", ModulePlaceholder("Knowledge", "Notes, docs, and knowledge base."))
        self._register_module("business", ModulePlaceholder("Business", "Invoices, contracts, and financial tools."))

        # FindService available for global search via Explorer
        self.find_service = FindService(context)
        self.search_panel = None

    def set_navigation_service(self, navigation_service):
        self.navigation_service = navigation_service
        # nothing to create here for search — Explorer uses WorkspaceManager.find_service directly
        try:
            # record navigation service reference for modules that need it
            self.navigation_service = navigation_service
        except Exception:
            pass

    def show_home(self):
        try:
            # ensure home panel receives context so it can refresh
            try:
                self.workspace.home.set_context(self.context)
                # record that user returned home
                try:
                    self.context.activity_service.record('navigate_home')
                except Exception:
                    pass
            except Exception:
                pass
            self.workspace.show_home()
        except Exception:
            pass

    def _register_module(self, key: str, widget):
        try:
            self.workspace.stack.addWidget(widget)
            self._modules[key] = widget
        except Exception:
            pass

    def show_home(self):
        try:
            self.workspace.show_home()
        except Exception:
            pass

    def show_project(self, project, section="dashboard"):
        try:
            # keep existing workspace logic
            self.workspace.show_section(project, section)
        except Exception:
            pass

    def show_module(self, key: str):
        w = self._modules.get(key)
        if not w:
            return
        try:
            # If projects dashboard, refresh its content
            if key == "projects_dashboard":
                try:
                    self.projects_dashboard.refresh()
                except Exception:
                    pass
            self.workspace.stack.setCurrentWidget(w)
        except Exception:
            pass


    def handle_navigation(self, key: str):
        if key == "home":
            self.show_home()
        elif key == "projects":
            self.show_module("projects_dashboard")
        else:
            self.show_module(key)
