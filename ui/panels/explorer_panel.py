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

        self.projects_root = QTreeWidgetItem(["📁 Projects"])
        self.tree.addTopLevelItem(self.projects_root)

        self.projects_root.setExpanded(True)

        self.tree.itemClicked.connect(self.on_item_clicked)

    def add_project(self, project: Project):

        project_item = QTreeWidgetItem([f"📁 {project.name}"])
        project_item.setData(0, Qt.UserRole, project)

        self.projects_root.addChild(project_item)

        folders = [
            "📝 Notes",
            "🖼 References",
            "📦 Assets",
            "🎬 Renders",
            "📤 Exports",
        ]

        for folder in folders:
            child = QTreeWidgetItem([folder])
            project_item.addChild(child)

        project_item.setExpanded(True)

    def clear_projects(self):
        self.projects_root.takeChildren()

    def load_projects(self, projects: list[Project]):

        self.clear_projects()

        for project in projects:
            self.add_project(project)

        self.projects_root.setExpanded(True)

    def on_item_clicked(self, item, column):

        project = item.data(0, Qt.UserRole)

        if isinstance(project, Project):
            self.project_selected.emit(project)