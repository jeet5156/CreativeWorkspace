"""Data models for Visual Markup & Annotation subsystem."""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any
import uuid


VALID_ANNOTATION_TYPES = {"freehand", "arrow", "rectangle", "ellipse", "text"}


def is_valid_normalized_coord(val: Any) -> bool:
    """Check if a coordinate value is a valid float/int within [0.0, 1.0]."""
    try:
        f = float(val)
        return 0.0 <= f <= 1.0
    except (ValueError, TypeError):
        return False


def is_valid_normalized_point(pt: Any) -> bool:
    """Check if a point dictionary or pair represents valid normalized coordinates."""
    if isinstance(pt, dict):
        x = pt.get("x")
        y = pt.get("y")
        return is_valid_normalized_coord(x) and is_valid_normalized_coord(y)
    elif isinstance(pt, (list, tuple)) and len(pt) >= 2:
        return is_valid_normalized_coord(pt[0]) and is_valid_normalized_coord(pt[1])
    return False


@dataclass
class MarkupDocument:
    """Represents an independent visual markup layer/document linked to a source media asset."""

    id: str = field(default_factory=lambda: f"mkp_{uuid.uuid4().hex[:12]}")
    name: str = "Untitled Markup"
    source_reference: Dict[str, Any] = field(default_factory=dict)
    annotations: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize MarkupDocument to a JSON-serializable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarkupDocument":
        """Instantiate MarkupDocument from a dictionary."""
        if not isinstance(data, dict):
            return cls()

        now = datetime.now().isoformat()
        return cls(
            id=str(data.get("id") or f"mkp_{uuid.uuid4().hex[:12]}"),
            name=str(data.get("name") or "Untitled Markup"),
            source_reference=dict(data.get("source_reference", {})),
            annotations=list(data.get("annotations", [])),
            created_at=str(data.get("created_at") or now),
            updated_at=str(data.get("updated_at") or now),
        )
