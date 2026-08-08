import uuid
from pathlib import Path
from typing import List, Dict, Any
from ui.lab.drop.drop_context import DropContext


class ThreeDDropHandler:
    """Handler for 3D Asset reference file drop operations onto the spatial Lab canvas.

    Converts local 3D file reference paths into 3D Asset Reference Node dictionaries
    without copying, moving, duplicating, or loading heavy mesh data into memory.
    """

    FORMAT_LABELS = {
        ".fbx": "FBX 3D Model",
        ".obj": "Wavefront OBJ Model",
        ".glb": "glTF Binary Asset",
        ".gltf": "glTF JSON Asset",
        ".blend": "Blender Project File",
        ".abc": "Alembic Geometry Cache",
        ".usd": "Universal Scene Description",
        ".usda": "USD ASCII Scene",
        ".usdc": "USD Crate Binary",
        ".usdz": "USD Zip Package",
        ".ztl": "ZBrush Tool File",
        ".ma": "Maya ASCII Scene",
        ".mb": "Maya Binary Scene",
        ".max": "3ds Max Scene File",
    }

    SUPPORTED_EXTENSIONS = set(FORMAT_LABELS.keys())

    def can_handle(self, context: DropContext) -> bool:
        if not context or not context.has_files():
            return False
        for p in context.paths:
            if p.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                return True
        return False

    def handle_drop(self, context: DropContext) -> List[Dict[str, Any]]:
        if not context or not context.has_files():
            return []

        nodes = []
        base_x = context.scene_pos.x() if context.scene_pos else 0.0
        base_y = context.scene_pos.y() if context.scene_pos else 0.0
        offset_step = 30.0

        valid_index = 0
        for p in context.paths:
            ext = p.suffix.lower()
            if ext not in self.SUPPORTED_EXTENSIONS:
                continue

            abs_path = p.resolve()
            rel_or_abs = str(abs_path)
            if context.project_location:
                try:
                    proj_root = Path(context.project_location).resolve()
                    if proj_root in abs_path.parents or proj_root == abs_path:
                        rel_or_abs = str(abs_path.relative_to(proj_root)).replace("\\", "/")
                except Exception:
                    pass

            # Calculate staggered position for multi-file drop
            x_pos = base_x + (valid_index * offset_step)
            y_pos = base_y + (valid_index * offset_step)

            format_lbl = self.FORMAT_LABELS.get(ext, "3D Model Asset")

            node_data = {
                "id": str(uuid.uuid4()),
                "type": "asset.3d",
                "transform": {
                    "x": round(x_pos, 2),
                    "y": round(y_pos, 2),
                    "z": 1,
                    "width": 320.0,
                    "height": 260.0,
                    "rotation": 0.0,
                },
                "style": {
                    "background": "#1E2029",
                    "accent": "#10B981",
                },
                "metadata": {
                    "version": 1,
                    "locked": False,
                },
                "payload": {
                    "asset_path": rel_or_abs,
                    "image_path": rel_or_abs,
                    "absolute_path": str(abs_path),
                    "filename": abs_path.name,
                    "file_name": abs_path.name,
                    "extension": ext,
                    "format_label": format_lbl,
                    "file_size_str": "",
                    "display_mode": "icon",
                    "title": "",
                    "caption": "",
                    "layout": {
                        "aspect_ratio": 1.23,
                        "width": 320.0,
                        "height": 260.0,
                    }
                }
            }
            nodes.append(node_data)
            valid_index += 1

        return nodes
