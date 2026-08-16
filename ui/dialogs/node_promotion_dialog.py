from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QMessageBox,
)
from PySide6.QtCore import Qt
from ui.theme import BG_DARK, CARD_BG, BORDER_COLOR, TEXT_PRIMARY, TEXT_MUTED, ACCENT


class NodePromotionDialog(QDialog):
    """Reusable destination selection dialog for moving or copying nodes between Workbench and Projects."""

    def __init__(self, parent, action_type: str, source_project, source_board_id: str, project_service=None, lab_service=None, target_nodes=None):
        super().__init__(parent)
        self.action_type = action_type.lower()  # "move" or "copy"
        self.source_project = source_project
        self.source_board_id = source_board_id or "Main"
        self.project_service = project_service
        self.lab_service = lab_service
        self.target_nodes = target_nodes or []

        # Fallback project service resolution if lab_service is provided but project_service omitted
        if not self.project_service and self.lab_service and getattr(self.lab_service, "project_service", None):
            self.project_service = self.lab_service.project_service

        # Secondary defensive fallback: inspect parent widget tree for _context or node_context
        if not self.project_service and parent:
            p_curr = parent
            while p_curr:
                ctx = getattr(p_curr, "_context", None)
                if not ctx and hasattr(p_curr, "node_context") and p_curr.node_context:
                    ctx = getattr(p_curr.node_context, "app_context", None)
                if ctx and getattr(ctx, "project_service", None):
                    self.project_service = ctx.project_service
                    if not self.lab_service and getattr(ctx, "lab_service", None):
                        self.lab_service = ctx.lab_service
                    break
                p_curr = p_curr.parent() if hasattr(p_curr, "parent") and callable(p_curr.parent) else None

        if not self.project_service:
            try:
                from services.project_service import ProjectService
                self.project_service = ProjectService()
            except Exception:
                pass

        if not self.lab_service:
            try:
                from services.lab_service import LabService
                self.lab_service = LabService(project_service=self.project_service)
            except Exception:
                pass

        if self.lab_service and self.source_board_id:
            s_entry = self.lab_service.get_board_entry(self.source_project, self.source_board_id)
            if s_entry and s_entry.get("id"):
                self.source_board_id = s_entry["id"]

        # Compute dynamic promotion count title
        action_verb = "Move" if self.action_type == "move" else "Copy"
        title_str = f"{action_verb} Node"

        if self.target_nodes:
            node_ids = [n.id if hasattr(n, "id") else str(n) for n in self.target_nodes]
            resolved_group = self.lab_service.resolve_promotion_group(self.source_project, self.source_board_id, node_ids) if self.lab_service else []

            if not resolved_group:
                resolved_group = []
                for n in self.target_nodes:
                    if isinstance(n, dict):
                        resolved_group.append(n)
                    else:
                        payload = getattr(n, "payload", {}) if isinstance(getattr(n, "payload", None), dict) else {}
                        t_id = getattr(n, "type_id", "note.blank")
                        if hasattr(n, "definition") and hasattr(n.definition, "type_id"):
                            t_id = n.definition.type_id
                        resolved_group.append({
                            "id": getattr(n, "id", str(n)),
                            "type": t_id,
                            "payload": payload
                        })

            if resolved_group:
                def _is_frame(it):
                    return isinstance(it, dict) and (it.get("type") == "frame" or "child_node_ids" in (it.get("payload") or {}))
                frames_cnt = sum(1 for it in resolved_group if _is_frame(it))
                non_frames_cnt = sum(1 for it in resolved_group if not _is_frame(it))

                if frames_cnt == 0:
                    if non_frames_cnt == 1:
                        title_str = f"{action_verb} Node"
                    else:
                        title_str = f"{action_verb} {non_frames_cnt} nodes"
                elif frames_cnt == 1:
                    if non_frames_cnt == 0:
                        title_str = f"{action_verb} Frame"
                    elif non_frames_cnt == 1:
                        title_str = f"{action_verb} Frame + 1 node"
                    else:
                        title_str = f"{action_verb} Frame + {non_frames_cnt} nodes"
                else:
                    if non_frames_cnt == 0:
                        title_str = f"{action_verb} {frames_cnt} Frames"
                    elif non_frames_cnt == 1:
                        title_str = f"{action_verb} {frames_cnt} Frames + 1 node"
                    else:
                        title_str = f"{action_verb} {frames_cnt} Frames + {non_frames_cnt} nodes"


        self.setWindowTitle(title_str)

        self.setMinimumWidth(380)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #181A20;
                color: #F1F5F9;
            }}
            QLabel {{
                color: #CBD5E1;
                font-size: 12px;
            }}
            QComboBox {{
                background-color: #14161D;
                color: #F1F5F9;
                border: 1px solid #343847;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QComboBox:focus {{
                border-color: {ACCENT};
            }}
            QPushButton {{
                background-color: #202334;
                color: #F1F5F9;
                border: 1px solid #313652;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #262A3E;
                border-color: {ACCENT};
            }}
            QPushButton#primary_btn {{
                background-color: {ACCENT};
                border: none;
            }}
            QPushButton#primary_btn:hover {{
                background-color: #3B82F6;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        hdr_label = QLabel(title_str)
        hdr_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #F1F5F9;")
        layout.addWidget(hdr_label)

        # Project Selector
        p_lbl = QLabel("Target Workspace / Project:")
        layout.addWidget(p_lbl)

        self.project_cb = QComboBox()
        self.project_cb.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.project_cb)

        # Board Selector
        b_lbl = QLabel("Target Lab Board:")
        layout.addWidget(b_lbl)

        self.board_cb = QComboBox()
        self.board_cb.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.board_cb)

        self.project_cb.currentIndexChanged.connect(self._on_project_changed)

        # Buttons Row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        action_btn_str = "Move" if self.action_type == "move" else "Copy"
        self.action_btn = QPushButton(action_btn_str)
        self.action_btn.setObjectName("primary_btn")
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.action_btn.clicked.connect(self._on_confirm)
        btn_row.addWidget(self.action_btn)

        layout.addLayout(btn_row)

        self._populate_projects()

    def _populate_projects(self):
        self.project_cb.blockSignals(True)
        self.project_cb.clear()

        # Always include Global Workbench first
        self.project_cb.addItem("🛠️ Global Workbench", None)

        if self.project_service:
            try:
                projects = sorted(self.project_service.all_projects(), key=lambda p: getattr(p, "name", "").lower())
                for p in projects:
                    self.project_cb.addItem(f"📁 {p.name}", p)
            except Exception:
                pass

        # Pre-select source project if currently inside a project
        if self.source_project:
            for idx in range(self.project_cb.count()):
                p_obj = self.project_cb.itemData(idx)
                if p_obj and getattr(p_obj, "location", None) == getattr(self.source_project, "location", None):
                    self.project_cb.setCurrentIndex(idx)
                    break

        self.project_cb.blockSignals(False)
        self._on_project_changed()

    def _on_project_changed(self):
        self.board_cb.clear()
        selected_project = self.project_cb.currentData()

        if self.lab_service:
            try:
                boards = self.lab_service.list_boards(selected_project)
                inbox_idx = 0
                for idx, b in enumerate(boards):
                    if isinstance(b, dict):
                        b_id = b.get("id")
                        b_name = b.get("name", "Main")
                        if not b_id:
                            continue

                        # If moving within same project/workbench, exclude current source board
                        same_proj = (selected_project == self.source_project) or (
                            selected_project is not None and self.source_project is not None and
                            getattr(selected_project, "location", None) == getattr(self.source_project, "location", None)
                        )
                        if self.action_type == "move" and same_proj and b_id == self.source_board_id:
                            continue

                        is_inbox = (b_name.lower() in ("main", "inbox") or b_id == "Main")
                        display_name = f"📥 {b_name} (Inbox)" if is_inbox else b_name
                        self.board_cb.addItem(display_name, b_id)

                        if is_inbox:
                            inbox_idx = self.board_cb.count() - 1

                if self.board_cb.count() > 0:
                    self.board_cb.setCurrentIndex(inbox_idx)
            except Exception:
                pass

    def get_selected_destination(self):
        return self.project_cb.currentData(), self.board_cb.currentData()

    def _on_confirm(self):
        p_target, b_id_target = self.get_selected_destination()
        if not b_id_target:
            QMessageBox.warning(self, "Invalid Selection", "Please select a target board.")
            return
        self.accept()
        self.accept()
