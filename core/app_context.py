from services.project_service import ProjectService
from services.settings_service import SettingsService
from services.asset_service import AssetService


class AppContext:

    def __init__(self):
        self.project_service = ProjectService()
        self.settings_service = SettingsService()
        # AssetService uses ProjectService for project locations and folder structure
        self.asset_service = AssetService(self.project_service)

        self.current_project = None

    def set_current_project(self, project):
        self.current_project = project