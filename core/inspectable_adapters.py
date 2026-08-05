from typing import List, Any
from pathlib import Path

from core.inspectable import InspectableObject, InspectableSection, InspectableField


class ProjectInspectable(InspectableObject):
    """Adapter wrapping Project model into the InspectableObject contract."""

    def __init__(self, project, project_service=None, on_updated_callback=None):
        self.project = project
        self.project_service = project_service
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
        org_fields = [
            InspectableField("tags", "Tags", "tags", value=", ".join(getattr(p, "tags", [])) if getattr(p, "tags", None) else ""),
            InspectableField("client", "Client", "string", value=getattr(p, "client", "")),
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
            self.project.client = str(value)
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
            if "color_theme" in payload:
                sections = []
                frame_fields = [
                    InspectableField("payload.title", "Frame Title", "string", value=str(payload.get("title", "Section Frame"))),
                    InspectableField("payload.color_theme", "Color Theme", "enum", value=str(payload.get("color_theme", "purple")), options=["purple", "blue", "green", "amber", "red", "gray"]),
                    InspectableField("payload.collapsed", "Collapsed", "boolean", value=bool(payload.get("collapsed", False))),
                ]
                sections.append(InspectableSection("Frame Properties", frame_fields))
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
        if field_key == "payload.color_theme" and hasattr(self.node_item, "set_color_theme"):
            self.node_item.set_color_theme(str(value))
            return True
        if field_key == "payload.collapsed" and hasattr(self.node_item, "set_collapsed"):
            self.node_item.set_collapsed(bool(value))
            return True
        if field_key.startswith("payload."):
            real_key = field_key.split(".", 1)[1]
            self.node_item.on_property_changed(real_key, value)
            return True
        return False
