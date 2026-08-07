from typing import List, Any
from pathlib import Path

from core.inspectable import InspectableObject, InspectableSection, InspectableField


class ProjectInspectable(InspectableObject):
    """Adapter wrapping Project model into the InspectableObject contract."""

    def __init__(self, project, project_service=None, client_service=None, on_updated_callback=None):
        self.project = project
        self.project_service = project_service
        self.client_service = client_service
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

        # Section 3: Appearance
        snapshot_path = str(Path(p.location) / "snapshot.png") if getattr(p, "location", None) else ""
        appearance_fields = [
            InspectableField("snapshot", "Cover Image", "image", value=snapshot_path),
            InspectableField("cover_actions", "Cover Actions", "cover_actions", value=snapshot_path),
        ]

        # Section 4: Metadata (Read-Only)
        created_str = p.created.strftime("%d %b %Y %H:%M") if getattr(p, "created", None) else "—"
        modified_str = p.modified.strftime("%d %b %Y %H:%M") if getattr(p, "modified", None) else created_str
        proj_id = Path(p.location).name if getattr(p, "location", None) else "—"
        metadata_fields = [
            InspectableField("created", "Created", "readonly", value=created_str),
            InspectableField("modified", "Modified", "readonly", value=modified_str),
            InspectableField("location", "Location Path", "readonly", value=str(getattr(p, "location", "—"))),
            InspectableField("id", "Project ID", "readonly", value=proj_id),
        ]

        return [
            InspectableSection("General", general_fields),
            InspectableSection("Organization", org_fields),
            InspectableSection("Appearance", appearance_fields),
            InspectableSection("Metadata", metadata_fields),
        ]

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

    def __init__(self, node_item):
        self.node_item = node_item

    def get_display_name(self) -> str:
        if self.node_item and getattr(self.node_item, "definition", None):
            return self.node_item.definition.title
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

        fields = [
            InspectableField("type_id", "Node Type", "readonly", value=defn.type_id if defn else "node"),
            InspectableField("id", "Node ID", "readonly", value=node.id),
        ]

        if getattr(node, "payload", None):
            payload = node.payload
            if "color_theme" in payload or "theme" in payload or "child_node_ids" in payload:
                sections = []
                frame_fields = [
                    InspectableField("payload.title", "Title", "string", value=str(payload.get("title", "Section Frame"))),
                    InspectableField("payload.theme", "Theme", "enum", value=str(payload.get("theme", payload.get("color_theme", "blue"))).lower(), options=["gray", "blue", "green", "yellow", "red", "purple"]),
                    InspectableField("payload.locked", "Locked", "boolean", value=bool(payload.get("locked", False))),
                    InspectableField("payload.collapsed", "Collapsed", "boolean", value=bool(payload.get("collapsed", False))),
                ]
                sections.append(InspectableSection("Frame Properties", frame_fields))

                child_count = len(node.attached_nodes()) if hasattr(node, "attached_nodes") else len(payload.get("child_node_ids", []))
                org_fields = [
                    InspectableField("children_count", "Children", "readonly", value=f"{child_count} nodes"),
                ]
                sections.append(InspectableSection("Organization", org_fields))
                return sections

            if "image_path" in payload:
                sections = []
                general_fields = [
                    InspectableField("payload.title", "Title", "string", value=str(payload.get("title", ""))),
                    InspectableField("payload.caption", "Caption", "text", value=str(payload.get("caption", ""))),
                    InspectableField("payload.fit_mode", "Fit Mode", "enum", value=str(payload.get("fit_mode", "fit")), options=["fit", "fill"]),
                ]
                sections.append(InspectableSection("Reference Properties", general_fields))

                abs_path = node._resolve_abs_path() if hasattr(node, "_resolve_abs_path") else None
                filename = payload.get("filename") or "—"
                rel_path = payload.get("image_path") or "—"
                resolution = "—"
                file_size_str = "—"
                mtime_str = "—"

                if abs_path and abs_path.exists():
                    raw_w = payload.get("layout", {}).get("raw_width")
                    raw_h = payload.get("layout", {}).get("raw_height")
                    if raw_w and raw_h:
                        resolution = f"{raw_w} × {raw_h}"
                    try:
                        from datetime import datetime
                        size_bytes = abs_path.stat().st_size
                        if size_bytes >= 1024 * 1024:
                            file_size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
                        else:
                            file_size_str = f"{size_bytes / 1024:.1f} KB"
                        mtime_str = datetime.fromtimestamp(abs_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        pass

                meta_fields = [
                    InspectableField("filename", "Filename", "readonly", value=filename),
                    InspectableField("relative_path", "Location", "readonly", value=rel_path),
                    InspectableField("resolution", "Resolution", "readonly", value=resolution),
                    InspectableField("filesize", "File Size", "readonly", value=file_size_str),
                    InspectableField("modified", "Modified", "readonly", value=mtime_str),
                ]
                sections.append(InspectableSection("Image Metadata", meta_fields))
                return sections

            for k, v in payload.items():
                if k != "layout":
                    fields.append(InspectableField(f"payload.{k}", k.capitalize(), "string", value=str(v)))

        return [InspectableSection("Node Properties", fields)]

    def set_inspectable_property(self, field_key: str, value: Any) -> bool:
        if not self.node_item:
            return False
        if field_key in ("payload.theme", "payload.color_theme") and hasattr(self.node_item, "set_color_theme"):
            self.node_item.set_color_theme(str(value))
            return True
        if field_key == "payload.locked" and hasattr(self.node_item, "set_locked"):
            self.node_item.set_locked(bool(value))
            return True
        if field_key == "payload.collapsed" and hasattr(self.node_item, "set_collapsed"):
            self.node_item.set_collapsed(bool(value))
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
        for n in self.nodes:
            t_name = n.definition.name if getattr(n, "definition", None) else n.__class__.__name__.replace("Item", "")
            type_counts[t_name] = type_counts.get(t_name, 0) + 1

        type_summary = ", ".join(f"{count} {t}" for t, count in type_counts.items())

        fields = [
            InspectableField("selection_count", "Selection Count", "readonly", value=f"{len(self.nodes)} nodes"),
            InspectableField("node_types", "Node Types", "readonly", value=type_summary),
        ]

        return [InspectableSection("Selection Summary", fields)]

    def set_inspectable_property(self, field_key: str, value: Any) -> bool:
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
