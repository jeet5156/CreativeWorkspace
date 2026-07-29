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
    # Navigation signal for top-level modules: emits a string key such as 'home', 'clients', 'assets_lib', 'knowledge', 'business'
    navigation_requested = Signal(str)
    set_snapshot_requested = Signal(Project)
    remove_snapshot_requested = Signal(Project)
    # Emits: (project, section, [paths]) when files/folders are dropped
    files_dropped = Signal(Project, str, object)

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        # Search box (global explorer search)
        from PySide6.QtWidgets import QLineEdit, QListWidget, QListWidgetItem
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search projects, assets, references...")
        layout.addWidget(self.search_edit)

        self.search_results = QListWidget()
        self.search_results.setVisible(False)
        layout.addWidget(self.search_results)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.on_context_menu)

        layout.addWidget(self.tree)

        self._context_menu_project = None
        self._create_context_menu_actions()

        # services set later via set_search_services
        self._find_service = None
        self._navigation_service = None
        self._app_state = None

        # wire search interactions
        try:
            self.search_edit.textChanged.connect(self._on_search_text_changed)
            self.search_results.itemDoubleClicked.connect(self._on_search_item_activated)
            self.search_results.itemClicked.connect(self._on_search_item_clicked)
        except Exception:
            pass

        # keyboard handling
        try:
            self.search_edit.installEventFilter(self)
            self.search_results.installEventFilter(self)
        except Exception:
            pass

        # Top-level entries
        self.home_root = QTreeWidgetItem(["🏠 Home"])
        self.home_root.setData(0, Qt.UserRole + 1, "home")
        self.tree.addTopLevelItem(self.home_root)

        self.projects_root = QTreeWidgetItem(["📁 Projects"])
        self.projects_root.setData(0, Qt.UserRole + 1, "projects")
        self.tree.addTopLevelItem(self.projects_root)
        self.projects_root.setExpanded(True)

        # Other app modules
        self.clients_root = QTreeWidgetItem(["👥 Clients"])
        self.clients_root.setData(0, Qt.UserRole + 1, "clients")
        self.tree.addTopLevelItem(self.clients_root)

        self.assets_root = QTreeWidgetItem(["📚 Asset Library"])
        self.assets_root.setData(0, Qt.UserRole + 1, "assets_lib")
        self.tree.addTopLevelItem(self.assets_root)

        self.knowledge_root = QTreeWidgetItem(["📖 Knowledge"])
        self.knowledge_root.setData(0, Qt.UserRole + 1, "knowledge")
        self.tree.addTopLevelItem(self.knowledge_root)

        self.business_root = QTreeWidgetItem(["💼 Business"])
        self.business_root.setData(0, Qt.UserRole + 1, "business")
        self.tree.addTopLevelItem(self.business_root)

        self.tree.itemClicked.connect(self.on_item_clicked)

        # expose navigation_requested when clicking top-level nodes

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

    def reveal_project(self, project, section: str = "dashboard", emit: bool = True):
        """Programmatically select and reveal a project in the tree.
        If emit is True (default), emits project_selected(project, section) so app reacts as if clicked.
        """
        # Find matching project item under projects_root
        for i in range(self.projects_root.childCount()):
            item = self.projects_root.child(i)
            p = item.data(0, Qt.UserRole)
            try:
                if p and str(p.location) == str(project.location):
                    # select and ensure visible
                    self.tree.setCurrentItem(item)
                    item.setExpanded(True)
                    # hide search results when revealing
                    try:
                        self.search_results.setVisible(False)
                    except Exception:
                        pass
                    # emit selection with given section
                    if emit:
                        try:
                            self.project_selected.emit(project, section)
                        except Exception:
                            pass
                    return
            except Exception:
                continue

    # ---------------------
    # Search integration
    # ---------------------
    def set_search_services(self, find_service, navigation_service, app_state):
        self._find_service = find_service
        self._navigation_service = navigation_service
        self._app_state = app_state

    def _on_search_text_changed(self, text: str):
        q = (text or "").strip()
        if not q:
            self.search_results.clear()
            self.search_results.setVisible(False)
            return
        if not self._find_service:
            return
        res = self._find_service.search(q)

        # prioritize current project results
        current = None
        try:
            if self._app_state:
                current = self._app_state.current_project
        except Exception:
            current = None

        self._render_search_results(res, current)

    def _render_search_results(self, res: dict, current_project):
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtCore import Qt
        self.search_results.clear()

        def add_label(text):
            it = QListWidgetItem(text)
            it.setFlags(Qt.NoItemFlags)
            self.search_results.addItem(it)

        # Projects (current project first)
        projects = res.get('projects', [])
        if projects:
            add_label('Projects')
            # move current project to top
            ordered = []
            for p in projects:
                if current_project and getattr(p.get('project'), 'location', None) == getattr(current_project, 'location', None):
                    ordered.insert(0, p)
                else:
                    ordered.append(p)
            for p in ordered:
                it = QListWidgetItem(p.get('label'))
                it.setData(Qt.UserRole, p)
                self.search_results.addItem(it)

        # Assets
        assets = res.get('assets', [])
        if assets:
            add_label('Assets')
            ordered = []
            for a in assets:
                if current_project and getattr(a.get('project'), 'location', None) == getattr(current_project, 'location', None):
                    ordered.insert(0, a)
                else:
                    ordered.append(a)
            for a in ordered:
                it = QListWidgetItem(a.get('label'))
                it.setData(Qt.UserRole, a)
                self.search_results.addItem(it)

        # References
        refs = res.get('references', [])
        if refs:
            add_label('References')
            ordered = []
            for r in refs:
                if current_project and getattr(r.get('project'), 'location', None) == getattr(current_project, 'location', None):
                    ordered.insert(0, r)
                else:
                    ordered.append(r)
            for r in ordered:
                it = QListWidgetItem(r.get('label'))
                it.setData(Qt.UserRole, r)
                self.search_results.addItem(it)

        self.search_results.setVisible(self.search_results.count() > 0)

    def _on_search_item_clicked(self, item):
        try:
            data = item.data(Qt.UserRole)
        except Exception:
            data = None
        if not data:
            return
        if not self._navigation_service:
            return
        try:
            self._navigation_service.navigate_search_result(data)
        except Exception:
            pass

    def _on_search_item_activated(self, item):
        try:
            data = item.data(Qt.UserRole)
        except Exception:
            data = None
        if not data:
            return
        if not self._navigation_service:
            return
        try:
            self._navigation_service.navigate_search_result(data)
        except Exception:
            pass
        # hide results after navigation
        try:
            self.search_results.setVisible(False)
        except Exception:
            pass

    def eventFilter(self, source, event):
        try:
            from PySide6.QtCore import QEvent, Qt
            if source == self.search_edit and event.type() == QEvent.KeyPress:
                key = event.key()
                if key == Qt.Key_Down:
                    if self.search_results.count() > 0:
                        self.search_results.setCurrentRow(max(0, self.search_results.currentRow() + 1))
                        self.search_results.setFocus()
                        return True
                if key == Qt.Key_Return or key == Qt.Key_Enter:
                    # activate current selection or first
                    row = self.search_results.currentRow()
                    if row < 0 and self.search_results.count() > 0:
                        row = 0
                    if row >= 0:
                        item = self.search_results.item(row)
                        if item:
                            self._on_search_item_activated(item)
                            return True
                if key == Qt.Key_Escape:
                    # clear search and hide results
                    self.search_edit.clear()
                    self.search_results.clear()
                    self.search_results.setVisible(False)
                    self.search_edit.clearFocus()
                    return True
            if source == self.search_results and event.type() == QEvent.KeyPress:
                key = event.key()
                if key == Qt.Key_Return or key == Qt.Key_Enter:
                    row = self.search_results.currentRow()
                    if row >= 0:
                        item = self.search_results.item(row)
                        if item:
                            self._on_search_item_activated(item)
                            return True
                if key == Qt.Key_Escape:
                    self.search_edit.clear()
                    self.search_results.clear()
                    self.search_results.setVisible(False)
                    self.search_edit.setFocus()
                    return True
            # allow other events
        except Exception:
            pass
        return super().eventFilter(source, event)

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
            return

        # If the clicked entry is a top-level navigation (home, clients, assets_lib, knowledge, business),
        # emit navigation_requested so the main app can handle module switching.
        if section in ("home", "projects", "clients", "assets_lib", "knowledge", "business"):
            try:
                self.navigation_requested.emit(section)
            except Exception:
                pass