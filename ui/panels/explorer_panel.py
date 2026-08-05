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
from pathlib import Path


# Named roles for QTreeWidgetItems to avoid magic numbers
ROLE_PROJECT = Qt.UserRole
ROLE_SECTION = Qt.UserRole + 1
ROLE_REL_PATH = Qt.UserRole + 2
ROLE_NODE_TYPE = Qt.UserRole + 3


class ExplorerPanel(QWidget):

    # Emits: (project, section, rel_path)
    project_selected = Signal(Project, str, object)
    # Navigation signal for top-level modules: emits a string key such as 'home', 'clients', 'assets_lib', 'knowledge', 'business'
    navigation_requested = Signal(str)
    set_snapshot_requested = Signal(Project)
    remove_snapshot_requested = Signal(Project)
    # Emits: (project, section, [paths]) when files/folders are dropped from OS
    files_dropped = Signal(Project, str, object)
    # Emits: (project, mime_data, target_rel_path) when internal assets are dropped onto a category or folder node
    internal_assets_dropped = Signal(object, object, str)

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
        self.tree.itemClicked.connect(self._on_tree_item_clicked)
        self.tree.itemExpanded.connect(self._on_tree_item_expanded)

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
        self.lab_root = QTreeWidgetItem(["🧪 Lab"])
        self.lab_root.setData(0, Qt.UserRole + 1, "lab")
        self.tree.addTopLevelItem(self.lab_root)

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
        self.tree.itemExpanded.connect(self._on_item_expanded)
        self.tree.itemCollapsed.connect(self._on_item_collapsed)

        # expose navigation_requested when clicking top-level nodes

        # Enable drag & drop
        self.setAcceptDrops(True)
        self._project_items = {}

    def set_context(self, context):
        """Provide AppContext to Explorer so it can perform folder operations."""
        try:
            self._context = context
            if context and getattr(context, 'asset_service', None):
                if not getattr(self, '_assets_changed_connected', False):
                    try:
                        context.asset_service.assets_changed.connect(self._on_assets_changed)
                        self._assets_changed_connected = True
                    except Exception:
                        pass
            if context and getattr(context, 'project_service', None):
                if not getattr(self, '_project_updated_connected', False):
                    try:
                        context.project_service.project_updated.connect(self._on_project_updated)
                        self._project_updated_connected = True
                    except Exception:
                        pass
        except Exception:
            self._context = None

    def _on_project_updated(self, project):
        if not project or not hasattr(self, '_project_cards'):
            return
        loc_str = str(getattr(project, 'location', ''))
        if loc_str in self._project_cards:
            try:
                card = self._project_cards[loc_str]
                card.update_project(project)
            except Exception:
                pass

    def _get_folder_service(self):
        context = getattr(self, "_context", None)
        return getattr(context, "folder_service", None) if context else None

    def add_project(self, project: Project):

        project_item = QTreeWidgetItem([""])
        project_item.setData(0, ROLE_PROJECT, project)
        project_item.setData(0, ROLE_SECTION, "dashboard")
        project_item.setData(0, ROLE_NODE_TYPE, "project")

        self.projects_root.addChild(project_item)
        if hasattr(project, 'location') and project.location:
            self._project_items[str(project.location)] = project_item

        # Attach custom ProjectTreeCard widget
        try:
            from ui.widgets.project_tree_card import ProjectTreeCard
            card = ProjectTreeCard(project)
            card.clicked.connect(lambda p, item=project_item: self._on_project_card_clicked(item, p))
            self.tree.setItemWidget(project_item, 0, card)
            project_item.setSizeHint(0, card.sizeHint())
            if not hasattr(self, '_project_cards'):
                self._project_cards = {}
            self._project_cards[str(project.location)] = card
        except Exception:
            pass

        sections = [
            ("📝 Notes", "notes"),
            ("🖼 References", "references"),
            ("📦 Assets", "assets"),
            ("🎬 Renders", "renders"),
            ("📤 Exports", "exports"),
        ]

        folder_service = self._get_folder_service()

        for title, section in sections:
            child = QTreeWidgetItem([title])
            child.setData(0, ROLE_PROJECT, project)
            child.setData(0, ROLE_SECTION, section)
            
            # Map section to top-level folder name
            top_folder = section.capitalize() if section != "assets" else "Assets"
            child.setData(0, ROLE_REL_PATH, top_folder)
            child.setData(0, ROLE_NODE_TYPE, "category")
            
            # Show expansion indicator if folder service confirms subfolders exist
            has_subfolders = False
            if folder_service:
                try:
                    has_subfolders = bool(folder_service.list_subfolders(project, top_folder))
                except Exception:
                    has_subfolders = False
            
            if has_subfolders:
                child.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
            else:
                child.setChildIndicatorPolicy(QTreeWidgetItem.DontShowIndicator)
            
            project_item.addChild(child)

        project_item.setExpanded(True)

    def clear_projects(self):
        self.projects_root.takeChildren()
        if hasattr(self, '_project_items'):
            self._project_items.clear()
        if hasattr(self, '_project_cards'):
            self._project_cards.clear()

    def _on_project_card_clicked(self, item: QTreeWidgetItem, project: Project):
        try:
            self.tree.setCurrentItem(item)
            self.on_item_clicked(item, 0)
        except Exception:
            pass

    def _update_project_card_selection(self, selected_project):
        if not hasattr(self, '_project_cards'):
            return
        selected_loc = str(getattr(selected_project, 'location', '')) if selected_project else ''
        for loc, card in self._project_cards.items():
            try:
                card.set_selected(loc == selected_loc)
            except Exception:
                pass

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int = 0):
        if not item:
            return
        mod_key = item.data(0, Qt.UserRole + 1)
        if mod_key in ("home", "projects", "lab", "clients", "assets_lib", "knowledge", "business"):
            try:
                self.navigation_requested.emit(mod_key)
            except Exception:
                pass
            return

        project = item.data(0, ROLE_PROJECT)
        section = item.data(0, ROLE_SECTION) or "dashboard"
        rel_path = item.data(0, ROLE_REL_PATH)

        if project:
            try:
                self.project_selected.emit(project, section, rel_path)
            except Exception:
                pass

    def _on_tree_item_expanded(self, item: QTreeWidgetItem):
        self._on_item_expanded(item)

    def _on_item_expanded(self, item: QTreeWidgetItem):
        """Lazy load subfolders on category/folder expansion, and expand metadata on project header."""
        node_type = item.data(0, ROLE_NODE_TYPE)
        if node_type == "project":
            # Collapse only other top-level project nodes
            if hasattr(self, 'projects_root') and self.projects_root:
                for i in range(self.projects_root.childCount()):
                    other_item = self.projects_root.child(i)
                    if other_item != item and other_item.isExpanded():
                        other_item.setExpanded(False)

            project = item.data(0, ROLE_PROJECT)
            loc_str = str(getattr(project, 'location', '')) if project else ''
            if hasattr(self, '_project_cards') and loc_str in self._project_cards:
                try:
                    card = self._project_cards[loc_str]
                    card.set_expanded(True)
                    item.setSizeHint(0, card.sizeHint())
                except Exception:
                    pass
            return

        if node_type not in ("category", "folder"):
            return

        project = item.data(0, ROLE_PROJECT)
        rel_path = item.data(0, ROLE_REL_PATH)
        section = item.data(0, ROLE_SECTION)

        if not project or not rel_path:
            return

        folder_service = self._get_folder_service()
        if not folder_service:
            return

        # Fetch fresh subfolders from service
        subfolders = folder_service.list_subfolders(project, rel_path)
        
        # Update parent indicator policy based on whether subfolders exist
        if subfolders:
            item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
        else:
            item.setChildIndicatorPolicy(QTreeWidgetItem.DontShowIndicator)

        # Clear existing children to rebuild only this expanded node
        item.takeChildren()

        for folder_name in subfolders:
            folder_rel_path = str(Path(rel_path) / folder_name).replace("\\", "/")
            
            child = QTreeWidgetItem([f"📁 {folder_name}"])
            child.setData(0, ROLE_PROJECT, project)
            child.setData(0, ROLE_SECTION, section)
            child.setData(0, ROLE_REL_PATH, folder_rel_path)
            child.setData(0, ROLE_NODE_TYPE, "folder")
            
            # Show expansion indicator for child folder if it contains subfolders
            child_has_subfolders = bool(folder_service.list_subfolders(project, folder_rel_path))
            if child_has_subfolders:
                child.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
            else:
                child.setChildIndicatorPolicy(QTreeWidgetItem.DontShowIndicator)

            item.addChild(child)

    def _on_item_collapsed(self, item: QTreeWidgetItem):
        """Collapse metadata on project header when project tree node is collapsed."""
        node_type = item.data(0, ROLE_NODE_TYPE)
        if node_type == "project":
            project = item.data(0, ROLE_PROJECT)
            loc_str = str(getattr(project, 'location', '')) if project else ''
            if hasattr(self, '_project_cards') and loc_str in self._project_cards:
                try:
                    card = self._project_cards[loc_str]
                    card.set_expanded(False)
                    item.setSizeHint(0, card.sizeHint())
                except Exception:
                    pass

    def _on_assets_changed(self, project, category=None):
        if not project or not hasattr(self, '_project_items'):
            return
        loc_str = str(getattr(project, 'location', ''))
        proj_item = self._project_items.get(loc_str)
        if not proj_item or not proj_item.isExpanded():
            return

        for i in range(proj_item.childCount()):
            cat_item = proj_item.child(i)
            if cat_item.isExpanded():
                self._refresh_expanded_node(cat_item)

    def _find_node_by_rel_path(self, parent_item: QTreeWidgetItem, target_rel_path: str) -> QTreeWidgetItem | None:
        if not parent_item or not target_rel_path:
            return None
        norm_target = target_rel_path.replace('\\', '/').strip('/')
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            rp = child.data(0, ROLE_REL_PATH)
            if rp and rp.replace('\\', '/').strip('/') == norm_target:
                return child
            sub = self._find_node_by_rel_path(child, target_rel_path)
            if sub:
                return sub
        return None

    def _ensure_path_expanded(self, proj_item: QTreeWidgetItem, rel_path: str):
        if not rel_path:
            return
        parts = rel_path.replace('\\', '/').strip('/').split('/')
        current_parent = proj_item
        accumulated = ""
        for part in parts:
            accumulated = f"{accumulated}/{part}" if accumulated else part
            self._on_item_expanded(current_parent)
            current_parent.setExpanded(True)
            found = None
            for i in range(current_parent.childCount()):
                child = current_parent.child(i)
                rp = child.data(0, ROLE_REL_PATH)
                if rp and rp.replace('\\', '/').strip('/') == accumulated.replace('\\', '/').strip('/'):
                    found = child
                    break
            if found:
                current_parent = found
            else:
                break

    def _refresh_expanded_node(self, item: QTreeWidgetItem):
        if not item:
            return

        expanded_paths = set()
        for i in range(item.childCount()):
            child = item.child(i)
            if child.isExpanded():
                rp = child.data(0, ROLE_REL_PATH)
                if rp:
                    expanded_paths.add(rp)

        current_item = self.tree.currentItem()
        current_rp = current_item.data(0, ROLE_REL_PATH) if current_item else None

        self._on_item_expanded(item)

        for i in range(item.childCount()):
            child = item.child(i)
            rp = child.data(0, ROLE_REL_PATH)
            if rp and rp in expanded_paths:
                child.setExpanded(True)
                self._refresh_expanded_node(child)

        if current_rp:
            matched = self._find_node_by_rel_path(item, current_rp)
            if matched:
                try:
                    self.tree.setCurrentItem(matched)
                except Exception:
                    pass

    def load_projects(self, projects):

        self.clear_projects()

        for project in projects:
            self.add_project(project)

        self.projects_root.setExpanded(True)

    def reveal_project(self, project, section: str = "dashboard", rel_path: str = None, emit: bool = True):
        """Programmatically select and reveal a project or specific subfolder in the tree.
        If rel_path is supplied, recursively locates matching node by ROLE_REL_PATH and selects it.
        If emit is True (default), emits project_selected(project, section, rel_path).
        """
        for i in range(self.projects_root.childCount()):
            proj_item = self.projects_root.child(i)
            p = proj_item.data(0, Qt.UserRole)
            try:
                if p and str(p.location) == str(project.location):
                    proj_item.setExpanded(True)
                    target_node = None

                    if rel_path:
                        self._ensure_path_expanded(proj_item, rel_path)
                        target_node = self._find_node_by_rel_path(proj_item, rel_path)

                    if target_node:
                        curr = target_node.parent()
                        while curr:
                            curr.setExpanded(True)
                            curr = curr.parent()
                        self.tree.setCurrentItem(target_node)
                    else:
                        self.tree.setCurrentItem(proj_item)

                    self._update_project_card_selection(project)

                    try:
                        self.search_results.setVisible(False)
                    except Exception:
                        pass

                    if emit:
                        try:
                            self.project_selected.emit(project, section, rel_path if target_node else None)
                        except Exception:
                            pass
                    return
            except Exception:
                continue

    def get_expansion_state(self) -> dict:
        """Return a serializable expansion state for explorer tree.
        Includes top-level node expansion and which project nodes are expanded.
        """
        state = {
            'home_expanded': bool(self.home_root.isExpanded()),
            'projects_expanded': bool(self.projects_root.isExpanded()),
            'clients_expanded': bool(self.clients_root.isExpanded()),
            'assets_lib_expanded': bool(self.assets_root.isExpanded()),
            'knowledge_expanded': bool(self.knowledge_root.isExpanded()),
            'business_expanded': bool(self.business_root.isExpanded()),
            'projects': []
        }
        try:
            for i in range(self.projects_root.childCount()):
                item = self.projects_root.child(i)
                p = item.data(0, Qt.UserRole)
                if p and item.isExpanded():
                    try:
                        state['projects'].append(str(p.location))
                    except Exception:
                        continue
        except Exception:
            pass
        return state

    def set_expansion_state(self, state: dict):
        if not state:
            return
        try:
            try:
                self.home_root.setExpanded(bool(state.get('home_expanded', False)))
                self.projects_root.setExpanded(bool(state.get('projects_expanded', True)))
                self.clients_root.setExpanded(bool(state.get('clients_expanded', False)))
                self.assets_root.setExpanded(bool(state.get('assets_lib_expanded', False)))
                self.knowledge_root.setExpanded(bool(state.get('knowledge_expanded', False)))
                self.business_root.setExpanded(bool(state.get('business_expanded', False)))
            except Exception:
                pass

            projects_expanded = set(state.get('projects', []) or [])
            for i in range(self.projects_root.childCount()):
                item = self.projects_root.child(i)
                p = item.data(0, Qt.UserRole)
                try:
                    if p and str(p.location) in projects_expanded:
                        item.setExpanded(True)
                    else:
                        item.setExpanded(False)
                except Exception:
                    pass
        except Exception:
            pass

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
        self.open_project_action = QAction("Open", self)
        self.open_project_action.triggered.connect(self._request_open_project)

        self.rename_project_action = QAction("Rename", self)
        self.rename_project_action.triggered.connect(self._request_rename_project)

        self.set_snapshot_action = QAction("Set Snapshot...", self)
        self.set_snapshot_action.triggered.connect(self._request_set_snapshot)

        self.remove_snapshot_action = QAction("Remove Snapshot", self)
        self.remove_snapshot_action.triggered.connect(self._request_remove_snapshot)

        self.delete_project_action = QAction("Delete", self)
        self.delete_project_action.triggered.connect(self._request_delete_project)

        # Folder actions
        self.new_folder_action = QAction("New Folder...", self)
        self.new_folder_action.triggered.connect(self._request_new_folder)

        self.rename_folder_action = QAction("Rename Folder...", self)
        self.rename_folder_action.triggered.connect(self._request_rename_folder)

        self.delete_folder_action = QAction("Delete Folder...", self)
        self.delete_folder_action.triggered.connect(self._request_delete_folder)

    def _get_active_context_item(self) -> QTreeWidgetItem | None:
        return getattr(self, '_context_menu_item', None) or self.tree.currentItem()

    def on_context_menu(self, position):
        item = self.tree.itemAt(position)
        project = item.data(0, Qt.UserRole) if item else None
        section = item.data(0, Qt.UserRole + 1) if item else None
        node_type = item.data(0, ROLE_NODE_TYPE) if item else None

        if not isinstance(project, Project):
            return

        self._context_menu_project = project
        self._context_menu_item = item

        menu = QMenu(self)

        if node_type == "project":
            menu.addAction(self.open_project_action)
            menu.addAction(self.rename_project_action)
            menu.addSeparator()
            menu.addAction(self.set_snapshot_action)
            menu.addAction(self.remove_snapshot_action)
            menu.addSeparator()
            menu.addAction(self.delete_project_action)
        else:
            # Section / Folder item actions
            menu.addAction(self.set_snapshot_action)
            menu.addAction(self.remove_snapshot_action)
            if section in ("assets", "references", "notes", "renders", "exports"):
                menu.addSeparator()
                menu.addAction(self.new_folder_action)
                if node_type == "folder":
                    menu.addAction(self.rename_folder_action)
                menu.addAction(self.delete_folder_action)

        menu.exec(self.tree.viewport().mapToGlobal(position))

        self._context_menu_project = None
        self._context_menu_item = None

    def _request_open_project(self):
        if self._context_menu_project is not None:
            self.reveal_project(self._context_menu_project, section="dashboard")

    def _request_rename_project(self):
        if self._context_menu_project is None:
            return
        try:
            from PySide6.QtWidgets import QInputDialog
            p = self._context_menu_project
            new_name, ok = QInputDialog.getText(self, "Rename Project", f"New name for '{p.name}':", text=p.name)
            if ok and new_name and new_name != p.name:
                p.name = new_name
                if getattr(self, '_context', None) and getattr(self._context, 'project_service', None):
                    self._context.project_service.save_project(p)
                if hasattr(self, '_project_cards') and str(p.location) in self._project_cards:
                    self._project_cards[str(p.location)].update_project(p)
                self.project_selected.emit(p, "dashboard", None)
        except Exception:
            pass

    def _request_delete_project(self):
        if self._context_menu_project is None:
            return
        try:
            from PySide6.QtWidgets import QMessageBox
            p = self._context_menu_project
            confirm = QMessageBox.question(
                self,
                "Delete Project",
                f"Are you sure you want to delete project '{p.name}'?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if confirm == QMessageBox.Yes and getattr(self, '_context', None) and getattr(self._context, 'project_service', None):
                self._context.project_service.delete_project(p)
                self.clear_projects()
                projects = self._context.project_service.list_projects()
                self.load_projects(projects)
        except Exception:
            pass

    def _request_set_snapshot(self):

        if self._context_menu_project is not None:
            self.set_snapshot_requested.emit(self._context_menu_project)

    def _request_remove_snapshot(self):

        if self._context_menu_project is not None:
            self.remove_snapshot_requested.emit(self._context_menu_project)

    def _request_new_folder(self):
        # Show dialog to get folder name and delegate to FolderService via context if available
        if self._context_menu_project is None:
            return
        try:
            from PySide6.QtWidgets import QInputDialog
            item = self._get_active_context_item()
            section = item.data(0, ROLE_SECTION) if item else None
            if section not in ("assets", "references", "notes", "renders", "exports"):
                return
            ok = False
            name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
            if not ok or not name:
                return
            # Map section key to top-level folder name used by AssetService
            top = section.capitalize() if section != 'assets' else 'Assets'
            rel_path = item.data(0, ROLE_REL_PATH) if item else None
            parent_rel = rel_path if rel_path else top
            if getattr(self, '_context', None) and getattr(self._context, 'folder_service', None):
                try:
                    self._context.folder_service.create_folder(self._context_menu_project, parent_rel, name)
                except Exception:
                    pass
        except Exception:
            pass

    def _request_rename_folder(self):
        if self._context_menu_project is None:
            return
        try:
            from PySide6.QtWidgets import QInputDialog, QMessageBox
            item = self._get_active_context_item()
            if not item:
                return
            node_type = item.data(0, ROLE_NODE_TYPE)
            old_rel_path = item.data(0, ROLE_REL_PATH)
            section = item.data(0, ROLE_SECTION)
            if node_type != "folder" or not old_rel_path:
                return

            old_name = Path(old_rel_path).name
            new_name, ok = QInputDialog.getText(self, "Rename Folder", f"New name for '{old_name}':", text=old_name)
            if not ok or not new_name or new_name == old_name:
                return

            folder_service = self._get_folder_service()
            if folder_service:
                res = folder_service.rename_folder(self._context_menu_project, old_rel_path, new_name)
                if res:
                    new_rel_path = str(Path(old_rel_path).parent / new_name).replace('\\', '/')
                    try:
                        self.reveal_project(self._context_menu_project, section, rel_path=new_rel_path, emit=True)
                    except Exception:
                        pass
                else:
                    QMessageBox.warning(self, "Rename Folder", f"Unable to rename folder '{old_name}'.")
        except Exception:
            pass

    def _request_delete_folder(self):
        # Prompt user for which folder (simple prompt) and delete via FolderService
        if self._context_menu_project is None:
            return
        try:
            from PySide6.QtWidgets import QInputDialog, QMessageBox
            item = self._get_active_context_item()
            section = item.data(0, ROLE_SECTION) if item else None
            if section not in ("assets", "references", "notes", "renders", "exports"):
                return
            top = section.capitalize() if section != 'assets' else 'Assets'
            rel_path = item.data(0, ROLE_REL_PATH) if item else None
            node_type = item.data(0, ROLE_NODE_TYPE) if item else None

            if node_type == "folder" and rel_path:
                target_delete_rel = rel_path
            else:
                folder, ok = QInputDialog.getText(self, "Delete Folder", f"Folder path to delete (relative to {top}):")
                if not ok or not folder:
                    return
                target_delete_rel = str(Path(top) / folder)

            if getattr(self, '_context', None) and getattr(self._context, 'folder_service', None):
                confirm = QMessageBox.question(self, "Confirm Delete", f"Delete folder '{target_delete_rel}' and all its contents?", QMessageBox.Yes | QMessageBox.No)
                if confirm != QMessageBox.Yes:
                    return
                try:
                    self._context.folder_service.delete_folder(self._context_menu_project, target_delete_rel)
                except Exception:
                    pass
        except Exception:
            pass

    # ---------------------
    # Drag & Drop
    # ---------------------
    def dragEnterEvent(self, event):
        try:
            from services.asset_operations_service import MIME_ASSETS
            mime = event.mimeData()
            if mime.hasFormat(MIME_ASSETS) or mime.hasUrls():
                event.acceptProposedAction()
            else:
                event.ignore()
        except Exception:
            event.ignore()

    def dragMoveEvent(self, event):
        try:
            from services.asset_operations_service import MIME_ASSETS
            mime = event.mimeData()
            if mime.hasFormat(MIME_ASSETS):
                try:
                    tree_pos = self.tree.viewport().mapFrom(self, event.pos().toPoint())
                except Exception:
                    tree_pos = self.tree.viewport().mapFrom(self, event.pos())

                item = self.tree.itemAt(tree_pos)
                if item:
                    node_type = item.data(0, ROLE_NODE_TYPE)
                    rel_path = item.data(0, ROLE_REL_PATH)
                    project = item.data(0, ROLE_PROJECT)
                    if node_type in ("category", "folder") and rel_path and project:
                        event.acceptProposedAction()
                        return
                event.ignore()
            elif mime.hasUrls():
                event.acceptProposedAction()
            else:
                event.ignore()
        except Exception:
            event.ignore()

    def dropEvent(self, event):
        try:
            from services.asset_operations_service import MIME_ASSETS
            mime = event.mimeData()

            # Internal asset drop from Asset Workspace
            if mime.hasFormat(MIME_ASSETS):
                try:
                    tree_pos = self.tree.viewport().mapFrom(self, event.pos().toPoint())
                except Exception:
                    tree_pos = self.tree.viewport().mapFrom(self, event.pos())

                item = self.tree.itemAt(tree_pos)
                if not item:
                    event.ignore()
                    return

                node_type = item.data(0, ROLE_NODE_TYPE)
                rel_path = item.data(0, ROLE_REL_PATH)
                project = item.data(0, ROLE_PROJECT)

                if node_type in ("category", "folder") and rel_path and project:
                    event.acceptProposedAction()
                    self.internal_assets_dropped.emit(project, mime, rel_path)
                else:
                    event.ignore()
                return

            # External file drop from OS
            if mime.hasUrls():
                urls = mime.urls()
                paths = [u.toLocalFile() for u in urls if u.isLocalFile()]

                if not paths:
                    event.ignore()
                    return

                try:
                    tree_pos = self.tree.viewport().mapFrom(self, event.pos().toPoint())
                except Exception:
                    tree_pos = self.tree.viewport().mapFrom(self, event.pos())

                item = self.tree.itemAt(tree_pos)

                project = item.data(0, Qt.UserRole) if item else None
                section = item.data(0, Qt.UserRole + 1) if item else None

                if section not in ("assets", "references", "notes", "renders", "exports"):
                    section = "assets"

                self.files_dropped.emit(project, section, paths)
                event.acceptProposedAction()
                return

            event.ignore()
        except Exception:
            event.ignore()

    # ---------------------
    def on_item_clicked(self, item, column):

        project = item.data(0, ROLE_PROJECT)
        section = item.data(0, ROLE_SECTION)
        rel_path = item.data(0, ROLE_REL_PATH)

        if isinstance(project, Project):
            self._update_project_card_selection(project)
            if getattr(self, '_context', None) and getattr(self._context, 'inspector_panel', None):
                try:
                    self._context.inspector_panel.show_project(project)
                except Exception:
                    pass
            self.project_selected.emit(project, section, rel_path)
            return

        # If the clicked entry is a top-level navigation (home, clients, assets_lib, knowledge, business),
        # emit navigation_requested so the main app can handle module switching.
        if section in ("home", "projects", "clients", "assets_lib", "knowledge", "business"):
            try:
                self.navigation_requested.emit(section)
            except Exception:
                pass