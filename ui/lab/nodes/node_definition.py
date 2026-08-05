from dataclasses import dataclass, field
from typing import Dict, Any, Tuple, Optional, Callable, Set
from ui.lab.nodes.node_capability import NodeCapability


@dataclass
class NodeDefinition:
    """Declarative specification for a spatial node type.

    Separates pure data schema and visual configurations from executable behavior callbacks.
    """

    type_id: str                          # Unique schema key (e.g. "note.goal", "asset.image")
    category: str                         # Context menu grouping (e.g. "note", "media", "asset", "ai", "utility")
    title: str                            # User-facing label (e.g. "Goal Card")
    icon: str                             # Display icon symbol (e.g. "🎯")
    accent_color: str                     # Visual accent color (e.g. "#3B82F6")
    background_color: str                 # Card surface background (e.g. "#1E2029")
    badge_bg: str                         # Header badge background (e.g. "#1E2E4A")
    badge_text: str                       # Header badge text color (e.g. "#60A5FA")
    default_size: Tuple[float, float] = (260.0, 180.0)
    minimum_size: Tuple[float, float] = (180.0, 120.0)
    capabilities: NodeCapability = NodeCapability.NONE
    payload_schema: Dict[str, Any] = field(default_factory=dict)
    search_keywords: Tuple[str, ...] = field(default_factory=tuple)

    # Executable Behavior Callbacks (Optional Hooks)
    factory: Optional[Callable] = None
    custom_renderer: Optional[Callable] = None
    context_menu_builder: Optional[Callable] = None

    def has_capability(self, cap: NodeCapability) -> bool:
        """Check if definition grants a specific capability flag."""
        return bool(self.capabilities & cap)
