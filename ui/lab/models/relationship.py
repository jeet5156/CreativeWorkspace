import uuid
import copy
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class Relationship:
    """Pure domain data model representing a semantic relationship between two spatial nodes.

    Decoupled from visual rendering or QGraphicsItem presentation layers.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_node_id: str = ""
    target_node_id: str = ""
    source_anchor: str = "center"
    target_anchor: str = "center"
    relationship_type: str = "related_to"
    title: str = ""
    notes: str = ""
    weight: float = 1.0
    created_by: str = "manual"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    modified_at: str = field(default_factory=lambda: datetime.now().isoformat())
    is_hidden: bool = False
    is_locked: bool = False
    metadata: Dict[str, Any] = field(default_factory=lambda: {
        "importance": 1.0,
        "confidence": 1.0,
        "source": "manual"
    })

    def to_dict(self) -> dict:
        """Serialize domain state to dictionary for versioned disk persistence."""
        return {
            "id": self.id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "source_anchor": self.source_anchor,
            "target_anchor": self.target_anchor,
            "relationship_type": self.relationship_type,
            "title": self.title,
            "notes": self.notes,
            "weight": self.weight,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "modified_at": datetime.now().isoformat(),
            "is_hidden": self.is_hidden,
            "is_locked": self.is_locked,
            "metadata": copy.deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Relationship":
        """Instantiate domain Relationship instance from dictionary."""
        if not isinstance(data, dict):
            return cls()

        rel_type = str(data.get("relationship_type") or data.get("type") or "related_to").lower().replace(" ", "_")

        meta = data.get("metadata")
        if not isinstance(meta, dict):
            meta = {
                "importance": 1.0,
                "confidence": 1.0,
                "source": "manual"
            }

        now = datetime.now().isoformat()

        return cls(
            id=str(data.get("id") or uuid.uuid4()),
            source_node_id=str(data.get("source_node_id") or data.get("source_id") or ""),
            target_node_id=str(data.get("target_node_id") or data.get("target_id") or ""),
            source_anchor=str(data.get("source_anchor") or "center"),
            target_anchor=str(data.get("target_anchor") or "center"),
            relationship_type=rel_type,
            title=str(data.get("title") or data.get("label") or ""),
            notes=str(data.get("notes") or ""),
            weight=float(data.get("weight") if data.get("weight") is not None else 1.0),
            created_by=str(data.get("created_by") or "manual"),
            created_at=str(data.get("created_at") or data.get("created") or now),
            modified_at=str(data.get("modified_at") or data.get("modified") or now),
            is_hidden=bool(data.get("is_hidden", False)),
            is_locked=bool(data.get("is_locked", False)),
            metadata=copy.deepcopy(meta),
        )
