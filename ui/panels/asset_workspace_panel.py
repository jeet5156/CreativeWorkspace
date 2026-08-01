from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QScrollArea,
    QGridLayout,
    QSizePolicy,
    QMenu,
    QMessageBox,
    QInputDialog,
    QApplication,
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QCursor, QAction, QKeySequence, QShortcut
from ui.widgets.asset_card import AssetCard
from ui.widgets.folder_card import FolderCard
from pathlib import Path, PurePosixPath
import shutil


SECTION_TO_FOLDER = {
    "notes": "Notes",
    "references": "References",
    "assets": "Assets",
    "renders": "Renders",
    "exports": "Exports",
}


class AssetWorkspacePanel(QWidget):
    asset_selected = Signal(str)
    assets_loaded = Signal()
    folder_navigation_requested = Signal(object, str, str)

    def clear(self):
        # remove all cards and reset title and selection state
        for i in reversed(range(self.grid.count())):
            widget = self.grid.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self._cards.clear()
        self._card_order = []
        self._selected_ids = set()
        self._last_selected_id = None
        self._pending_selection = None
        self._suppress_selection_emit = False
        self._current_rel_path = None
        self.title.setText("Assets (0)")

    """Displays a responsive, scrollable grid of asset cards and folder cards for a project section.
    The panel receives an AppContext via show_project_section and uses AssetService and FolderService
    to fetch metadata and subfolders.
    """

    def __init__(self):
        super().__init__()

        self._project = None
        self._section = None
        self._context = None
        self._current_rel_path = None

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
        self._card_order = []  # preserve order for shift-range selection
        self._selected_ids = set()
        self._last_selected_id = None
        self._suppress_selection_emit = False

        # keyboard shortcuts
        try:
            sc_rename = QShortcut(QKeySequence("F2"), self)
            sc_rename.activated.connect(self._on_shortcut_rename)
            sc_delete = QShortcut(QKeySequence("Delete"), self)
            sc_delete.activated.connect(self._on_shortcut_delete)
        except Exception:
            pass

    def show_project_section(self, project, section, context=None, rel_path=None):
        self._project = project
        self._section = section
        if context is not None:
            self._context = context

        root_folder = SECTION_TO_FOLDER.get(section, "Assets")
        if rel_path:
            self._current_rel_path = rel_path
        else:
            self._current_rel_path = root_folder

        # mark assets as not yet loaded and clear pending selection
        self._assets_loaded = False
        self._pending_selection = None

        self._load_assets()

    def _is_asset_in_folder(self, asset: dict, target_rel_path: str) -> bool:
        rel = (asset.get('relative_path') or '').replace('\\', '/').strip('/')
        target = target_rel_path.replace('\\', '/').strip('/')
        if not rel:
            return False
        parent = str(PurePosixPath(rel).parent)
        if parent == '.':
            parent = ''
        return parent.lower() == target.lower()

    def _on_folder_card_double_clicked(self, target_rel_path: str):
        if self._project and self._section:
            self.folder_navigation_requested.emit(self._project, self._section, target_rel_path)

    def _on_folder_card_assets_dropped(self, mime_data, target_rel_path: str):
        if not self._project or not self._context:
            return
        ops = getattr(self._context, 'asset_operations', None)
        if ops:
            try:
                ops.move_assets_to_folder(self._project, mime_data, target_rel_path)
            except Exception:
                pass

    def _load_assets(self):
        root_folder = SECTION_TO_FOLDER.get(self._section, "Assets")
        if not self._current_rel_path:
            self._current_rel_path = root_folder

        # ask service for metadata
        all_assets = []
        try:
            if self._context:
                category = SECTION_TO_FOLDER.get(self._section, 'Assets')
                all_assets = self._context.asset_service.get_assets(self._project, category)
        except Exception:
            all_assets = []

        # clear existing widgets
        for i in reversed(range(self.grid.count())):
            widget = self.grid.itemAt(i).widget()
            if widget:
                try:
                    widget.setParent(None)
                except Exception:
                    pass

        self._cards.clear()
        folder_cards = []

        # Build parent navigation card ".." if currently inside a subfolder
        curr_p = PurePosixPath(self._current_rel_path.replace('\\', '/'))
        root_p = PurePosixPath(root_folder.replace('\\', '/'))

        if curr_p != root_p and len(curr_p.parts) > len(root_p.parts):
            parent_rel_path = str(curr_p.parent)
            parent_card = FolderCard(
                folder_name="..",
                rel_path=parent_rel_path,
                size=self.card_size,
                is_parent_nav=True,
            )
            parent_card.double_clicked.connect(self._on_folder_card_double_clicked)
            parent_card.assets_dropped.connect(self._on_folder_card_assets_dropped)
            folder_cards.append(parent_card)

        # Build subfolder cards from FolderService
        folder_service = getattr(self._context, 'folder_service', None) if self._context else None
        if folder_service and self._project:
            try:
                subfolders = folder_service.list_subfolders(self._project, self._current_rel_path)
                for fname in subfolders:
                    sub_rel_path = f"{self._current_rel_path.rstrip('/')}/{fname}"
                    # Count items in subfolder
                    sub_count = 0
                    try:
                        sub_subs = folder_service.list_subfolders(self._project, sub_rel_path)
                        sub_count += len(sub_subs)
                    except Exception:
                        pass
                    try:
                        sub_assets = [a for a in all_assets if self._is_asset_in_folder(a, sub_rel_path)]
                        sub_count += len(sub_assets)
                    except Exception:
                        pass

                    fcard = FolderCard(
                        folder_name=fname,
                        rel_path=sub_rel_path,
                        size=self.card_size,
                        is_parent_nav=False,
                        item_count=sub_count,
                    )
                    fcard.double_clicked.connect(self._on_folder_card_double_clicked)
                    fcard.assets_dropped.connect(self._on_folder_card_assets_dropped)
                    folder_cards.append(fcard)
            except Exception:
                pass

        # Filter assets for current folder level
        folder_assets = [a for a in all_assets if self._is_asset_in_folder(a, self._current_rel_path)]

        if not folder_cards and not folder_assets:
            lbl = QLabel("No assets or subfolders yet\nDrag & Drop files here\nor Import Assets...")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet('color:#666;font-size:14px;')
            self.grid.addWidget(lbl, 0, 0)
            self._assets_loaded = True
            try:
                self.assets_loaded.emit()
            except Exception:
                pass
            if self._pending_selection:
                try:
                    self.select_asset(self._pending_selection)
                except Exception:
                    pass
                self._pending_selection = None
            return

        # Update title with current location and item count
        rel_display = self._current_rel_path.replace('\\', '/')
        total_items = len(folder_cards) + len(folder_assets)
        self.title.setText(f"{rel_display} ({total_items})")

        # Create card widgets with responsive columns
        avail_width = self.scroll.viewport().width() if self.scroll and self.scroll.viewport() else self.width()
        card_total_w = self.card_size.width() + 24
        columns = max(1, avail_width // card_total_w)
        row = 0
        col = 0
        self._card_order = []

        # 1. Place folder cards
        for fcard in folder_cards:
            self.grid.addWidget(fcard, row, col)
            col += 1
            if col >= columns:
                col = 0
                row += 1

        # 2. Place asset cards
        for asset in folder_assets:
            aid = asset['id']
            thumb_svc = getattr(self._context, 'thumbnail_service', None)
            card = AssetCard(asset, self.card_size, thumbnail_service=thumb_svc, project_location=getattr(self._project, 'location', None))
            card.clicked.connect(self._on_card_clicked)
            card.double_clicked.connect(self._on_card_double_clicked)
            card.context_requested.connect(self._on_card_context)
            self.grid.addWidget(card, row, col)
            self._cards[aid] = card
            self._card_order.append(aid)

            col += 1
            if col >= columns:
                col = 0
                row += 1

        # assets have been populated
        self._assets_loaded = True
        try:
            self.assets_loaded.emit()
        except Exception:
            pass
        if self._pending_selection:
            try:
                self.request_select_asset(self._pending_selection)
            except Exception:
                pass
            self._pending_selection = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # reload assets to reflow grid
        self._load_assets()

    # ------------------
    # Interaction handlers
    # ------------------
    def _on_card_clicked(self, asset_id):
        # handle multi-selection modifiers
        try:
            mods = QApplication.keyboardModifiers()
        except Exception:
            mods = None

        ctrl = mods & Qt.ControlModifier if mods is not None else False
        shift = mods & Qt.ShiftModifier if mods is not None else False

        # if ctrl -> toggle selection
        if ctrl:
            if asset_id in self._selected_ids:
                self._selected_ids.remove(asset_id)
            else:
                self._selected_ids.add(asset_id)
            self._last_selected_id = asset_id
            self._apply_selection()
            return

        # if shift -> select range from last_selected to this
        if shift and self._last_selected_id and self._last_selected_id in self._card_order:
            try:
                i1 = self._card_order.index(self._last_selected_id)
                i2 = self._card_order.index(asset_id)
                if i1 <= i2:
                    rng = self._card_order[i1:i2+1]
                else:
                    rng = self._card_order[i2:i1+1]
                self._selected_ids.update(rng)
                self._last_selected_id = asset_id
                self._apply_selection()
            except Exception:
                pass
            return

        # default: single select
        self._selected_ids = {asset_id}
        self._last_selected_id = asset_id
        self._apply_selection()

    def _apply_selection(self):
        # update visual states
        for aid, card in list(self._cards.items()):
            try:
                card.set_selected(aid in self._selected_ids)
            except Exception:
                pass
        # notify inspector of the canonical selection (last selected) unless suppressed
        last = self._last_selected_id or (next(iter(self._selected_ids)) if self._selected_ids else None)
        if getattr(self, '_suppress_selection_emit', False):
            # skip emitting while suppressed
            return
        try:
            from PySide6.QtCore import QTimer
            if last:
                QTimer.singleShot(0, lambda aid=last: self.asset_selected.emit(aid))
            else:
                QTimer.singleShot(0, lambda: self.asset_selected.emit(None))
        except Exception:
            try:
                if last:
                    self.asset_selected.emit(last)
                else:
                    self.asset_selected.emit(None)
            except Exception:
                pass

    def request_select_asset(self, asset_id):
        """Request a programmatic selection. If assets are loaded, select immediately; otherwise store as pending."""
        if getattr(self, '_assets_loaded', False):
            try:
                self.select_assets([asset_id])
            except Exception:
                pass
        else:
            self._pending_selection = asset_id

    def select_assets(self, asset_ids: list):
        """Select a list of assets (preserves order by card order) and emit last selected."""
        if not asset_ids:
            self._selected_ids = set()
            self._last_selected_id = None
            self._apply_selection()
            return
        # preserve only IDs that exist
        valid = [aid for aid in self._card_order if aid in asset_ids]
        self._selected_ids = set(valid)
        self._last_selected_id = valid[-1] if valid else None
        self._apply_selection()

    def _on_card_double_clicked(self, asset_id):
        if not self._context:
            return
        # delegate open to AssetService (no change in ownership)
        try:
            self._context.asset_service.open_asset(self._project, asset_id)
            try:
                self._context.activity_service.record('open_asset', {'project': self._project.location, 'asset_id': asset_id})
            except Exception:
                pass
        except Exception:
            pass

    def _on_card_context(self, asset_id):
        # Right-click should select the item unless it's already part of the selection
        try:
            mods = QApplication.keyboardModifiers()
        except Exception:
            mods = None
        ctrl = mods & Qt.ControlModifier if mods is not None else False
        # If right-clicked item not in selection and ctrl not held, select only this
        if asset_id not in self._selected_ids and not ctrl:
            # suppress emitting selection change until after menu closes to avoid UI updates
            self._suppress_selection_emit = True
            try:
                self.select_assets([asset_id])
            except Exception:
                pass
        # Show context menu near cursor; operate on canonical selection
        sel = self.get_selected_ids()
        menu = QMenu()

        open_action = QAction("Open")
        open_action.triggered.connect(lambda: [self._context.asset_service.open_asset(self._project, aid) for aid in sel])
        menu.addAction(open_action)

        open_folder = QAction("Open Containing Folder")
        open_folder.triggered.connect(lambda: [self._context.asset_service.open_containing_folder(self._project, aid) for aid in sel])
        menu.addAction(open_folder)

        duplicate_action = QAction("Duplicate")
        duplicate_action.triggered.connect(lambda: [self._duplicate_asset(aid) for aid in sel])
        menu.addAction(duplicate_action)

        move_action = QAction("Move")
        move_action.triggered.connect(lambda: [self._move_asset(aid) for aid in sel])
        menu.addAction(move_action)

        reveal_action = QAction("Reveal in Explorer")
        reveal_action.triggered.connect(lambda: [self._context.asset_operations.reveal_in_explorer(self._project, aid) if getattr(self._context, 'asset_operations', None) else self._context.asset_service.open_containing_folder(self._project, aid) for aid in sel])
        menu.addAction(reveal_action)

        copy_path_action = QAction("Copy Path")
        copy_path_action.triggered.connect(lambda: [self._context.asset_operations.copy_path(self._project, aid) if getattr(self._context, 'asset_operations', None) else None for aid in sel])
        menu.addAction(copy_path_action)

        rename_action = QAction("Rename")
        rename_action.triggered.connect(lambda: self._rename_asset(self._last_selected_id) )
        menu.addAction(rename_action)

        delete_action = QAction("Delete")
        delete_action.triggered.connect(lambda: self._delete_asset(None))
        menu.addAction(delete_action)

        properties_action = QAction("Properties")
        properties_action.triggered.connect(lambda: self._show_properties(self._last_selected_id))
        menu.addAction(properties_action)

        refresh_action = QAction("Refresh")
        # refresh via AssetService so signals are emitted
        refresh_action.triggered.connect(lambda: self._context.asset_service.refresh_index(self._project) if self._context else None)
        menu.addAction(refresh_action)

        # show the menu; exec returns after menu closes
        try:
            menu.exec(QCursor.pos())
        finally:
            # clear suppression and emit canonical selection now that menu is closed
            try:
                self._suppress_selection_emit = False
                last = self._last_selected_id or (self.get_selected_ids()[-1] if self.get_selected_ids() else None)
                if last:
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(0, lambda aid=last: self.asset_selected.emit(aid))
                else:
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(0, lambda: self.asset_selected.emit(None))
            except Exception:
                pass

    def _duplicate_asset(self, asset_id):
        if not asset_id or not self._context:
            return
        ops = getattr(self._context, 'asset_operations', None)
        success = False
        if ops:
            success = ops.duplicate_asset(self._project, asset_id)
        else:
            # fallback: perform a simple duplicate using shutil
            entry = self._context.asset_service.get_asset(self._project, asset_id)
            if not entry:
                return
            src = Path(entry.get('absolute_path') or (Path(self._project.location) / entry.get('relative_path')))
            try:
                parent = src.parent
                stem = src.stem
                suffix = src.suffix
                i = 1
                while True:
                    candidate = parent / f"{stem}_copy{i}{suffix}"
                    if not candidate.exists():
                        break
                    i += 1
                shutil.copy2(src, candidate)
                self._context.asset_service._ensure_index_loaded(self._project)
                new_entry = self._context.asset_service._make_asset_entry(self._project, str(candidate.resolve()), entry.get('category'))
                self._context.asset_service._indices[self._project.location].append(new_entry)
                self._context.asset_service._save_index(self._project)
                try:
                    self._context.activity_service.record('duplicate_asset', {'project': self._project.location, 'asset_id': asset_id, 'new_asset_id': new_entry.get('id')})
                except Exception:
                    pass
                try:
                    self._context.asset_service.assets_changed.emit(self._project, entry.get('category'))
                except Exception:
                    pass
                success = True
            except Exception:
                success = False
        if not success:
            QMessageBox.warning(self, "Duplicate", "Unable to duplicate asset.")
        else:
            pass

    def _move_asset(self, asset_id):
        if not asset_id or not self._context:
            return
        # ask user for target section
        options = ["assets", "references", "renders", "exports"]
        choice, ok = QInputDialog.getItem(self, "Move Asset", "Target section:", options, 0, False)
        if not ok or not choice:
            return
        ops = getattr(self._context, 'asset_operations', None)
        success = False
        if ops:
            success = ops.move_asset(self._project, asset_id, choice)
        else:
            # fallback naive move implementation
            entry = self._context.asset_service.get_asset(self._project, asset_id)
            if not entry:
                return
            src = Path(entry.get('absolute_path') or (Path(self._project.location) / entry.get('relative_path')))
            try:
                dest_dir = self._context.asset_service._determine_dest_dir(self._project, choice, src)
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / src.name
                if dest.exists():
                    stem = dest.stem
                    suffix = dest.suffix
                    j = 1
                    while True:
                        cand = dest_dir / f"{stem}_{j}{suffix}"
                        if not cand.exists():
                            dest = cand
                            break
                        j += 1
                shutil.move(str(src), str(dest))
                assets = self._context.asset_service._ensure_index_loaded(self._project)
                e = next((a for a in assets if a.get('id') == asset_id), None)
                if e:
                    e['filename'] = dest.name
                    try:
                        rel = str(dest.relative_to(Path(self._project.location))).replace('\\', '/')
                    except Exception:
                        rel = str(dest)
                    e['relative_path'] = rel
                    e['absolute_path'] = str(dest)
                    e['category'] = choice.capitalize() if choice != 'assets' else 'Assets'
                    e['updated_at'] = __import__('datetime').datetime.now().isoformat()
                    self._context.asset_service._save_index(self._project)
                try:
                    self._context.activity_service.record('move_asset', {'project': self._project.location, 'asset_id': asset_id, 'to': choice})
                except Exception:
                    pass
                try:
                    self._context.asset_service.assets_changed.emit(self._project, e.get('category') if e else None)
                except Exception:
                    pass
                success = True
            except Exception:
                success = False
        if not success:
            QMessageBox.warning(self, "Move", "Unable to move asset.")
        else:
            pass

    def _rename_asset(self, asset_id):
        if not asset_id or not self._context:
            return
        # Only allow rename when a single item is selected; otherwise prompt user
        sel = self.get_selected_ids()
        if len(sel) > 1 and asset_id is None:
            QMessageBox.information(self, "Rename", "Please select a single item to rename.")
            return
        target = asset_id or (sel[-1] if sel else None)
        if not target:
            return
        assets = self._context.asset_service.get_assets(self._project)
        entry = next((a for a in assets if a['id'] == target), None)
        if not entry:
            return
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=entry['filename'])
        if not ok or not new_name:
            return
        ops = getattr(self._context, 'asset_operations', None)
        success = False
        if ops:
            success = ops.rename_asset(self._project, target, new_name)
        else:
            success = self._context.asset_service.rename_asset(self._project, target, new_name)
        if not success:
            QMessageBox.warning(self, "Rename", "Unable to rename asset.")
        else:
            # rely on AssetService.assets_changed signal to refresh views
            pass

    def _delete_asset(self, asset_id=None):
        # If no specific id passed, delete current selection
        sel = self.get_selected_ids()
        targets = [asset_id] if asset_id else sel
        if not targets:
            return
        confirm = QMessageBox.question(self, "Delete", f"Delete {len(targets)} selected asset(s)? This cannot be undone.")
        if confirm != QMessageBox.Yes:
            return
        ops = getattr(self._context, 'asset_operations', None)
        failed = []
        for aid in targets:
            try:
                if ops:
                    res = ops.delete_asset(self._project, aid)
                else:
                    res = self._context.asset_service.delete_asset(self._project, aid)
                if not res:
                    failed.append(aid)
            except Exception:
                failed.append(aid)
        if failed:
            QMessageBox.warning(self, "Delete", f"Unable to delete {len(failed)} item(s).")
        else:
            # rely on AssetService.assets_changed to refresh UI and AppState to clear inspector
            pass

    def get_selected_ids(self):
        # return selected ids in card order
        return [aid for aid in self._card_order if aid in self._selected_ids]

    def _on_shortcut_rename(self):
        last = self._last_selected_id or (self.get_selected_ids()[-1] if self.get_selected_ids() else None)
        if last:
            self._rename_asset(last)

    def _on_shortcut_delete(self):
        self._delete_asset(None)

    def _show_properties(self, asset_id):
        assets = self._context.asset_service.get_assets(self._project)
        entry = next((a for a in assets if a['id'] == asset_id), None)
        if not entry:
            return
        info = f"Filename: {entry['filename']}\nType: {entry['friendly_type']}\nCategory: {entry['category']}\nAdded: {entry['date_added']}\nPath: {entry['relative_path']}"
        QMessageBox.information(self, "Properties", info)
        try:
            self._context.activity_service.record('view_asset_properties', {'project': self._project.location, 'asset_id': asset_id})
        except Exception:
            pass
        # ensure canonical selection includes this
        try:
            self.select_assets([asset_id])
        except Exception:
            pass
