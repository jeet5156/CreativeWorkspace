from pathlib import Path
from dataclasses import asdict
from datetime import datetime
import json

from models.project import Project


class ProjectService:

    def __init__(self):
        self.projects: list[Project] = []

    def create_project(
        self,
        name: str,
        project_type: str,
        location: str,
        description: str,
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

        data = asdict(project)
        data["created"] = project.created.isoformat()

        with open(
            project_folder / "project.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(data, f, indent=4)

        self.add_project(project)

        return project

    def load_project(self, project_folder):

        project_folder = Path(project_folder)
        project_file = project_folder / "project.json"

        if not project_file.exists():
            return None

        with open(project_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        project = Project(
            name=data["name"],
            project_type=data["project_type"],
            location=data["location"],
            description=data.get("description", ""),
            created=datetime.fromisoformat(data["created"]),
        )

        self.add_project(project)

        return project

    def add_project(self, project):

        for p in self.projects:
            if (
                Path(p.location) == Path(project.location)
            ):
                return

        self.projects.append(project)

    def clear(self):
        self.projects.clear()

    def all_projects(self):
        return self.projects