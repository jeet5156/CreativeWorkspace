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
    "library_references": "Library References",
}


class AssetWorkspacePanel(QWidget):
    asset_selected = Signal(str)
    assets_loaded = Signal()
    folder_navigation_requested = Signal(object, str, str)

    def __init__(self):
        super().__init__()

        self._project = None
        self._section = None
        self._context = None
        self._current_rel_path = None
        self._assets_loaded = False
        self._pending_selection = None
        self._suppress_selection_emit = False

        self.card_size = QSize(150, 185)
        self._cards = {}
        self._card_order = []  # preserve order for shift-range selection
        self._folder_cards = []
        self._ordered_widgets = []
        self._selected_ids = set()
        self._last_selected_id = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header / Title Bar
        self.header_widget = QWidget()
        self.header_widget.setStyleSheet(
            "background-color: #141620; border-bottom: 1px solid #282C40;"
        )
        header_layout = QVBoxLayout(self.header_widget)
        header_layout.setContentsMargins(16, 10, 16, 10)

        self.title = QLabel("Assets")
        self.title.setStyleSheet(
            "color: #F1F5F9; font-size: 14px; font-weight: 600; background: transparent;"
        )
        header_layout.addWidget(self.title)
        layout.addWidget(self.header_widget)

        # Scrollable Grid Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(
            "QScrollArea { border: none; background-color: #181B27; }"
            "QScrollBar:vertical { width: 8px; background: transparent; }"
            "QScrollBar::thumb:vertical { background: #313652; border-radius: 4px; }"
            "QScrollBar::thumb:vertical:hover { background: #434A6E; }"
        )

        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(self.container)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.grid.setContentsMargins(16, 16, 16, 16)
        self.grid.setSpacing(14)
        self.container.setLayout(self.grid)
        self.scroll.setWidget(self.container)

        layout.addWidget(self.scroll)

        # Keyboard shortcuts
        try:
            sc_rename = QShortcut(QKeySequence("F2"), self)
            sc_rename.activated.connect(self._on_shortcut_rename)
            sc_delete = QShortcut(QKeySequence("Delete"), self)
            sc_delete.activated.connect(self._on_shortcut_delete)
        except Exception:
            pass

    def clear(self):
        """Remove all cards and reset selection and navigation state."""
        for i in reversed(range(self.grid.count())):
            item = self.grid.itemAt(i)
            widget = item.widget() if item else None
            if widget:
                widget.setParent(None)
        self._cards.clear()
        self._card_order.clear()
        self._folder_cards.clear()
        self._ordered_widgets.clear()
        self._selected_ids.clear()
        self._last_selected_id = None
        self._pending_selection = None
        self._suppress_selection_emit = False
        self._current_rel_path = None
        self.title.setText("Assets (0)")

    def set_context(self, context):
        """Provide AppContext so panel has access to services."""
        self._context = context

    def show_project_section(self, project, section, context=None, rel_path=None):
        # Preserve active card selection across live reloads if not already pending
        if not self._pending_selection:
            for aid, card in self._cards.items():
                if getattr(card, '_selected', False):
                    self._pending_selection = aid
                    break

        self._project = project
        self._section = section
        if context is not None:
            self._context = context

        root_folder = SECTION_TO_FOLDER.get(section, "Assets")
        if rel_path:
            self._current_rel_path = rel_path
        else:
            self._current_rel_path = root_folder

        self._assets_loaded = False

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

        # Ask service for metadata
        all_assets = []
        try:
            if self._context:
                category = SECTION_TO_FOLDER.get(self._section, 'Assets')
                all_assets = self._context.asset_service.get_assets(self._project, category)
        except Exception:
            all_assets = []

        # Clear existing widgets from grid layout
        for i in reversed(range(self.grid.count())):
            item = self.grid.itemAt(i)
            widget = item.widget() if item else None
            if widget:
                try:
                    widget.setParent(None)
                except Exception:
                    pass

        self._cards.clear()
        self._card_order.clear()
        self._folder_cards.clear()
        self._ordered_widgets.clear()
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
            parent_card.clicked.connect(self._on_folder_card_clicked)
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
                    fcard.clicked.connect(self._on_folder_card_clicked)
                    fcard.double_clicked.connect(self._on_folder_card_double_clicked)
                    fcard.assets_dropped.connect(self._on_folder_card_assets_dropped)
                    folder_cards.append(fcard)
            except Exception:
                pass

        # Filter assets for current folder level and group sequences non-destructively
        from core.asset_intelligence import group_assets_and_sequences
        sec_lower = (self._section or '').lower()
        if sec_lower == "library_references":
            raw_folder_assets = all_assets
        else:
            raw_folder_assets = [a for a in all_assets if self._is_asset_in_folder(a, self._current_rel_path)]
        folder_assets = group_assets_and_sequences(raw_folder_assets)

        # Resolve live drive availability for Library references
        lib_svc = getattr(self._context, "library_service", None) if self._context else None
        if lib_svc:
            for asset in folder_assets:
                if asset.get('is_library_reference'):
                    drive_id = asset.get('drive_id')
                    drive_rel = asset.get('drive_relative_path')
                    drive_obj = lib_svc.get_drive(drive_id)
                    if drive_obj:
                        asset['drive_name'] = drive_obj.name
                    if drive_id and drive_rel:
                        phys = lib_svc.drive_detector.resolve_drive_path(drive_id, drive_rel)
                        if phys and phys.exists():
                            asset['availability'] = "Available"
                            asset['absolute_path'] = str(phys)
                        else:
                            asset['availability'] = "Offline"

        # Update title bar
        rel_display = self._current_rel_path.replace('\\', '/')
        total_items = len(folder_cards) + len(folder_assets)
        if sec_lower == 'references':
            icon_prefix = "🖼️"
        elif sec_lower == 'renders':
            icon_prefix = "🎬"
        elif sec_lower == 'exports':
            icon_prefix = "📤"
        elif sec_lower == 'library_references':
            icon_prefix = "📚"
            rel_display = "Library References"
        else:
            icon_prefix = "📁"
        self.title.setText(f"{icon_prefix} {rel_display} ({total_items})")

        # Empty state check
        if not folder_cards and not folder_assets:
            sec_name = (self._section or "assets").lower()
            if sec_name == "references":
                empty_text = "🖼️ No references yet\nDrag images or reference files here to collect inspiration"
            elif sec_name == "renders":
                empty_text = "🎬 No renders yet\nSave viewport snapshots, turntable clips, or render output here"
            elif sec_name == "exports":
                empty_text = "📤 No exports yet\nExport game-ready 3D models, textures, or packages here"
            elif sec_name == "library_references":
                empty_text = "📚 No library references yet\nReference assets from the Global Asset Library to use them here"
            else:
                empty_text = "📂 No assets yet\nImport a folder or drag files here to start organizing"
            lbl = QLabel(empty_text)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(
                "color: #64748B; font-size: 13px; font-weight: 500; line-height: 1.6; padding: 40px; background: transparent;"
            )
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

        # Create Asset cards
        asset_cards = []
        for asset in folder_assets:
            aid = asset['id']
            thumb_svc = getattr(self._context, 'thumbnail_service', None)
            card = AssetCard(
                asset,
                self.card_size,
                thumbnail_service=thumb_svc,
                project_location=getattr(self._project, 'location', None),
            )
            card.clicked.connect(self._on_card_clicked)
            card.double_clicked.connect(self._on_card_double_clicked)
            card.context_requested.connect(self._on_card_context)
            self._cards[aid] = card
            self._card_order.append(aid)
            asset_cards.append(card)

        self._folder_cards = folder_cards
        self._ordered_widgets = folder_cards + asset_cards

        # Relayout grid items
        self._relayout_grid()

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

    def _relayout_grid(self):
        """Cleanly reflow existing widgets into columns without reloading backend data."""
        if not self._ordered_widgets:
            return

        # Clear items from layout without destroying them
        for i in reversed(range(self.grid.count())):
            item = self.grid.itemAt(i)
            if item:
                self.grid.removeItem(item)

        avail_width = self.scroll.viewport().width() if self.scroll and self.scroll.viewport() else self.width()
        spacing = self.grid.spacing()
        margins = self.grid.contentsMargins()
        usable_width = max(100, avail_width - margins.left() - margins.right())
        card_w = self.card_size.width()
        columns = max(1, (usable_width + spacing) // (card_w + spacing))

        row = 0
        col = 0
        for widget in self._ordered_widgets:
            self.grid.addWidget(widget, row, col)
            col += 1
            if col >= columns:
                col = 0
                row += 1

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout_grid()

    # ------------------
    # Interaction Handlers
    # ------------------
    def _on_folder_card_clicked(self, target_rel_path: str):
        self._selected_ids.clear()
        self._last_selected_id = None
        self._apply_selection()
        for fc in self._folder_cards:
            fc.set_selected(fc.rel_path == target_rel_path)

    def _on_card_clicked(self, asset_id):
        # Deselect all folder cards when an asset card is clicked
        for fc in self._folder_cards:
            fc.set_selected(False)

        try:
            mods = QApplication.keyboardModifiers()
        except Exception:
            mods = None

        ctrl = mods & Qt.ControlModifier if mods is not None else False
        shift = mods & Qt.ShiftModifier if mods is not None else False

        if ctrl:
            if asset_id in self._selected_ids:
                self._selected_ids.remove(asset_id)
            else:
                self._selected_ids.add(asset_id)
            self._last_selected_id = asset_id
            self._apply_selection()
            return

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

        self._selected_ids = {asset_id}
        self._last_selected_id = asset_id
        self._apply_selection()

    def _apply_selection(self):
        for aid, card in list(self._cards.items()):
            try:
                card.set_selected(aid in self._selected_ids)
            except Exception:
                pass

        if getattr(self, '_suppress_selection_emit', False):
            return

        last = self._last_selected_id or (next(iter(self._selected_ids)) if self._selected_ids else None)
        if last is not None and last in self._cards:
            try:
                self.asset_selected.emit(last)
            except Exception:
                pass

    def request_select_asset(self, asset_id):
        if getattr(self, '_assets_loaded', False):
            try:
                self.select_assets([asset_id])
            except Exception:
                pass
        else:
            self._pending_selection = asset_id

    def select_assets(self, asset_ids: list):
        if not asset_ids:
            self._selected_ids = set()
            self._last_selected_id = None
            self._apply_selection()
            return
        valid = [aid for aid in self._card_order if aid in asset_ids]
        if not valid:
            for aid in asset_ids:
                aid_str = str(aid).replace("\\", "/").strip("/")
                for card_id, card in self._cards.items():
                    asset = getattr(card, "asset", {})
                    rp = (asset.get("relative_path") or "").replace("\\", "/").strip("/")
                    fn = (asset.get("filename") or Path(rp).name)
                    if aid_str == rp or aid_str == fn or aid_str.lower() == fn.lower() or aid_str.endswith("/" + fn):
                        valid.append(card_id)
        self._selected_ids = set(valid)
        self._last_selected_id = valid[-1] if valid else None
        self._apply_selection()

    def _on_card_double_clicked(self, asset_id):
        if not self._context:
            return
        card = self._cards.get(asset_id)
        if card and card.asset.get("is_library_reference"):
            self._open_library_reference(asset_id)
            return
        try:
            self._context.asset_service.open_asset(self._project, asset_id)
            try:
                self._context.activity_service.record('open_asset', {'project': self._project.location, 'asset_id': asset_id})
            except Exception:
                pass
        except Exception:
            pass

    def _on_card_context(self, asset_id):
        try:
            mods = QApplication.keyboardModifiers()
        except Exception:
            mods = None
        ctrl = mods & Qt.ControlModifier if mods is not None else False
        if asset_id not in self._selected_ids and not ctrl:
            self._suppress_selection_emit = True
            try:
                self.select_assets([asset_id])
            except Exception:
                pass

        sel = self.get_selected_ids()
        menu = QMenu(self)

        card = self._cards.get(asset_id)
        is_lib_ref = bool(card and card.asset.get("is_library_reference"))

        if is_lib_ref:
            # Dedicated Library Reference Context Menu
            open_action = QAction("Open / Use Original", self)
            open_action.triggered.connect(lambda: self._open_library_reference(asset_id))
            menu.addAction(open_action)

            reveal_action = QAction("Reveal in Explorer", self)
            reveal_action.triggered.connect(lambda: self._reveal_library_reference(asset_id))
            menu.addAction(reveal_action)

            open_lib_action = QAction("Reveal in Asset Library", self)
            open_lib_action.setStatusTip("Navigate to this asset's location in Global Asset Library and select it.")
            open_lib_action.triggered.connect(lambda: self._open_in_asset_library(asset_id))
            menu.addAction(open_lib_action)

            menu.addSeparator()

            copy_proj_action = QAction("Copy to Project", self)
            copy_proj_action.setStatusTip("Make an independent project-local copy of this asset in References.")
            copy_proj_action.triggered.connect(lambda: self._copy_reference_to_project(asset_id))
            menu.addAction(copy_proj_action)

            menu.addSeparator()

            remove_ref_action = QAction("Remove Reference from Project", self)
            remove_ref_action.setStatusTip("Remove this reference from the project only. The original file and Library catalog will remain untouched.")
            remove_ref_action.triggered.connect(lambda: self._remove_reference_from_project(asset_id))
            menu.addAction(remove_ref_action)

            menu.addSeparator()

            properties_action = QAction("Properties", self)
            properties_action.triggered.connect(lambda: self._show_properties(self._last_selected_id))
            menu.addAction(properties_action)

        else:
            open_action = QAction("Open", self)
            open_action.triggered.connect(lambda: [self._context.asset_service.open_asset(self._project, aid) for aid in sel])
            menu.addAction(open_action)

            open_folder = QAction("Open Containing Folder", self)
            open_folder.triggered.connect(lambda: [self._context.asset_service.open_containing_folder(self._project, aid) for aid in sel])
            menu.addAction(open_folder)

            duplicate_action = QAction("Duplicate", self)
            duplicate_action.triggered.connect(lambda: [self._duplicate_asset(aid) for aid in sel])
            menu.addAction(duplicate_action)

            move_action = QAction("Move", self)
            move_action.triggered.connect(lambda: [self._move_asset(aid) for aid in sel])
            menu.addAction(move_action)

            reveal_action = QAction("Reveal in Explorer", self)
            reveal_action.triggered.connect(lambda: [self._reveal_asset(aid) for aid in sel])
            menu.addAction(reveal_action)

            copy_path_action = QAction("Copy Path", self)
            copy_path_action.triggered.connect(lambda: [self._context.asset_operations.copy_path(self._project, aid) if getattr(self._context, 'asset_operations', None) else None for aid in sel])
            menu.addAction(copy_path_action)

            rename_action = QAction("Rename", self)
            rename_action.triggered.connect(lambda: self._rename_asset(self._last_selected_id))
            menu.addAction(rename_action)

            delete_action = QAction("Delete", self)
            delete_action.triggered.connect(lambda: self._delete_asset(None))
            menu.addAction(delete_action)

            properties_action = QAction("Properties", self)
            properties_action.triggered.connect(lambda: self._show_properties(self._last_selected_id))
            menu.addAction(properties_action)

            refresh_action = QAction("Refresh", self)
            refresh_action.triggered.connect(lambda: self._context.asset_service.refresh_index(self._project) if self._context else None)
            menu.addAction(refresh_action)

        try:
            menu.exec(QCursor.pos())
        finally:
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

    def _open_library_reference(self, asset_id: str):
        card = self._cards.get(asset_id)
        if not card:
            return
        asset = card.asset
        lib_svc = getattr(self._context, "library_service", None) if self._context else None
        drive_id = asset.get("drive_id")
        drive_rel = asset.get("drive_relative_path")
        phys_path = None
        if lib_svc and drive_id and drive_rel:
            phys_path = lib_svc.drive_detector.resolve_drive_path(drive_id, drive_rel)

        if not phys_path or not phys_path.exists():
            QMessageBox.warning(
                self,
                "Reference Offline",
                f"Cannot open '{asset.get('filename')}'.\n\nThe source drive is currently disconnected or the file is missing.",
            )
            return
        try:
            import os, subprocess
            if os.name == "nt":
                os.startfile(str(phys_path))
            else:
                subprocess.Popen(["xdg-open" if os.name == "posix" else "open", str(phys_path)])
        except Exception as e:
            QMessageBox.warning(self, "Open Reference", f"Unable to open reference file: {e}")

    def _reveal_library_reference(self, asset_id: str):
        card = self._cards.get(asset_id)
        if not card:
            return
        asset = card.asset
        lib_svc = getattr(self._context, "library_service", None) if self._context else None
        drive_id = asset.get("drive_id")
        drive_rel = asset.get("drive_relative_path")
        phys_path = None
        if lib_svc and drive_id and drive_rel:
            phys_path = lib_svc.drive_detector.resolve_drive_path(drive_id, drive_rel)

        if not phys_path or not phys_path.exists():
            QMessageBox.warning(
                self,
                "Reference Offline",
                f"Cannot reveal '{asset.get('filename')}'.\n\nThe source drive is currently disconnected.",
            )
            return
        try:
            import os, subprocess
            if os.name == "nt":
                subprocess.Popen(f'explorer /select,"{str(phys_path)}"')
            else:
                folder = phys_path.parent
                subprocess.Popen(["xdg-open" if os.name == "posix" else "open", str(folder)])
        except Exception as e:
            QMessageBox.warning(self, "Reveal Reference", f"Unable to reveal reference in explorer: {e}")

    def _open_in_asset_library(self, asset_id: str):
        card = self._cards.get(asset_id)
        if not card or not self._context:
            return
        wm = getattr(self._context, "workspace_manager", None)
        nav = getattr(self._context, "navigation_service", None)
        if wm and hasattr(wm, "show_module"):
            wm.show_module("assets_lib")
            if hasattr(wm, "library_panel") and wm.library_panel:
                if hasattr(wm.library_panel, "navigate_to_asset"):
                    wm.library_panel.navigate_to_asset(card.asset)
                elif hasattr(wm.library_panel, "select_assets"):
                    lib_id = card.asset.get("library_asset_id")
                    if lib_id:
                        wm.library_panel.select_assets([lib_id])
        elif nav:
            nav.navigate_module("assets_lib")

    def _copy_reference_to_project(self, asset_id: str):
        card = self._cards.get(asset_id)
        if not card or not self._project or not self._context:
            return
        asset = card.asset
        lib_svc = getattr(self._context, "library_service", None)
        asset_svc = getattr(self._context, "asset_service", None)
        if not lib_svc or not asset_svc:
            return
        try:
            copied = asset_svc.copy_library_asset(self._project, asset, lib_svc, target_section="References")
            if copied:
                QMessageBox.information(
                    self,
                    "Copied to Project",
                    f"Successfully created an independent copy of '{asset.get('filename')}' in References.",
                )
        except Exception as e:
            QMessageBox.critical(self, "Copy to Project", f"Failed to copy reference to project: {e}")

    def _remove_reference_from_project(self, asset_id: str):
        card = self._cards.get(asset_id)
        if not card or not self._project or not self._context:
            return
        asset = card.asset
        filename = asset.get("filename", "this asset")

        confirm = QMessageBox.question(
            self,
            "Remove Reference from Project",
            f"Remove reference '{filename}' from project '{self._project.name}'?\n\n"
            f"Note: This removes only the project reference. The original external file and the Global Library catalog will NOT be deleted or modified.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        asset_svc = getattr(self._context, "asset_service", None)
        lib_svc = getattr(self._context, "library_service", None)
        if asset_svc:
            asset_svc.remove_library_reference(self._project, asset_id, library_service=lib_svc)
            self._load_assets()

    def _reveal_asset(self, asset_id):
        if not asset_id or not self._project:
            return False
        real_id = asset_id
        card = self._cards.get(asset_id)
        if card and card.asset.get("is_sequence"):
            frame_assets = card.asset.get("frame_assets", [])
            if frame_assets and frame_assets[0].get("id"):
                real_id = frame_assets[0]["id"]
            elif card.asset.get("absolute_path"):
                folder = Path(card.asset["absolute_path"]).parent
                try:
                    if os.name == 'nt':
                        os.startfile(str(folder))
                    else:
                        import subprocess
                        subprocess.Popen(['xdg-open' if os.name == 'posix' else 'open', str(folder)])
                    return True
                except Exception:
                    return False

        ops = getattr(self._context, 'asset_operations', None)
        if ops:
            return ops.reveal_in_explorer(self._project, real_id)
        elif getattr(self._context, 'asset_service', None):
            return self._context.asset_service.open_containing_folder(self._project, real_id)
        return False

    def _duplicate_asset(self, asset_id):
        if not asset_id or not self._context:
            return
        ops = getattr(self._context, 'asset_operations', None)
        success = False
        if ops:
            success = ops.duplicate_asset(self._project, asset_id)
        else:
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

    def _move_asset(self, asset_id):
        if not asset_id or not self._context:
            return
        options = ["assets", "references", "renders", "exports"]
        choice, ok = QInputDialog.getItem(self, "Move Asset", "Target section:", options, 0, False)
        if not ok or not choice:
            return
        ops = getattr(self._context, 'asset_operations', None)
        success = False
        if ops:
            success = ops.move_asset(self._project, asset_id, choice)
        else:
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

    def _rename_asset(self, asset_id):
        if not asset_id or not self._context:
            return
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

    def _delete_asset(self, asset_id=None):
        sel = self.get_selected_ids()
        targets = [asset_id] if asset_id else sel
        if not targets:
            return

        # Check if single target is a library reference
        if len(targets) == 1:
            card = self._cards.get(targets[0])
            if card and card.asset.get("is_library_reference"):
                self._remove_reference_from_project(targets[0])
                return

        expanded_frame_ids = []
        is_sequence_selected = False
        display_names = []

        for aid in targets:
            card = self._cards.get(aid)
            if card and card.asset.get("is_sequence"):
                is_sequence_selected = True
                frame_assets = card.asset.get("frame_assets", [])
                for fa in frame_assets:
                    if fa.get("id"):
                        expanded_frame_ids.append(fa["id"])
                display_names.append(f"sequence '{card.asset.get('filename')}' ({len(frame_assets)} frames)")
            else:
                expanded_frame_ids.append(aid)

        if is_sequence_selected and len(targets) == 1:
            confirm_msg = f"Delete {display_names[0]}? All constituent frame files will be permanently deleted."
        else:
            confirm_msg = f"Delete {len(targets)} selected asset(s)? This cannot be undone."

        confirm = QMessageBox.question(self, "Delete", confirm_msg)
        if confirm != QMessageBox.Yes:
            return

        ops = getattr(self._context, 'asset_operations', None)
        success = False
        if ops and hasattr(ops, 'delete_assets'):
            success = ops.delete_assets(self._project, expanded_frame_ids)
        elif self._context and getattr(self._context, 'asset_service', None) and hasattr(self._context.asset_service, 'delete_assets'):
            success = self._context.asset_service.delete_assets(self._project, expanded_frame_ids)
        else:
            failed = []
            for fid in expanded_frame_ids:
                try:
                    if ops:
                        res = ops.delete_asset(self._project, fid)
                    else:
                        res = self._context.asset_service.delete_asset(self._project, fid)
                    if not res:
                        failed.append(fid)
                except Exception:
                    failed.append(fid)
            success = len(failed) == 0

        if not success:
            QMessageBox.warning(self, "Delete", "Unable to complete asset deletion.")

    def get_selected_ids(self):
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
        try:
            self.select_assets([asset_id])
        except Exception:
            pass
