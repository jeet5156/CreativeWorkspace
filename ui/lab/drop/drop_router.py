from typing import List, Dict, Any
from ui.lab.drop.drop_context import DropContext
from ui.lab.drop.handlers.image_handler import ImageDropHandler


class DropRouter:
    """Central router for spatial canvas drag & drop file events.

    Delegates context routing to type-specific drop handlers (e.g. ImageDropHandler).
    Extensible for future asset types (PDF, 3D, USD, etc.) without mutating existing node architecture.
    """

    def __init__(self):
        self.handlers = [
            ImageDropHandler(),
        ]

    def can_route(self, context: DropContext) -> bool:
        if not context:
            return False
        for handler in self.handlers:
            if handler.can_handle(context):
                return True
        return False

    def route_drop(self, context: DropContext) -> List[Dict[str, Any]]:
        if not context:
            return []

        nodes = []
        for handler in self.handlers:
            if handler.can_handle(context):
                nodes.extend(handler.handle_drop(context))

        return nodes
