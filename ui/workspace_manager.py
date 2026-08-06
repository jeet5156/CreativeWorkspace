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

        # Register Lab Panel
        try:
            from ui.panels.lab_panel import LabPanel
            self.lab_panel = LabPanel(self.context)
            self._register_module("lab", self.lab_panel)
        except Exception:
            self.lab_panel = None

        # Register Client Workspace Panel
        try:
            from ui.panels.client_workspace_panel import ClientWorkspacePanel
            self.client_panel = ClientWorkspacePanel(self.context)
            self._register_module("clients", self.client_panel)
        except Exception:
            self.client_panel = ModulePlaceholder("Clients", "Manage client records, contacts, and deliverables.")
            self._register_module("clients", self.client_panel)

        self._register_module(
            "assets_lib",
            ModulePlaceholder(
                "Global Asset Library (Coming Soon)",
                "Global asset repository, multi-project tagging, and cross-project asset discovery. This module will provide central asset indexing across all creative projects.",
                badge="Coming Soon",
                icon="📚"
            )
        )
        self._register_module(
            "knowledge",
            ModulePlaceholder(
                "Global Knowledge (Coming Soon)",
                "Central documentation, creative notes, and knowledge base. This module will synthesize notes and documentation across all active projects.",
                badge="Coming Soon",
                icon="📖"
            )
        )
        self._register_module(
            "business",
            ModulePlaceholder(
                "Business Tools (Coming Soon)",
                "Invoices, contracts, rates, and financial tools for creative projects and client management.",
                badge="Coming Soon",
                icon="💼"
            )
        )

        # FindService available for global search via Explorer
        self.find_service = FindService(context)
        self.search_panel = None

    def set_navigation_service(self, navigation_service):
        self.navigation_service = navigation_service
        try:
            if hasattr(self.workspace, 'folder_navigation_requested'):
                self.workspace.folder_navigation_requested.connect(
                    lambda p, s, r: self.navigation_service.navigate_project(p, s, rel_path=r)
                    if self.navigation_service else None
                )
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

    def show_project(self, project, section="dashboard", rel_path=None):
        if not project:
            return
        try:
            if self.context:
                self.context.set_current_project(project)
                if hasattr(self.context, "inspector_panel") and self.context.inspector_panel:
                    try:
                        self.context.inspector_panel.show_project(project)
                    except Exception:
                        pass
            self.workspace.show_section(project, section, rel_path=rel_path)
        except Exception:
            pass

    def show_module(self, key: str):
        w = self._modules.get(key)
        if not w:
            return
        try:
            try:
                self.workspace.home_active.emit(False)
            except Exception:
                pass
            # If projects dashboard, refresh its content
            if key == "projects_dashboard":
                try:
                    self.projects_dashboard.refresh()
                except Exception:
                    pass
            elif key == "lab" and getattr(self, "lab_panel", None):
                try:
                    proj = getattr(self.context, "current_project", None)
                    if proj:
                        self.lab_panel.show_project(proj)
                except Exception:
                    pass
            elif key == "clients" and getattr(self, "client_panel", None):
                try:
                    if hasattr(self.client_panel, "stack") and hasattr(self.client_panel, "dashboard_panel") and self.client_panel.stack.currentWidget() == self.client_panel.dashboard_panel:
                        pass
                    elif hasattr(self.client_panel, "show_clients_root_dashboard"):
                        self.client_panel.show_clients_root_dashboard()
                    elif hasattr(self.client_panel, "refresh"):
                        self.client_panel.refresh()
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
