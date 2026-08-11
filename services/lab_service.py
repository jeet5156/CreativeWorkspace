import json
import uuid
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import QObject, Signal


class LabService(QObject):
    """Manages Lab board persistence (<board_id>.lab.json) and board_manifest.json in <ProjectRoot>/Lab/boards/."""

    board_updated = Signal(object, str)
    manifest_updated = Signal(object)

    def __init__(self, project_service=None):
        super().__init__()
        self.project_service = project_service

    def get_boards_dir(self, project) -> Path:
        if not project or not getattr(project, "location", None):
            global_dir = Path.home() / ".creativeworkspace" / "workbench" / "boards"
            global_dir.mkdir(parents=True, exist_ok=True)
            return global_dir
        boards_dir = Path(project.location) / "Lab" / "boards"
        boards_dir.mkdir(parents=True, exist_ok=True)
        return boards_dir

    def get_manifest_path(self, project) -> Path:
        return self.get_boards_dir(project) / "board_manifest.json"

    def default_manifest_data(self) -> dict:
        return {
            "version": "1.0",
            "active_board_id": None,
            "last_view": {
                "zoom": 1.0,
                "pan_x": 0.0,
                "pan_y": 0.0,
                "grid_visible": True,
                "snap_to_grid": False,
            },
            "boards": [],
        }

    def default_board_entry(self, board_id: str, name: str, order: int = 0) -> dict:
        now = datetime.now().isoformat()
        return {
            "id": board_id,
            "name": name,
            "filename": f"{board_id}.lab.json",
            "created": now,
            "modified": now,
            "color": None,
            "icon": None,
            "thumbnail": None,
            "favorite": False,
            "locked": False,
            "order": order,
        }

    def default_board_data(self, board_id: str, name: str = "Main") -> dict:
        now = datetime.now().isoformat()
        return {
            "version": "1.0",
            "board_id": board_id,
            "name": name,
            "created": now,
            "modified": now,
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

    def get_manifest(self, project) -> dict:
        manifest_path = self.get_manifest_path(project)
        boards_dir = self.get_boards_dir(project)

        if not manifest_path.exists():
            manifest = self.default_manifest_data()
            main_path = boards_dir / "Main.lab.json"
            main_id = str(uuid.uuid4())

            if main_path.exists():
                # Migration: rename Main.lab.json to <main_id>.lab.json
                target_path = boards_dir / f"{main_id}.lab.json"
                try:
                    main_path.rename(target_path)
                except Exception:
                    pass
                entry = self.default_board_entry(main_id, "Main", order=0)
            else:
                entry = self.default_board_entry(main_id, "Main", order=0)
                board_data = self.default_board_data(main_id, "Main")
                board_file = boards_dir / f"{main_id}.lab.json"
                try:
                    with open(board_file, "w", encoding="utf-8") as f:
                        json.dump(board_data, f, indent=2)
                except Exception:
                    pass

            manifest["active_board_id"] = main_id
            manifest["boards"].append(entry)
            self.save_manifest(project, manifest)
            return manifest

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            if "boards" not in manifest or not isinstance(manifest["boards"], list):
                manifest["boards"] = []
            if "last_view" not in manifest or not isinstance(manifest["last_view"], dict):
                manifest["last_view"] = self.default_manifest_data()["last_view"]

            if not manifest["boards"]:
                main_id = str(uuid.uuid4())
                entry = self.default_board_entry(main_id, "Main", order=0)
                board_data = self.default_board_data(main_id, "Main")
                board_file = boards_dir / f"{main_id}.lab.json"
                with open(board_file, "w", encoding="utf-8") as f:
                    json.dump(board_data, f, indent=2)
                manifest["active_board_id"] = main_id
                manifest["boards"].append(entry)
                self.save_manifest(project, manifest)

            if not manifest.get("active_board_id") or not any(b.get("id") == manifest["active_board_id"] for b in manifest["boards"]):
                manifest["active_board_id"] = manifest["boards"][0]["id"]
                self.save_manifest(project, manifest)

            return manifest
        except Exception:
            manifest = self.default_manifest_data()
            main_id = str(uuid.uuid4())
            entry = self.default_board_entry(main_id, "Main", order=0)
            manifest["active_board_id"] = main_id
            manifest["boards"].append(entry)
            self.save_manifest(project, manifest)
            return manifest

    def save_manifest(self, project, manifest: dict) -> bool:
        manifest_path = self.get_manifest_path(project)
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
            self.manifest_updated.emit(project)
            return True
        except Exception:
            return False

    def list_boards(self, project) -> list:
        manifest = self.get_manifest(project)
        boards = manifest.get("boards", [])
        return sorted(boards, key=lambda b: (b.get("order", 0), b.get("created", "")))

    def get_board_entry(self, project, board_id_or_name: str) -> dict:
        manifest = self.get_manifest(project)
        for b in manifest.get("boards", []):
            if b.get("id") == board_id_or_name or b.get("name") == board_id_or_name:
                return b
        return None

    def get_active_board_id(self, project) -> str:
        manifest = self.get_manifest(project)
        return manifest.get("active_board_id")

    def set_active_board_id(self, project, board_id: str) -> bool:
        manifest = self.get_manifest(project)
        if any(b.get("id") == board_id for b in manifest.get("boards", [])):
            manifest["active_board_id"] = board_id
            return self.save_manifest(project, manifest)
        return False

    def get_board_path(self, project, board_id_or_name: str = "Main") -> Path:
        boards_dir = self.get_boards_dir(project)
        entry = self.get_board_entry(project, board_id_or_name)
        if entry:
            return boards_dir / f"{entry['id']}.lab.json"
        # Fallback sanitize if unknown identifier
        sanitized = "".join(c for c in board_id_or_name if c.isalnum() or c in ("_", "-")).strip() or "Main"
        return boards_dir / f"{sanitized}.lab.json"

    def create_board(self, project, name: str = "Untitled Board") -> dict:
        manifest = self.get_manifest(project)
        new_id = str(uuid.uuid4())
        order = len(manifest.get("boards", []))

        entry = self.default_board_entry(new_id, name.strip() or "Untitled Board", order=order)
        board_data = self.default_board_data(new_id, entry["name"])

        board_file = self.get_boards_dir(project) / f"{new_id}.lab.json"
        try:
            with open(board_file, "w", encoding="utf-8") as f:
                json.dump(board_data, f, indent=2)
        except Exception:
            pass

        manifest["boards"].append(entry)
        manifest["active_board_id"] = new_id
        self.save_manifest(project, manifest)
        self.board_updated.emit(project, new_id)
        return entry

    def rename_board(self, project, board_id: str, new_name: str) -> bool:
        cleaned_name = new_name.strip()
        if not cleaned_name:
            return False

        manifest = self.get_manifest(project)
        found = False
        for b in manifest.get("boards", []):
            if b.get("id") == board_id:
                b["name"] = cleaned_name
                b["modified"] = datetime.now().isoformat()
                found = True
                break

        if not found:
            return False

        self.save_manifest(project, manifest)

        # Update board file internally
        board_data = self.load_board(project, board_id)
        board_data["name"] = cleaned_name
        self.save_board(project, board_data, board_id)
        self.board_updated.emit(project, board_id)
        return True

    def duplicate_board(self, project, board_id: str, new_name: str = None) -> dict:
        manifest = self.get_manifest(project)
        source_entry = None
        for b in manifest.get("boards", []):
            if b.get("id") == board_id:
                source_entry = b
                break

        if not source_entry:
            return None

        source_name = source_entry["name"]
        if not new_name:
            existing_names = {b["name"] for b in manifest.get("boards", [])}
            candidate = f"{source_name} (Copy)"
            counter = 2
            while candidate in existing_names:
                candidate = f"{source_name} (Copy {counter})"
                counter += 1
            new_name = candidate

        source_data = self.load_board(project, board_id)
        new_id = str(uuid.uuid4())
        new_entry = self.default_board_entry(new_id, new_name, order=len(manifest.get("boards", [])))

        # Deep copy board data and re-ID items
        import copy
        new_board_data = copy.deepcopy(source_data)
        new_board_data["board_id"] = new_id
        new_board_data["name"] = new_name
        now = datetime.now().isoformat()
        new_board_data["created"] = now
        new_board_data["modified"] = now

        for item in new_board_data.get("items", []):
            item["id"] = str(uuid.uuid4())

        board_file = self.get_boards_dir(project) / f"{new_id}.lab.json"
        try:
            with open(board_file, "w", encoding="utf-8") as f:
                json.dump(new_board_data, f, indent=2)
        except Exception:
            pass

        manifest["boards"].append(new_entry)
        self.save_manifest(project, manifest)
        self.board_updated.emit(project, new_id)
        return new_entry

    def delete_board(self, project, board_id: str) -> bool:
        manifest = self.get_manifest(project)
        boards = manifest.get("boards", [])

        if len(boards) <= 1:
            raise ValueError("Cannot delete the final remaining board in a project.")

        target_idx = -1
        for i, b in enumerate(boards):
            if b.get("id") == board_id:
                target_idx = i
                break

        if target_idx == -1:
            return False

        # If deleting the active board, fallback to nearest remaining board
        if manifest.get("active_board_id") == board_id:
            fallback_idx = target_idx - 1 if target_idx > 0 else 1
            manifest["active_board_id"] = boards[fallback_idx]["id"]

        del boards[target_idx]
        manifest["boards"] = boards
        self.save_manifest(project, manifest)

        # Delete board file from disk
        board_file = self.get_boards_dir(project) / f"{board_id}.lab.json"
        try:
            if board_file.exists():
                board_file.unlink()
        except Exception:
            pass

        self.board_updated.emit(project, manifest.get("active_board_id"))
        return True

    def load_board(self, project, board_id_or_name: str = "Main", board_name: str = None, board_id: str = None) -> dict:
        identifier = board_id or board_name or board_id_or_name
        entry = self.get_board_entry(project, identifier)
        target_id = entry["id"] if entry else identifier
        name = entry["name"] if entry else "Main"

        path = self.get_board_path(project, target_id)

        if not path.exists():
            data = self.default_board_data(target_id, name)
            self.save_board(project, data, board_id_or_name=target_id)
            return data

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "viewport" not in data or not isinstance(data["viewport"], dict):
                data["viewport"] = self.default_board_data(target_id, name)["viewport"]
            if "items" not in data:
                data["items"] = []
            if "connectors" not in data:
                data["connectors"] = []
            if "groups" not in data:
                data["groups"] = []

            return data
        except Exception:
            data = self.default_board_data(target_id, name)
            self.save_board(project, data, board_id_or_name=target_id)
            return data

    def save_board(self, project, board_data: dict, board_id_or_name: str = "Main", board_name: str = None, board_id: str = None) -> bool:
        identifier = board_id or board_name or board_id_or_name
        entry = self.get_board_entry(project, identifier)
        target_id = entry["id"] if entry else identifier

        path = self.get_board_path(project, target_id)
        now = datetime.now().isoformat()
        board_data["modified"] = now

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(board_data, f, indent=2)

            # Update modified timestamp in manifest
            manifest = self.get_manifest(project)
            for b in manifest.get("boards", []):
                if b.get("id") == target_id:
                    b["modified"] = now
                    break
            self.save_manifest(project, manifest)

            self.board_updated.emit(project, target_id)
            return True
        except Exception:
            return False

    def save_viewport(self, project, viewport_dict: dict, board_id_or_name: str = "Main", board_name: str = None, board_id: str = None) -> bool:
        identifier = board_id or board_name or board_id_or_name
        manifest = self.get_manifest(project)
        if "last_view" not in manifest:
            manifest["last_view"] = {}
        manifest["last_view"].update(viewport_dict)
        self.save_manifest(project, manifest)

        board_data = self.load_board(project, board_id_or_name=identifier)
        board_data["viewport"].update(viewport_dict)
        return self.save_board(project, board_data, board_id_or_name=identifier)

    def load_items(self, project, board_id_or_name: str = "Main", board_name: str = None, board_id: str = None) -> list:
        identifier = board_id or board_name or board_id_or_name
        board_data = self.load_board(project, board_id_or_name=identifier)
        return board_data.get("items", [])

    def save_items(self, project, items_list: list, board_id_or_name: str = "Main", board_name: str = None, board_id: str = None, connectors_list: list = None) -> bool:
        identifier = board_id or board_name or board_id_or_name
        board_data = self.load_board(project, board_id_or_name=identifier)
        board_data["items"] = items_list
        if connectors_list is not None:
            board_data["connectors"] = connectors_list
        return self.save_board(project, board_data, board_id_or_name=identifier)

    def save_item(self, project, item_dict: dict, board_id_or_name: str = "Main", board_name: str = None, board_id: str = None) -> bool:
        identifier = board_id or board_name or board_id_or_name
        if not item_dict or "id" not in item_dict:
            return False
        board_data = self.load_board(project, board_id_or_name=identifier)
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
        return self.save_board(project, board_data, board_id_or_name=identifier)

    def remove_item(self, project, item_id: str, board_id_or_name: str = "Main", board_name: str = None, board_id: str = None) -> bool:
        identifier = board_id or board_name or board_id_or_name
        board_data = self.load_board(project, board_id_or_name=identifier)
        items = board_data.get("items", [])
        new_items = [it for it in items if it.get("id") != item_id]
        if len(new_items) == len(items):
            return False
        board_data["items"] = new_items
        return self.save_board(project, board_data, board_id_or_name=identifier)

    def get_project_summary_metadata(self, project) -> dict:
        """Derive live aggregated metadata across all project or global Workbench boards without duplicating persistence.

        Fast, lightweight, and fault-tolerant against corrupt or unreadable board files.
        """
        if project is not None and not getattr(project, "location", None):
            return {
                "boards": [],
                "pinned_nodes": [],
                "all_tags": [],
                "task_stats": {"total": 0, "completed": 0, "pending": 0, "items": []},
                "total_nodes": 0,
            }

        try:
            boards = self.list_boards(project)
        except Exception:
            boards = []

        pinned_nodes = []
        all_tags = set()
        total_nodes = 0
        task_total = 0
        task_completed = 0
        task_items = []
        board_summaries = []

        for b in boards:
            if not isinstance(b, dict):
                continue
            b_id = b.get("id")
            b_name = b.get("name", "Untitled")
            if not b_id:
                continue

            try:
                board_data = self.load_board(project, b_id)
            except Exception:
                board_data = {}

            items = board_data.get("items", []) if isinstance(board_data, dict) else []
            if not isinstance(items, list):
                items = []

            total_nodes += len(items)

            board_summaries.append({
                "id": b_id,
                "name": b_name,
                "item_count": len(items),
                "modified": b.get("modified", ""),
                "favorite": b.get("favorite", False),
                "icon": b.get("icon", None),
                "color": b.get("color", None),
            })

            for item in items:
                if not isinstance(item, dict):
                    continue

                # Extract tags
                item_tags = item.get("tags") or item.get("metadata", {}).get("tags") or []
                if isinstance(item_tags, (list, tuple, set)):
                    for t in item_tags:
                        if t and isinstance(t, str):
                            all_tags.add(t.strip())

                # Extract attention
                payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
                attn = item.get("attention") or payload.get("attention") or item.get("metadata", {}).get("attention") or "normal"

                # Extract pinned
                is_pinned = item.get("is_pinned") or item.get("metadata", {}).get("pinned") or False
                if is_pinned:
                    try:
                        item_copy = dict(item)
                        item_copy["_board_name"] = b_name
                        item_copy["_board_id"] = b_id
                        item_copy["_attention"] = attn
                        pinned_nodes.append(item_copy)
                    except Exception:
                        pass

                # Extract note checklist tasks
                content = payload.get("content", "")
                if content and isinstance(content, str):
                    for line in content.splitlines():
                        l = line.strip()
                        if l.startswith("- [ ]") or l.startswith("* [ ]") or l.startswith("+ [ ]") or l.startswith("[ ]"):
                            task_total += 1
                            txt = l.replace("- [ ]", "").replace("* [ ]", "").replace("+ [ ]", "").replace("[ ]", "").strip()
                            if txt:
                                task_items.append({"text": txt, "completed": False, "board_name": b_name, "board_id": b_id, "node_id": item.get("id"), "attention": attn})
                        elif l.startswith("- [x]") or l.startswith("- [X]") or l.startswith("* [x]") or l.startswith("* [X]") or l.startswith("+ [x]") or l.startswith("+ [X]") or l.startswith("[x]") or l.startswith("[X]"):
                            task_total += 1
                            task_completed += 1
                            txt = l.replace("- [x]", "").replace("- [X]", "").replace("* [x]", "").replace("* [X]", "").replace("+ [x]", "").replace("+ [X]", "").replace("[x]", "").replace("[X]", "").strip()
                            if txt:
                                task_items.append({"text": txt, "completed": True, "board_name": b_name, "board_id": b_id, "node_id": item.get("id"), "attention": attn})

        return {
            "boards": board_summaries,
            "pinned_nodes": pinned_nodes,
            "all_tags": sorted(list(all_tags)),
            "task_stats": {
                "total": task_total,
                "completed": task_completed,
                "pending": task_total - task_completed,
                "items": task_items,
            },
            "total_nodes": total_nodes,
        }

    def get_pinned_order(self) -> list:
        config_path = self.get_boards_dir(None) / "home_config.json"
        if not config_path.exists():
            return []
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("pinned_order", [])
        except Exception:
            return []

    def save_pinned_order(self, order_list: list) -> bool:
        config_path = self.get_boards_dir(None) / "home_config.json"
        try:
            data = {}
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data["pinned_order"] = order_list
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False

    def toggle_task_completion(self, project, board_id_or_name: str, node_id: str, task_text: str, target_completed: bool) -> bool:
        """Toggle checklist task completion in original note node payload without duplicating task data."""
        board_data = self.load_board(project, board_id_or_name)
        items = board_data.get("items", [])
        modified = False

        for item in items:
            if isinstance(item, dict) and item.get("id") == node_id:
                payload = item.get("payload", {})
                content = payload.get("content", "")
                if not content or not isinstance(content, str):
                    continue

                lines = content.splitlines()
                new_lines = []
                for line in lines:
                    stripped = line.strip()
                    if task_text in stripped:
                        if target_completed and (stripped.startswith("- [ ]") or stripped.startswith("* [ ]") or stripped.startswith("+ [ ]") or stripped.startswith("[ ]")):
                            line = line.replace("[ ]", "[x]")
                            modified = True
                        elif not target_completed and (stripped.startswith("- [x]") or stripped.startswith("- [X]") or stripped.startswith("* [x]") or stripped.startswith("* [X]") or stripped.startswith("+ [x]") or stripped.startswith("+ [X]") or stripped.startswith("[x]") or stripped.startswith("[X]")):
                            line = line.replace("[x]", "[ ]").replace("[X]", "[ ]")
                            modified = True
                    new_lines.append(line)

                if modified:
                    payload["content"] = "\n".join(new_lines)
                    item["payload"] = payload
                    break

        if modified:
            self.save_board(project, board_data, board_id_or_name)
            entry = self.get_board_entry(project, board_id_or_name)
            target_id = entry["id"] if entry else board_id_or_name
            self.board_updated.emit(project, target_id)
            return True

        return False

    def add_quick_capture_note(self, text: str) -> dict:
        """Quick Capture: add a note node to active Workbench board without requiring a project."""
        txt = text.strip()
        if not txt:
            return None

        active_id = self.get_active_board_id(None) or "Main"
        board_data = self.load_board(None, active_id)
        items = board_data.get("items", [])

        # Collect existing note coordinates to prevent overlapping
        existing_coords = set()
        for item in items:
            if isinstance(item, dict):
                tr = item.get("transform", {})
                if "x" in tr and "y" in tr:
                    existing_coords.add((round(float(tr["x"])), round(float(tr["y"]))))

        # Calculate a non-overlapping staggered position
        base_x, base_y = 50, 50
        stagger_x, stagger_y = base_x, base_y
        idx = 0
        while (round(float(stagger_x)), round(float(stagger_y))) in existing_coords:
            idx += 1
            stagger_x = base_x + (idx % 4) * 260 + (idx // 4) * 30
            stagger_y = base_y + (idx // 4) * 160 + (idx % 4) * 30

        note_id = str(uuid.uuid4())
        title_line = txt.splitlines()[0][:40] if txt else "Quick Note"

        new_item = {
            "id": note_id,
            "type": "note.blank",
            "transform": {"x": stagger_x, "y": stagger_y, "width": 240, "height": 140},
            "tags": ["quick_capture"],
            "is_pinned": True,
            "payload": {
                "title": title_line,
                "content": txt,
            },
            "created": datetime.now().isoformat(),
        }

        items.append(new_item)
        board_data["items"] = items
        self.save_board(None, board_data, active_id)
        self.board_updated.emit(None, active_id)
        return new_item



