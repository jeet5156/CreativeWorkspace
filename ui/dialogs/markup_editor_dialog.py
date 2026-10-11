"""Markup Editor Dialog for Visual Annotations on Project and Library Assets.

Provides a dedicated workspace with an interactive markup canvas,
real-time bidirectional annotations list and navigation panel,
and atomic persistence via MarkupService.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from PySide6.QtCore import QPointF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from models.markup import MarkupDocument
from services.markup_service import MarkupService
from ui.widgets.markup_canvas import MarkupCanvas, MarkupTool


# -----------------------------------------------------------------------------
# Custom List Item Widget for Annotation Row
# -----------------------------------------------------------------------------

class AnnotationRowWidget(QWidget):
    """Clean representation of an individual annotation row in the side panel."""

    def __init__(self, annotation_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.annotation_data = annotation_data
        self.annotation_id = str(annotation_data.get("id", ""))
        self.annotation_type = str(annotation_data.get("type", "text")).lower()

        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # 1. Type Icon
        if self.annotation_type in ("text", "pin", "callout"):
            icon_str = "📍"
            title_str = self.annotation_data.get("text") or "Note Pin"
            pos = self.annotation_data.get("position") or {"x": 0.0, "y": 0.0}
            px = int(round(float(pos.get("x", 0.0) if isinstance(pos, dict) else pos[0]) * 100))
            py = int(round(float(pos.get("y", 0.0) if isinstance(pos, dict) else pos[1]) * 100))
            detail_str = f"({px}%, {py}%)"
        elif self.annotation_type == "arrow":
            icon_str = "↗"
            title_str = "Directional Arrow"
            start = self.annotation_data.get("start") or {"x": 0.0, "y": 0.0}
            end = self.annotation_data.get("end") or {"x": 0.0, "y": 0.0}
            sx = int(round(float(start.get("x", 0.0) if isinstance(start, dict) else start[0]) * 100))
            sy = int(round(float(start.get("y", 0.0) if isinstance(start, dict) else start[1]) * 100))
            ex = int(round(float(end.get("x", 0.0) if isinstance(end, dict) else end[0]) * 100))
            ey = int(round(float(end.get("y", 0.0) if isinstance(end, dict) else end[1]) * 100))
            detail_str = f"{sx}%,{sy}% → {ex}%,{ey}%"
        elif self.annotation_type in ("freehand", "draw", "stroke"):
            icon_str = "✏"
            title_str = "Freehand Stroke"
            pts = self.annotation_data.get("points") or []
            detail_str = f"{len(pts)} pts"
        elif self.annotation_type in ("rectangle", "rect", "box"):
            icon_str = "▢"
            title_str = "Rectangle"
            detail_str = "Box"
        elif self.annotation_type in ("ellipse", "circle"):
            icon_str = "◯"
            title_str = "Ellipse"
            detail_str = "Circle"
        else:
            icon_str = "🏷️"
            title_str = "Annotation"
            detail_str = ""

        # Icon Label
        lbl_icon = QLabel(icon_str)
        lbl_icon.setStyleSheet("font-size: 13px; background: transparent;")
        layout.addWidget(lbl_icon)

        # Title / Note text
        lbl_title = QLabel(title_str)
        lbl_title.setFont(QFont("Segoe UI", 9, QFont.Bold if self.annotation_type in ("text", "pin") else QFont.Normal))
        lbl_title.setStyleSheet("color: #F1F5F9; background: transparent;")
        lbl_title.setWordWrap(False)
        layout.addWidget(lbl_title, 1)

        # Position / Details badge
        if detail_str:
            lbl_detail = QLabel(detail_str)
            lbl_detail.setFont(QFont("Segoe UI", 8))
            lbl_detail.setStyleSheet("""
                QLabel {
                    color: #94A3B8;
                    background-color: #1E2235;
                    border: 1px solid #2E334D;
                    border-radius: 4px;
                    padding: 1px 5px;
                }
            """)
            layout.addWidget(lbl_detail)


# -----------------------------------------------------------------------------
# Main Markup Editor Dialog
# -----------------------------------------------------------------------------

class MarkupEditorDialog(QDialog):
    """Complete full-featured Visual Markup Editor window with canvas and side navigation."""

    def __init__(
        self,
        image_source: Union[str, Path, QPixmap],
        source_reference: Dict[str, Any],
        markup_service: Optional[MarkupService] = None,
        context=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setModal(True)
        self.resize(1150, 750)
        self.setMinimumSize(850, 550)

        self._image_source = image_source
        self._source_reference = copy_ref = dict(source_reference)
        self._context = context
        self._markup_service = markup_service or (getattr(context, "markup_service", None) if context else None) or MarkupService()

        # Resolve asset title and path
        self._asset_name = self._resolve_asset_name()
        self.setWindowTitle(f"Markup: {self._asset_name}")

        self._document: Optional[MarkupDocument] = None
        self._is_updating_list_selection = False

        self._setup_ui()
        self._load_image_and_document()

    def _resolve_asset_name(self) -> str:
        """Resolve a human-readable title for the image being annotated."""
        rel_path = self._source_reference.get("relative_path")
        if rel_path:
            return Path(rel_path).name

        if isinstance(self._image_source, (str, Path)):
            return Path(self._image_source).name

        return "Image Reference"

    # -------------------------------------------------------------------------
    # UI Setup
    # -------------------------------------------------------------------------

    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #12141C;
                color: #F1F5F9;
            }
            QSplitter::handle {
                background-color: #24283B;
                width: 1px;
            }
            QListWidget {
                background-color: #141724;
                border: 1px solid #24283B;
                border-radius: 6px;
                color: #F1F5F9;
                outline: none;
                padding: 4px;
            }
            QListWidget::item {
                border-radius: 6px;
                margin-bottom: 3px;
                padding: 2px;
            }
            QListWidget::item:hover {
                background-color: #1E2337;
            }
            QListWidget::item:selected {
                background-color: #283556;
                border: 1px solid #38BDF8;
            }
            QPushButton#btnClose {
                background-color: #1E2029;
                color: #CBD5E1;
                border: 1px solid #2E3342;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#btnClose:hover {
                background-color: #283556;
                color: #38BDF8;
                border-color: #38BDF8;
            }
            QPushButton#btnDeleteAnn {
                background-color: #1E2029;
                color: #EF4444;
                border: 1px solid #3B2428;
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#btnDeleteAnn:hover {
                background-color: #EF4444;
                color: #FFFFFF;
            }
            QPushButton#btnDeleteAnn:disabled {
                background-color: #141620;
                color: #475569;
                border-color: #202330;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Header Bar
        header_bar = self._create_header_bar()
        main_layout.addWidget(header_bar)

        # 2. Main Content Splitter (Canvas on Left, Annotations on Right)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setContentsMargins(0, 0, 0, 0)

        # Left Canvas Widget
        self.canvas = MarkupCanvas(self)
        self.canvas.set_markup_service(self._markup_service)
        self.splitter.addWidget(self.canvas)

        # Right Side Panel (Annotations List & Navigation)
        self.side_panel = self._create_side_panel()
        self.splitter.addWidget(self.side_panel)

        # Splitter sizing: 75% Canvas, 25% Side Panel
        self.splitter.setSizes([850, 300])
        main_layout.addWidget(self.splitter, 1)

        # Connect Canvas Signals to Side Panel
        self.canvas.annotation_selected.connect(self._on_canvas_annotation_selected)
        self.canvas.annotation_created.connect(self._on_canvas_annotation_created)
        self.canvas.view.undo_stack_changed.connect(self._on_document_mutated)

    def _create_header_bar(self) -> QWidget:
        header = QFrame()
        header.setFixedHeight(48)
        header.setStyleSheet("""
            QFrame {
                background-color: #141620;
                border-bottom: 1px solid #24283B;
                padding: 0 16px;
            }
        """)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        # Icon + Asset Name
        lbl_icon = QLabel("🖼️")
        lbl_icon.setStyleSheet("font-size: 16px; background: transparent;")
        layout.addWidget(lbl_icon)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(1)
        title_layout.setAlignment(Qt.AlignVCenter)

        lbl_title = QLabel(f"Visual Markup: {self._asset_name}")
        lbl_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        lbl_title.setStyleSheet("color: #F1F5F9; background: transparent;")
        title_layout.addWidget(lbl_title)

        source_type_str = self._source_reference.get("source_type", "asset").replace("_", " ").title()
        rel_path = self._source_reference.get("relative_path", "")
        lbl_sub = QLabel(f"{source_type_str} • {rel_path}" if rel_path else source_type_str)
        lbl_sub.setFont(QFont("Segoe UI", 8))
        lbl_sub.setStyleSheet("color: #64748B; background: transparent;")
        title_layout.addWidget(lbl_sub)

        layout.addLayout(title_layout)
        layout.addStretch()

        # Counter Badge
        self.lbl_counter = QLabel("0 Annotations")
        self.lbl_counter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.lbl_counter.setStyleSheet("""
            QLabel {
                background-color: #1E2235;
                color: #38BDF8;
                border: 1px solid #2E334D;
                border-radius: 12px;
                padding: 3px 10px;
            }
        """)
        layout.addWidget(self.lbl_counter)

        # Close Button
        btn_close = QPushButton("Done")
        btn_close.setObjectName("btnClose")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

        return header

    def _create_side_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet("background-color: #10121A;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Panel Header
        hdr_layout = QHBoxLayout()
        lbl_hdr = QLabel("ANNOTATIONS")
        lbl_hdr.setFont(QFont("Segoe UI", 10, QFont.Bold))
        lbl_hdr.setStyleSheet("color: #94A3B8; letter-spacing: 0.5px;")
        hdr_layout.addWidget(lbl_hdr)
        hdr_layout.addStretch()

        self.btn_delete_ann = QPushButton("Delete")
        self.btn_delete_ann.setObjectName("btnDeleteAnn")
        self.btn_delete_ann.setEnabled(False)
        self.btn_delete_ann.setToolTip("Delete Selected Annotation (Del)")
        self.btn_delete_ann.clicked.connect(self._on_delete_selected_clicked)
        hdr_layout.addWidget(self.btn_delete_ann)

        layout.addLayout(hdr_layout)

        # Annotations List Widget
        self.ann_list = QListWidget()
        self.ann_list.itemClicked.connect(self._on_list_item_clicked)
        self.ann_list.itemDoubleClicked.connect(self._on_list_item_double_clicked)
        layout.addWidget(self.ann_list, 1)

        # Help Hint
        lbl_hint = QLabel("Click an annotation to focus • Double-click note to edit")
        lbl_hint.setFont(QFont("Segoe UI", 8))
        lbl_hint.setStyleSheet("color: #475569; padding-top: 2px;")
        lbl_hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_hint)

        return panel

    # -------------------------------------------------------------------------
    # Image & Document Loading
    # -------------------------------------------------------------------------

    def _load_image_and_document(self):
        """Load image into canvas and resolve or create persistent MarkupDocument."""
        # 1. Load Image
        self.canvas.set_image(self._image_source)

        # 2. Query Existing Markup for this Source Reference
        existing_markups = self._markup_service.list_markups_for_source(self._source_reference)
        if existing_markups:
            self._document = existing_markups[0]
        else:
            # Create new persistent MarkupDocument
            self._document = self._markup_service.create_markup(
                self._source_reference,
                name=f"Markup: {self._asset_name}",
            )

        # 3. Bind Document to Canvas
        self.canvas.set_document(self._document)
        self._refresh_annotations_list()

    # -------------------------------------------------------------------------
    # Annotations List Synchronization & Navigation
    # -------------------------------------------------------------------------

    def _refresh_annotations_list(self):
        """Rebuild the side panel annotations list from document state."""
        self.ann_list.clear()

        doc = self.canvas.document()
        if not doc:
            self.lbl_counter.setText("0 Annotations")
            self.btn_delete_ann.setEnabled(False)
            return

        annotations = doc.annotations
        count = len(annotations)
        self.lbl_counter.setText(f"{count} Annotation{'s' if count != 1 else ''}")

        selected_id = self.canvas.selected_annotation_id()
        selected_item = None

        for ann in annotations:
            ann_id = str(ann.get("id", ""))
            item = QListWidgetItem(self.ann_list)
            item.setData(Qt.UserRole, ann_id)

            row_widget = AnnotationRowWidget(ann, self.ann_list)
            item.setSizeHint(QSize(240, 36))

            self.ann_list.addItem(item)
            self.ann_list.setItemWidget(item, row_widget)

            if ann_id == selected_id:
                selected_item = item

        if selected_item:
            self._is_updating_list_selection = True
            self.ann_list.setCurrentItem(selected_item)
            self.btn_delete_ann.setEnabled(True)
            self._is_updating_list_selection = False
        else:
            self.btn_delete_ann.setEnabled(bool(selected_id))

    def _on_canvas_annotation_selected(self, annotation_id: str):
        """Update side panel list selection when canvas selection changes."""
        self.btn_delete_ann.setEnabled(bool(annotation_id))
        if self._is_updating_list_selection:
            return

        self._is_updating_list_selection = True
        if not annotation_id:
            self.ann_list.clearSelection()
            self._is_updating_list_selection = False
            return

        for i in range(self.ann_list.count()):
            item = self.ann_list.item(i)
            if item.data(Qt.UserRole) == annotation_id:
                self.ann_list.setCurrentItem(item)
                self.ann_list.scrollToItem(item)
                break
        self._is_updating_list_selection = False

    def _on_canvas_annotation_created(self, annotation_id: str):
        """Refresh list and select newly created annotation."""
        self._refresh_annotations_list()

    def _on_document_mutated(self):
        """Handle undo/redo mutations."""
        self._refresh_annotations_list()

    def _on_list_item_clicked(self, item: QListWidgetItem):
        """Navigate to and select annotation on canvas when clicked in side panel."""
        if self._is_updating_list_selection or not item:
            return

        ann_id = item.data(Qt.UserRole)
        self.canvas.select_annotation(ann_id)

        # Center viewport on annotation
        ann_data = self.canvas.view.get_annotation_data(ann_id)
        if ann_data and self.canvas.has_image():
            pos = ann_data.get("position") or ann_data.get("start")
            if pos:
                px = float(pos.get("x", 0.0) if isinstance(pos, dict) else pos[0])
                py = float(pos.get("y", 0.0) if isinstance(pos, dict) else pos[1])
                w = self.canvas.view.image_size.width()
                h = self.canvas.view.image_size.height()
                self.canvas.view.centerOn(px * w, py * h)

    def _on_list_item_double_clicked(self, item: QListWidgetItem):
        """Double clicking a text annotation in list prompts editing."""
        if not item:
            return
        ann_id = item.data(Qt.UserRole)
        ann_data = self.canvas.view.get_annotation_data(ann_id)
        if ann_data and ann_data.get("type") in ("text", "pin"):
            from ui.widgets.markup_canvas import NoteInputDialog
            dlg = NoteInputDialog(initial_text=ann_data.get("text", ""), title="Edit Note", parent=self)
            if dlg.exec() == QDialog.Accepted:
                new_txt = dlg.get_text()
                if new_txt:
                    self.canvas.edit_annotation_text(ann_id, new_txt)
                    self._refresh_annotations_list()

    def _on_delete_selected_clicked(self):
        """Delete currently selected annotation."""
        if self.canvas.selected_annotation_id():
            self.canvas.delete_selected_annotation()
            self._refresh_annotations_list()

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @classmethod
    def open_for_project_asset(
        cls,
        project,
        asset_id: str,
        asset_service,
        markup_service: Optional[MarkupService] = None,
        context=None,
        parent=None,
    ) -> Optional["MarkupEditorDialog"]:
        """Factory method to resolve a project asset and open MarkupEditorDialog."""
        if not project or not asset_id or not asset_service:
            return None

        # Resolve asset record
        asset = asset_service.get_asset(project, asset_id) if hasattr(asset_service, "get_asset") else None
        if not asset and isinstance(asset_id, dict):
            asset = asset_id

        if not asset:
            return None

        # Check if asset is a library reference inside the project
        if asset.get("is_library_reference"):
            lib_svc = getattr(context, "library_service", None) if context else None
            return cls.open_for_library_asset(
                asset,
                library_service=lib_svc,
                markup_service=markup_service,
                context=context,
                parent=parent,
            )

        # Resolve physical file path
        phys_path = None
        if hasattr(asset_service, "get_asset_path"):
            phys_path = asset_service.get_asset_path(project, asset.get("id") or asset_id)

        if not phys_path:
            abs_p = asset.get("absolute_path")
            if abs_p and Path(abs_p).exists():
                phys_path = Path(abs_p)
            elif asset.get("relative_path") and hasattr(project, "location"):
                cand = Path(project.location) / asset["relative_path"]
                if cand.exists():
                    phys_path = cand

        if not phys_path or not Path(phys_path).exists():
            return None

        source_ref = {
            "source_type": "project_asset",
            "project_id": str(getattr(project, "id", getattr(project, "name", str(project)))),
            "asset_id": str(asset.get("id", asset_id)),
            "relative_path": str(asset.get("relative_path", "")),
            "category": str(asset.get("category", "References")),
        }

        dlg = cls(
            image_source=str(phys_path),
            source_reference=source_ref,
            markup_service=markup_service,
            context=context,
            parent=parent,
        )
        return dlg

    @classmethod
    def open_for_library_asset(
        cls,
        library_asset: Dict[str, Any],
        library_service,
        markup_service: Optional[MarkupService] = None,
        context=None,
        parent=None,
    ) -> Optional["MarkupEditorDialog"]:
        """Factory method to resolve a library asset and open MarkupEditorDialog."""
        if not library_asset:
            return None

        aid = str(library_asset.get("id", ""))
        drive_id = library_asset.get("drive_id")
        drive_rel = library_asset.get("drive_relative_path")

        phys_path = None
        if library_service and drive_id and drive_rel and hasattr(library_service, "drive_detector"):
            phys_path = library_service.drive_detector.resolve_drive_path(drive_id, drive_rel)

        if not phys_path or not Path(phys_path).exists():
            # Fallback to local_path if exists
            local_p = library_asset.get("local_path")
            if local_p and Path(local_p).exists():
                phys_path = Path(local_p)

        if not phys_path or not Path(phys_path).exists():
            return None

        source_ref = {
            "source_type": "library_asset",
            "library_asset_id": aid,
            "relative_path": str(drive_rel or phys_path.name),
        }

        dlg = cls(
            image_source=str(phys_path),
            source_reference=source_ref,
            markup_service=markup_service,
            context=context,
            parent=parent,
        )
        return dlg
