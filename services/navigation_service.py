from PySide6.QtCore import QObject, Signal


class NavigationService(QObject):
    """Central navigation controller.

    Emits signals for navigation events and delegates to WorkspaceManager/Explorer.
    """

    navigate_to_home = Signal()
    navigate_to_project = Signal(object, str)
    navigate_to_module = Signal(str)

    def __init__(self, workspace_manager, explorer, context):
        super().__init__()
        self.workspace_manager = workspace_manager
        self.explorer = explorer
        self.context = context

    # Public API
    def handle_navigation(self, key: str):
        if key == "home":
            self.navigate_home()
        elif key == "projects":
            self.navigate_projects_dashboard()
        else:
            self.navigate_module(key)

    def navigate_home(self):
        try:
            self.workspace_manager.show_home()
            self.navigate_to_home.emit()
        except Exception:
            pass

    def navigate_projects_dashboard(self):
        try:
            self.workspace_manager.show_module("projects_dashboard")
            self.navigate_to_module.emit("projects_dashboard")
        except Exception:
            pass

    def navigate_module(self, key: str):
        try:
            self.workspace_manager.show_module(key)
            self.navigate_to_module.emit(key)
        except Exception:
            pass

    def navigate_project(self, project, section: str = "dashboard"):
        try:
            # Reveal in explorer without re-emitting signal to avoid loops
            try:
                self.explorer.reveal_project(project, section, emit=False)
            except Exception:
                pass
            # show project in workspace
            try:
                self.workspace_manager.show_project(project, section)
            except Exception:
                pass
            self.navigate_to_project.emit(project, section)
        except Exception:
            pass

    def navigate_to_asset(self, project, asset_id):
        try:
            # show project assets and select the asset card
            self.workspace_manager.show_project(project, "assets")
            # attempt to request selection on asset workspace
            try:
                aw = self.workspace_manager.workspace.asset_workspace
                try:
                    aw.request_select_asset(asset_id)
                except Exception:
                    pass
            except Exception:
                pass
        except Exception:
            pass

    def navigate_search_result(self, result: dict):
        """Unified entry for activating a search result.

        Result is expected to be a dict with a 'type' key: 'project', 'asset', or 'reference'.
        For assets/references, result contains 'project' and 'asset_id'.
        """
        try:
            t = result.get('type')
            if t == 'project':
                proj = result.get('project')
                self.navigate_project(proj)
            elif t == 'asset':
                proj = result.get('project')
                aid = result.get('asset_id')
                # navigate to project first, then to asset
                self.navigate_project(proj, 'assets')
                # request selection on asset workspace
                try:
                    aw = self.workspace_manager.workspace.asset_workspace
                    try:
                        aw.request_select_asset(aid)
                    except Exception:
                        pass
                except Exception:
                    pass
            elif t == 'reference':
                proj = result.get('project')
                aid = result.get('asset_id')
                self.navigate_project(proj, 'references')
                try:
                    aw = self.workspace_manager.workspace.asset_workspace
                    try:
                        aw.request_select_asset(aid)
                    except Exception:
                        pass
                except Exception:
                    pass
            else:
                pass
        except Exception:
            pass
