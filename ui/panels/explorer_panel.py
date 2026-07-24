from PySide6.QtCore import Qt, Signal

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
)

from models.project import Project


class ExplorerPanel(QWidget):

    project_selected = Signal(Project)

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)

        layout.addWidget(self.tree)

        self.projects_root = QTreeWidgetItem(["Projects"])
        self.tree.addTopLevelItem(self.projects_root)

        self.tree.itemClicked.connect(self.on_item_clicked)
        print("Explorer initialized")
        self.projects_root.setExpanded(True)

    def add_project(self, project: Project):

        item = QTreeWidgetItem([project.name])

        item.setData(0, Qt.UserRole, project)

        self.projects_root.addChild(item)

        self.projects_root.setExpanded(True)

    def clear_projects(self):

        self.projects_root.takeChildren()

    def load_projects(self, projects: list[Project]):

        self.clear_projects()

        for project in projects:
            self.add_project(project)

    def on_item_clicked(self, item, column):

        project = item.data(0, Qt.UserRole)

        if isinstance(project, Project):
            self.project_selected.emit(project)