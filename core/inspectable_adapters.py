from typing import List, Any
from pathlib import Path

from core.inspectable import InspectableObject, InspectableSection, InspectableField


class ProjectInspectable(InspectableObject):
    """Adapter wrapping Project model into the InspectableObject contract."""

    def __init__(self, project, project_service=None, client_service=None, lab_service=None, project_context_service=None, on_updated_callback=None):
        self.project = project
        self.project_service = project_service
        self.client_service = client_service
        self.lab_service = lab_service
        self.project_context_service = project_context_service
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

        sections = [
            InspectableSection("General", general_fields),
            InspectableSection("Organization", org_fields),
        ]

        # Section 3: Project Overview / Metrics (Derived)
        if self.project_context_service:
            try:
                ctx = self.project_context_service.get_project_context(p)
                avail = ctx.availability_summary
                lib_str = f"{ctx.library_summary.total_linked_assets} ({avail.online_library_assets} 🟢, {avail.offline_library_assets} 🟠, {avail.missing_library_assets} 🔴)"
                overview_fields = [
                    InspectableField("overview_assets", "Total Assets", "readonly", value=str(ctx.asset_summary.total_assets)),
                    InspectableField("overview_knowledge", "Knowledge Notes", "readonly", value=str(ctx.knowledge_summary.total_notes)),
                    InspectableField("overview_library", "Library References", "readonly", value=lib_str),
                    InspectableField("overview_lab", "Lab Boards", "readonly", value=f"{ctx.lab_summary.total_boards} ({ctx.lab_summary.total_nodes} nodes)"),
                    InspectableField("overview_tasks", "Checklist Tasks", "readonly", value=f"{ctx.lab_summary.task_status.get('completed', 0)} / {ctx.lab_summary.task_status.get('total', 0)} Done"),
                ]
                sections.append(InspectableSection("Project Overview", overview_fields))
            except Exception:
                pass
        elif self.lab_service:
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
        cat = str(self.asset_dict.get("category", "")).lower()
        if cat == "renders":
            return "🎬"
        elif cat == "exports":
            return "📤"
        elif cat == "references":
            return "🖼️"
        return "📦"

    def get_inspection_sections(self) -> List[InspectableSection]:
        a = self.asset_dict
        cat = str(a.get("category", "")).lower()
        filename = a.get("filename", "—")
        friendly_type = a.get("friendly_type", "—")
        rel_path = a.get("relative_path", "—")
        tags_val = ", ".join(a.get("tags", [])) if a.get("tags") else ""
        notes_val = a.get("notes", "")

        fields = []

        if cat == "renders":
            fields.append(InspectableField("filename", "Filename", "readonly", value=filename))
            fields.append(InspectableField("friendly_type", "Format", "readonly", value=friendly_type))

            # Resolution if reliably available
            resolution = a.get("resolution") or a.get("metadata", {}).get("resolution")
            if not resolution and a.get("absolute_path"):
                try:
                    p = Path(a["absolute_path"])
                    if p.exists() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
                        from PySide6.QtGui import QImageReader
                        reader = QImageReader(str(p))
                        sz = reader.size()
                        if sz.isValid():
                            resolution = f"{sz.width()} × {sz.height()}"
                except Exception:
                    pass
            if resolution:
                fields.append(InspectableField("resolution", "Resolution", "readonly", value=str(resolution)))

            # Frame range if reliably available
            frame_range = a.get("frame_range") or a.get("metadata", {}).get("frame_range")
            if frame_range:
                fields.append(InspectableField("frame_range", "Frame Range", "readonly", value=str(frame_range)))

            # Version if reliably available
            version = a.get("version") or a.get("metadata", {}).get("version")
            if version:
                fields.append(InspectableField("version", "Version", "readonly", value=str(version)))

            fields.append(InspectableField("relative_path", "Path", "readonly", value=rel_path))
            fields.append(InspectableField("tags", "Tags", "tags", value=tags_val))
            fields.append(InspectableField("notes", "Notes", "text", value=notes_val))

            return [InspectableSection("Render Properties", fields)]

        elif cat == "exports":
            fields.append(InspectableField("filename", "Filename", "readonly", value=filename))
            fields.append(InspectableField("friendly_type", "Format", "readonly", value=friendly_type))

            # Version if reliably available
            version = a.get("version") or a.get("metadata", {}).get("version")
            if version:
                fields.append(InspectableField("version", "Version", "readonly", value=str(version)))

            # Engine / Target if reliably available
            target_engine = a.get("target_engine") or a.get("metadata", {}).get("target_engine")
            if target_engine:
                fields.append(InspectableField("target_engine", "Target Engine", "readonly", value=str(target_engine)))

            # LOD if reliably available
            lod = a.get("lod") or a.get("metadata", {}).get("lod")
            if lod:
                fields.append(InspectableField("lod", "LOD Level", "readonly", value=str(lod)))

            fields.append(InspectableField("relative_path", "Path", "readonly", value=rel_path))
            fields.append(InspectableField("tags", "Tags", "tags", value=tags_val))
            fields.append(InspectableField("notes", "Notes", "text", value=notes_val))

            return [InspectableSection("Export Properties", fields)]

        elif a.get("is_library_reference"):
            avail_val = a.get("availability") or "Available"
            drive_val = a.get("drive_name") or a.get("drive_id") or "External Drive"
            fields = [
                InspectableField("source", "Reference Source", "readonly", value="📚 Global Asset Library Reference"),
                InspectableField("filename", "Filename", "readonly", value=filename),
                InspectableField("friendly_type", "Type", "readonly", value=friendly_type),
                InspectableField("availability", "Availability", "readonly", value=avail_val),
                InspectableField("drive", "Source Drive", "readonly", value=str(drive_val)),
                InspectableField("drive_relative_path", "Drive Path", "readonly", value=a.get("drive_relative_path", "—")),
                InspectableField("tags", "Tags", "tags", value=tags_val),
                InspectableField("notes", "Notes", "text", value=notes_val),
            ]
            return [InspectableSection("Library Reference Properties", fields)]

        else:
            fields = [
                InspectableField("filename", "Filename", "readonly", value=filename),
                InspectableField("friendly_type", "Type", "readonly", value=friendly_type),
                InspectableField("category", "Category", "readonly", value=a.get("category", "—")),
                InspectableField("relative_path", "Path", "readonly", value=rel_path),
                InspectableField("tags", "Tags", "tags", value=tags_val),
                InspectableField("notes", "Notes", "text", value=notes_val),
            ]
            return [InspectableSection("Asset Properties", fields)]

    def set_inspectable_property(self, field_key: str, value: Any) -> bool:
        if field_key == "tags":
            tags_list = [t.strip() for t in str(value).split(",") if t.strip()]
            self.asset_dict["tags"] = tags_list
            if self.asset_service and self.project:
                target_ids = [fa["id"] for fa in self.asset_dict.get("frame_assets", []) if "id" in fa]
                if not target_ids and self.asset_dict.get("id"):
                    target_ids = [self.asset_dict["id"]]
                for aid in target_ids:
                    self.asset_service.update_asset(self.project, aid, {"tags": tags_list})
            return True
        elif field_key == "notes":
            notes_str = str(value)
            self.asset_dict["notes"] = notes_str
            if self.asset_service and self.project:
                target_ids = [fa["id"] for fa in self.asset_dict.get("frame_assets", []) if "id" in fa]
                if not target_ids and self.asset_dict.get("id"):
                    target_ids = [self.asset_dict["id"]]
                for aid in target_ids:
                    self.asset_service.update_asset(self.project, aid, {"notes": notes_str})
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


class LibraryAssetInspectable(InspectableObject):
    """Adapter wrapping a LibraryAsset or dictionary into the InspectableObject contract."""

    def __init__(self, library_asset, library_service=None, context=None, on_updated_callback=None):
        self.asset = library_asset
        self.library_service = library_service
        self.context = context
        self.on_updated_callback = on_updated_callback

    def get_display_name(self) -> str:
        if isinstance(self.asset, dict):
            return self.asset.get("filename", "Library Asset")
        return getattr(self.asset, "filename", "Library Asset")

    def get_display_icon(self) -> str:
        return "📚"

    def _get_val(self, key, default=None):
        if isinstance(self.asset, dict):
            return self.asset.get(key, default)
        return getattr(self.asset, key, default)

    def get_inspection_sections(self) -> List[InspectableSection]:
        if not self.asset:
            return []

        filename = self._get_val("filename", "—")
        friendly_type = self._get_val("friendly_type", "—")
        category = self._get_val("category", "—")
        drive_rel = self._get_val("drive_relative_path", "—")
        tags_raw = self._get_val("tags", [])
        tags_val = ", ".join(tags_raw) if tags_raw else ""
        notes_val = self._get_val("notes", "")
        favorite = bool(self._get_val("favorite", False))

        # Resolve drive name
        drive_name = "External Drive"
        drive_id = self._get_val("drive_id", "")
        if self.library_service and hasattr(self.library_service, "get_drive"):
            d = self.library_service.get_drive(drive_id)
            if d:
                drive_name = d.name

        # Resolve availability
        avail_str = "Available"
        if self.library_service and hasattr(self.library_service, "get_asset_availability"):
            avail_enum = self.library_service.get_asset_availability(self.asset)
            avail_str = avail_enum.value if hasattr(avail_enum, "value") else str(avail_enum)

        # Resolve project reference status
        proj_ref_val = "Not Referenced"
        curr_proj = getattr(self.context, "current_project", None) if getattr(self, "context", None) else None
        if curr_proj:
            refs = self._get_val("project_references", [])
            is_ref = any(r.get("project_location") == curr_proj.location for r in refs)
            if is_ref:
                proj_ref_val = f"Referenced in '{curr_proj.name}'"
            else:
                proj_ref_val = f"Not Referenced in '{curr_proj.name}'"

        # File size formatting
        size_bytes = self._get_val("file_size", 0)
        if size_bytes < 1024:
            size_str = f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

        fields = [
            InspectableField("source", "Catalog Source", "readonly", value="📚 Global Asset Library"),
            InspectableField("filename", "Filename", "readonly", value=filename),
            InspectableField("friendly_type", "Type", "readonly", value=friendly_type),
            InspectableField("category", "Category", "readonly", value=category),
            InspectableField("drive", "Location / Drive", "readonly", value=drive_name),
            InspectableField("drive_relative_path", "Relative Path", "readonly", value=drive_rel),
            InspectableField("availability", "Availability", "readonly", value=avail_str),
            InspectableField("project_reference", "Project Reference", "readonly", value=proj_ref_val),
            InspectableField("file_size", "Size", "readonly", value=size_str),
        ]

        version = self._get_val("version")
        if version:
            fields.append(InspectableField("version", "Version", "readonly", value=str(version)))

        lod = self._get_val("lod")
        if lod:
            fields.append(InspectableField("lod", "LOD Level", "readonly", value=str(lod)))

        fields.append(InspectableField("favorite", "Favorite", "boolean", value=favorite))
        fields.append(InspectableField("tags", "Tags", "tags", value=tags_val))
        fields.append(InspectableField("notes", "Notes", "text", value=notes_val))

        return [InspectableSection("Library Asset Properties", fields)]

    def set_inspectable_property(self, field_key: str, value: Any) -> bool:
        if not self.asset:
            return False

        updated = False
        asset_id = self._get_val("id")

        if field_key == "tags":
            if isinstance(value, str):
                tags_list = [t.strip() for t in value.split(",") if t.strip()]
            elif isinstance(value, (list, tuple)):
                tags_list = [str(t).strip() for t in value if str(t).strip()]
            else:
                tags_list = []

            if isinstance(self.asset, dict):
                self.asset["tags"] = tags_list
            else:
                self.asset.tags = tags_list

            if self.library_service and asset_id:
                self.library_service.update_asset(asset_id, tags=tags_list)
            updated = True

        elif field_key == "notes":
            notes_str = str(value)
            if isinstance(self.asset, dict):
                self.asset["notes"] = notes_str
            else:
                self.asset.notes = notes_str

            if self.library_service and asset_id:
                self.library_service.update_asset(asset_id, notes=notes_str)
            updated = True

        elif field_key == "favorite":
            fav_bool = bool(value)
            if isinstance(self.asset, dict):
                self.asset["favorite"] = fav_bool
            else:
                self.asset.favorite = fav_bool

            if self.library_service and asset_id:
                self.library_service.update_asset(asset_id, favorite=fav_bool)
            updated = True

        if updated and self.on_updated_callback:
            try:
                self.on_updated_callback(self.asset)
            except Exception:
                pass

        return updated


class LibraryFolderInspectable(InspectableObject):
    """Adapter wrapping a LibraryLocation or Library subfolder into the InspectableObject contract."""

    def __init__(self, folder_data: dict, library_service=None, on_updated_callback=None):
        self.folder_data = folder_data or {}
        self.library_service = library_service
        self.on_updated_callback = on_updated_callback

    def get_display_name(self) -> str:
        return self.folder_data.get("name", "Folder Details")

    def get_display_icon(self) -> str:
        if self.folder_data.get("favorite"):
            return "⭐📁"
        return "📁"

    def get_inspection_sections(self) -> List[InspectableSection]:
        f = self.folder_data
        name = f.get("name", "—")
        drive_name = f.get("drive_name", "External Drive")
        rel_path = f.get("relative_path", "—")
        avail_str = f.get("availability", "Available")
        asset_count = f.get("asset_count", 0)
        favorite = bool(f.get("favorite", False))

        fields = [
            InspectableField("name", "Folder Name", "readonly", value=name),
            InspectableField("drive", "Location / Drive", "readonly", value=drive_name),
            InspectableField("relative_path", "Relative Path", "readonly", value=rel_path),
            InspectableField("availability", "Availability", "readonly", value=avail_str),
            InspectableField("item_count", "Total Items", "readonly", value=f"{asset_count} items"),
            InspectableField("favorite", "Favorite Folder", "boolean", value=favorite),
        ]

        return [InspectableSection("Folder Properties", fields)]

    def set_inspectable_property(self, field_key: str, value: Any) -> bool:
        if field_key == "favorite":
            fav_bool = bool(value)
            self.folder_data["favorite"] = fav_bool
            loc_id = self.folder_data.get("location_id")
            if self.library_service and loc_id:
                self.library_service.update_location(loc_id, favorite=fav_bool)

            if self.on_updated_callback:
                try:
                    self.on_updated_callback(self.folder_data)
                except Exception:
                    pass
            return True
        return False


class KnowledgeDocumentInspectable(InspectableObject):
    """Adapter wrapping a KnowledgeDocument model into the InspectableObject contract."""

    def __init__(self, doc, knowledge_service=None, on_updated_callback=None):
        self.doc = doc
        self.knowledge_service = knowledge_service
        self.on_updated_callback = on_updated_callback

    def get_display_name(self) -> str:
        return self.doc.title if self.doc else "Untitled Note"

    def get_display_icon(self) -> str:
        if self.doc and getattr(self.doc, "favorite", False):
            return "⭐📝"
        return "📝"

    def get_inspection_sections(self) -> List[InspectableSection]:
        if not self.doc:
            return []

        # Resolve Folder Name
        folder_name = "Root (No Folder)"
        folder_id = getattr(self.doc, "folder_id", None)
        if folder_id and self.knowledge_service:
            try:
                fld = self.knowledge_service.get_folder(folder_id)
                if fld:
                    folder_name = fld.name
            except Exception:
                folder_name = str(folder_id)

        # General properties
        title_val = getattr(self.doc, "title", "Untitled Note")
        tags_val = getattr(self.doc, "tags", [])
        tags_str = ", ".join(tags_val) if isinstance(tags_val, list) else str(tags_val)
        fav_val = bool(getattr(self.doc, "favorite", False))

        general_fields = [
            InspectableField("title", "Document Title", "string", value=title_val),
            InspectableField("folder", "Folder", "readonly", value=folder_name),
            InspectableField("favorite", "Favorite", "boolean", value=fav_val),
            InspectableField("tags", "Tags", "tags", value=tags_str),
        ]

        # Metadata
        created_raw = getattr(self.doc, "created", None)
        modified_raw = getattr(self.doc, "modified", None)
        created_str = "—"
        modified_str = "—"
        if created_raw:
            try:
                from datetime import datetime
                created_str = datetime.fromisoformat(created_raw).strftime("%d %b %Y %H:%M")
            except Exception:
                created_str = str(created_raw)
        if modified_raw:
            try:
                from datetime import datetime
                modified_str = datetime.fromisoformat(modified_raw).strftime("%d %b %Y %H:%M")
            except Exception:
                modified_str = str(modified_raw)

        content = getattr(self.doc, "content", "")
        metadata_fields = [
            InspectableField("id", "Document ID", "readonly", value=getattr(self.doc, "id", "—")),
            InspectableField("char_count", "Characters", "readonly", value=f"{len(content)} characters"),
            InspectableField("created", "Created", "readonly", value=created_str),
            InspectableField("modified", "Modified", "readonly", value=modified_str),
        ]

        # Relationships
        proj_count = len(getattr(self.doc, "project_ids", []))
        lib_count = len(getattr(self.doc, "library_asset_ids", []))
        proj_asset_count = len(getattr(self.doc, "project_asset_refs", []))
        lab_count = len(getattr(self.doc, "lab_node_ids", []))
        total_rels = proj_count + lib_count + proj_asset_count + lab_count

        rel_fields = [
            InspectableField("total_relationships", "Total Linked", "readonly", value=f"{total_rels} items"),
            InspectableField("linked_projects", "Projects", "readonly", value=f"{proj_count} linked" if proj_count else "None"),
            InspectableField("linked_library_assets", "Library Assets", "readonly", value=f"{lib_count} linked" if lib_count else "None"),
            InspectableField("linked_project_assets", "Project Assets", "readonly", value=f"{proj_asset_count} linked" if proj_asset_count else "None"),
            InspectableField("linked_lab_nodes", "Lab Nodes", "readonly", value=f"{lab_count} linked" if lab_count else "None"),
        ]

        return [
            InspectableSection("Document Properties", general_fields),
            InspectableSection("Relationships", rel_fields),
            InspectableSection("Metadata", metadata_fields),
        ]

    def set_inspectable_property(self, field_key: str, value: Any) -> bool:
        if not self.doc:
            return False

        updated = False
        doc_id = getattr(self.doc, "id", None)

        if field_key == "title":
            title_str = str(value).strip() or "Untitled Note"
            self.doc.title = title_str
            if self.knowledge_service and doc_id:
                self.knowledge_service.update_document(doc_id, title=title_str)
            updated = True

        elif field_key in ("favorite", "is_favorite"):
            fav_bool = bool(value)
            self.doc.favorite = fav_bool
            if self.knowledge_service and doc_id:
                self.knowledge_service.update_document(doc_id, favorite=fav_bool)
            updated = True

        elif field_key == "tags":
            if isinstance(value, str):
                tags_list = [t.strip() for t in value.split(",") if t.strip()]
            elif isinstance(value, (list, tuple)):
                tags_list = [str(t).strip() for t in value if str(t).strip()]
            else:
                tags_list = []
            self.doc.tags = tags_list
            if self.knowledge_service and doc_id:
                self.knowledge_service.update_document(doc_id, tags=tags_list)
            updated = True

        if updated and self.on_updated_callback:
            try:
                self.on_updated_callback(self.doc)
            except Exception:
                pass

        return updated
