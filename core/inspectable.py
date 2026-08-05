from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class InspectableField:
    """Represents an editable or read-only property field inside an Inspector section."""

    def __init__(
        self,
        key: str,
        label: str,
        field_type: str,
        value: Any = None,
        options: Optional[List[str]] = None,
        read_only: bool = False,
    ):
        self.key = key
        self.label = label
        self.field_type = field_type  # "string", "text", "select", "tags", "image", "readonly"
        self.value = value
        self.options = options or []
        self.read_only = read_only


class InspectableSection:
    """Represents a logical section grouping inside the Inspector (e.g. General, Organization, Preview, Metadata)."""

    def __init__(self, title: str, fields: List[InspectableField]):
        self.title = title
        self.fields = fields


class InspectableObject(ABC):
    """Universal abstract contract for objects presented and edited inside the InspectorPanel."""

    @abstractmethod
    def get_display_name(self) -> str:
        """Returns human-readable display title."""
        pass

    @abstractmethod
    def get_display_icon(self) -> str:
        """Returns icon or symbol."""
        pass

    @abstractmethod
    def get_inspection_sections(self) -> List[InspectableSection]:
        """Returns structured section categories and property fields."""
        pass

    @abstractmethod
    def set_inspectable_property(self, field_key: str, value: Any) -> bool:
        """Mutates property on underlying model and saves state. Returns True if updated."""
        pass
