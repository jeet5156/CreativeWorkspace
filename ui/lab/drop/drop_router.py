from typing import List, Dict, Any
from ui.lab.drop.drop_context import DropContext
from ui.lab.drop.handlers.image_handler import ImageDropHandler
from ui.lab.drop.handlers.pdf_handler import PdfDropHandler
from ui.lab.drop.handlers.threed_handler import ThreeDDropHandler
from ui.lab.drop.handlers.archive_handler import ArchiveDropHandler
from ui.lab.drop.handlers.folder_handler import FolderDropHandler
from ui.lab.drop.handlers.generic_file_handler import GenericFileDropHandler


class DropRouter:
    """Central router for spatial canvas drag & drop file/folder events.

    Delegates context routing to type-specific drop handlers in priority sequence:
    1. ImageDropHandler
    2. PdfDropHandler
    3. ThreeDDropHandler
    4. ArchiveDropHandler
    5. FolderDropHandler
    6. GenericFileDropHandler
    """

    def __init__(self):
        self.handlers = [
            ImageDropHandler(),
            PdfDropHandler(),
            ThreeDDropHandler(),
            ArchiveDropHandler(),
            FolderDropHandler(),
            GenericFileDropHandler(),
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
                break  # Stop after first matching handler to enforce priority

        return nodes
