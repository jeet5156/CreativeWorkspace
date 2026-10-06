import json
from pathlib import Path
from typing import Optional, Union, Dict, Any


class SettingsService:

    DEFAULT_SETTINGS = {
        "recent_projects": [],
        "last_session": {}
    }

    def __init__(self, config_dir: Optional[Union[str, Path]] = None):
        if config_dir:
            self.config_folder = Path(config_dir)
        else:
            self.config_folder = Path.home() / ".creativeworkspace"

        self.config_folder.mkdir(parents=True, exist_ok=True)
        self.settings_file = self.config_folder / "settings.json"

        # Ensure valid settings file exists on disk
        self.load()

    def _get_defaults(self) -> Dict[str, Any]:
        return {
            "recent_projects": [],
            "last_session": {}
        }

    def load(self) -> Dict[str, Any]:
        if not self.settings_file.exists() or self.settings_file.stat().st_size == 0:
            defaults = self._get_defaults()
            self.save(defaults)
            return defaults

        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except Exception:
            defaults = self._get_defaults()
            self.save(defaults)
            return defaults

        if not isinstance(settings, dict):
            defaults = self._get_defaults()
            self.save(defaults)
            return defaults

        needs_save = False
        if "recent_projects" not in settings or not isinstance(settings["recent_projects"], list):
            settings["recent_projects"] = []
            needs_save = True

        if "last_session" not in settings or not isinstance(settings["last_session"], dict):
            settings["last_session"] = {}
            needs_save = True

        if needs_save:
            self.save(settings)

        return settings

    def save(self, settings: Dict[str, Any]):
        self.config_folder.mkdir(parents=True, exist_ok=True)
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)

    def recent_projects(self):
        return self.load().get("recent_projects", [])

    def add_recent_project(self, project_path):
        settings = self.load()
        recent = settings.get("recent_projects", [])
        if not isinstance(recent, list):
            recent = []

        project_path = str(Path(project_path))

        if project_path in recent:
            recent.remove(project_path)

        recent.insert(0, project_path)
        settings["recent_projects"] = recent[:20]
        self.save(settings)

    def remove_recent_project(self, project_path):
        settings = self.load()
        recent = settings.get("recent_projects", [])
        if not isinstance(recent, list):
            recent = []

        project_path = str(Path(project_path))

        if project_path in recent:
            recent.remove(project_path)
            settings["recent_projects"] = recent
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
        last = settings.get("last_session")
        if isinstance(last, dict):
            return last
        return {}

    def save_last_session(self, session: dict):
        settings = self.load()
        settings["last_session"] = session if isinstance(session, dict) else {}
        self.save(settings)