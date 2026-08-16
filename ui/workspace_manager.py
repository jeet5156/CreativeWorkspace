from typing import Any, Dict, List, Optional, Union

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

        try:
            if hasattr(self.workspace, "home") and self.workspace.home:
                self.workspace.home.open_workbench_requested.connect(self.show_workbench)
                self.workspace.home.open_board_requested.connect(
                    lambda proj, b_name, nid=None: (
                        self.show_project(proj, section="lab") if proj else self.show_workbench(),
                        self.lab_panel.show_project(proj, board_name=b_name, target_node_id=nid) if self.lab_panel else None,
                        self.show_module("lab")
                    )
                )
        except Exception:
            pass

        # Register Global Asset Library Panel
        try:
            from ui.panels.library_workspace_panel import LibraryWorkspacePanel
            self.library_panel = LibraryWorkspacePanel(self.context)
            self._register_module("assets_lib", self.library_panel)
        except Exception:
            self.library_panel = ModulePlaceholder(
                "Global Asset Library (Coming Soon)",
                "Global asset repository, multi-project tagging, and cross-project asset discovery. This module will provide central asset indexing across all creative projects.",
                badge="Coming Soon",
                icon="📚"
            )
            self._register_module("assets_lib", self.library_panel)

        # Register Global Knowledge Panel
        try:
            from ui.panels.knowledge_workspace_panel import KnowledgeWorkspacePanel
            self.knowledge_panel = KnowledgeWorkspacePanel(self.context)
            self._register_module("knowledge", self.knowledge_panel)
        except Exception:
            self.knowledge_panel = ModulePlaceholder(
                "Global Knowledge (Coming Soon)",
                "Central documentation, creative notes, and knowledge base. This module will synthesize notes and documentation across all active projects.",
                badge="Coming Soon",
                icon="📖"
            )
            self._register_module("knowledge", self.knowledge_panel)

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
            elif key == "assets_lib" and getattr(self, "library_panel", None):
                try:
                    if hasattr(self.library_panel, "show_library"):
                        self.library_panel.show_library()
                    elif hasattr(self.library_panel, "refresh_library"):
                        self.library_panel.refresh_library()
                except Exception:
                    pass
            elif key == "knowledge" and getattr(self, "knowledge_panel", None):
                try:
                    if hasattr(self.knowledge_panel, "refresh"):
                        self.knowledge_panel.refresh()
                except Exception:
                    pass
            self.workspace.stack.setCurrentWidget(w)
        except Exception:
            pass


    def show_workbench(self):
        """Navigate to global Workbench in LabPanel (project=None)."""
        if getattr(self, "lab_panel", None):
            try:
                if self.context:
                    self.context.set_current_project(None)
                self.lab_panel.show_project(None)
            except Exception:
                pass
            self.show_module("lab")

    def _resolve_project(self, project_or_name: Any):
        """Resolve a Project object from either a Project instance or name/location string."""
        if not project_or_name:
            return None
        if hasattr(project_or_name, "location"):
            return project_or_name
        proj_svc = getattr(self.context, "project_service", None)
        if proj_svc:
            p_str = str(project_or_name).strip()
            for p in proj_svc.all_projects():
                if p.name.lower() == p_str.lower() or getattr(p, "location", "").lower() == p_str.lower():
                    return p
        return None

    def navigate(self, payload: Any) -> bool:
        """Execute unified navigation targeting exact entity across any workspace."""
        from core.navigation import NavigationPayload, NavigationTargetType

        if isinstance(payload, dict):
            payload = NavigationPayload.from_dict(payload)
        elif not isinstance(payload, NavigationPayload):
            return False

        t_type = payload.target_type

        # 1. Project Overview / Section Navigation
        if t_type in (NavigationTargetType.PROJECT.value, "project"):
            proj = self._resolve_project(payload.project or payload.project_id)
            if proj:
                self.show_project(proj, section=payload.section or "dashboard", rel_path=payload.rel_path)
                return True
            return False

        # 2. Exact Project Asset Navigation
        elif t_type in (NavigationTargetType.PROJECT_ASSET.value, "project_asset"):
            proj = self._resolve_project(payload.project or payload.project_id)
            if not proj:
                return False

            asset_svc = getattr(self.context, "asset_service", None)
            asset_entry = None
            if asset_svc and payload.target_id:
                asset_entry = asset_svc.get_asset(proj, payload.target_id)

            section = payload.section or "assets"
            rel_folder = payload.rel_path
            asset_id_to_select = payload.target_id

            if asset_entry:
                asset_id_to_select = asset_entry.get("id") or payload.target_id
                rp = asset_entry.get("relative_path", "")
                if rp:
                    parts = rp.replace("\\", "/").split("/")
                    top = parts[0].lower()
                    if top in ("references", "renders", "exports", "notes"):
                        section = top
                    elif top in ("library references", "library_references") or asset_entry.get("is_library_reference"):
                        section = "library_references"
                    else:
                        section = "assets"
                    if len(parts) > 1:
                        rel_folder = "/".join(parts[:-1])
                    else:
                        rel_folder = parts[0]

            self.show_project(proj, section=section, rel_path=rel_folder)

            if hasattr(self.workspace, "asset_workspace") and self.workspace.asset_workspace:
                self.workspace.asset_workspace.request_select_asset(asset_id_to_select)

            insp = getattr(self.context, "inspector_panel", None)
            if insp and asset_id_to_select:
                try:
                    insp.show_asset(proj, asset_id_to_select)
                except Exception:
                    pass
            return True

        # 3. Exact Library Asset Navigation
        elif t_type in (NavigationTargetType.LIBRARY_ASSET.value, "library_asset"):
            self.show_module("assets_lib")
            if getattr(self, "library_panel", None) and payload.target_id:
                self.library_panel.navigate_to_asset(payload.target_id)
                lib_svc = getattr(self.context, "library_service", None)
                insp = getattr(self.context, "inspector_panel", None)
                if lib_svc and insp:
                    asset = lib_svc.get_asset(payload.target_id)
                    if asset:
                        try:
                            insp.show_library_asset(asset)
                        except Exception:
                            pass
            return True

        # 4. Exact Knowledge Document Navigation
        elif t_type in (NavigationTargetType.KNOWLEDGE_DOC.value, "knowledge", "knowledge_doc"):
            self.show_module("knowledge")
            if getattr(self, "knowledge_panel", None) and payload.target_id:
                if hasattr(self.knowledge_panel, "show_document"):
                    self.knowledge_panel.show_document(payload.target_id)
                insp = getattr(self.context, "inspector_panel", None)
                k_svc = getattr(self.context, "knowledge_service", None)
                if insp and k_svc:
                    doc = k_svc.get_document(payload.target_id)
                    if doc:
                        try:
                            insp.show_knowledge_document(doc)
                        except Exception:
                            pass
            return True

        # 5. Exact Lab Node / Board Navigation
        elif t_type in (NavigationTargetType.LAB_NODE.value, "lab_node", NavigationTargetType.LAB_BOARD.value, "lab_board"):
            proj = self._resolve_project(payload.project or payload.project_id) if (payload.project or payload.project_id) else None
            board_id = payload.target_id
            node_id = payload.sub_target_id

            if proj:
                self.show_project(proj, section="lab")
            else:
                self.show_workbench()

            if getattr(self, "lab_panel", None):
                self.lab_panel.show_project(proj, board_id=board_id, target_node_id=node_id)
            self.show_module("lab")
            return True

        return False

    def handle_navigation(self, key: str):
        if key == "home":
            self.show_home()
        elif key == "projects":
            self.show_module("projects_dashboard")
        elif key in ("lab", "workbench"):
            self.show_workbench()
        else:
            self.show_module(key)

