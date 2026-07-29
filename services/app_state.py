from PySide6.QtCore import QObject, Signal


class AppState(QObject):
    """Central app state with signals for observers.

    Tracks current workspace, project, asset, reference, and search state.
    """

    current_project_changed = Signal(object)
    current_asset_changed = Signal(object)
    current_reference_changed = Signal(object)
    current_workspace_changed = Signal(str)
    search_state_changed = Signal(dict)

    def __init__(self):
        super().__init__()
        self.current_workspace = "home"
        self.current_project = None
        self.current_asset = None
        self.current_reference = None
        self.search_state = {}

    def set_workspace(self, key: str):
        self.current_workspace = key
        try:
            self.current_workspace_changed.emit(key)
        except Exception:
            pass

    def set_current_project(self, project):
        self.current_project = project
        try:
            self.current_project_changed.emit(project)
        except Exception:
            pass

    def set_current_asset(self, asset_id):
        self.current_asset = asset_id
        try:
            self.current_asset_changed.emit(asset_id)
        except Exception:
            pass

    def set_current_reference(self, ref_id):
        self.current_reference = ref_id
        try:
            self.current_reference_changed.emit(ref_id)
        except Exception:
            pass

    def set_search_state(self, state: dict):
        self.search_state = state
        try:
            self.search_state_changed.emit(state)
        except Exception:
            pass
