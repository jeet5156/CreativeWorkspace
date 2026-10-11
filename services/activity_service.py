import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Union

from core.paths import get_local_config_dir
from core.storage import atomic_write_json, safe_read_json


class ActivityService:
    """Record user actions for Recent Activity and analytics.
    Persists to machine-local config (~/.creativeworkspace/activity.json) and keeps an in-memory list.
    """
    MAX_ENTRIES = 100

    def __init__(self, config_folder: Optional[Union[str, Path]] = None, storage_file: Optional[Union[str, Path]] = None):
        if storage_file:
            self._file = Path(storage_file)
            self.config_folder = self._file.parent
        elif config_folder:
            self.config_folder = Path(config_folder)
            self._file = self.config_folder / "activity.json"
        else:
            self.config_folder = get_local_config_dir()
            self._file = self.config_folder / "activity.json"

        self.config_folder.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        if not self._file.exists():
            self._entries = []
            return
        data, err = safe_read_json(self._file)
        if not err and isinstance(data, list):
            self._entries = data[-self.MAX_ENTRIES:]
        else:
            self._entries = []

    def _save(self):
        try:
            atomic_write_json(self._file, self._entries[-self.MAX_ENTRIES:])
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
