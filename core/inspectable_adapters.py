from typing import List, Any
from pathlib import Path

from core.inspectable import InspectableObject, InspectableSection, InspectableField


class ProjectInspectable(InspectableObject):
    """Adapter wrapping Project model into the InspectableObject contract."""

    def __init__(self, project, project_service=None, client_service=None, lab_service=None, on_updated_callback=None):
        self.project = project
        self.project_service = project_service
        self.client_service = client_service
        self.lab_service = lab_service
        self.on_updated_callback = on_updated_callback

    def get_display_name(self) -> str:
        return self.project.name if self.project else "Untitled Project"

    def get_display_icon(self) -> str:
        return "📁"

    def get_inspection_sections(self) -> List[InspectableSection]:
        if not self.project:
            return []

        p = self.project

        # Section 1: General
        general_fields = [
            InspectableField("name", "Project Name", "string", value=getattr(p, "name", "")),
            InspectableField(
                "project_type",
                "Project Type",
                "select",
                value=getattr(p, "project_type", "game").capitalize(),
                options=["Game", "Portfolio", "R&D", "Audio", "Video", "General"],
            ),
            InspectableField(
                "priority",
                "Priority",
                "select",
                value=str(getattr(p, "priority", "medium")).capitalize(),
                options=["High", "Medium", "Low"],
            ),
            InspectableField(
                "status",
                "Status",
                "select",
                value=str(getattr(p, "status", "active")).capitalize(),
                options=["Active", "In Progress", "On Hold", "Archived"],
            ),
            InspectableField("is_pinned", "Favourite Project", "boolean", value=bool(getattr(p, "is_pinned", False))),
            InspectableField("description", "Description", "text", value=getattr(p, "description", "")),
        ]

        # Section 2: Organization
        client_options = ["None"]
        current_client_val = "None"
        if self.client_service:
            all_clients = self.client_service.list_clients()
            client_options += [c.name for c in all_clients if c.name]
            if getattr(p, "client_id", None):
                c_found = self.client_service.get_client(p.client_id)
                if c_found:
                    current_client_val = c_found.name
            elif getattr(p, "client", None):
                current_client_val = p.client

        org_fields = [
            InspectableField("tags", "Tags", "tags", value=", ".join(getattr(p, "tags", [])) if getattr(p, "tags", None) else ""),
            InspectableField("client", "Client", "select", value=current_client_val, options=client_options),
            InspectableField("repository", "Git Repository", "string", value=getattr(p, "repository", "")),
            InspectableField("deadline", "Deadline", "string", value=getattr(p, "deadline", "")),
        ]

        # Section 3: Creative Lab Summary (Live Derived Metrics)
        sections = [
            InspectableSection("General", general_fields),
            InspectableSection("Organization", org_fields),
        ]

        if self.lab_service:
            try:
                summary = self.lab_service.get_project_summary_metadata(p)
                t_stats = summary.get("task_stats", {})
                lab_fields = [
                    InspectableField("boards_count", "Boards", "readonly", value=str(len(summary.get("boards", [])))),
                    InspectableField("nodes_count", "Spatial Nodes", "readonly", value=str(summary.get("total_nodes", 0))),
                    InspectableField("pinned_count", "Pinned References", "readonly", value=str(len(summary.get("pinned_nodes", [])))),
                    InspectableField("tasks_count", "Checklist Tasks", "readonly", value=f"{t_stats.get('completed', 0)} / {t_stats.get('total', 0)} Completed"),
                ]
                sections.append(InspectableSection("Creative Lab Summary", lab_fields))
            except Exception:
                pass

        # Section 4: Appearance
        snapshot_path = str(Path(p.location) / "snapshot.png") if getattr(p, "location", None) else ""
        appearance_fields = [
            InspectableField("snapshot", "Cover Image", "image", value=snapshot_path),
            InspectableField("cover_actions", "Cover Actions", "cover_actions", value=snapshot_path),
        ]
        sections.append(InspectableSection("Appearance", appearance_fields))

        # Section 5: Metadata (Read-Only)
        created_str = p.created.strftime("%d %b %Y %H:%M") if getattr(p, "created", None) else "—"
        modified_str = p.modified.strftime("%d %b %Y %H:%M") if getattr(p, "modified", None) else created_str
        proj_id = Path(p.location).name if getattr(p, "location", None) else "—"
        metadata_fields = [
            InspectableField("created", "Created", "readonly", value=created_str),
            InspectableField("modified", "Modified", "readonly", value=modified_str),
            InspectableField("location", "Location Path", "readonly", value=str(getattr(p, "location", "—"))),
            InspectableField("id", "Project ID", "readonly", value=proj_id),
        ]
        sections.append(InspectableSection("Metadata", metadata_fields))

        return sections

    def set_inspectable_property(self, field_key: str, value: Any) -> bool:
        if not self.project:
            return False

        updated = False
        val_str = str(value).strip() if value is not None else ""

        if field_key == "name" and val_str:
            self.project.name = val_str
            updated = True
        elif field_key == "project_type":
            self.project.project_type = val_str.lower()
            updated = True
        elif field_key == "priority":
            self.project.priority = val_str.lower()
            updated = True
        elif field_key == "status":
            self.project.status = val_str.lower()
            updated = True
        elif field_key in ("is_pinned", "is_favorite", "favorite"):
            self.project.is_pinned = bool(value)
            updated = True
        elif field_key == "description":
            self.project.description = str(value)
            updated = True
        elif field_key == "tags":
            tags_list = [t.strip() for t in str(value).split(",") if t.strip()]
            self.project.tags = tags_list
            updated = True
        elif field_key == "client":
            old_cid = getattr(self.project, "client_id", "")
            proj_identifier = getattr(self.project, "id", getattr(self.project, "name", ""))
            
            if val_str == "None" or not val_str:
                self.project.client = ""
                self.project.client_id = ""
                if old_cid and self.client_service:
                    self.client_service.remove_project_from_client(proj_identifier, old_cid, self.project_service)
            else:
                target_client = None
                if self.client_service:
                    for c in self.client_service.list_clients():
                        if c.name == val_str:
                            target_client = c
                            break
                if target_client:
                    new_cid = target_client.id
                    if old_cid and old_cid != new_cid and self.client_service:
                        self.client_service.remove_project_from_client(proj_identifier, old_cid, self.project_service)
                    self.project.client = target_client.name
                    self.project.client_id = new_cid
                    if self.client_service:
                        self.client_service.assign_project_to_client(proj_identifier, new_cid, self.project_service)
                else:
                    self.project.client = val_str
            updated = True
        elif field_key == "client_id":
            self.project.client_id = val_str
            if self.client_service:
                c = self.client_service.get_client(val_str)
                if c:
                    self.project.client = c.name
            updated = True
        elif field_key == "repository":
            self.project.repository = str(value)
            updated = True
        elif field_key == "deadline":
            self.project.deadline = str(value)
            updated = True

        if updated:
            if self.project_service:
                try:
                    self.project_service.save_project(self.project)
                except Exception:
                    pass
            if self.on_updated_callback:
                try:
                    self.on_updated_callback(self.project)
                except Exception:
                    pass

        return updated


class AssetInspectable(InspectableObject):
    """Adapter wrapping Asset dictionary properties into InspectableObject contract."""

    def __init__(self, asset_dict: dict, asset_service=None, project=None):
        self.asset_dict = asset_dict or {}
        self.asset_service = asset_service
        self.project = project

    def get_display_name(self) -> str:
        return self.asset_dict.get("filename", "Asset Details")

    def get_display_icon(self) -> str:
        return "📦"

    def get_inspection_sections(self) -> List[InspectableSection]:
        a = self.asset_dict
        general_fields = [
            InspectableField("filename", "Filename", "readonly", value=a.get("filename", "—")),
            InspectableField("friendly_type", "Type", "readonly", value=a.get("friendly_type", "—")),
            InspectableField("category", "Category", "readonly", value=a.get("category", "—")),
            InspectableField("relative_path", "Path", "readonly", value=a.get("relative_path", "—")),
            InspectableField("tags", "Tags", "tags", value=", ".join(a.get("tags", [])) if a.get("tags") else ""),
            InspectableField("notes", "Notes", "text", value=a.get("notes", "")),
        ]
        return [InspectableSection("Asset Properties", general_fields)]

    def set_inspectable_property(self, field_key: str, value: Any) -> bool:
        if field_key == "tags":
            tags_list = [t.strip() for t in str(value).split(",") if t.strip()]
            self.asset_dict["tags"] = tags_list
            return True
        elif field_key == "notes":
            self.asset_dict["notes"] = str(value)
            return True
        return False


class NodeInspectable(InspectableObject):
    """Adapter wrapping Spatial Lab NodeItem into InspectableObject contract."""

    def __init__(self, node_item, connection_manager=None, canvas=None):
        self.node_item = node_item
        self.connection_manager = connection_manager
        self.canvas = canvas

    def get_display_name(self) -> str:
        if self.node_item and getattr(self.node_item, "definition", None):
            title = self.node_item.definition.title
            content_title = self.node_item.payload.get("title") if isinstance(self.node_item.payload, dict) else None
            if content_title:
                return f"{title}: {content_title}"
            return title
        return "Lab Node"

    def get_display_icon(self) -> str:
        if self.node_item and getattr(self.node_item, "definition", None):
            return self.node_item.definition.icon
        return "✦"

    def get_inspection_sections(self) -> List[InspectableSection]:
        if not self.node_item:
            return []

        node = self.node_item
        defn = getattr(node, "definition", None)
        sections = []

        # ---------------------------------------------------------------------
        # Section 1: Summary Statistics Block (Scannable for thinking)
        # ---------------------------------------------------------------------
        cm = self.connection_manager
        if not cm and hasattr(node, "scene") and node.scene() and node.scene().views():
            cv = node.scene().views()[0]
            if hasattr(cv, "connection_manager"):
                cm = cv.connection_manager

        outgoing_rels = []
        incoming_rels = []
        if cm:
            all_node_rels = cm.get_node_relationships(node.id)
            for r in all_node_rels:
                if r.source_node_id == node.id:
                    outgoing_rels.append(r)
                else:
                    incoming_rels.append(r)

        total_rels = len(outgoing_rels) + len(incoming_rels)
        tags_str = ", ".join(node.tags) if hasattr(node, "tags") and node.tags else "None"
        node_meta = getattr(node, "metadata", None)
        is_pinned = bool(node.payload.get("pinned", False) or (isinstance(node_meta, dict) and node_meta.get("pinned", False)))

        parent_frame_id = node.payload.get("parent_frame_id") if isinstance(node.payload, dict) else None
        frame_title = "Canvas Root"
        if parent_frame_id and hasattr(node, "scene") and node.scene() and node.scene().views():
            cv = node.scene().views()[0]
            if hasattr(cv, "node"):
                f_node = cv.node(parent_frame_id)
                if f_node and hasattr(f_node, "payload"):
                    frame_title = str(f_node.payload.get("title", "Frame"))

        attn_val = str(node.payload.get("attention") or (node_meta.get("attention") if isinstance(node_meta, dict) else "normal")).lower()
        if attn_val not in ("normal", "important", "urgent"):
            attn_val = "normal"

        stat_fields = [
            InspectableField("summary_total", "Knowledge Relationships", "readonly", value=str(total_rels)),
            InspectableField("summary_incoming", "Incoming (Backlinks)", "readonly", value=str(len(incoming_rels))),
            InspectableField("summary_outgoing", "Outgoing", "readonly", value=str(len(outgoing_rels))),
            InspectableField("summary_frame", "Frame Location", "readonly", value=frame_title),
            InspectableField("summary_tags", "Tags", "readonly", value=tags_str),
            InspectableField("is_pinned", "Pinned Node", "boolean", value=is_pinned),
            InspectableField("attention", "Attention Priority", "enum", value=attn_val.capitalize(), options=["Normal", "Important", "Urgent"]),
        ]
        sections.append(InspectableSection("Knowledge Overview", stat_fields))

        # ---------------------------------------------------------------------
        # Section 2: Grouped Outgoing Relationships
        # ---------------------------------------------------------------------
        from ui.lab.models.relationship_registry import RelationshipRegistry

        if outgoing_rels:
            out_grouped = {}
            for r in outgoing_rels:
                lbl = RelationshipRegistry.get_label(r.relationship_type)
                out_grouped.setdefault(lbl, []).append(r)

            out_fields = []
            for rel_lbl, r_list in out_grouped.items():
                for r in r_list:
                    tgt_title = r.target_node_id[:8]
                    if hasattr(node, "scene") and node.scene() and node.scene().views():
                        cv = node.scene().views()[0]
                        if hasattr(cv, "node"):
                            tnode = cv.node(r.target_node_id)
                            if tnode:
                                tgt_title = tnode.payload.get("title") or (tnode.definition.title if tnode.definition else tnode.id[:8])
                    txt = f"• {tgt_title}" + (f" ({r.title})" if r.title else "")
                    out_fields.append(InspectableField(f"rel_jump.{r.target_node_id}", f"{rel_lbl} ({len(r_list)})", "readonly", value=txt))

            sections.append(InspectableSection(f"Outgoing Connections ({len(outgoing_rels)})", out_fields))

        # ---------------------------------------------------------------------
        # Section 3: Grouped Incoming Relationships (Obsidian Backlinks)
        # ---------------------------------------------------------------------
        if incoming_rels:
            in_grouped = {}
            for r in incoming_rels:
                lbl = RelationshipRegistry.get_label(r.relationship_type)
                in_grouped.setdefault(lbl, []).append(r)

            in_fields = []
            for rel_lbl, r_list in in_grouped.items():
                for r in r_list:
                    src_title = r.source_node_id[:8]
                    if hasattr(node, "scene") and node.scene() and node.scene().views():
                        cv = node.scene().views()[0]
                        if hasattr(cv, "node"):
                            snode = cv.node(r.source_node_id)
                            if snode:
                                src_title = snode.payload.get("title") or (snode.definition.title if snode.definition else snode.id[:8])
                    txt = f"• {src_title}" + (f" ({r.title})" if r.title else "")
                    in_fields.append(InspectableField(f"rel_jump.{r.source_node_id}", f"Referenced By: {rel_lbl}", "readonly", value=txt))

            sections.append(InspectableSection(f"Incoming Backlinks ({len(incoming_rels)})", in_fields))

        # ---------------------------------------------------------------------
        # Section 4: Node Specific Properties & Metadata
        # ---------------------------------------------------------------------
        fields = [
            InspectableField("type_id", "Node Type", "readonly", value=defn.type_id if defn else "node"),
            InspectableField("id", "Node ID", "readonly", value=node.id),
        ]

        if getattr(node, "payload", None):
            payload = node.payload
            if "color_theme" in payload or "theme" in payload or "child_node_ids" in payload:
                frame_fields = [
                    InspectableField("payload.title", "Title", "string", value=str(payload.get("title", "Section Frame"))),
                    InspectableField("payload.theme", "Theme", "enum", value=str(payload.get("theme", payload.get("color_theme", "blue"))).lower(), options=["gray", "blue", "green", "yellow", "red", "purple"]),
                    InspectableField("payload.locked", "Locked", "boolean", value=bool(payload.get("locked", False))),
                    InspectableField("payload.collapsed", "Collapsed", "boolean", value=bool(payload.get("collapsed", False))),
                ]
                sections.append(InspectableSection("Frame Properties", frame_fields))
            elif defn and defn.type_id == "file.reference" or "file_path" in payload:
                abs_path_val = payload.get("absolute_path") or payload.get("file_path") or payload.get("image_path") or "No file selected"
                filename_val = payload.get("filename") or payload.get("file_name") or ""
                size_val = payload.get("file_size_str") or "Unknown"
                ext_val = payload.get("extension") or ""

                file_fields = [
                    InspectableField("payload.file", "Original File", "readonly", value=filename_val if filename_val else str(abs_path_val)),
                    InspectableField("payload.path", "Original Path", "readonly", value=str(abs_path_val)),
                    InspectableField("payload.extension", "Extension", "readonly", value=str(ext_val)),
                    InspectableField("payload.file_size", "File Size", "readonly", value=str(size_val)),
                    InspectableField("payload.title", "Title", "string", value=str(payload.get("title", ""))),
                    InspectableField("payload.caption", "Caption", "text", value=str(payload.get("caption", ""))),
                ]
                sections.append(InspectableSection("File Reference Properties", file_fields))
            elif defn and defn.type_id == "folder.reference" or "folder_path" in payload:
                abs_path_val = payload.get("absolute_path") or payload.get("folder_path") or payload.get("image_path") or "No directory selected"
                foldername_val = payload.get("foldername") or payload.get("filename") or payload.get("file_name") or ""

                folder_fields = [
                    InspectableField("payload.folder", "Folder", "readonly", value=foldername_val if foldername_val else str(abs_path_val)),
                    InspectableField("payload.path", "Original Path", "readonly", value=str(abs_path_val)),
                    InspectableField("payload.title", "Title", "string", value=str(payload.get("title", ""))),
                    InspectableField("payload.caption", "Caption", "text", value=str(payload.get("caption", ""))),
                ]
                sections.append(InspectableSection("Folder Reference Properties", folder_fields))
            elif defn and defn.type_id == "archive.reference" or "archive_path" in payload:
                abs_path_val = payload.get("absolute_path") or payload.get("archive_path") or payload.get("image_path") or "No archive selected"
                filename_val = payload.get("filename") or payload.get("file_name") or ""
                size_val = payload.get("file_size_str") or "Unknown"
                ext_val = payload.get("extension") or ""

                archive_fields = [
                    InspectableField("payload.archive", "Archive", "readonly", value=filename_val if filename_val else str(abs_path_val)),
                    InspectableField("payload.path", "Original Path", "readonly", value=str(abs_path_val)),
                    InspectableField("payload.extension", "Extension", "readonly", value=str(ext_val)),
                    InspectableField("payload.file_size", "File Size", "readonly", value=str(size_val)),
                    InspectableField("payload.title", "Title", "string", value=str(payload.get("title", ""))),
                    InspectableField("payload.caption", "Caption", "text", value=str(payload.get("caption", ""))),
                ]
                sections.append(InspectableSection("Archive Reference Properties", archive_fields))
            elif defn and defn.type_id == "asset.3d" or "asset_path" in payload:
                abs_path_val = payload.get("absolute_path") or payload.get("asset_path") or payload.get("image_path") or "No file selected"
                filename_val = payload.get("filename") or payload.get("file_name") or ""
                size_val = payload.get("file_size_str") or "Unknown"
                format_lbl = payload.get("format_label") or (payload.get("extension") or "").upper() or "3D Model"

                threed_fields = [
                    InspectableField("payload.file", "Original File", "readonly", value=filename_val if filename_val else str(abs_path_val)),
                    InspectableField("payload.path", "Original Path", "readonly", value=str(abs_path_val)),
                    InspectableField("payload.format", "Format", "readonly", value=str(format_lbl)),
                    InspectableField("payload.file_size", "File Size", "readonly", value=str(size_val)),
                    InspectableField("payload.title", "Title", "string", value=str(payload.get("title", ""))),
                    InspectableField("payload.caption", "Caption", "text", value=str(payload.get("caption", ""))),
                ]
                sections.append(InspectableSection("3D Asset Properties", threed_fields))
            elif defn and defn.type_id == "document.pdf" or "pdf_path" in payload:
                abs_path_val = payload.get("absolute_path") or payload.get("pdf_path") or payload.get("image_path") or "No file selected"
                filename_val = payload.get("filename") or payload.get("file_name") or ""
                size_val = payload.get("file_size_str") or "Unknown"
                page_cnt = payload.get("page_count", 0)
                pages_val = f"{page_cnt} pages" if page_cnt > 0 else "Unknown"
                mode_val = payload.get("display_mode", "icon")

                pdf_fields = [
                    InspectableField("payload.file", "Original File", "readonly", value=filename_val if filename_val else str(abs_path_val)),
                    InspectableField("payload.path", "Original Path", "readonly", value=str(abs_path_val)),
                    InspectableField("payload.file_size", "File Size", "readonly", value=str(size_val)),
                    InspectableField("payload.page_count", "Page Count", "readonly", value=pages_val),
                    InspectableField("payload.display_mode", "Display Mode", "enum", value=str(mode_val), options=["icon", "preview"]),
                    InspectableField("payload.title", "Title", "string", value=str(payload.get("title", ""))),
                    InspectableField("payload.caption", "Caption", "text", value=str(payload.get("caption", ""))),
                ]
                sections.append(InspectableSection("PDF Properties", pdf_fields))
            elif "image_path" in payload or "absolute_path" in payload:
                abs_path_val = payload.get("absolute_path") or payload.get("image_path") or "No file selected"
                filename_val = payload.get("filename") or payload.get("file_name") or ""
                size_val = payload.get("file_size_str") or "Unknown"
                general_fields = [
                    InspectableField("payload.file", "Original File", "readonly", value=filename_val if filename_val else str(abs_path_val)),
                    InspectableField("payload.path", "Original Path", "readonly", value=str(abs_path_val)),
                    InspectableField("payload.file_size", "File Size", "readonly", value=str(size_val)),
                    InspectableField("payload.title", "Title", "string", value=str(payload.get("title", ""))),
                    InspectableField("payload.caption", "Caption", "text", value=str(payload.get("caption", ""))),
                    InspectableField("payload.fit_mode", "Fit Mode", "enum", value=str(payload.get("fit_mode", "fit")), options=["fit", "fill"]),
                ]
                sections.append(InspectableSection("Reference Properties", general_fields))
            else:
                for k, v in payload.items():
                    if k not in ("layout", "pinned"):
                        fields.append(InspectableField(f"payload.{k}", k.capitalize(), "string", value=str(v)))

        fields.append(InspectableField("tags", "Tags (comma-separated)", "tags", value=tags_str if tags_str != "None" else ""))
        sections.append(InspectableSection("General Properties", fields))

        action_fields = [
            InspectableField("action_move_project", "Move to Project", "action", value="📁 Move to Project..."),
            InspectableField("action_copy_project", "Copy to Project", "action", value="📋 Copy to Project..."),
        ]
        sections.append(InspectableSection("Actions", action_fields))

        return sections

    def set_inspectable_property(self, field_key: str, value: Any) -> bool:
        if not self.node_item:
            return False
        if field_key in ("attention", "payload.attention"):
            val_str = str(value or "normal").lower()
            if val_str not in ("normal", "important", "urgent"):
                val_str = "normal"
            self.node_item.payload["attention"] = val_str
            node_meta = getattr(self.node_item, "metadata", None)
            if isinstance(node_meta, dict):
                node_meta["attention"] = val_str
            self.node_item.update()
            if hasattr(self.node_item, "_emit_modified"):
                self.node_item._emit_modified()
            return True
        if field_key == "is_pinned":
            val = bool(value)
            self.node_item.payload["pinned"] = val
            node_meta = getattr(self.node_item, "metadata", None)
            if isinstance(node_meta, dict):
                node_meta["pinned"] = val
            self.node_item.update()
            self.node_item._emit_modified()
            return True
        if field_key == "tags":
            if isinstance(value, list):
                self.node_item.set_tags(value)
            else:
                tag_list = [t.strip() for t in str(value or "").split(",") if t.strip()]
                self.node_item.set_tags(tag_list)
            self.node_item.update()
            return True
        if field_key in ("payload.theme", "payload.color_theme") and hasattr(self.node_item, "set_color_theme"):
            self.node_item.set_color_theme(str(value))
            return True
        if field_key == "payload.locked" and hasattr(self.node_item, "set_locked"):
            self.node_item.set_locked(bool(value))
            return True
        if field_key in ("payload.collapsed", "collapsed"):
            val = bool(value)
            if hasattr(self.node_item, "set_collapsed"):
                self.node_item.set_collapsed(val)
            else:
                self.node_item.payload["collapsed"] = val
                self.node_item.update()
                self.node_item._emit_modified()
            return True
        if field_key.startswith("payload."):
            real_key = field_key.split(".", 1)[1]
            self.node_item.on_property_changed(real_key, value)
            return True
        return False


class MultiNodeInspectable(InspectableObject):
    """Adapter wrapping a multi-selection list of spatial Lab node items into InspectableObject."""

    def __init__(self, nodes: List[Any]):
        self.nodes = nodes or []

    def get_display_name(self) -> str:
        return f"{len(self.nodes)} Items Selected"

    def get_display_icon(self) -> str:
        return "🔲"

    def get_inspection_sections(self) -> List[InspectableSection]:
        if not self.nodes:
            return []

        type_counts = {}
        all_tags_sets = []
        pinned_states = []

        for n in self.nodes:
            t_name = n.definition.title if getattr(n, "definition", None) else n.__class__.__name__.replace("Item", "")
            type_counts[t_name] = type_counts.get(t_name, 0) + 1
            all_tags_sets.append(set(getattr(n, "tags", [])))
            pinned_states.append(bool(getattr(n, "is_pinned", False)))

        type_summary = ", ".join(f"{count} {t}" for t, count in type_counts.items())

        # Compute common tags across selection
        common_tags = set.intersection(*all_tags_sets) if all_tags_sets else set()
        common_tags_str = ", ".join(sorted(common_tags))

        # Check if all selected items are pinned
        all_pinned = all(pinned_states) if pinned_states else False

        fields = [
            InspectableField("selection_count", "Selection Count", "readonly", value=f"{len(self.nodes)} nodes"),
            InspectableField("node_types", "Node Types", "readonly", value=type_summary),
            InspectableField("is_pinned", "Pinned (All Selected)", "boolean", value=all_pinned),
            InspectableField("tags", "Tags (comma-separated)", "tags", value=common_tags_str),
        ]

        action_fields = [
            InspectableField("action_move_project", "Move to Project", "action", value="📁 Move to Project..."),
            InspectableField("action_copy_project", "Copy to Project", "action", value="📋 Copy to Project..."),
        ]

        return [
            InspectableSection("Selection Summary", fields),
            InspectableSection("Actions", action_fields),
        ]


    def set_inspectable_property(self, field_key: str, value: Any) -> bool:
        if not self.nodes:
            return False

        if field_key == "is_pinned":
            val = bool(value)
            for node in self.nodes:
                if hasattr(node, "set_pinned"):
                    node.set_pinned(val)
                elif hasattr(node, "payload") and isinstance(node.payload, dict):
                    node.payload["pinned"] = val
                    if hasattr(node, "update"):
                        node.update()
            return True

        if field_key == "tags":
            if isinstance(value, list):
                raw_tags = [str(t).strip().lower() for t in value if str(t).strip()]
            else:
                raw_tags = [t.strip().lower() for t in str(value or "").split(",") if t.strip()]

            for node in self.nodes:
                if hasattr(node, "tags") and hasattr(node, "set_tags"):
                    existing = list(node.tags)
                    combined = list(dict.fromkeys(existing + raw_tags))
                    node.set_tags(combined)
            return True

        return False


class ClientInspectable(InspectableObject):
    """Adapter wrapping Client domain model into the InspectableObject contract.

    Provides live auto-saving property inspection sections for Company, Client Name,
    Status, Priority, Client Type, Industry, Website, Country, Tags, Notes, Associated Projects, and Metadata.
    """

    def __init__(self, client, client_service=None, project_service=None, on_updated_callback=None):
        self.client = client
        self.client_service = client_service
        self.project_service = project_service
        self.on_updated_callback = on_updated_callback

    def get_display_name(self) -> str:
        return self.client.name if self.client and self.client.name else "Untitled Client"

    def get_display_icon(self) -> str:
        return "👥"

    def get_inspection_sections(self) -> List[InspectableSection]:
        if not self.client:
            return []

        c = self.client
        from models.client import CLIENT_STATUSES, CLIENT_TYPES, CLIENT_PRIORITIES

        general_fields = [
            InspectableField("company", "Company", "string", value=getattr(c, "company", "")),
            InspectableField("name", "Client Name", "string", value=getattr(c, "name", "")),
            InspectableField(
                "status",
                "Status",
                "select",
                value=str(getattr(c, "status", "Active")),
                options=CLIENT_STATUSES,
            ),
            InspectableField(
                "priority",
                "Priority",
                "select",
                value=str(getattr(c, "priority", "Medium")),
                options=CLIENT_PRIORITIES,
            ),
            InspectableField(
                "client_type",
                "Client Type",
                "select",
                value=str(getattr(c, "client_type", "Game Studio")),
                options=CLIENT_TYPES,
            ),
            InspectableField("industry", "Industry", "string", value=getattr(c, "industry", "")),
            InspectableField("website", "Website", "string", value=getattr(c, "website", "")),
            InspectableField("country", "Country", "string", value=getattr(c, "country", "")),
            InspectableField("tags", "Tags", "tags", value=", ".join(getattr(c, "tags", [])) if getattr(c, "tags", None) else ""),
            InspectableField("notes", "Notes", "text", value=getattr(c, "notes", "")),
        ]

        projs = []
        if self.project_service and hasattr(self.project_service, "all_projects"):
            projs = [p for p in self.project_service.all_projects() if getattr(p, "client_id", None) == c.id]

        proj_str = ", ".join([p.name for p in projs]) if projs else "None assigned"
        projects_fields = [
            InspectableField("associated_projects", "Associated Projects", "readonly", value=proj_str),
            InspectableField("project_count", "Project Count", "readonly", value=str(len(projs))),
        ]

        created_str = c.created.strftime("%d %b %Y %H:%M") if hasattr(c.created, "strftime") else str(getattr(c, "created", "—"))
        modified_str = c.modified.strftime("%d %b %Y %H:%M") if hasattr(c.modified, "strftime") else created_str
        metadata_fields = [
            InspectableField("created", "Created", "readonly", value=created_str),
            InspectableField("modified", "Updated", "readonly", value=modified_str),
            InspectableField("id", "ID", "readonly", value=str(getattr(c, "id", "—"))),
        ]

        return [
            InspectableSection("General", general_fields),
            InspectableSection("Projects", projects_fields),
            InspectableSection("Metadata", metadata_fields),
        ]

    def set_inspectable_property(self, field_key: str, value: Any) -> bool:
        if not self.client:
            return False

        updated = False
        val_str = str(value).strip() if value is not None else ""

        if field_key == "name" and val_str:
            self.client.name = val_str
            updated = True
        elif field_key == "company":
            self.client.company = val_str
            updated = True
        elif field_key == "client_type":
            self.client.client_type = val_str
            updated = True
        elif field_key == "status":
            self.client.status = val_str
            updated = True
        elif field_key == "priority":
            self.client.priority = val_str
            updated = True
        elif field_key == "industry":
            self.client.industry = val_str
            updated = True
        elif field_key == "website":
            self.client.website = val_str
            updated = True
        elif field_key == "country":
            self.client.country = val_str
            updated = True
        elif field_key == "notes":
            self.client.notes = val_str
            updated = True
        elif field_key == "tags":
            if isinstance(value, list):
                self.client.tags = [str(t).strip() for t in value if str(t).strip()]
            else:
                self.client.tags = [t.strip() for t in val_str.split(",") if t.strip()]
            updated = True

        if updated:
            if self.client_service:
                self.client_service.save_client(self.client)
            if self.on_updated_callback:
                try:
                    self.on_updated_callback(self.client)
                except Exception:
                    pass
            return True

        return False


class ConnectorInspectable(InspectableObject):
    """Adapter wrapping a ConnectorItem instance into the InspectableObject contract."""

    def __init__(self, connector_item):
        self.connector = connector_item

    def get_display_name(self) -> str:
        if not self.connector:
            return "Relationship"
        from ui.lab.models.relationship_registry import RelationshipRegistry
        lbl = RelationshipRegistry.get_label(self.connector.relationship_type)
        if self.connector.title:
            return f"Relationship: {lbl} ({self.connector.title})"
        return f"Relationship: {lbl}"

    def get_display_icon(self) -> str:
        return "🔗"

    def get_inspection_sections(self) -> List[InspectableSection]:
        if not self.connector:
            return []

        from ui.lab.models.relationship_registry import RelationshipRegistry
        c = self.connector
        curr_rel = getattr(c, "relationship_type", "related_to") or "related_to"
        all_defs = RelationshipRegistry.all_definitions()
        opts = [d.label for d in all_defs]

        curr_label = RelationshipRegistry.get_label(curr_rel)

        rel_fields = [
            InspectableField("relationship_type", "Relationship Type", "enum", value=curr_label, options=opts),
            InspectableField("title", "Custom Title", "string", value=str(c.title or "")),
            InspectableField("notes", "Decision Notes (Rationale)", "text", value=str(getattr(c, "notes", ""))),
            InspectableField("weight", "Relationship Weight", "string", value=str(getattr(c.relationship, "weight", 1.0))),
            InspectableField("created_by", "Created By", "readonly", value=str(getattr(c.relationship, "created_by", "manual"))),
        ]
        sections = [InspectableSection("Relationship Properties", rel_fields)]

        endpoints_fields = [
            InspectableField("source_id", "Source Node ID", "readonly", value=str(c.source_id)),
            InspectableField("source_anchor", "Source Anchor", "string", value=str(getattr(c, "source_anchor", "center"))),
            InspectableField("target_id", "Target Node ID", "readonly", value=str(c.target_id)),
            InspectableField("target_anchor", "Target Anchor", "string", value=str(getattr(c, "target_anchor", "center"))),
            InspectableField("id", "Relationship ID", "readonly", value=str(c.id)),
        ]
        sections.append(InspectableSection("Endpoints & Graph", endpoints_fields))
        return sections

    def set_inspectable_property(self, field_key: str, value: Any) -> bool:
        if not self.connector or not hasattr(self.connector, "_manager") or not self.connector._manager:
            return False

        c = self.connector
        mgr = c._manager

        if field_key == "relationship_type":
            from ui.lab.models.relationship_registry import RelationshipRegistry
            # Lookup definition ID by label
            val_str = str(value or "Related To")
            target_id = "related_to"
            for d in RelationshipRegistry.all_definitions():
                if d.label.lower() == val_str.lower() or d.id.lower() == val_str.lower():
                    target_id = d.id
                    break
            mgr.change_type(c.id, target_id)
            return True
        elif field_key in ("title", "label"):
            mgr.update_relationship(c.id, title=str(value or "").strip())
            return True
        elif field_key == "notes":
            mgr.update_relationship(c.id, notes=str(value or "").strip())
            return True
        elif field_key == "weight":
            try:
                w = float(value)
                mgr.update_relationship(c.id, weight=w)
                return True
            except Exception:
                return False
        elif field_key == "source_anchor":
            mgr.update_relationship(c.id, source_anchor=str(value or "center"))
            return True
        elif field_key == "target_anchor":
            mgr.update_relationship(c.id, target_anchor=str(value or "center"))
            return True
        return False
