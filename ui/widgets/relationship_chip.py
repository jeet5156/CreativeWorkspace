"""Relationship Chip Widget for displaying linked projects, library assets, project assets, and lab nodes."""

from typing import Optional, Dict, Any
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
)

from models.library_models import AssetAvailability


class RelationshipChip(QFrame):
    """Interactive visual chip representing a linked external entity with lazy status badge and navigation."""

    clicked = Signal(str, dict)       # (rel_type, target_data)
    remove_requested = Signal(str, dict) # (rel_type, target_data)

    def __init__(self, rel_type: str, data: Dict[str, Any], context=None, parent=None):
        super().__init__(parent)
        self.rel_type = rel_type
        self.data = data
        self._context = context

        self._setup_ui()

    def _setup_ui(self):
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 6, 2)
        layout.setSpacing(6)

        # Resolve human-readable name and status
        icon_str, title_str, status_str, status_color = self._resolve_entity_info()

        # Type Icon + Title
        lbl = QLabel(f"{icon_str}  {title_str}")
        lbl.setFont(QFont("Segoe UI", 9, QFont.Medium))
        lbl.setStyleSheet("color: #F1F5F9; background: transparent;")
        layout.addWidget(lbl)

        # Status Badge
        status_lbl = QLabel(status_str)
        status_lbl.setFont(QFont("Segoe UI", 8, QFont.Bold))
        status_lbl.setStyleSheet(f"""
            QLabel {{
                background-color: {status_color}22;
                color: {status_color};
                border: 1px solid {status_color}55;
                border-radius: 4px;
                padding: 1px 5px;
                font-size: 9px;
            }}
        """)
        layout.addWidget(status_lbl)

        # Remove Button
        btn_remove = QPushButton("✕")
        btn_remove.setFixedSize(16, 16)
        btn_remove.setCursor(QCursor(Qt.PointingHandCursor))
        btn_remove.setToolTip("Remove relationship")
        btn_remove.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94A3B8;
                border: none;
                font-weight: bold;
                font-size: 11px;
                padding: 0;
            }
            QPushButton:hover {
                color: #EF4444;
                background-color: #EF444422;
                border-radius: 8px;
            }
        """)
        btn_remove.clicked.connect(self._on_remove_clicked)
        layout.addWidget(btn_remove)

        # Base Frame Style
        self.setStyleSheet(f"""
            RelationshipChip {{
                background-color: #1A1D2B;
                border: 1px solid #282C40;
                border-radius: 6px;
            }}
            RelationshipChip:hover {{
                background-color: #23273A;
                border-color: #38BDF8;
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.rel_type, self.data)
        super().mousePressEvent(event)

    def _on_remove_clicked(self):
        self.remove_requested.emit(self.rel_type, self.data)

    def _resolve_entity_info(self) -> tuple[str, str, str, str]:
        """Resolve icon, title, status label, and status color using context services."""
        if self.rel_type == "project":
            proj_id = self.data.get("project_id", "")
            icon = "📁"
            title = proj_id
            status = "Available"
            color = "#10B981"

            proj_svc = getattr(self._context, "project_service", None) if self._context else None
            if proj_svc:
                proj = next((p for p in proj_svc.all_projects() if p.name == proj_id or getattr(p, "location", "") == proj_id), None)
                if proj:
                    title = proj.name
                    if not Path(proj.location).exists():
                        status = "Missing"
                        color = "#EF4444"
                else:
                    status = "Missing"
                    color = "#EF4444"
            return icon, title, status, color

        elif self.rel_type == "library_asset":
            asset_id = self.data.get("asset_id", "")
            icon = "📚"
            title = asset_id
            status = "Available"
            color = "#10B981"

            lib_svc = getattr(self._context, "library_service", None) if self._context else None
            if lib_svc:
                asset = lib_svc.get_asset(asset_id)
                if asset:
                    title = asset.filename
                    avail = lib_svc.get_asset_availability(asset)
                    if avail == AssetAvailability.AVAILABLE:
                        status = "Available"
                        color = "#10B981"
                    elif avail == AssetAvailability.OFFLINE:
                        status = "Offline"
                        color = "#F59E0B"
                    else:
                        status = "Missing"
                        color = "#EF4444"
                else:
                    status = "Missing"
                    color = "#EF4444"
            return icon, title, status, color

        elif self.rel_type == "project_asset":
            proj_id = self.data.get("project_id", "")
            asset_id = self.data.get("asset_id", "")
            rel_path = self.data.get("relative_path", "")
            icon = "📦"
            title = Path(rel_path).name if rel_path else (asset_id or "Asset")
            status = "Available"
            color = "#10B981"

            proj_svc = getattr(self._context, "project_service", None) if self._context else None
            asset_svc = getattr(self._context, "asset_service", None) if self._context else None
            if proj_svc:
                proj = next((p for p in proj_svc.all_projects() if p.name == proj_id or getattr(p, "location", "") == proj_id), None)
                if proj:
                    entry = None
                    if asset_svc:
                        entry = asset_svc.get_asset(proj, asset_id or rel_path)

                    if entry:
                        title = entry.get("filename") or title
                        abs_p = entry.get("absolute_path")
                        if abs_p and not Path(abs_p).exists():
                            status = "Missing"
                            color = "#EF4444"
                        else:
                            status = "Available"
                            color = "#10B981"
                    else:
                        # Fallback direct disk check if entry was not yet indexed
                        disk_p = Path(proj.location) / (rel_path or asset_id)
                        if disk_p.exists():
                            title = disk_p.name
                            status = "Available"
                            color = "#10B981"
                        else:
                            status = "Missing"
                            color = "#EF4444"
                else:
                    status = "Missing"
                    color = "#EF4444"
            return icon, f"{title} [{proj_id}]" if proj_id else title, status, color

        elif self.rel_type == "lab_node":
            node_id = self.data.get("node_id", "")
            icon = "🎨"
            title = f"Node {node_id[:8]}"
            status = "Available"
            color = "#10B981"

            lab_svc = getattr(self._context, "lab_service", None) if self._context else None
            proj_svc = getattr(self._context, "project_service", None) if self._context else None

            if lab_svc and proj_svc:
                # Search boards across projects or global workbench
                found = False
                all_projs = [None] + proj_svc.all_projects()
                for p in all_projs:
                    boards = lab_svc.list_boards(p)
                    for b in boards:
                        b_data = lab_svc.load_board(p, b.get("id"))
                        items = b_data.get("items", [])
                        for item in items:
                            if item.get("id") == node_id:
                                payload = item.get("payload", {})
                                title = payload.get("title") or payload.get("label") or payload.get("name") or item.get("type", "Node")
                                found = True
                                break
                        if found:
                            break
                    if found:
                        break
                if not found:
                    status = "Missing"
                    color = "#EF4444"

            return icon, title, status, color

        return "🔗", "Linked Item", "Unknown", "#94A3B8"
