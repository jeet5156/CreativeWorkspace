from models.project import Project
from datetime import datetime


class ProjectManager:

    def __init__(self):
        self.projects = []

    def create_project(self, name, location):

        project = Project(
            name=name,
            location=location,
            created=datetime.now(),
            modified=datetime.now()
        )

        self.projects.append(project)

        return project

    def all_projects(self):
        return self.projects