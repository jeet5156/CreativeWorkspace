from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QCheckBox,
    QPushButton,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QFrame,
    QScrollArea,
)
from PySide6.QtCore import Qt, QTimer

from core.inspectable import InspectableObject, InspectableSection, InspectableField
from core.inspectable_adapters import ProjectInspectable, AssetInspectable, NodeInspectable
from ui.widgets.image_preview import ImagePreview


class InspectorPanel(QWidget):
    """Universal section-based Object Inspector for CreativeWorkspace.

    Consumes any model implementing the InspectableObject contract (Project, Asset, Lab Node, etc.),
    providing real-time field editing and clean visual sections without type-specific hardcoding.
    """

    def __init__(self):
        super().__init__()

        self._context = None
        self._current_inspectable = None
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._pending_save_action = None
        self._save_timer.timeout.connect(self._execute_pending_save)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---------------------------------------------------------------------
        # Fixed Header Bar
        # ---------------------------------------------------------------------
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #1E2029;
                border-bottom: 1px solid #2E3342;
                padding: 6px 12px;
            }
            QLabel#inspector_title {
                color: #F1F5F9;
                font-size: 14px;
                font-weight: bold;
            }
            QLabel#inspector_subtitle {
                color: #94A3B8;
                font-size: 11px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(8, 6, 8, 6)
        header_layout.setSpacing(2)

        self.header_title = QLabel("Inspector")
        self.header_title.setObjectName("inspector_title")
        header_layout.addWidget(self.header_title)

        self.header_subtitle = QLabel("No object selected")
        self.header_subtitle.setObjectName("inspector_subtitle")
        header_layout.addWidget(self.header_subtitle)

        main_layout.addWidget(header_frame)

        # ---------------------------------------------------------------------
        # Scrollable Form Area
        # ---------------------------------------------------------------------
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("QScrollArea { background-color: #14161D; }")

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(12, 12, 12, 12)
        self.content_layout.setSpacing(16)

        # Default Placeholder
        self.placeholder = QLabel(
            "Select a project, asset, or canvas node to view and edit properties.\n\n"
            "The Inspector provides a single universal editing surface for all workspace items."
        )
        self.placeholder.setWordWrap(True)
        self.placeholder.setStyleSheet("color: #64748B; padding: 16px; font-size: 12px;")
        self.content_layout.addWidget(self.placeholder)

        self.scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll_area)

    def set_context(self, context):
        self._context = context
        if context and getattr(context, "project_service", None):
            try:
                context.project_service.project_updated.connect(self._on_project_service_updated)
            except Exception:
                pass
        if context and getattr(context, "client_service", None):
            try:
                context.client_service.client_updated.connect(self._on_client_service_updated)
                context.client_service.client_deleted.connect(self._on_client_service_deleted)
            except Exception:
                pass

    def _execute_pending_save(self):
        if self._pending_save_action:
            action = self._pending_save_action
            self._pending_save_action = None
            try:
                action()
            except Exception:
                pass

    def _schedule_save(self, action):
        self._pending_save_action = action
        self._save_timer.start(500)

    def inspect(self, inspectable: InspectableObject):
        self._current_inspectable = inspectable

        # Clear existing dynamic widgets
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not inspectable:
            self.header_title.setText("Inspector")
            self.header_subtitle.setText("No object selected")
            self.content_layout.addWidget(self.placeholder)
            self.placeholder.setVisible(True)
            return

        self.header_title.setText(f"{inspectable.get_display_icon()}  {inspectable.get_display_name()}")
        self.header_subtitle.setText(f"{inspectable.__class__.__name__.replace('Inspectable', '')} Properties")

        sections = inspectable.get_inspection_sections()
        for section in sections:
            section_box = QFrame()
            section_box.setStyleSheet("""
                QFrame#section_box {
                    background-color: #1E2029;
                    border: 1px solid #2E3342;
                    border-radius: 6px;
                }
                QLabel#section_title {
                    color: #6366F1;
                    font-size: 11px;
                    font-weight: bold;
                    text-transform: uppercase;
                }
                QLabel {
                    color: #94A3B8;
                    font-size: 12px;
                }
                QLineEdit, QTextEdit, QComboBox {
                    background-color: #14161D;
                    color: #F1F5F9;
                    border: 1px solid #343847;
                    border-radius: 4px;
                    padding: 4px 6px;
                    font-size: 12px;
                }
                QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                    border: 1px solid #6366F1;
                }
                QPushButton {
                    background-color: #202334;
                    color: #F1F5F9;
                    border: 1px solid #313652;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #262A3E;
                    border: 1px solid #6366F1;
                }
            """)
            section_box.setObjectName("section_box")

            sec_layout = QVBoxLayout(section_box)
            sec_layout.setContentsMargins(10, 8, 10, 10)
            sec_layout.setSpacing(8)

            sec_title = QLabel(section.title)
            sec_title.setObjectName("section_title")
            sec_layout.addWidget(sec_title)

            form_layout = QFormLayout()
            form_layout.setContentsMargins(0, 4, 0, 0)
            form_layout.setSpacing(8)

            for field in section.fields:
                ctrl = self._create_control_for_field(inspectable, field)
                form_layout.addRow(f"{field.label}:", ctrl)

            sec_layout.addLayout(form_layout)
            self.content_layout.addWidget(section_box)

        self.content_layout.addStretch()

    def inspect_object(self, inspectable: InspectableObject):
        self.inspect(inspectable)

    def clear_inspection(self):
        self.inspect(None)

    def show_client(self, client):
        if not client:
            self.inspect(None)
            return
        client_svc = getattr(self._context, "client_service", None) if self._context else None
        proj_svc = getattr(self._context, "project_service", None) if self._context else None
        from core.inspectable_adapters import ClientInspectable
        inspectable = ClientInspectable(
            client,
            client_service=client_svc,
            project_service=proj_svc,
            on_updated_callback=self._on_client_updated_callback,
        )
        self.inspect(inspectable)

    def _on_client_updated_callback(self, client):
        if self._current_inspectable and hasattr(self._current_inspectable, "client") and getattr(self._current_inspectable, "client", None) == client:
            self.header_title.setText(f"{self._current_inspectable.get_display_icon()}  {client.name}")

    def _on_client_service_updated(self, client):
        if self._current_inspectable and hasattr(self._current_inspectable, "client"):
            c = getattr(self._current_inspectable, "client", None)
            if c and c.id == getattr(client, "id", None):
                self.header_title.setText(f"{self._current_inspectable.get_display_icon()}  {client.name}")

    def _on_client_service_deleted(self, client_id):
        if self._current_inspectable and hasattr(self._current_inspectable, "client"):
            c = getattr(self._current_inspectable, "client", None)
            if c and c.id == client_id:
                self.clear_inspection()

    # -------------------------------------------------------------------------
    # Backward-Compatibility Adapters
    # -------------------------------------------------------------------------

    def show_project(self, project):
        if not project:
            self.inspect(None)
            return
        proj_service = getattr(self._context, "project_service", None) if self._context else None
        inspectable = ProjectInspectable(
            project,
            project_service=proj_service,
            client_service=getattr(self._context, "client_service", None) if self._context else None,
            lab_service=getattr(self._context, "lab_service", None) if self._context else None,
            on_updated_callback=self._on_project_updated,
        )
        self.inspect(inspectable)

    def show_asset(self, project, asset_id):
        if not self._context or not getattr(self._context, "asset_service", None):
            self.inspect(None)
            return
        asset_dict = self._context.asset_service.get_asset(project, asset_id)
        if not asset_dict:
            self.inspect(None)
            return
        inspectable = AssetInspectable(
            asset_dict,
            asset_service=self._context.asset_service,
            project=project,
        )
        self.inspect(inspectable)

    def show_node(self, node_item):
        if not node_item:
            self.inspect(None)
            return
        inspectable = NodeInspectable(node_item)
        self.inspect(inspectable)

    # -------------------------------------------------------------------------
    # Control Generator & Event Listeners
    # -------------------------------------------------------------------------

    def _create_control_for_field(self, inspectable: InspectableObject, field: InspectableField) -> QWidget:
        if field.field_type == "readonly" or field.read_only:
            lbl = QLabel(str(field.value) if field.value is not None else "—")
            lbl.setWordWrap(True)
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lbl.setStyleSheet("color: #CBD5E1;")
            return lbl

        elif field.field_type in ("select", "enum"):
            cb = QComboBox()
            if field.options:
                cb.addItems([str(opt) for opt in field.options])
            if field.value:
                val_str = str(field.value)
                idx = cb.findText(val_str, Qt.MatchFixedString)
                if idx < 0:
                    for i in range(cb.count()):
                        if cb.itemText(i).lower() == val_str.lower():
                            idx = i
                            break
                if idx >= 0:
                    cb.setCurrentIndex(idx)
            cb.currentTextChanged.connect(
                lambda text, key=field.key: self._on_property_changed(inspectable, key, text)
            )
            return cb

        elif field.field_type == "boolean":
            chk = QCheckBox()
            chk.setChecked(bool(field.value))
            chk.stateChanged.connect(
                lambda state, key=field.key: self._on_property_changed(inspectable, key, bool(state == Qt.Checked or state == 2))
            )
            return chk

        elif field.field_type == "text":
            te = QTextEdit()
            te.setMinimumHeight(70)
            te.setMaximumHeight(130)
            te.setPlainText(str(field.value) if field.value else "")
            te.textChanged.connect(
                lambda key=field.key, widget=te: self._schedule_save(
                    lambda: self._on_property_changed(inspectable, key, widget.toPlainText())
                )
            )
            return te

        elif field.field_type == "image":
            img_prev = ImagePreview()
            img_prev.setFixedHeight(140)
            if field.value and Path(str(field.value)).exists():
                img_prev.load_image(Path(str(field.value)))
            else:
                img_prev.clear()
            return img_prev

        elif field.field_type == "action":
            btn = QPushButton(str(field.value))
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, f=field, insp=inspectable: self._on_action_triggered(insp, f))
            return btn

        elif field.field_type == "cover_actions":
            box = QWidget()
            btn_layout = QHBoxLayout(box)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.setSpacing(8)

            btn_change = QPushButton("Change Cover...")
            btn_change.clicked.connect(lambda: self._request_change_cover(inspectable))
            btn_layout.addWidget(btn_change)

            btn_remove = QPushButton("Remove Cover")
            btn_remove.clicked.connect(lambda: self._request_remove_cover(inspectable))
            btn_layout.addWidget(btn_remove)

            return box

        else:
            # Default "string" or "tags"
            le = QLineEdit()
            le.setText(str(field.value) if field.value else "")
            le.textChanged.connect(
                lambda text, key=field.key: self._schedule_save(
                    lambda: self._on_property_changed(inspectable, key, text)
                )
            )
            return le

    def _on_property_changed(self, inspectable, key, value):
        if not inspectable:
            return
        res = inspectable.set_inspectable_property(key, value)
        if res and hasattr(inspectable, "get_display_name"):
            self.header_title.setText(f"{inspectable.get_display_icon()}  {inspectable.get_display_name()}")

    def _request_change_cover(self, inspectable):
        if not isinstance(inspectable, ProjectInspectable) or not inspectable.project:
            return
        p = inspectable.project
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Cover Image",
            p.location,
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if file_path and getattr(inspectable, "project_service", None):
            inspectable.project_service.set_snapshot(p, file_path)
            self.inspect(inspectable)

    def _request_remove_cover(self, inspectable):
        if not isinstance(inspectable, ProjectInspectable) or not inspectable.project:
            return
        p = inspectable.project
        if getattr(inspectable, "project_service", None):
            inspectable.project_service.remove_snapshot(p)
            self.inspect(inspectable)

    def _on_project_updated(self, project):
        if self._current_inspectable and getattr(self._current_inspectable, "project", None) == project:
            self.header_title.setText(f"{self._current_inspectable.get_display_icon()}  {project.name}")

    def _on_project_service_updated(self, project):
        if self._current_inspectable and getattr(self._current_inspectable, "project", None) and self._current_inspectable.project.location == project.location:
            self._on_project_updated(project)

    def _on_action_triggered(self, inspectable, field):
        if not inspectable:
            return
        target_nodes = []
        if hasattr(inspectable, "nodes") and inspectable.nodes:
            target_nodes = list(inspectable.nodes)
        elif hasattr(inspectable, "node_item") and inspectable.node_item:
            target_nodes = [inspectable.node_item]

        if not target_nodes:
            return

        action_type = "move" if field.key == "action_move_project" else "copy"
        first_node = target_nodes[0]

        if hasattr(first_node, "scene") and first_node.scene() and first_node.scene().views():
            cv = first_node.scene().views()[0]
            if hasattr(cv, "_prompt_promote_nodes"):
                cv._prompt_promote_nodes(items=target_nodes, action=action_type)
            elif hasattr(cv, "_prompt_promote_node"):
                cv._prompt_promote_node(first_node, action=action_type)
        else:
            proj_svc = getattr(self._context, "project_service", None) if self._context else None
            lab_svc = getattr(self._context, "lab_service", None) if self._context else None
            if not lab_svc:
                from services.lab_service import LabService
                lab_svc = LabService(project_service=proj_svc)

            from ui.dialogs.node_promotion_dialog import NodePromotionDialog
            from PySide6.QtWidgets import QMessageBox, QDialog

            source_project = getattr(first_node, "project", None)
            if source_project is None and hasattr(first_node, "metadata") and isinstance(first_node.metadata, dict):
                src_p_name = first_node.metadata.get("project_name")
                if src_p_name and proj_svc:
                    for p in proj_svc.all_projects():
                        if getattr(p, "name", "") == src_p_name:
                            source_project = p
                            break

            if source_project is None and self._context:
                source_project = getattr(self._context, "current_project", None)

            source_board_id = getattr(first_node, "_board_id", None)
            if not source_board_id and hasattr(first_node, "metadata") and isinstance(first_node.metadata, dict):
                source_board_id = first_node.metadata.get("board_id")
            if not source_board_id and lab_svc:
                source_board_id = lab_svc.get_active_board_id(source_project) or "Main"
            if not source_board_id:
                source_board_id = "Main"

            dialog = NodePromotionDialog(self, action_type, source_project, source_board_id, proj_svc, lab_svc, target_nodes=target_nodes)
            if dialog.exec_() == QDialog.Accepted:
                p_target, b_id_target = dialog.get_selected_destination()
                if b_id_target:
                    target_ids = [n.id for n in target_nodes if hasattr(n, "id")]
                    dialog_title = dialog.windowTitle()
                    if action_type == "move":
                        res = lab_svc.move_nodes(source_project, source_board_id, p_target, b_id_target, target_ids)
                        if res:
                            QMessageBox.information(self, "Nodes Moved", f"Moved {dialog_title} to target board.")
                            self.inspect(None)
                        else:
                            QMessageBox.critical(self, "Move Failed", f"Could not move selected nodes.")
                    else:
                        res = lab_svc.copy_nodes(source_project, source_board_id, p_target, b_id_target, target_ids)
                        if res:
                            QMessageBox.information(self, "Nodes Copied", f"Copied {dialog_title} to target board.")
                        else:
                            QMessageBox.critical(self, "Copy Failed", f"Could not copy selected nodes.")