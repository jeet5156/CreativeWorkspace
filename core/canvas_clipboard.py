import copy
from typing import List, Dict, Any, Optional


CLIPBOARD_TYPE_HEADER = "creativeworkspace.clipboard"
CLIPBOARD_VERSION = 1


class CanvasClipboard:
    """Independent runtime memory subsystem for managing serializable spatial node representations.

    Maintains JSON-compatible node payload dictionaries without storing live NodeItem or Qt object references.
    Supports payload format verification, payload versioning, and deep copy isolation.
    """

    def __init__(self):
        self._data: Dict[str, Any] = {
            "type": CLIPBOARD_TYPE_HEADER,
            "version": CLIPBOARD_VERSION,
            "nodes": [],
        }
        self._paste_count: int = 0

    def copy(self, nodes: List[Any], connectors: Optional[List[dict]] = None):
        """Serialize a list of spatial NodeItem instances into JSON clipboard payload."""
        if not nodes:
            return

        serialized_nodes = []
        for node in nodes:
            if isinstance(node, dict):
                serialized_nodes.append(copy.deepcopy(node))
            elif hasattr(node, "to_dict"):
                try:
                    serialized_nodes.append(copy.deepcopy(node.to_dict()))
                except Exception:
                    pass

        serialized_connectors = []
        if connectors and isinstance(connectors, list):
            for conn in connectors:
                if isinstance(conn, dict):
                    serialized_connectors.append(copy.deepcopy(conn))
                elif hasattr(conn, "to_dict"):
                    try:
                        serialized_connectors.append(copy.deepcopy(conn.to_dict()))
                    except Exception:
                        pass

        self._data = {
            "type": CLIPBOARD_TYPE_HEADER,
            "version": CLIPBOARD_VERSION,
            "nodes": serialized_nodes,
            "connectors": serialized_connectors,
        }
        # Reset cumulative paste count upon new copy
        self._paste_count = 0

    def get_nodes(self) -> List[Dict[str, Any]]:
        """Return deep copy of stored JSON node dictionaries if clipboard type header is valid."""
        if not self.has_content():
            return []
        return copy.deepcopy(self._data.get("nodes", []))

    def get_connectors(self) -> List[Dict[str, Any]]:
        """Return deep copy of stored JSON connector dictionaries if clipboard type header is valid."""
        if not self.has_content():
            return []
        return copy.deepcopy(self._data.get("connectors", []))

    def has_content(self) -> bool:
        """Check if clipboard contains valid creativeworkspace payload with at least one node."""
        if not isinstance(self._data, dict):
            return False
        if self._data.get("type") != CLIPBOARD_TYPE_HEADER:
            return False
        nodes = self._data.get("nodes")
        return bool(nodes and isinstance(nodes, list))

    def get_paste_count(self) -> int:
        return self._paste_count

    def increment_paste_count(self) -> int:
        self._paste_count += 1
        return self._paste_count

    def clear(self):
        """Clear stored clipboard payload and reset paste count."""
        self._data = {
            "type": CLIPBOARD_TYPE_HEADER,
            "version": CLIPBOARD_VERSION,
            "nodes": [],
        }
        self._paste_count = 0
