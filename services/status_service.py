from enum import Enum
from pathlib import Path
from typing import Dict

from models.project import Project


class Status(Enum):
    EMPTY = "empty"
    READY = "ready"
    WARNING = "warning"


class StatusService:
    """Lightweight service that reports folder status for a project.

    Public API:
      get_project_statuses(project) -> Dict[str, Status]

    The service performs filesystem checks here (service layer), so the UI only
    receives an enum it can render consistently.
    """

    def __init__(self, project_service=None):
        # project_service is optional for future expansion
        self.project_service = project_service

    def _folder_has_items(self, project: Project, folder_name: str) -> bool:
        try:
            folder = Path(project.location) / folder_name
            if not folder.exists() or not folder.is_dir():
                return False
            # check for at least one file (recursively)
            for _ in folder.rglob("*"):
                # ensure there's at least one file
                return True
            return False
        except Exception:
            return False

    def get_project_statuses(self, project: Project) -> Dict[str, Status]:
        result = {}
        mapping = {
            "assets": "Assets",
            "references": "References",
            "exports": "Exports",
        }

        for key, folder in mapping.items():
            try:
                has_items = self._folder_has_items(project, folder)
                if has_items:
                    result[key] = Status.READY
                else:
                    result[key] = Status.EMPTY
            except Exception:
                result[key] = Status.WARNING

        return result
