from services.project_service import ProjectService
from services.settings_service import SettingsService
from services.asset_service import AssetService
from services.status_service import StatusService
from services.app_state import AppState
from services.activity_service import ActivityService


class AppContext:

    def __init__(self):
        self.project_service = ProjectService()
        self.settings_service = SettingsService()
        # AssetService uses ProjectService for project locations and folder structure
        self.asset_service = AssetService(self.project_service)
        # StatusService provides enum-based folder status reporting
        self.status_service = StatusService(self.project_service)

        # Central app state and activity tracking
        self.app_state = AppState()
        self.activity_service = ActivityService()

        # AssetOperationsService handles file-level operations and coordinates updates
        try:
            from services.asset_operations_service import AssetOperationsService
            self.asset_operations = AssetOperationsService(self.asset_service, self.activity_service, self.project_service, app_state=self.app_state)
        except Exception:
            self.asset_operations = None

        self.current_project = None

    def set_current_project(self, project):
        self.current_project = project
        try:
            self.app_state.set_current_project(project)
        except Exception:
            pass