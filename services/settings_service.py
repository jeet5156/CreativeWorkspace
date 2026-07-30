import json
from pathlib import Path


class SettingsService:

    def __init__(self):

        self.config_folder = Path("config")
        self.config_folder.mkdir(exist_ok=True)

        self.settings_file = self.config_folder / "settings.json"

        if not self.settings_file.exists():
            self.save(
                {
                    "recent_projects": [],
                    "last_session": {}
                }
            )

    def load(self):

        with open(self.settings_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, settings):

        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)

    def recent_projects(self):
        return self.load()["recent_projects"]

    def add_recent_project(self, project_path):

        settings = self.load()

        recent = settings["recent_projects"]

        project_path = str(Path(project_path))

        if project_path in recent:
            recent.remove(project_path)

        recent.insert(0, project_path)

        settings["recent_projects"] = recent[:20]

        self.save(settings)

    def remove_recent_project(self, project_path):

        settings = self.load()

        recent = settings["recent_projects"]

        project_path = str(Path(project_path))

        if project_path in recent:
            recent.remove(project_path)

        self.save(settings)

    # -------------------------
    # Splitter state helpers
    # -------------------------
    def get_splitter_state(self):
        settings = self.load()
        return settings.get("splitter_state")

    def set_splitter_state(self, hex_state: str):
        settings = self.load()
        settings["splitter_state"] = hex_state
        self.save(settings)

    # -------------------------
    # Last session helpers
    # -------------------------
    def load_last_session(self):
        settings = self.load()
        return settings.get("last_session", {})

    def save_last_session(self, session: dict):
        settings = self.load()
        settings["last_session"] = session or {}
        self.save(settings)