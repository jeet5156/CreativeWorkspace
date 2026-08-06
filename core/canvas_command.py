from enum import Enum


class CanvasCommand(str, Enum):
    """Canonical commands for spatial canvas operations."""

    COPY = "copy"
    PASTE = "paste"
    DUPLICATE = "duplicate"
    DELETE = "delete"
    SELECT_ALL = "select_all"
    CLEAR_SELECTION = "clear_selection"
