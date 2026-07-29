import json
from pathlib import Path
from datetime import datetime


class ActivityService:
    """Record user actions for Recent Activity and analytics.

    Persists to config/activity.json and keeps an in-memory list.
    """

    MAX_ENTRIES = 500

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
        except Exception:
            self._entries = []

    def _save(self):
        try:
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump(self._entries[-self.MAX_ENTRIES:], f, indent=2)
        except Exception:
            pass

    def record(self, action: str, details: dict | None = None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details or {},
        }
        self._entries.append(entry)
        # trim
        self._entries = self._entries[-self.MAX_ENTRIES:]
        self._save()

    def recent(self, limit: int = 20):
        return list(reversed(self._entries[-limit:]))

    def clear(self):
        self._entries = []
        self._save()
