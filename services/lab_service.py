import json
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import QObject, Signal


class LabService(QObject):
    """Manages Lab board persistence (.lab.json files) in <ProjectRoot>/Lab/boards/."""

    board_updated = Signal(object, str)

    def __init__(self, project_service=None):
        super().__init__()
        self.project_service = project_service

    def get_boards_dir(self, project) -> Path:
        if not project or not getattr(project, "location", None):
            raise ValueError("Invalid project")
        boards_dir = Path(project.location) / "Lab" / "boards"
        boards_dir.mkdir(parents=True, exist_ok=True)
        return boards_dir

    def get_board_path(self, project, board_name: str = "Main") -> Path:
        sanitized_name = "".join(c for c in board_name if c.isalnum() or c in ("_", "-")).strip()
        if not sanitized_name:
            sanitized_name = "Main"
        return self.get_boards_dir(project) / f"{sanitized_name}.lab.json"

    def default_board_data(self, board_name: str = "Main") -> dict:
        now = datetime.now().isoformat()
        return {
            "version": "1.0",
            "board_id": f"board_{board_name.lower()}_001",
            "name": board_name,
            "created_at": now,
            "updated_at": now,
            "viewport": {
                "zoom": 1.0,
                "pan_x": 0.0,
                "pan_y": 0.0,
                "grid_visible": True,
                "grid_size": 20,
                "snap_to_grid": False,
                "active_tool": "select",
            },
            "items": [],
            "connectors": [],
            "groups": [],
        }

    def load_board(self, project, board_name: str = "Main") -> dict:
        path = self.get_board_path(project, board_name)
        if not path.exists():
            data = self.default_board_data(board_name)
            self.save_board(project, data, board_name=board_name)
            return data

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Ensure minimal required fields exist
            if "viewport" not in data or not isinstance(data["viewport"], dict):
                data["viewport"] = self.default_board_data(board_name)["viewport"]
            if "items" not in data:
                data["items"] = []
            if "connectors" not in data:
                data["connectors"] = []
            if "groups" not in data:
                data["groups"] = []

            return data
        except Exception:
            data = self.default_board_data(board_name)
            self.save_board(project, data, board_name=board_name)
            return data

    def save_board(self, project, board_data: dict, board_name: str = "Main") -> bool:
        path = self.get_board_path(project, board_name)
        board_data["updated_at"] = datetime.now().isoformat()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(board_data, f, indent=2)
            self.board_updated.emit(project, board_name)
            return True
        except Exception:
            return False

    def save_viewport(self, project, viewport_dict: dict, board_name: str = "Main") -> bool:
        board_data = self.load_board(project, board_name)
        board_data["viewport"].update(viewport_dict)
        return self.save_board(project, board_data, board_name=board_name)

    def load_items(self, project, board_name: str = "Main") -> list:
        board_data = self.load_board(project, board_name)
        return board_data.get("items", [])

    def save_items(self, project, items_list: list, board_name: str = "Main") -> bool:
        board_data = self.load_board(project, board_name)
        board_data["items"] = items_list
        return self.save_board(project, board_data, board_name=board_name)

    def save_item(self, project, item_dict: dict, board_name: str = "Main") -> bool:
        if not item_dict or "id" not in item_dict:
            return False
        board_data = self.load_board(project, board_name)
        items = board_data.get("items", [])
        updated = False
        for i, existing in enumerate(items):
            if existing.get("id") == item_dict["id"]:
                items[i] = item_dict
                updated = True
                break
        if not updated:
            items.append(item_dict)
        board_data["items"] = items
        return self.save_board(project, board_data, board_name=board_name)

    def remove_item(self, project, item_id: str, board_name: str = "Main") -> bool:
        board_data = self.load_board(project, board_name)
        items = board_data.get("items", [])
        new_items = [it for it in items if it.get("id") != item_id]
        if len(new_items) == len(items):
            return False
        board_data["items"] = new_items
        return self.save_board(project, board_data, board_name=board_name)
