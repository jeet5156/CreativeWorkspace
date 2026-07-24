from PySide6.QtCore import Qt, Signal

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
)

from models.project import Project


class ExplorerPanel(QWidget):

    # Emits: (project, section)
    project_selected = Signal(Project, str)

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
        project_item.setData(0, Qt.UserRole + 1, "dashboard")

        self.projects_root.addChild(project_item)

        sections = [
            ("📝 Notes", "notes"),
            ("🖼 References", "references"),
            ("📦 Assets", "assets"),
            ("🎬 Renders", "renders"),
            ("📤 Exports", "exports"),
        ]

        for title, section in sections:
            child = QTreeWidgetItem([title])
            child.setData(0, Qt.UserRole, project)
            child.setData(0, Qt.UserRole + 1, section)
            project_item.addChild(child)

        project_item.setExpanded(True)

    def clear_projects(self):
        self.projects_root.takeChildren()

    def load_projects(self, projects):

        self.clear_projects()

        for project in projects:
            self.add_project(project)

        self.projects_root.setExpanded(True)

    def on_item_clicked(self, item, column):

        project = item.data(0, Qt.UserRole)
        section = item.data(0, Qt.UserRole + 1)

        if isinstance(project, Project):
            self.project_selected.emit(project, section)