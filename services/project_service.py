class ProjectService:
    """
    Handles all project operations.
    """

    def __init__(self):
        self.projects = []

    def add_project(self, project):
        self.projects.append(project)

    def all_projects(self):
        return self.projects