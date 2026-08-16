import json
import uuid
import copy
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import QObject, Signal
class LabService(QObject):
    """Manages Lab board persistence (<board_id>.lab.json) and board_manifest.json in <ProjectRoot>/Lab/boards/."""
    board_updated = Signal(object, str)
    manifest_updated = Signal(object)
    def __init__(self, project_service=None, activity_service=None):
        super().__init__()
        self.project_service = project_service
        self.activity_service = activity_service
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
                item_due = item.get("due_date") or payload.get("due_date") or item.get("metadata", {}).get("due_date")
                if content and isinstance(content, str):
                    for line in content.splitlines():
                        l = line.strip()
                        is_comp = False
                        raw_txt = None
                        if l.startswith("- [ ]") or l.startswith("* [ ]") or l.startswith("+ [ ]") or l.startswith("[ ]"):
                            raw_txt = l.replace("- [ ]", "").replace("* [ ]", "").replace("+ [ ]", "").replace("[ ]", "").strip()
                            is_comp = False
                        elif l.startswith("- [x]") or l.startswith("- [X]") or l.startswith("* [x]") or l.startswith("* [X]") or l.startswith("+ [x]") or l.startswith("+ [X]") or l.startswith("[x]") or l.startswith("[X]"):
                            raw_txt = l.replace("- [x]", "").replace("- [X]", "").replace("* [x]", "").replace("* [X]", "").replace("+ [x]", "").replace("+ [X]", "").replace("[x]", "").replace("[X]", "").strip()
                            is_comp = True
                        if raw_txt:
                            task_total += 1
                            if is_comp:
                                task_completed += 1
                            clean_txt, due_str, due_stat = self._parse_due_date_and_status(raw_txt, item_due)
                            task_items.append({
                                "text": clean_txt,
                                "completed": is_comp,
                                "board_name": b_name,
                                "board_id": b_id,
                                "node_id": item.get("id"),
                                "attention": attn,
                                "due_date": due_str,
                                "due_status": due_stat,
                            })
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
    @staticmethod
    def _parse_due_date_and_status(line_txt: str, item_due_date: str = None) -> tuple:
        """Parse due_date from payload metadata or inline @due(YYYY-MM-DD), returning (clean_txt, due_date_str, due_status)."""
        import re
        from datetime import datetime, timedelta
        due_date = item_due_date
        clean_txt = line_txt
        match = re.search(r'@due\(([^)]+)\)', clean_txt)
        if match:
            due_date = match.group(1).strip()
            clean_txt = re.sub(r'\s*@due\([^)]+\)', '', clean_txt).strip()
        if not due_date or not isinstance(due_date, str):
            return clean_txt, None, "none"
        due_date = due_date.strip()
        due_status = "normal"
        try:
            today = datetime.now().date()
            if due_date.lower() == "today":
                due_date = today.isoformat()
                due_status = "due_today"
            elif due_date.lower() == "tomorrow":
                due_date = (today + timedelta(days=1)).isoformat()
                due_status = "due_soon"
            else:
                target_dt = datetime.strptime(due_date, "%Y-%m-%d").date()
                if target_dt < today:
                    due_status = "overdue"
                elif target_dt == today:
                    due_status = "due_today"
                elif today < target_dt <= today + timedelta(days=7):
                    due_status = "due_soon"
        except Exception:
            due_status = "normal"
        return clean_txt, due_date, due_status
    def add_quick_task_note(self, text: str, attention: str = "normal", due_date: str = None, project=None, board_id: str = None) -> dict:
        """Quick Task: create a note node with checklist item `- [ ] <text>` on target board."""
        txt = text.strip()
        if not txt:
            return None
        clean_text = txt
        for prefix in ("- [ ]", "* [ ]", "+ [ ]", "[ ]"):
            if clean_text.startswith(prefix):
                clean_text = clean_text[len(prefix):].strip()
                break
        target_board_id = board_id or self.get_active_board_id(project) or "Main"
        board_data = self.load_board(project, target_board_id)
        items = board_data.get("items", [])
        existing_coords = set()
        for item in items:
            if isinstance(item, dict):
                tr = item.get("transform", {})
                if "x" in tr and "y" in tr:
                    existing_coords.add((round(float(tr["x"])), round(float(tr["y"]))))
        base_x, base_y = 50, 50
        stagger_x, stagger_y = base_x, base_y
        idx = 0
        while (round(float(stagger_x)), round(float(stagger_y))) in existing_coords:
            idx += 1
            stagger_x = base_x + (idx % 4) * 260 + (idx // 4) * 30
            stagger_y = base_y + (idx // 4) * 160 + (idx % 4) * 30
        note_id = str(uuid.uuid4())
        title_line = clean_text[:40] if clean_text else "Task"
        content_str = f"- [ ] {clean_text}"
        normalized_attn = (attention or "normal").lower()
        if normalized_attn not in ("normal", "important", "urgent"):
            normalized_attn = "normal"
        payload_dict = {
            "title": title_line,
            "content": content_str,
            "attention": normalized_attn,
        }
        if due_date and isinstance(due_date, str) and due_date.strip():
            payload_dict["due_date"] = due_date.strip()
        new_item = {
            "id": note_id,
            "type": "note.blank",
            "transform": {"x": stagger_x, "y": stagger_y, "width": 240, "height": 140},
            "tags": ["task", "quick_task"],
            "attention": normalized_attn,
            "is_pinned": True,
            "payload": payload_dict,
            "created": datetime.now().isoformat(),
        }
        if due_date and isinstance(due_date, str) and due_date.strip():
            new_item["due_date"] = due_date.strip()
        items.append(new_item)
        board_data["items"] = items
        self.save_board(project, board_data, target_board_id)
        entry = self.get_board_entry(project, target_board_id)
        target_id = entry["id"] if entry else target_board_id
        self.board_updated.emit(project, target_id)
        if self.activity_service:
            desc = f"Created task '{clean_text[:35]}'"
            self.activity_service.record(
                action="quick_task",
                event_type="quick_task",
                description=desc,
                project=project,
                board_id=target_board_id,
                node_id=note_id,
                details={"text": clean_text, "attention": normalized_attn, "due_date": due_date},
            )
        return new_item
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
    def get_project_order(self) -> list:
        config_path = self.get_boards_dir(None) / "home_config.json"
        if not config_path.exists():
            return []
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("project_order", [])
        except Exception:
            return []
    def save_project_order(self, order_list: list) -> bool:
        config_path = self.get_boards_dir(None) / "home_config.json"
        try:
            data = {}
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data["project_order"] = order_list
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
            if self.activity_service:
                act_str = "task_complete" if target_completed else "task_incomplete"
                action_label = "Completed task" if target_completed else "Uncompleted task"
                desc = f"{action_label} '{task_text[:35]}'"
                self.activity_service.record(
                    action=act_str,
                    event_type=act_str,
                    description=desc,
                    project=project,
                    board_id=board_id_or_name,
                    node_id=node_id,
                    details={"text": task_text, "completed": target_completed},
                )
            return True
        return False
    def add_quick_capture_note(self, text: str, project=None, board_id: str = None) -> dict:
        """Quick Capture: add a note node to target board (defaults to active Workbench Inbox board)."""
        txt = text.strip()
        if not txt:
            return None
        target_board_id = board_id or self.get_active_board_id(project) or "Main"
        board_data = self.load_board(project, target_board_id)
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
        self.save_board(project, board_data, target_board_id)
        if self.activity_service:
            desc = f"Quick captured note '{title_line[:35]}'"
            self.activity_service.record(
                action="quick_capture",
                event_type="quick_capture",
                description=desc,
                project=project,
                board_id=target_board_id,
                node_id=note_id,
                details={"title": title_line, "text": txt},
            )
        return new_item
    def get_inbox_board_id(self, project=None) -> str:
        """Return the designated inbox board ID for Workbench or a Project."""
        return self.get_active_board_id(project) or "Main"
    def resolve_promotion_group(self, source_project, source_board_id: str, node_ids: list[str]) -> list[dict]:
        """Resolve a list of node IDs into a unique collection of board item dicts.
        If any node is a Frame, automatically includes all contained child nodes (recursively).
        Deduplicates items if a Frame and its child nodes are both passed in node_ids.
        Returns items in original source board order.
        """
        if not node_ids or not source_board_id:
            return []
        src_entry = self.get_board_entry(source_project, source_board_id)
        canon_src_id = src_entry["id"] if src_entry else source_board_id
        boards_dir = self.get_boards_dir(source_project)
        board_file = boards_dir / f"{canon_src_id}.lab.json"
        source_board = self.load_board(source_project, canon_src_id)
        source_items = source_board.get("items", [])
        item_map = {item.get("id"): item for item in source_items if isinstance(item, dict) and item.get("id")}
        present_ids = [nid for nid in node_ids if nid in item_map]
        resolved_ids = set()
        queue = [nid for nid in node_ids if nid in item_map]
        while queue:
            curr_id = queue.pop(0)
            if curr_id in resolved_ids:
                continue
            resolved_ids.add(curr_id)
            curr_item = item_map.get(curr_id)
            if not curr_item:
                continue
            # Check if curr_item is a Frame node and expand children registered in child_node_ids
            payload = curr_item.get("payload") if isinstance(curr_item.get("payload"), dict) else {}
            child_ids = payload.get("child_node_ids", [])
            if isinstance(child_ids, list):
                for cid in child_ids:
                    if cid in item_map and cid not in resolved_ids:
                        queue.append(cid)
            # Also expand any items in source_board whose parent_frame_id == curr_id
            for it in source_items:
                if isinstance(it, dict):
                    it_payload = it.get("payload") if isinstance(it.get("payload"), dict) else {}
                    p_id = it_payload.get("parent_frame_id") or it.get("parent_frame_id")
                    if p_id == curr_id and it.get("id") not in resolved_ids:
                        queue.append(it["id"])
        return [item for item in source_items if isinstance(item, dict) and item.get("id") in resolved_ids]
    def move_nodes(self, source_project, source_board_id: str, target_project, target_board_id: str, node_ids: list[str]) -> list[dict]:
        """Atomically move a collection of nodes (and frame children) from source to target board.
        Preserves relative positions, payload, metadata, tags, attention, pin status.
        Transfers internal connectors where both endpoints are moved.
        Detaches external connectors where only one endpoint is moved.
        Clears orphaned parent_frame_id references.
        """
        if not node_ids or not source_board_id or not target_board_id:
            return []
        src_entry = self.get_board_entry(source_project, source_board_id)
        canon_src_id = src_entry["id"] if src_entry else source_board_id
        tgt_entry = self.get_board_entry(target_project, target_board_id)
        canon_tgt_id = tgt_entry["id"] if tgt_entry else target_board_id
        promotion_items = self.resolve_promotion_group(source_project, canon_src_id, node_ids)
        if not promotion_items:
            return []
        # Same board move is a no-op
        same_proj = (source_project == target_project) or (
            source_project is not None and target_project is not None and
            getattr(source_project, "location", None) == getattr(target_project, "location", None)
        )
        if same_proj and canon_src_id == canon_tgt_id:
            return promotion_items
        source_board = self.load_board(source_project, canon_src_id)
        target_board = self.load_board(target_project, canon_tgt_id)
        source_items = source_board.get("items", [])
        target_items = target_board.get("items", [])
        moved_node_ids = {item["id"] for item in promotion_items if isinstance(item, dict) and "id" in item}
        # Remove moved items from source items
        source_items = [it for it in source_items if isinstance(it, dict) and it.get("id") not in moved_node_ids]
        # Target node IDs set before adding moved items
        target_existing_ids = {it.get("id") for it in target_items if isinstance(it, dict)}
        # ID collision handling in target board
        id_remap = {}
        items_to_add = []
        for item in promotion_items:
            item_copy = copy.deepcopy(item)
            old_id = item_copy.get("id")
            if old_id in target_existing_ids:
                new_id = str(uuid.uuid4())
                id_remap[old_id] = new_id
                item_copy["id"] = new_id
            items_to_add.append(item_copy)
        all_moved_target_ids = {it["id"] for it in items_to_add} | target_existing_ids
        # Frame parent & children safety for moved items
        for item_copy in items_to_add:
            payload = item_copy.get("payload") if isinstance(item_copy.get("payload"), dict) else {}
            parent_frame_id = payload.get("parent_frame_id") or item_copy.get("parent_frame_id")
            if parent_frame_id:
                remapped_parent = id_remap.get(parent_frame_id, parent_frame_id)
                if remapped_parent not in all_moved_target_ids:
                    if isinstance(item_copy.get("payload"), dict):
                        item_copy["payload"]["parent_frame_id"] = None
                    item_copy["parent_frame_id"] = None
                elif remapped_parent != parent_frame_id:
                    if isinstance(item_copy.get("payload"), dict):
                        item_copy["payload"]["parent_frame_id"] = remapped_parent
                    item_copy["parent_frame_id"] = remapped_parent
            if "child_node_ids" in payload and isinstance(payload["child_node_ids"], list):
                new_children = []
                for cid in payload["child_node_ids"]:
                    remapped_c = id_remap.get(cid, cid)
                    if remapped_c in all_moved_target_ids:
                        new_children.append(remapped_c)
                payload["child_node_ids"] = new_children
            # Origin Metadata
            if "metadata" not in item_copy or not isinstance(item_copy["metadata"], dict):
                item_copy["metadata"] = {}
            src_proj_name = source_project.name if source_project else "__workbench__"
            tgt_proj_name = target_project.name if target_project else "__workbench__"
            item_copy["metadata"]["origin"] = {
                "source_project": src_proj_name,
                "source_board_id": canon_src_id,
                "target_project": tgt_proj_name,
                "target_board_id": canon_tgt_id,
                "action": "move",
                "promoted_at": datetime.now().isoformat()
            }
        # Connector safety for Move:
        # Internal connectors (both endpoints in moved_node_ids) -> move to target_board
        # External connectors (one endpoint in moved_node_ids) -> detach/remove from source_board
        source_connectors = source_board.get("connectors", [])
        new_source_connectors = []
        target_connectors = target_board.get("connectors", [])
        for conn in source_connectors:
            if isinstance(conn, dict):
                src_id = conn.get("source_node_id") or conn.get("source_id")
                tgt_id = conn.get("target_node_id") or conn.get("target_id")
                src_in_moved = src_id in moved_node_ids
                tgt_in_moved = tgt_id in moved_node_ids
                if src_in_moved and tgt_in_moved:
                    conn_copy = copy.deepcopy(conn)
                    new_src = id_remap.get(src_id, src_id)
                    new_tgt = id_remap.get(tgt_id, tgt_id)
                    if "source_node_id" in conn_copy: conn_copy["source_node_id"] = new_src
                    if "source_id" in conn_copy: conn_copy["source_id"] = new_src
                    if "target_node_id" in conn_copy: conn_copy["target_node_id"] = new_tgt
                    if "target_id" in conn_copy: conn_copy["target_id"] = new_tgt
                    target_connectors.append(conn_copy)
                    continue
                elif src_in_moved or tgt_in_moved:
                    continue
            new_source_connectors.append(conn)
        source_board["items"] = source_items
        source_board["connectors"] = new_source_connectors
        target_items.extend(items_to_add)
        target_board["items"] = target_items
        target_board["connectors"] = target_connectors
        # Save both boards atomically
        self.save_board(source_project, source_board, canon_src_id)
        self.save_board(target_project, target_board, canon_tgt_id)
        if self.activity_service:
            try:
                target_proj_name = target_project.name if target_project else "Workbench"
                first_nid = items_to_add[0]["id"] if items_to_add else None
                count_str = f"{len(items_to_add)} node(s)" if len(items_to_add) > 1 else f"node"
                desc = f"Moved {count_str} to {target_proj_name} ({canon_tgt_id})"
                self.activity_service.record(
                    action="move_nodes",
                    event_type="move_nodes",
                    description=desc,
                    project=target_project,
                    board_id=canon_tgt_id,
                    node_id=first_nid,
                    details={
                        "source_board_id": canon_src_id,
                        "target_board_id": canon_tgt_id,
                        "moved_count": len(items_to_add),
                        "node_ids": [it.get("id") for it in items_to_add if isinstance(it, dict)],
                    },
                )
            except Exception as err:
                print(f"[LabService] Warning: ActivityService.record failed during move_nodes: {err}")
        return items_to_add
    def copy_nodes(self, source_project, source_board_id: str, target_project, target_board_id: str, node_ids: list[str]) -> list[dict]:
        """Duplicate/Copy a collection of nodes (and frame children) from source to target board.
        Generates fresh UUIDs for all copied nodes and internal connectors.
        Remaps parent_frame_id and child_node_ids relationships.
        Preserves relative transform layout (offsets (+30, +30) on same-board copy).
        Leaves source board untouched.
        """
        if not node_ids or not source_board_id or not target_board_id:
            return []
        src_entry = self.get_board_entry(source_project, source_board_id)
        canon_src_id = src_entry["id"] if src_entry else source_board_id
        tgt_entry = self.get_board_entry(target_project, target_board_id)
        canon_tgt_id = tgt_entry["id"] if tgt_entry else target_board_id
        promotion_items = self.resolve_promotion_group(source_project, canon_src_id, node_ids)
        if not promotion_items:
            return []
        source_board = self.load_board(source_project, canon_src_id)
        target_board = self.load_board(target_project, canon_tgt_id)
        source_items = source_board.get("items", [])
        target_items = target_board.get("items", [])
        # Build old_to_new_id_map
        old_to_new_id_map = {}
        for item in promotion_items:
            if isinstance(item, dict) and "id" in item:
                old_to_new_id_map[item["id"]] = str(uuid.uuid4())
        same_proj = (source_project == target_project) or (
            source_project is not None and target_project is not None and
            getattr(source_project, "location", None) == getattr(target_project, "location", None)
        )
        is_same_board = same_proj and canon_src_id == canon_tgt_id
        target_existing_ids = {it.get("id") for it in target_items if isinstance(it, dict)}
        copied_items = []
        for item in promotion_items:
            copied_item = copy.deepcopy(item)
            old_id = copied_item.get("id")
            new_id = old_to_new_id_map[old_id]
            copied_item["id"] = new_id
            # Transform offset if same board copy
            if is_same_board:
                tr = copied_item.get("transform", {})
                if isinstance(tr, dict) and "x" in tr and "y" in tr:
                    tr["x"] = float(tr["x"]) + 30
                    tr["y"] = float(tr["y"]) + 30
            # Remap parent_frame_id
            payload = copied_item.get("payload") if isinstance(copied_item.get("payload"), dict) else {}
            parent_frame_id = payload.get("parent_frame_id") or copied_item.get("parent_frame_id")
            if parent_frame_id:
                new_parent_id = old_to_new_id_map.get(parent_frame_id)
                if not new_parent_id:
                    if parent_frame_id in target_existing_ids:
                        new_parent_id = parent_frame_id
                    else:
                        new_parent_id = None
                if isinstance(copied_item.get("payload"), dict):
                    copied_item["payload"]["parent_frame_id"] = new_parent_id
                copied_item["parent_frame_id"] = new_parent_id
            # Remap child_node_ids
            if "child_node_ids" in payload and isinstance(payload["child_node_ids"], list):
                new_children = []
                for cid in payload["child_node_ids"]:
                    new_cid = old_to_new_id_map.get(cid)
                    if not new_cid and cid in target_existing_ids:
                        new_cid = cid
                    if new_cid:
                        new_children.append(new_cid)
                payload["child_node_ids"] = new_children
            # Origin Metadata
            if "metadata" not in copied_item or not isinstance(copied_item["metadata"], dict):
                copied_item["metadata"] = {}
            src_proj_name = source_project.name if source_project else "__workbench__"
            tgt_proj_name = target_project.name if target_project else "__workbench__"
            copied_item["metadata"]["origin"] = {
                "source_project": src_proj_name,
                "source_board_id": canon_src_id,
                "target_project": tgt_proj_name,
                "target_board_id": canon_tgt_id,
                "action": "copy",
                "promoted_at": datetime.now().isoformat()
            }
            copied_items.append(copied_item)
        # Connector safety for Copy:
        # Copy internal connectors (where both endpoints in old_to_new_id_map) to target board
        source_connectors = source_board.get("connectors", [])
        target_connectors = target_board.get("connectors", [])
        for conn in source_connectors:
            if isinstance(conn, dict):
                src_id = conn.get("source_node_id") or conn.get("source_id")
                tgt_id = conn.get("target_node_id") or conn.get("target_id")
                if src_id in old_to_new_id_map and tgt_id in old_to_new_id_map:
                    conn_copy = copy.deepcopy(conn)
                    conn_copy["id"] = str(uuid.uuid4())
                    new_src = old_to_new_id_map[src_id]
                    new_tgt = old_to_new_id_map[tgt_id]
                    if "source_node_id" in conn_copy: conn_copy["source_node_id"] = new_src
                    if "source_id" in conn_copy: conn_copy["source_id"] = new_src
                    if "target_node_id" in conn_copy: conn_copy["target_node_id"] = new_tgt
                    if "target_id" in conn_copy: conn_copy["target_id"] = new_tgt
                    target_connectors.append(conn_copy)
        target_items.extend(copied_items)
        target_board["items"] = target_items
        target_board["connectors"] = target_connectors
        self.save_board(target_project, target_board, canon_tgt_id)
        if self.activity_service:
            try:
                target_proj_name = target_project.name if target_project else "Workbench"
                first_nid = copied_items[0]["id"] if copied_items else None
                count_str = f"{len(copied_items)} node(s)" if len(copied_items) > 1 else f"node"
                desc = f"Copied {count_str} to {target_proj_name} ({canon_tgt_id})"
                self.activity_service.record(
                    action="copy_nodes",
                    event_type="copy_nodes",
                    description=desc,
                    project=target_project,
                    board_id=canon_tgt_id,
                    node_id=first_nid,
                    details={
                        "source_board_id": canon_src_id,
                        "target_board_id": canon_tgt_id,
                        "copied_count": len(copied_items),
                        "node_ids": [it.get("id") for it in copied_items if isinstance(it, dict)],
                    },
                )
            except Exception as err:
                print(f"[LabService] Warning: ActivityService.record failed during copy_nodes: {err}")
        return copied_items
    def move_node(self, source_project, source_board_id: str, target_project, target_board_id: str, node_id: str) -> dict | None:
        """Atomically move a node (and frame children if target is frame) from source to target board."""
        if not node_id:
            return None
        res = self.move_nodes(source_project, source_board_id, target_project, target_board_id, [node_id])
        if not res:
            return None
        for item in res:
            if item.get("id") == node_id:
                return item
        return res[0]
    def copy_node(self, source_project, source_board_id: str, target_project, target_board_id: str, node_id: str) -> dict | None:
        """Duplicate/Copy a node (and frame children if target is frame) from source to target board."""
        if not node_id:
            return None
        res = self.copy_nodes(source_project, source_board_id, target_project, target_board_id, [node_id])
        if not res:
            return None
        for item in res:
            if item.get("id") == node_id:
                return item
        return res[0]
