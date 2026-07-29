from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QScrollArea,
    QGridLayout,
    QSizePolicy,
    QMenu,
    QMessageBox,
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QCursor, QAction
from ui.widgets.asset_card import AssetCard


class AssetWorkspacePanel(QWidget):
    asset_selected = Signal(str)

    def clear(self):
        # remove all cards and reset title
        for i in reversed(range(self.grid.count())):
            widget = self.grid.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self._cards.clear()
        self.title.setText("Assets (0)")
    """Displays a responsive, scrollable grid of asset cards for a project section.
    The panel receives an AppContext via show_project_section and uses AssetService
    to fetch metadata. UI actions invoke AssetService methods.
    """

    def __init__(self):
        super().__init__()

        self._project = None
        self._section = None
        self._context = None

        layout = QVBoxLayout(self)

        self.title = QLabel("Assets")
        self.title.setStyleSheet("font-size:16px;font-weight:bold;padding:6px;")
        layout.addWidget(self.title)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(12)
        self.container.setLayout(self.grid)
        self.scroll.setWidget(self.container)

        layout.addWidget(self.scroll)

        self.card_size = QSize(140, 160)
        self._cards = {}

    def show_project_section(self, project, section, context):
        self._project = project
        self._section = section
        self._context = context

        self._load_assets()

    def _load_assets(self):
        # ask service for metadata
        assets = []
        try:
            if self._context:
                # map section to category name used in index
                category = 'Assets' if self._section == 'assets' else self._section.capitalize()
                assets = self._context.asset_service.get_assets(self._project, category)
        except Exception:
            assets = []

        # clear existing widgets: disconnect signals first to avoid re-entrancy when selections fire
        try:
            # disconnect known card signals
            for card in list(self._cards.values()):
                try:
                    card.clicked.disconnect(self._on_card_clicked)
                except Exception:
                    pass
                try:
                    card.double_clicked.disconnect(self._on_card_double_clicked)
                except Exception:
                    pass
                try:
                    card.context_requested.disconnect(self._on_card_context)
                except Exception:
                    pass
                try:
                    card.setParent(None)
                except Exception:
                    pass
        except Exception:
            # fallback: remove widgets from grid
            for i in reversed(range(self.grid.count())):
                widget = self.grid.itemAt(i).widget()
                if widget:
                    try:
                        widget.setParent(None)
                    except Exception:
                        pass

        self._cards.clear()

        if not assets:
            lbl = QLabel("No assets yet\nDrag & Drop files here\nor Import Assets...")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet('color:#666;font-size:14px;')
            self.grid.addWidget(lbl, 0, 0)
            return

        # Update title with asset count
        category_name = 'Assets' if self._section == 'assets' else self._section.capitalize()
        self.title.setText(f"{category_name} ({len(assets)})")

        # Create card widgets with responsive columns
        avail_width = self.scroll.viewport().width() if self.scroll and self.scroll.viewport() else self.width()
        card_total_w = self.card_size.width() + 24
        columns = max(1, avail_width // card_total_w)
        row = 0
        col = 0
        for asset in assets:
            card = AssetCard(asset, self.card_size)
            card.clicked.connect(self._on_card_clicked)
            card.double_clicked.connect(self._on_card_double_clicked)
            card.context_requested.connect(self._on_card_context)
            self.grid.addWidget(card, row, col)
            self._cards[asset['id']] = card

            col += 1
            if col >= columns:
                col = 0
                row += 1

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # reload assets to reflow grid
        self._load_assets()

    # ------------------
    # Interaction handlers
    # ------------------
    def _on_card_clicked(self, asset_id):
        # highlight selection safely: iterate over a snapshot so concurrent modifications don't crash
        for aid, card in list(self._cards.items()):
            try:
                card.set_selected(aid == asset_id)
            except Exception:
                # widget may have been removed; ignore
                pass
        # emit selection for inspector asynchronously to avoid re-entrancy during refresh
        try:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda aid=asset_id: self.asset_selected.emit(aid))
        except Exception:
            try:
                self.asset_selected.emit(asset_id)
            except Exception:
                pass

    def _on_card_double_clicked(self, asset_id):
        if not self._context:
            return
        self._context.asset_service.open_asset(self._project, asset_id)

    def _on_card_context(self, asset_id):
        # Show context menu near cursor
        menu = QMenu()
        open_action = QAction("Open")
        open_action.triggered.connect(lambda: self._context.asset_service.open_asset(self._project, asset_id))
        menu.addAction(open_action)

        open_folder = QAction("Open Containing Folder")
        open_folder.triggered.connect(lambda: self._context.asset_service.open_containing_folder(self._project, asset_id))
        menu.addAction(open_folder)

        rename_action = QAction("Rename")
        rename_action.triggered.connect(lambda: self._rename_asset(asset_id))
        menu.addAction(rename_action)

        delete_action = QAction("Delete")
        delete_action.triggered.connect(lambda: self._delete_asset(asset_id))
        menu.addAction(delete_action)

        properties_action = QAction("Properties")
        properties_action.triggered.connect(lambda: self._show_properties(asset_id))
        menu.addAction(properties_action)

        refresh_action = QAction("Refresh")
        refresh_action.triggered.connect(self._load_assets)
        menu.addAction(refresh_action)

        menu.exec(QCursor.pos())

    def _rename_asset(self, asset_id):
        from PySide6.QtWidgets import QInputDialog
        assets = self._context.asset_service.get_assets(self._project)
        entry = next((a for a in assets if a['id'] == asset_id), None)
        if not entry:
            return
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=entry['filename'])
        if not ok or not new_name:
            return
        success = self._context.asset_service.rename_asset(self._project, asset_id, new_name)
        if not success:
            QMessageBox.warning(self, "Rename", "Unable to rename asset.")
        else:
            self._load_assets()

    def _delete_asset(self, asset_id):
        confirm = QMessageBox.question(self, "Delete", "Delete selected asset? This cannot be undone.")
        if confirm != QMessageBox.Yes:
            return
        success = self._context.asset_service.delete_asset(self._project, asset_id)
        if not success:
            QMessageBox.warning(self, "Delete", "Unable to delete asset.")
        else:
            self._load_assets()

    def _show_properties(self, asset_id):
        assets = self._context.asset_service.get_assets(self._project)
        entry = next((a for a in assets if a['id'] == asset_id), None)
        if not entry:
            return
        info = f"Filename: {entry['filename']}\nType: {entry['friendly_type']}\nCategory: {entry['category']}\nAdded: {entry['date_added']}\nPath: {entry['relative_path']}"
        QMessageBox.information(self, "Properties", info)
