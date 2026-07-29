from PySide6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt


class SearchPanel(QWidget):
    def __init__(self, find_service, navigation_service):
        super().__init__()
        self.find_service = find_service
        self.navigation_service = navigation_service

        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search projects, assets, references...")
        layout.addWidget(self.search)

        self.results = QListWidget()
        layout.addWidget(self.results)

        self.search.returnPressed.connect(self.run_search)
        self.results.itemDoubleClicked.connect(self._on_double_click)
        # keyboard navigation: Up/Down on search field moves selection
        self.search.installEventFilter(self)

    def eventFilter(self, source, event):
        try:
            from PySide6.QtCore import QEvent
            if source == self.search and event.type() in (QEvent.KeyPress,):
                key = event.key()
                from PySide6.QtCore import Qt
                if key == Qt.Key_Down:
                    r = self.results
                    if r.count() > 0:
                        r.setCurrentRow(max(0, r.currentRow() + 1))
                        return True
                if key == Qt.Key_Up:
                    r = self.results
                    if r.count() > 0:
                        r.setCurrentRow(max(0, r.currentRow() - 1))
                        return True
                if key == Qt.Key_Return or key == Qt.Key_Enter:
                    # activate current selection
                    row = self.results.currentRow()
                    if row >= 0:
                        item = self.results.item(row)
                        if item:
                            self._on_double_click(item)
                            return True
        except Exception:
            pass
        return super().eventFilter(source, event)

    def run_search(self):
        q = self.search.text()
        self.results.clear()
        res = self.find_service.search(q)
        # render grouped results
        def add_group_label(text):
            it = QListWidgetItem(text)
            it.setFlags(Qt.NoItemFlags)
            self.results.addItem(it)

        for proj in res.get('projects', []):
            add_group_label('Projects')
            it = QListWidgetItem(proj.get('label'))
            it.setData(Qt.UserRole, proj)
            self.results.addItem(it)

        if res.get('assets'):
            add_group_label('Assets')
            for a in res['assets']:
                it = QListWidgetItem(a.get('label'))
                it.setData(Qt.UserRole, a)
                self.results.addItem(it)

        if res.get('references'):
            add_group_label('References')
            for r in res['references']:
                it = QListWidgetItem(r.get('label'))
                it.setData(Qt.UserRole, r)
                self.results.addItem(it)

    def _on_double_click(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole)
        if not data:
            return
        t = data.get('type')
        if t == 'project':
            self.navigation_service.navigate_project(data.get('project'))
        elif t == 'asset':
            self.navigation_service.navigate_to_asset(data.get('project'), data.get('asset_id'))
        elif t == 'reference':
            # treat like asset for now
            self.navigation_service.navigate_to_asset(data.get('project'), data.get('asset_id'))
