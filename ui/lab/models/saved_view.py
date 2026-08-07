import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class SavedView:
    """First-class project asset model representing a saved camera position across boards."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    board_id: str = "Main"
    camera_x: float = 0.0
    camera_y: float = 0.0
    zoom: float = 1.0
    folder: str = ""
    is_favorite: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    modified_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "board_id": self.board_id,
            "camera_x": round(self.camera_x, 2),
            "camera_y": round(self.camera_y, 2),
            "zoom": round(self.zoom, 3),
            "folder": self.folder,
            "is_favorite": self.is_favorite,
            "created_at": self.created_at,
            "modified_at": datetime.now().isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SavedView":
        if not isinstance(data, dict):
            return cls()

        now = datetime.now().isoformat()
        return cls(
            id=str(data.get("id") or uuid.uuid4()),
            name=str(data.get("name") or "Saved View"),
            board_id=str(data.get("board_id") or "Main"),
            camera_x=float(data.get("camera_x", 0.0)),
            camera_y=float(data.get("camera_y", 0.0)),
            zoom=float(data.get("zoom", 1.0)),
            folder=str(data.get("folder") or ""),
            is_favorite=bool(data.get("is_favorite", False)),
            created_at=str(data.get("created_at") or now),
            modified_at=str(data.get("modified_at") or now),
        )
