from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class RelationshipDefinition:
    """Registry definition for a semantic knowledge relationship type."""
    id: str
    label: str
    color: str
    directional: bool = True
    description: str = ""


class RelationshipRegistry:
    """Single source of truth registry for Lab knowledge graph relationship types."""

    _definitions: Dict[str, RelationshipDefinition] = {}
    _initialized: bool = False

    @classmethod
    def initialize_defaults(cls):
        if cls._initialized:
            return
        
        defaults = [
            RelationshipDefinition("related_to", "Related To", "#8A8A8A", directional=False, description="General neutral connection"),
            RelationshipDefinition("depends_on", "Depends On", "#EF4444", directional=True, description="Structural or logical dependency"),
            RelationshipDefinition("references", "References", "#3B82F6", directional=True, description="Informational or design reference"),
            RelationshipDefinition("alternative", "Alternative", "#A855F7", directional=False, description="Alternative design option or approach"),
            RelationshipDefinition("uses", "Uses", "#10B981", directional=True, description="Functional or resource utilization"),
            RelationshipDefinition("decision", "Decision", "#F97316", directional=True, description="Architectural or production choice"),
            RelationshipDefinition("inspired_by", "Inspired By", "#EAB308", directional=True, description="Creative inspiration source"),
            RelationshipDefinition("contains", "Contains", "#06B6D4", directional=True, description="Parent container relationship"),
            RelationshipDefinition("contained_by", "Contained By", "#0891B2", directional=True, description="Child member relationship"),
            RelationshipDefinition("blocks", "Blocks", "#DC2626", directional=True, description="Production or execution blocker"),
            RelationshipDefinition("leads_to", "Leads To", "#14B8A6", directional=True, description="Sequential or causal progression"),
        ]

        for d in defaults:
            cls._definitions[d.id] = d
        
        cls._initialized = True

    @classmethod
    def register(cls, definition: RelationshipDefinition):
        """Register a custom or dynamic relationship definition."""
        cls.initialize_defaults()
        cls._definitions[definition.id] = definition

    @classmethod
    def get(cls, relationship_type_id: str) -> RelationshipDefinition:
        """Fetch definition by ID, falling back to 'related_to' if unknown."""
        cls.initialize_defaults()
        rel_id = str(relationship_type_id or "related_to").lower().replace(" ", "_")
        return cls._definitions.get(rel_id, cls._definitions["related_to"])

    @classmethod
    def get_color(cls, relationship_type_id: str) -> str:
        """Fetch hex color string for relationship type."""
        return cls.get(relationship_type_id).color

    @classmethod
    def get_label(cls, relationship_type_id: str) -> str:
        """Fetch human-readable display label for relationship type."""
        return cls.get(relationship_type_id).label

    @classmethod
    def is_directional(cls, relationship_type_id: str) -> bool:
        """Query if relationship type is directional (requires arrowhead)."""
        return cls.get(relationship_type_id).directional

    @classmethod
    def all_definitions(cls) -> List[RelationshipDefinition]:
        """Return list of all registered relationship definitions."""
        cls.initialize_defaults()
        return list(cls._definitions.values())


# Auto-initialize default registry
RelationshipRegistry.initialize_defaults()
