from pathlib import Path
from dataclasses import asdict
from datetime import datetime
import json
import shutil
from PySide6.QtCore import QObject, Signal

from models.project import Project


class ProjectService(QObject):
    """Single source of truth for Project lifecycle operations and event notifications."""

    project_created = Signal(object)
    project_updated = Signal(object)
    project_deleted = Signal(object)
    project_opened = Signal(object)

    def __init__(self):
        super().__init__()
        self.projects: list[Project] = []

    def create_project(
        self,
        name: str,
        project_type: str,
        location: str,
        description: str,
        snapshot_path: str = "",
    ) -> Project:

        project_folder = Path(location) / name

        project = Project(
            name=name,
            project_type=project_type,
            location=str(project_folder),
            description=description,
        )

        project_folder.mkdir(parents=True, exist_ok=True)

        for folder in (
            "Notes",
            "References",
            "Assets",
            "Renders",
            "Exports",
        ):
            (project_folder / folder).mkdir(exist_ok=True)

        if snapshot_path:
            source = Path(snapshot_path)
            if source.exists():
                shutil.copy2(
                    source,
                    project_folder / "snapshot.png",
                )

        self.save_project(project)
        self.add_project(project)

        try:
            self.project_created.emit(project)
        except Exception:
            pass

        return project

    def save_project(self, project: Project):
        if not project or not getattr(project, "location", None):
            return

        project.modified = datetime.now()

        data = asdict(project)
        data["created"] = project.created.isoformat() if isinstance(project.created, datetime) else str(project.created)
        data["modified"] = project.modified.isoformat() if isinstance(project.modified, datetime) else str(project.modified)
        data["last_opened"] = project.last_opened.isoformat() if isinstance(getattr(project, "last_opened", None), datetime) else str(getattr(project, "last_opened", datetime.now().isoformat()))

        project_file = Path(project.location) / "project.json"
        with open(project_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        try:
            self.project_updated.emit(project)
        except Exception:
            pass

    def open_project(self, project: Project):
        if not project:
            return
        project.last_opened = datetime.now()
        self.save_project(project)
        try:
            self.project_opened.emit(project)
        except Exception:
            pass

    def toggle_pin_project(self, project: Project):
        if not project:
            return
        project.is_pinned = not getattr(project, "is_pinned", False)
        self.save_project(project)

    def delete_project(self, project: Project):
        if not project:
            return
        loc = Path(project.location)
        if loc.exists() and loc.is_dir():
            shutil.rmtree(loc, ignore_errors=True)

        self.projects = [p for p in self.projects if Path(p.location) != loc]

        try:
            self.project_deleted.emit(project)
        except Exception:
            pass

    def set_snapshot(self, project: Project, snapshot_path: str):
        if not project or not getattr(project, "location", None):
            return
        shutil.copy2(
            snapshot_path,
            Path(project.location) / "snapshot.png",
        )
        self.save_project(project)

    def remove_snapshot(self, project: Project):
        if not project or not getattr(project, "location", None):
            return
        snapshot = Path(project.location) / "snapshot.png"
        if snapshot.exists():
            snapshot.unlink()
        self.save_project(project)

    def load_project(self, project_folder) -> Project | None:
        project_folder = Path(project_folder)
        project_file = project_folder / "project.json"

        if not project_file.exists():
            return None

        with open(project_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        created_dt = datetime.fromisoformat(data["created"]) if "created" in data and data["created"] else datetime.now()
        modified_dt = datetime.fromisoformat(data["modified"]) if "modified" in data and data["modified"] else created_dt
        last_opened_dt = datetime.fromisoformat(data["last_opened"]) if "last_opened" in data and data["last_opened"] else modified_dt

        project = Project(
            name=data.get("name", "Untitled"),
            project_type=data.get("project_type", "general"),
            location=data.get("location", str(project_folder)),
            description=data.get("description", ""),
            priority=data.get("priority", "medium"),
            status=data.get("status", "active"),
            tags=data.get("tags", []),
            client=data.get("client", ""),
            repository=data.get("repository", ""),
            deadline=data.get("deadline", ""),
            is_pinned=data.get("is_pinned", False),
            created=created_dt,
            modified=modified_dt,
            last_opened=last_opened_dt,
        )

        self.add_project(project)
        return project

    def add_project(self, project: Project):
        for p in self.projects:
            if Path(p.location) == Path(project.location):
                return
        self.projects.append(project)

    def clear(self):
        self.projects.clear()

    def all_projects(self):
        return self.projects