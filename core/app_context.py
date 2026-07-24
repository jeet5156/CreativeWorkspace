from services.project_service import ProjectService
from services.settings_service import SettingsService


class AppContext:

    def __init__(self):
        self.project_service = ProjectService()
        self.settings_service = SettingsService()

        self.current_project = None

    def set_current_project(self, project):
        self.current_project = project