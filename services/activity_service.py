import json
from pathlib import Path
from datetime import datetime
class ActivityService:
    """Record user actions for Recent Activity and analytics.
    Persists to config/activity.json and keeps an in-memory list.
    """
    MAX_ENTRIES = 100
    def __init__(self):
        self.config_folder = Path("config")
        self.config_folder.mkdir(exist_ok=True)
        self._file = self.config_folder / "activity.json"
        self._load()
    def _load(self):
        if not self._file.exists():
            self._entries = []
            return
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                self._entries = json.load(f)
                if isinstance(self._entries, list):
                    self._entries = self._entries[-self.MAX_ENTRIES:]
                else:
                    self._entries = []
        except Exception:
            self._entries = []
    def _save(self):
        try:
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump(self._entries[-self.MAX_ENTRIES:], f, indent=2)
        except Exception:
            pass
    def record(
        self,
        action: str,
        details: dict | None = None,
        description: str | None = None,
        project=None,
        board_id: str | None = None,
        node_id: str | None = None,
        event_type: str | None = None,
    ):
        proj_name = None
        proj_loc = None
        if project:
            proj_name = getattr(project, "name", str(project))
            proj_loc = getattr(project, "location", str(project))
        ev_type = event_type or action
        desc = description or action
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": ev_type,
            "action": action,
            "description": desc,
            "project_name": proj_name,
            "project_location": proj_loc,
            "board_id": board_id,
            "node_id": node_id,
            "details": details or {},
        }
        self._entries.append(entry)
        self._entries = self._entries[-self.MAX_ENTRIES:]
        self._save()
    def recent(self, limit: int = 10):
        """Return the most recent activity entries, newest first."""
        return list(reversed(self._entries[-limit:]))
    def clear(self):
        self._entries = []
        self._save()
