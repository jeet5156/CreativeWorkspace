"""Global Asset Library Workspace Panel for CreativeWorkspace.

Provides an in-place catalog browser for external drives without copying or moving source files.
"""

import os
import subprocess
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Set

from PySide6.QtCore import QSize, Qt, Signal, QTimer
from PySide6.QtGui import QAction, QCursor, QFontMetrics, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from models.library_models import AssetAvailability, LibraryAsset, LibraryLocation
from ui.widgets.asset_card import AssetCard
from ui.widgets.folder_card import FolderCard


class LibraryWorkspacePanel(QWidget):
    """Interactive workspace panel for the Global Asset Library."""

    asset_selected = Signal(object)
    folder_selected = Signal(object)
    assets_loaded = Signal()

    def __init__(self, context=None):
        super().__init__()

        self._context = context
        self.card_size = QSize(150, 185)

        # Navigation state
        self._current_location_id: Optional[str] = None  # None = root of all locations/drives
        self._current_subpath: str = ""  # Relative path within active location
        self._search_query: str = ""

        # Card and selection management
        self._cards: Dict[str, AssetCard] = {}
        self._card_order: List[str] = []
        self._folder_cards: List[FolderCard] = []
        self._selected_ids: Set[str] = set()
        self._selected_folder_card: Optional[FolderCard] = None
        self._selected_folder_data: Optional[dict] = None
        self._last_selected_id: Optional[str] = None
        self._pending_selection: Optional[str] = None
        self._suppress_selection_emit: bool = False

        # Live Drive Availability Poller (Lightweight: checks logical roots every 3s)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(3000)
        self._poll_timer.timeout.connect(self._on_poll_timer_tick)

        # Build UI layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---------------------------------------------------------------------
        # 1. Header Toolbar
        # ---------------------------------------------------------------------
        self.header_widget = QWidget()
        self.header_widget.setStyleSheet(
            "background-color: #141620; border-bottom: 1px solid #282C40;"
        )
        header_vbox = QVBoxLayout(self.header_widget)
        header_vbox.setContentsMargins(16, 12, 16, 12)
        header_vbox.setSpacing(8)

        # Top row: Title + Actions
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)

        self.title_label = QLabel("📚 Global Asset Library")
        self.title_label.setStyleSheet(
            "color: #F1F5F9; font-size: 15px; font-weight: 700; background: transparent;"
        )
        top_row.addWidget(self.title_label)

        top_row.addStretch()

        # Reference in Project Button
        self.btn_ref_project = QPushButton("📎 Reference in Project")
        self.btn_ref_project.setEnabled(False)
        self.btn_ref_project.setStyleSheet("""
            QPushButton {
                background-color: #1E2235;
                color: #38BDF8;
                border: 1px solid #0284C7;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover:enabled {
                background-color: #0369A1;
                color: #FFFFFF;
            }
            QPushButton:disabled {
                color: #475569;
                border-color: #282C40;
                background-color: #141620;
            }
        """)
        self.btn_ref_project.clicked.connect(self._on_toolbar_reference_clicked)
        top_row.addWidget(self.btn_ref_project)

        # Copy to Project Button
        self.btn_copy_project = QPushButton("📋 Copy to Project")
        self.btn_copy_project.setEnabled(False)
        self.btn_copy_project.setStyleSheet("""
            QPushButton {
                background-color: #1E2235;
                color: #34D399;
                border: 1px solid #059669;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover:enabled {
                background-color: #047857;
                color: #FFFFFF;
            }
            QPushButton:disabled {
                color: #475569;
                border-color: #282C40;
                background-color: #141620;
            }
        """)
        self.btn_copy_project.clicked.connect(self._on_toolbar_copy_clicked)
        top_row.addWidget(self.btn_copy_project)

        # Add Location Button
        self.btn_add_location = QPushButton("📁 Add Library Location")
        self.btn_add_location.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
            QPushButton:pressed {
                background-color: #1D4ED8;
            }
        """)
        self.btn_add_location.clicked.connect(self._on_add_location_clicked)
        top_row.addWidget(self.btn_add_location)

        # Rescan / Refresh Button
        self.btn_rescan = QPushButton("🔄 Rescan All")
        self.btn_rescan.setStyleSheet("""
            QPushButton {
                background-color: #1E2235;
                color: #94A3B8;
                border: 1px solid #333A56;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #282E47;
                color: #F1F5F9;
                border-color: #4B557A;
            }
        """)
        self.btn_rescan.clicked.connect(self._on_rescan_clicked)
        top_row.addWidget(self.btn_rescan)

        header_vbox.addLayout(top_row)

        # Bottom row: Breadcrumbs + Search Filter
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(10)

        # Breadcrumb / Navigation label
        self.breadcrumb_label = QLabel("📁 All Library Locations")
        self.breadcrumb_label.setStyleSheet(
            "color: #94A3B8; font-size: 12px; background: transparent;"
        )
        bottom_row.addWidget(self.breadcrumb_label)

        bottom_row.addStretch()

        # Search box
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Search assets, tags, formats...")
        self.search_edit.setFixedWidth(280)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #181B27;
                border: 1px solid #282C40;
                border-radius: 6px;
                color: #F1F5F9;
                padding: 5px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #6366F1;
                background-color: #1B1E2D;
            }
        """)
        self.search_edit.textChanged.connect(self._on_search_changed)
        bottom_row.addWidget(self.search_edit)

        header_vbox.addLayout(bottom_row)
        main_layout.addWidget(self.header_widget)

        # ---------------------------------------------------------------------
        # 2. Scrollable Grid Container
        # ---------------------------------------------------------------------
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

        main_layout.addWidget(self.scroll)

        # Keyboard shortcuts
        try:
            sc_delete = QShortcut(QKeySequence("Delete"), self)
            sc_delete.activated.connect(lambda: self._remove_selected_assets(delete_files=False))
        except Exception:
            pass

        # Accept Drag & Drop
        self.setAcceptDrops(True)

    # -------------------------------------------------------------------------
    # Context & Lifecycle
    # -------------------------------------------------------------------------

    def set_context(self, context):
        """Provide AppContext with access to LibraryService and ThumbnailService."""
        if getattr(self, "_connected_library_service", None):
            try:
                self._connected_library_service.drive_mounts_changed.disconnect(self._on_drive_mounts_changed)
            except Exception:
                pass
            self._connected_library_service = None

        self._context = context
        svc = self._get_library_service()
        if svc and hasattr(svc, "drive_mounts_changed"):
            svc.drive_mounts_changed.connect(self._on_drive_mounts_changed)
            self._connected_library_service = svc

        self.refresh_library()
        if self.isVisible() and not self._poll_timer.isActive():
            self._poll_timer.start(3000)

    def _on_poll_timer_tick(self):
        """Periodic lightweight check for drive mounts (logical roots only)."""
        svc = self._get_library_service()
        if svc and hasattr(svc, "check_drive_mounts"):
            svc.check_drive_mounts()

    def _on_drive_mounts_changed(self):
        """Live response when a drive is plugged in, unplugged, or mounted to a new letter."""
        # 1. Save scroll position
        scroll_val = 0
        if self.scroll and self.scroll.verticalScrollBar():
            scroll_val = self.scroll.verticalScrollBar().value()

        # 2. Save active selection states
        saved_selected_ids = set(self._selected_ids)
        saved_last_id = self._last_selected_id
        saved_folder_card_rel = getattr(self._selected_folder_card, "rel_path", None) if self._selected_folder_card else None
        saved_folder_data = dict(self._selected_folder_data) if self._selected_folder_data else None

        # 3. Refresh grid in-place (preserves current folder / subpath)
        self.refresh_library(preserve_selection=False)

        # 4. Restore scroll position
        if self.scroll and self.scroll.verticalScrollBar():
            self.scroll.verticalScrollBar().setValue(scroll_val)

        svc = self._get_library_service()
        if not svc:
            return

        # 5. Restore folder selection & update Inspector
        if saved_folder_card_rel:
            for fc in self._folder_cards:
                if fc.rel_path == saved_folder_card_rel:
                    fc.set_selected(True)
                    self._selected_folder_card = fc
                    break

            if saved_folder_data:
                loc_id = saved_folder_data.get("location_id")
                loc = svc.get_location(loc_id) if loc_id else None
                if loc:
                    avail = svc.get_location_availability(loc)
                    saved_folder_data["availability"] = avail.value if hasattr(avail, "value") else str(avail)
                self._selected_folder_data = saved_folder_data
                self.folder_selected.emit(saved_folder_data)

        # 6. Restore asset selection & update Inspector
        if saved_selected_ids:
            self.select_assets(list(saved_selected_ids))
            target_aid = saved_last_id or (next(iter(saved_selected_ids)) if saved_selected_ids else None)
            if target_aid:
                asset_obj = svc.get_asset(target_aid)
                if asset_obj:
                    self.asset_selected.emit(asset_obj)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._poll_timer.isActive():
            self._poll_timer.start(3000)

    def hideEvent(self, event):
        super().hideEvent(event)
        if self._poll_timer.isActive():
            self._poll_timer.stop()

    def closeEvent(self, event):
        super().closeEvent(event)
        if self._poll_timer.isActive():
            self._poll_timer.stop()

    def show_library(self):
        """Refresh and display the global asset library."""
        if not self._poll_timer.isActive():
            self._poll_timer.start(3000)
        self.refresh_library()

    def refresh_library(self, preserve_selection: bool = True):
        """Rebuild the visual card grid from the active LibraryService state."""
        if not self._pending_selection and preserve_selection:
            for aid, card in self._cards.items():
                if getattr(card, "_selected", False):
                    self._pending_selection = aid
                    break

        svc = self._get_library_service()

        # Update Breadcrumb
        if self._search_query:
            self.breadcrumb_label.setText(f'🔍 Search: "{self._search_query}"')
        elif not self._current_location_id:
            self.breadcrumb_label.setText("📁 All Library Locations")
        else:
            loc = svc.get_location(self._current_location_id) if svc else None
            loc_name = loc.display_name if loc else "Location"
            if self._current_subpath:
                self.breadcrumb_label.setText(f"📁 {loc_name} / {self._current_subpath}")
            else:
                self.breadcrumb_label.setText(f"📁 {loc_name}")

        # Clear existing grid widgets
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
        self._selected_folder_card = None

        if not svc:
            self._show_empty_state("Library service unavailable.")
            return

        locations = svc.get_locations()
        if not locations:
            self._show_empty_state(
                "No Library Locations Registered\n\n"
                "Drag and drop folders or files from external drives here,\n"
                "or click 'Add Library Location' to catalog assets in-place without copying."
            )
            return

        # ---------------------------------------------------------------------
        # View 1: Root / All Locations View (NO search)
        # ---------------------------------------------------------------------
        if not self._current_location_id and not self._search_query:
            # Display ONLY registered locations as top-level folder cards
            folder_cards = []
            for loc in locations:
                drive = svc.get_drive(loc.drive_id)
                drive_name = drive.name if drive else "External Drive"
                drive_label = f"[{drive_name}]"
                f_name = f"{loc.display_name} {drive_label}"

                avail = svc.get_location_availability(loc)
                loc_assets = svc.query_assets(location_id=loc.location_id)
                item_count = len(loc_assets)

                folder_data = {
                    "type": "location",
                    "location_id": loc.location_id,
                    "name": loc.display_name,
                    "drive_name": drive_name,
                    "relative_path": loc.drive_relative_path or "/",
                    "availability": avail.value if hasattr(avail, "value") else str(avail),
                    "asset_count": item_count,
                    "favorite": bool(getattr(loc, "favorite", False)),
                }

                f_card = FolderCard(
                    f_name,
                    loc.location_id,
                    size=self.card_size,
                    item_count=item_count,
                    availability=avail.value if hasattr(avail, "value") else str(avail),
                    is_favorite=bool(getattr(loc, "favorite", False)),
                )
                f_card.clicked.connect(lambda lid, fc=f_card, fd=folder_data: self._on_folder_card_clicked(fc, fd))
                f_card.double_clicked.connect(lambda lid=loc.location_id: self._navigate_into_location(lid))
                f_card.context_requested.connect(lambda lid, fd=folder_data: self._on_location_folder_context(fd))
                folder_cards.append(f_card)

            self._folder_cards = folder_cards
            self._populate_grid(folder_cards, [])
            total_assets = len(svc.query_assets())
            self.title_label.setText(f"📚 Global Asset Library ({len(locations)} locations, {total_assets} assets)")
            return

        # ---------------------------------------------------------------------
        # View 2: Location Subfolder View or Global Search Results View
        # ---------------------------------------------------------------------
        folder_cards = []

        # If inside a location, add a Parent Directory [⬆ Up] folder card
        if self._current_location_id and not self._search_query:
            parent_card = FolderCard(
                "Parent Directory",
                "..",
                size=self.card_size,
                is_parent_nav=True,
            )
            parent_card.double_clicked.connect(self._navigate_up)
            folder_cards.append(parent_card)

        # Query assets
        if self._search_query:
            matched_assets = svc.query_assets(query=self._search_query)
            display_assets = matched_assets
        elif self._current_location_id:
            loc = svc.get_location(self._current_location_id)
            loc_assets = svc.query_assets(location_id=self._current_location_id)
            avail = svc.get_location_availability(loc) if loc else AssetAvailability.AVAILABLE
            drive = svc.get_drive(loc.drive_id) if loc else None
            drive_name = drive.name if drive else "External Drive"

            base_rel = loc.drive_relative_path.replace("\\", "/").strip("/") if loc else ""
            sub_prefix = self._current_subpath.replace("\\", "/").strip("/")

            subdirs_found: Dict[str, int] = {}  # dname -> child asset count
            level_assets: List[LibraryAsset] = []

            for a in loc_assets:
                a_rel = a.drive_relative_path.replace("\\", "/").strip("/")

                # Determine relative path from location base
                if base_rel:
                    if a_rel == base_rel:
                        rel_inside_loc = ""
                    elif a_rel.startswith(base_rel + "/"):
                        rel_inside_loc = a_rel[len(base_rel) + 1:]
                    else:
                        rel_inside_loc = a_rel
                else:
                    rel_inside_loc = a_rel

                # Check if matches current subpath level
                if sub_prefix:
                    if not rel_inside_loc.startswith(sub_prefix + "/"):
                        continue
                    inside_sub = rel_inside_loc[len(sub_prefix) + 1:]
                else:
                    inside_sub = rel_inside_loc

                parts = inside_sub.split("/")
                if len(parts) > 1:
                    dname = parts[0]
                    subdirs_found[dname] = subdirs_found.get(dname, 0) + 1
                else:
                    level_assets.append(a)

            for dname, count in sorted(subdirs_found.items()):
                new_sub = f"{sub_prefix}/{dname}".strip("/") if sub_prefix else dname
                folder_data = {
                    "type": "subfolder",
                    "location_id": self._current_location_id,
                    "subpath": new_sub,
                    "name": dname,
                    "drive_name": drive_name,
                    "relative_path": f"{base_rel}/{new_sub}".strip("/"),
                    "availability": avail.value if hasattr(avail, "value") else str(avail),
                    "asset_count": count,
                    "favorite": False,
                }
                f_card = FolderCard(
                    dname,
                    new_sub,
                    size=self.card_size,
                    item_count=count,
                    availability=avail.value if hasattr(avail, "value") else str(avail),
                )
                f_card.clicked.connect(lambda sub, fc=f_card, fd=folder_data: self._on_folder_card_clicked(fc, fd))
                f_card.double_clicked.connect(lambda sub=new_sub: self._navigate_into_subpath(sub))
                f_card.context_requested.connect(lambda sub, fd=folder_data: self._on_subfolder_context(fd))
                folder_cards.append(f_card)

            display_assets = level_assets
        else:
            display_assets = svc.query_assets()

        self._folder_cards = folder_cards
        self._populate_grid(folder_cards, display_assets)
        self.title_label.setText(f"📚 Global Asset Library ({len(display_assets)} items)")

    def _populate_grid(self, folder_cards: List[FolderCard], assets: List[LibraryAsset]):
        """Populate the flow grid layout with folder cards and asset cards."""
        thumb_svc = getattr(self._context, "thumbnail_service", None) if self._context else None
        svc = self._get_library_service()

        all_widgets = []
        for fc in folder_cards:
            all_widgets.append((None, fc))

        for a in assets:
            avail = svc.get_asset_availability(a) if svc else AssetAvailability.AVAILABLE
            drive = svc.get_drive(a.drive_id) if svc else None
            drive_name = drive.name if drive else "External Drive"

            asset_dict = a.to_dict()
            asset_dict["availability"] = avail.value if hasattr(avail, "value") else str(avail)
            asset_dict["drive_name"] = drive_name
            # Resolve physical path for direct thumbnail and launch
            abs_p = svc.resolve_asset_path(a) if svc else None
            if abs_p:
                asset_dict["absolute_path"] = str(abs_p)

            card = AssetCard(
                asset=asset_dict,
                size=self.card_size,
                thumbnail_service=thumb_svc,
            )
            card.clicked.connect(self._on_card_clicked)
            card.double_clicked.connect(self._on_card_double_clicked)
            card.context_requested.connect(self._on_card_context)

            self._cards[a.id] = card
            self._card_order.append(a.id)
            all_widgets.append((a.id, card))

        # Flow into columns based on viewport width
        avail_w = max(400, self.scroll.viewport().width() - 40) if self.scroll.viewport() else 800
        col_w = self.card_size.width() + 14
        cols = max(1, avail_w // col_w)

        for idx, (aid, widget) in enumerate(all_widgets):
            row = idx // cols
            col = idx % cols
            self.grid.addWidget(widget, row, col)

        # Restore pending selection
        if self._pending_selection and self._pending_selection in self._cards:
            sel_id = self._pending_selection
            self._pending_selection = None
            self.select_assets([sel_id])
        else:
            self._pending_selection = None

        self.assets_loaded.emit()

    def _show_empty_state(self, message: str):
        """Render a clean empty state placeholder."""
        empty_lbl = QLabel(message)
        empty_lbl.setAlignment(Qt.AlignCenter)
        empty_lbl.setStyleSheet("color: #64748B; font-size: 13px; padding: 60px; line-height: 1.5;")
        self.grid.addWidget(empty_lbl, 0, 0, 1, 4)

    # -------------------------------------------------------------------------
    # Navigation
    # -------------------------------------------------------------------------

    def navigate_to_asset(self, asset_id_or_data) -> bool:
        """Navigate directly to the containing Library folder and select/highlight the exact asset.

        Works seamlessly whether the drive is Available or Offline by leveraging
        the cataloged library_asset_id, drive_id, and drive_relative_path.
        """
        svc = self._get_library_service()
        if not svc:
            return False

        target_asset: Optional[LibraryAsset] = None
        if isinstance(asset_id_or_data, str):
            target_asset = svc.get_asset(asset_id_or_data)
        elif isinstance(asset_id_or_data, dict):
            lib_id = asset_id_or_data.get("library_asset_id") or asset_id_or_data.get("id")
            if lib_id:
                target_asset = svc.get_asset(lib_id)
            if not target_asset:
                drive_id = asset_id_or_data.get("drive_id")
                drive_rel = asset_id_or_data.get("drive_relative_path")
                if drive_id and drive_rel:
                    target_asset = svc.get_asset_by_drive_path(drive_id, drive_rel)
        elif hasattr(asset_id_or_data, "id"):
            target_asset = asset_id_or_data

        if not target_asset:
            return False

        # Reset search filter to display folder hierarchy
        self._search_query = ""
        if hasattr(self, "search_edit") and self.search_edit:
            self.search_edit.blockSignals(True)
            self.search_edit.clear()
            self.search_edit.blockSignals(False)

        # Resolve location and subpath
        loc = svc.get_location(target_asset.location_id) if target_asset.location_id else None
        a_rel = target_asset.drive_relative_path.replace("\\", "/").strip("/")

        if not loc and target_asset.drive_id:
            # Fallback: locate best matching location on the drive
            candidates = svc.get_locations(drive_id=target_asset.drive_id)
            best_loc = None
            best_len = -1
            for cand in candidates:
                cand_rel = cand.drive_relative_path.replace("\\", "/").strip("/")
                if cand_rel == "" or a_rel == cand_rel or a_rel.startswith(cand_rel + "/"):
                    if len(cand_rel) > best_len:
                        best_len = len(cand_rel)
                        best_loc = cand
            loc = best_loc

        if loc:
            self._current_location_id = loc.location_id
            base_rel = loc.drive_relative_path.replace("\\", "/").strip("/")
            if base_rel:
                if a_rel == base_rel:
                    rel_inside_loc = ""
                elif a_rel.startswith(base_rel + "/"):
                    rel_inside_loc = a_rel[len(base_rel) + 1:]
                else:
                    rel_inside_loc = a_rel
            else:
                rel_inside_loc = a_rel

            parent = str(PurePosixPath(rel_inside_loc).parent)
            self._current_subpath = "" if parent == "." else parent
        else:
            self._current_location_id = None
            self._current_subpath = ""

        # Refresh library and select target asset
        self.refresh_library(preserve_selection=False)
        self.select_assets([target_asset.id])
        return True

    def _navigate_into_location(self, location_id: str):
        self._current_location_id = location_id
        self._current_subpath = ""
        self.refresh_library()

    def _navigate_into_subpath(self, subpath: str):
        self._current_subpath = subpath
        self.refresh_library()

    def _navigate_up(self):
        if self._current_subpath:
            parent = str(PurePosixPath(self._current_subpath).parent)
            self._current_subpath = "" if parent == "." else parent
        else:
            self._current_location_id = None
            self._current_subpath = ""
        self.refresh_library()

    def _on_search_changed(self, text: str):
        self._search_query = text.strip()
        self.refresh_library(preserve_selection=False)

    # -------------------------------------------------------------------------
    # Drag & Drop Ingestion (Strict Zero Copy In-Place Registration)
    # -------------------------------------------------------------------------

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
        mime = event.mimeData() if hasattr(event, "mimeData") else None
        if not mime or not hasattr(mime, "urls"):
            event.ignore()
            return

        urls = mime.urls()
        paths = []
        for u in urls:
            if hasattr(u, "toLocalFile") and u.isLocalFile():
                paths.append(Path(u.toLocalFile()).resolve())
            elif isinstance(u, (str, Path)):
                paths.append(Path(u).resolve())

        if not paths:
            event.ignore()
            return

        svc = self._get_library_service()
        if not svc:
            event.ignore()
            return

        registered_any = False
        for p in paths:
            if not p.exists():
                continue

            if p.is_dir():
                # Directory dropped: register entire folder as a LibraryLocation
                try:
                    svc.add_library_location(p, display_name=p.name, scan_immediately=True)
                    registered_any = True
                except Exception:
                    pass
            elif p.is_file():
                # Single file dropped: register containing folder if not already covered
                parent_dir = p.parent
                try:
                    existing_locs = svc.get_locations()
                    covered = False
                    for loc in existing_locs:
                        res = svc.drive_detector.resolve_drive_path(loc.drive_id, loc.drive_relative_path)
                        if res and str(p).startswith(str(res)):
                            covered = True
                            svc.scan_location(loc.location_id)
                            break
                    if not covered:
                        svc.add_library_location(parent_dir, display_name=parent_dir.name, scan_immediately=True)
                    registered_any = True
                except Exception:
                    pass

        event.acceptProposedAction()

        if registered_any:
            # Immediate live refresh
            self.refresh_library(preserve_selection=True)

    # -------------------------------------------------------------------------
    # User Actions
    # -------------------------------------------------------------------------

    def _on_add_location_clicked(self):
        folder = QFileDialog.getExistingDirectory(self, "Select External Library Folder to Index")
        if not folder:
            return

        svc = self._get_library_service()
        if not svc:
            return

        try:
            folder_path = Path(folder).resolve()
            loc, drive = svc.add_library_location(folder_path, display_name=folder_path.name, scan_immediately=True)
            self.refresh_library(preserve_selection=True)
            QMessageBox.information(
                self,
                "Library Location Added",
                f"Successfully cataloged '{loc.display_name}' on [{drive.name}].\n\nOriginal files remain in-place on your external drive.",
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not add library location: {e}")

    def _on_rescan_clicked(self):
        svc = self._get_library_service()
        if not svc:
            return
        svc.scan_all_locations()
        self.refresh_library(preserve_selection=True)

    # -------------------------------------------------------------------------
    # Selection & Inspector Dispatch (Cards & Folders)
    # -------------------------------------------------------------------------

    def _on_folder_card_clicked(self, folder_card: FolderCard, folder_data: dict):
        """Single-click on FolderCard selects it and inspects in Inspector."""
        # Deselect all asset cards
        self._selected_ids.clear()
        self._last_selected_id = None
        for card in self._cards.values():
            card.set_selected(False)

        # Deselect other folder cards
        for fc in self._folder_cards:
            fc.set_selected(fc is folder_card)

        self._selected_folder_card = folder_card
        self._selected_folder_data = dict(folder_data) if folder_data else None

        # Emit to Inspector
        self.folder_selected.emit(folder_data)

    def _on_card_clicked(self, asset_id: str):
        # Deselect all folder cards
        for fc in self._folder_cards:
            fc.set_selected(False)
        self._selected_folder_card = None
        self._selected_folder_data = None

        ctrl = bool(QApplication.keyboardModifiers() & Qt.ControlModifier)
        shift = bool(QApplication.keyboardModifiers() & Qt.ShiftModifier)

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
                rng = self._card_order[min(i1, i2):max(i1, i2) + 1]
                self._selected_ids.update(rng)
                self._last_selected_id = asset_id
                self._apply_selection()
            except Exception:
                pass
            return

        self._selected_ids = {asset_id}
        self._last_selected_id = asset_id
        self._apply_selection()

    def select_assets(self, asset_ids: List[str]):
        if not asset_ids:
            self._selected_ids.clear()
            self._last_selected_id = None
            self._apply_selection()
            return
        valid = [aid for aid in self._card_order if aid in asset_ids]
        self._selected_ids = set(valid)
        self._last_selected_id = valid[-1] if valid else None
        self._apply_selection()

    def get_selected_ids(self) -> List[str]:
        return [aid for aid in self._card_order if aid in self._selected_ids]

    def _apply_selection(self):
        for aid, card in list(self._cards.items()):
            try:
                card.set_selected(aid in self._selected_ids)
            except Exception:
                pass

        # Update toolbar button enabled states
        has_sel = bool(self._selected_ids)
        curr_proj = getattr(self._context, "current_project", None) if self._context else None
        has_proj = curr_proj is not None

        if hasattr(self, "btn_ref_project"):
            self.btn_ref_project.setEnabled(has_sel and has_proj)
            if has_proj:
                self.btn_ref_project.setToolTip(f"Add selected asset as a reference to project '{curr_proj.name}'")
            else:
                self.btn_ref_project.setToolTip("No active project open")

        if hasattr(self, "btn_copy_project"):
            self.btn_copy_project.setEnabled(has_sel and has_proj)
            if has_proj:
                self.btn_copy_project.setToolTip(f"Copy selected asset into project '{curr_proj.name}' local storage")
            else:
                self.btn_copy_project.setToolTip("No active project open")

        if self._suppress_selection_emit:
            return

        last = self._last_selected_id or (next(iter(self._selected_ids)) if self._selected_ids else None)
        if last is not None and last in self._cards:
            svc = self._get_library_service()
            asset_obj = svc.get_asset(last) if svc else None
            if asset_obj:
                self.asset_selected.emit(asset_obj)

    def _on_toolbar_reference_clicked(self):
        if not self._selected_ids:
            return
        aid = self._last_selected_id or next(iter(self._selected_ids))
        self._reference_asset_in_project(aid)

    def _on_toolbar_copy_clicked(self):
        if not self._selected_ids:
            return
        aid = self._last_selected_id or next(iter(self._selected_ids))
        self._copy_asset_to_project(aid)

    def _reference_asset_in_project(self, asset_id: str):
        if not self._context:
            return
        curr_proj = getattr(self._context, "current_project", None)
        if not curr_proj:
            QMessageBox.warning(self, "Reference in Project", "No active project is currently open.\nPlease open or select a project first.")
            return

        lib_svc = self._get_library_service()
        asset_svc = getattr(self._context, "asset_service", None)
        if not lib_svc or not asset_svc:
            return

        asset = lib_svc.get_asset(asset_id)
        if not asset:
            return

        entry = asset_svc.add_library_reference(curr_proj, asset, target_category="References")
        lib_svc.log_project_reference(asset_id, curr_proj.location, curr_proj.name, mode="reference")

        # Update inspector if currently inspected
        if self._selected_ids and asset_id in self._selected_ids:
            self.asset_selected.emit(asset)

        QMessageBox.information(
            self,
            "Referenced in Project",
            f"Successfully referenced '{asset.filename}' in project '{curr_proj.name}' References.\n\n"
            f"Original file remains on the external drive without being copied.",
        )

    def _copy_asset_to_project(self, asset_id: str):
        if not self._context:
            return
        curr_proj = getattr(self._context, "current_project", None)
        if not curr_proj:
            QMessageBox.warning(self, "Copy to Project", "No active project is currently open.\nPlease open or select a project first.")
            return

        lib_svc = self._get_library_service()
        asset_svc = getattr(self._context, "asset_service", None)
        if not lib_svc or not asset_svc:
            return

        asset = lib_svc.get_asset(asset_id)
        if not asset:
            return

        try:
            copied_entry = asset_svc.copy_library_asset(curr_proj, asset, lib_svc, target_section="References")
            if copied_entry:
                QMessageBox.information(
                    self,
                    "Copied to Project",
                    f"Successfully copied '{asset.filename}' into project '{curr_proj.name}' References.\n\n"
                    f"Created an independent local copy.",
                )
            else:
                QMessageBox.warning(self, "Copy to Project", "Unable to complete asset copy.")
        except Exception as e:
            QMessageBox.critical(self, "Copy to Project", f"Failed to copy asset to project: {e}")

    def select_assets(self, asset_ids: list):
        if not asset_ids:
            self._selected_ids = set()
            self._last_selected_id = None
            self._apply_selection()
            return
        valid = [aid for aid in self._card_order if aid in asset_ids]
        self._selected_ids = set(valid)
        self._last_selected_id = valid[-1] if valid else None
        self._apply_selection()

    def _on_card_double_clicked(self, asset_id: str):
        svc = self._get_library_service()
        if not svc:
            return
        asset = svc.get_asset(asset_id)
        if not asset:
            return
        phys_path = svc.resolve_asset_path(asset)
        if not phys_path or not phys_path.exists():
            QMessageBox.warning(
                self,
                "Asset Offline",
                f"Cannot open '{asset.filename}'.\n\nThe source drive is currently disconnected or the file is missing.",
            )
            return
        try:
            if os.name == "nt":
                os.startfile(str(phys_path))
            else:
                subprocess.Popen(["xdg-open" if os.name == "posix" else "open", str(phys_path)])
        except Exception as e:
            QMessageBox.warning(self, "Open Asset", f"Unable to open asset: {e}")

    # -------------------------------------------------------------------------
    # Context Menus & Safe Removal Semantics
    # -------------------------------------------------------------------------

    def _on_card_context(self, asset_id: str):
        svc = self._get_library_service()
        if not svc:
            return
        asset = svc.get_asset(asset_id)
        if not asset:
            return

        menu = QMenu(self)
        phys_path = svc.resolve_asset_path(asset)
        is_online = phys_path is not None and phys_path.exists()

        # 1. Open
        open_action = QAction("Open", self)
        open_action.setEnabled(is_online)
        open_action.triggered.connect(lambda: self._on_card_double_clicked(asset_id))
        menu.addAction(open_action)

        # 2. Reveal in Explorer
        reveal_action = QAction("Reveal in Explorer", self)
        reveal_action.setEnabled(is_online)
        reveal_action.triggered.connect(lambda: self._reveal_path(phys_path))
        menu.addAction(reveal_action)

        menu.addSeparator()

        # 3. Add to Project Submenu
        curr_proj = getattr(self._context, "current_project", None) if self._context else None
        proj_menu = menu.addMenu("Add to Project")
        if not curr_proj:
            proj_menu.setEnabled(False)
            proj_menu.setTitle("Add to Project (No Active Project)")
        else:
            ref_act = QAction(f"📎 Reference in '{curr_proj.name}'", self)
            ref_act.setStatusTip("Reference this library asset in the project without copying the file.")
            ref_act.triggered.connect(lambda: self._reference_asset_in_project(asset_id))
            proj_menu.addAction(ref_act)

            copy_act = QAction(f"📋 Copy to '{curr_proj.name}'", self)
            copy_act.setEnabled(is_online)
            copy_act.setStatusTip("Make an independent project-local copy of this asset in References.")
            copy_act.triggered.connect(lambda: self._copy_asset_to_project(asset_id))
            proj_menu.addAction(copy_act)

        menu.addSeparator()

        # 4. Add to / Remove from Favorites
        is_fav = bool(getattr(asset, "favorite", False))
        fav_text = "Remove from Favorites" if is_fav else "Add to Favorites"
        fav_action = QAction(fav_text, self)
        fav_action.triggered.connect(lambda: self._toggle_asset_favorite(asset_id, not is_fav))
        menu.addAction(fav_action)

        menu.addSeparator()

        # 5. Safe Remove from Library (DEFAULT)
        remove_action = QAction("Remove from Library", self)
        remove_action.setStatusTip("Remove this asset from the Library catalog without deleting the original file.")
        remove_action.triggered.connect(lambda: self._remove_single_asset(asset_id, delete_file=False))
        menu.addAction(remove_action)

        # 6. Explicit Destructive Delete Original File
        delete_action = QAction("Delete Original File...", self)
        delete_action.setEnabled(is_online)
        delete_action.triggered.connect(lambda: self._confirm_and_delete_asset(asset_id))
        menu.addAction(delete_action)

        menu.exec(QCursor.pos())

    def _on_location_folder_context(self, folder_data: dict):
        svc = self._get_library_service()
        if not svc:
            return
        location_id = folder_data.get("location_id")
        loc = svc.get_location(location_id)
        if not loc:
            return

        menu = QMenu(self)
        phys_root = svc.drive_detector.resolve_drive_path(loc.drive_id, loc.drive_relative_path)
        is_online = phys_root is not None and phys_root.exists()

        # 1. Open
        open_action = QAction("Open", self)
        open_action.triggered.connect(lambda: self._navigate_into_location(location_id))
        menu.addAction(open_action)

        # 2. Reveal in Explorer
        reveal_action = QAction("Reveal in Explorer", self)
        reveal_action.setEnabled(is_online)
        reveal_action.triggered.connect(lambda: self._reveal_path(phys_root))
        menu.addAction(reveal_action)

        menu.addSeparator()

        # 3. Add to / Remove from Favorites
        is_fav = bool(getattr(loc, "favorite", False))
        fav_text = "Remove from Favorites" if is_fav else "Add to Favorites"
        fav_action = QAction(fav_text, self)
        fav_action.triggered.connect(lambda: self._toggle_location_favorite(location_id, not is_fav))
        menu.addAction(fav_action)

        menu.addSeparator()

        # 4. Safe Remove Folder from Library (DEFAULT)
        remove_action = QAction("Remove Folder from Library", self)
        remove_action.setStatusTip("Remove this folder from the Library catalog. Original files remain untouched.")
        remove_action.triggered.connect(lambda: self._remove_location(location_id, delete_folder=False))
        menu.addAction(remove_action)

        # 5. Explicit Destructive Delete Original Folder
        delete_action = QAction("Delete Original Folder...", self)
        delete_action.setEnabled(is_online)
        delete_action.triggered.connect(lambda: self._confirm_and_delete_location(location_id))
        menu.addAction(delete_action)

        menu.exec(QCursor.pos())

    def _on_subfolder_context(self, folder_data: dict):
        svc = self._get_library_service()
        if not svc:
            return
        location_id = folder_data.get("location_id")
        loc = svc.get_location(location_id)
        subpath = folder_data.get("subpath", "")

        phys_sub = None
        if loc:
            loc_root = svc.drive_detector.resolve_drive_path(loc.drive_id, loc.drive_relative_path)
            if loc_root:
                phys_sub = loc_root / subpath

        is_online = phys_sub is not None and phys_sub.exists()

        menu = QMenu(self)

        # 1. Open
        open_action = QAction("Open", self)
        open_action.triggered.connect(lambda: self._navigate_into_subpath(subpath))
        menu.addAction(open_action)

        # 2. Reveal in Explorer
        reveal_action = QAction("Reveal in Explorer", self)
        reveal_action.setEnabled(is_online)
        reveal_action.triggered.connect(lambda: self._reveal_path(phys_sub))
        menu.addAction(reveal_action)

        menu.exec(QCursor.pos())

    def _toggle_asset_favorite(self, asset_id: str, favorite: bool):
        svc = self._get_library_service()
        if not svc:
            return
        svc.update_asset(asset_id, favorite=favorite)
        self.refresh_library(preserve_selection=True)

    def _toggle_location_favorite(self, location_id: str, favorite: bool):
        svc = self._get_library_service()
        if not svc:
            return
        svc.update_location(location_id, favorite=favorite)
        self.refresh_library(preserve_selection=True)

    def _reveal_path(self, target_path: Optional[Path]):
        if not target_path or not target_path.exists():
            return
        try:
            if os.name == "nt":
                if target_path.is_dir():
                    os.startfile(str(target_path))
                else:
                    subprocess.Popen(f'explorer /select,"{str(target_path)}"')
            else:
                subprocess.Popen(["xdg-open" if os.name == "posix" else "open", str(target_path.parent)])
        except Exception:
            pass

    def _remove_single_asset(self, asset_id: str, delete_file: bool = False):
        svc = self._get_library_service()
        if not svc:
            return
        svc.remove_asset(asset_id, delete_file=delete_file)
        self.refresh_library(preserve_selection=False)

    def _remove_selected_assets(self, delete_files: bool = False):
        """Safe removal handler for keyboard shortcut or menu actions."""
        svc = self._get_library_service()
        if not svc or not self._selected_ids:
            return
        for aid in list(self._selected_ids):
            svc.remove_asset(aid, delete_file=delete_files)
        self._selected_ids.clear()
        self._last_selected_id = None
        self.refresh_library(preserve_selection=False)

    def _confirm_and_delete_asset(self, asset_id: str):
        svc = self._get_library_service()
        if not svc:
            return
        asset = svc.get_asset(asset_id)
        if not asset:
            return

        confirm = QMessageBox.warning(
            self,
            "Delete Original File",
            f"Are you sure you want to permanently delete the original file '{asset.filename}' from disk?\n\n"
            "This action is permanent and cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self._remove_single_asset(asset_id, delete_file=True)

    def _remove_location(self, location_id: str, delete_folder: bool = False):
        svc = self._get_library_service()
        if not svc:
            return
        svc.remove_library_location(location_id, remove_assets=True, delete_folder=delete_folder)
        if self._current_location_id == location_id:
            self._current_location_id = None
            self._current_subpath = ""
        self.refresh_library(preserve_selection=False)

    def _confirm_and_delete_location(self, location_id: str):
        svc = self._get_library_service()
        if not svc:
            return
        loc = svc.get_location(location_id)
        if not loc:
            return

        confirm = QMessageBox.warning(
            self,
            "Delete Original Folder",
            f"Are you sure you want to permanently delete the original folder '{loc.display_name}' and ALL its files from disk?\n\n"
            "This action is permanent and cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self._remove_location(location_id, delete_folder=True)

    # -------------------------------------------------------------------------
    # Service Helpers
    # -------------------------------------------------------------------------

    def _get_library_service(self):
        if self._context and getattr(self._context, "library_service", None):
            return self._context.library_service
        return None
