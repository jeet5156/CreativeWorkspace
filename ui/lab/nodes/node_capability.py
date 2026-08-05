from enum import Flag, auto


class NodeCapability(Flag):
    """Capability flags defining spatial node behavior without type checks or inheritance branching."""

    NONE = 0
    CAN_EDIT_TEXT = auto()       # Contains double-click inline text editor
    CAN_RESIZE = auto()          # Interactive resizing handles
    CAN_ROTATE = auto()          # Rotation transform support
    CAN_CONNECT = auto()         # Can connect to other nodes via ports/edges
    CAN_GROUP = auto()           # Group container membership
    CAN_HAVE_CHILDREN = auto()   # Can host child nodes (Frames/Groups)
    CAN_EMBED_ASSETS = auto()    # Workspace asset linkage
    CAN_LOCK = auto()            # Position and edit locking
    CAN_DUPLICATE = auto()       # Cloning and duplicating
    CAN_COLLAPSE = auto()        # Header-only collapsed state
