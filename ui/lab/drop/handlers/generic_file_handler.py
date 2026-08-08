import uuid
from pathlib import Path
from typing import List, Dict, Any
from ui.lab.drop.drop_context import DropContext
from ui.lab.drop.handlers.image_handler import ImageDropHandler
from ui.lab.drop.handlers.pdf_handler import PdfDropHandler
from ui.lab.drop.handlers.threed_handler import ThreeDDropHandler
from ui.lab.drop.handlers.archive_handler import ArchiveDropHandler


class GenericFileDropHandler:
    """Catch-all Handler for generic file reference drop operations onto the spatial Lab canvas.

    Converts any file format (.psd, .c4d, .sbsar, .doc, etc.) into Generic File Reference
    node dictionaries without launching external applications or maintaining an exhaustive registry.
    """

    EXCLUDED_EXTENSIONS = (
        ImageDropHandler.SUPPORTED_EXTENSIONS
        | PdfDropHandler.SUPPORTED_EXTENSIONS
        | ThreeDDropHandler.SUPPORTED_EXTENSIONS
        | ArchiveDropHandler.SUPPORTED_EXTENSIONS
    )

    def can_handle(self, context: DropContext) -> bool:
        if not context or not context.has_files():
            return False
        for p in context.paths:
            if p.is_file() and p.suffix.lower() not in self.EXCLUDED_EXTENSIONS:
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
            if not p.is_file():
                continue

            ext = p.suffix.lower()
            if ext in self.EXCLUDED_EXTENSIONS:
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
            ext_upper = ext.replace(".", "").upper() or "FILE"

            node_data = {
                "id": str(uuid.uuid4()),
                "type": "file.reference",
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
                    "accent": "#6366F1",
                },
                "metadata": {
                    "version": 1,
                    "locked": False,
                },
                "payload": {
                    "file_path": rel_or_abs,
                    "image_path": rel_or_abs,
                    "absolute_path": str(abs_path),
                    "filename": abs_path.name,
                    "file_name": abs_path.name,
                    "extension": ext,
                    "format_label": f"{ext_upper} File Reference",
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
