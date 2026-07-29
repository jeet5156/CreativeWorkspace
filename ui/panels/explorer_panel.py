from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction

from PySide6.QtWidgets import (
    QMenu,
    QWidget,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
)

from models.project import Project


class ExplorerPanel(QWidget):

    # Emits: (project, section)
    project_selected = Signal(Project, str)
    set_snapshot_requested = Signal(Project)
    remove_snapshot_requested = Signal(Project)
    # Emits: (project, section, [paths]) when files/folders are dropped
    files_dropped = Signal(Project, str, object)

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.on_context_menu)

        layout.addWidget(self.tree)

        self._context_menu_project = None
        self._create_context_menu_actions()

        self.projects_root = QTreeWidgetItem(["📁 Projects"])
        self.tree.addTopLevelItem(self.projects_root)
        self.projects_root.setExpanded(True)

        self.tree.itemClicked.connect(self.on_item_clicked)

        # Enable drag & drop
        self.setAcceptDrops(True)

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

    def _create_context_menu_actions(self):

        self.set_snapshot_action = QAction("Set Snapshot", self)
        self.set_snapshot_action.triggered.connect(
            self._request_set_snapshot
        )

        self.remove_snapshot_action = QAction("Remove Snapshot", self)
        self.remove_snapshot_action.triggered.connect(
            self._request_remove_snapshot
        )

    def on_context_menu(self, position):

        item = self.tree.itemAt(position)
        project = item.data(0, Qt.UserRole) if item else None

        if not isinstance(project, Project):
            return

        self._context_menu_project = project

        menu = QMenu(self)
        menu.addAction(self.set_snapshot_action)
        menu.addAction(self.remove_snapshot_action)
        menu.exec(self.tree.viewport().mapToGlobal(position))

        self._context_menu_project = None

    def _request_set_snapshot(self):

        if self._context_menu_project is not None:
            self.set_snapshot_requested.emit(self._context_menu_project)

    def _request_remove_snapshot(self):

        if self._context_menu_project is not None:
            self.remove_snapshot_requested.emit(self._context_menu_project)

    # ---------------------
    # Drag & Drop
    # ---------------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        # Gather local file paths
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]

        if not paths:
            event.ignore()
            return

        # Determine drop target (project + section)
        try:
            tree_pos = self.tree.viewport().mapFrom(self, event.pos().toPoint())
        except Exception:
            tree_pos = self.tree.viewport().mapFrom(self, event.pos())

        item = self.tree.itemAt(tree_pos)

        project = item.data(0, Qt.UserRole) if item else None
        section = item.data(0, Qt.UserRole + 1) if item else None

        # Default to assets if no specific section
        if section not in ("assets", "references", "notes", "renders", "exports"):
            section = "assets"

        # Emit to application to let services handle business logic
        self.files_dropped.emit(project, section, paths)

        event.acceptProposedAction()

    # ---------------------
    def on_item_clicked(self, item, column):

        project = item.data(0, Qt.UserRole)
        section = item.data(0, Qt.UserRole + 1)

        if isinstance(project, Project):
            self.project_selected.emit(project, section)