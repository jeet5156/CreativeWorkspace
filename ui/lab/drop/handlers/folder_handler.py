import uuid
from pathlib import Path
from typing import List, Dict, Any
from ui.lab.drop.drop_context import DropContext


class FolderDropHandler:
    """Handler for Directory / Folder drop operations onto the spatial Lab canvas.

    Converts local folder paths into Folder Reference Node dictionaries without copying,
    moving, monitoring, or enumerating folder contents.
    """

    def can_handle(self, context: DropContext) -> bool:
        if not context or not context.has_files():
            return False
        for p in context.paths:
            if p.exists() and p.is_dir():
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
            if not p.exists() or not p.is_dir():
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

            x_pos = base_x + (valid_index * offset_step)
            y_pos = base_y + (valid_index * offset_step)

            node_data = {
                "id": str(uuid.uuid4()),
                "type": "folder.reference",
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
                    "accent": "#F59E0B",
                },
                "metadata": {
                    "version": 1,
                    "locked": False,
                },
                "payload": {
                    "folder_path": rel_or_abs,
                    "image_path": rel_or_abs,
                    "absolute_path": str(abs_path),
                    "foldername": abs_path.name,
                    "filename": abs_path.name,
                    "file_name": abs_path.name,
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
