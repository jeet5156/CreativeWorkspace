import copy
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class NavigationEvent:
    """Rich navigation event recording spatial board state, selected node, and camera transform.

    Supports VS Code 'Go Back' / 'Go Forward' navigation stack restoring board, node selection,
    Inspector view, and camera zoom/pan coordinates.
    """

    board_id: str = "Main"
    node_id: Optional[str] = None
    camera_x: float = 0.0
    camera_y: float = 0.0
    zoom: float = 1.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "board_id": self.board_id,
            "node_id": self.node_id,
            "camera_x": self.camera_x,
            "camera_y": self.camera_y,
            "zoom": self.zoom,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NavigationEvent":
        if not isinstance(data, dict):
            return cls()
        return cls(
            board_id=str(data.get("board_id") or "Main"),
            node_id=str(data["node_id"]) if data.get("node_id") else None,
            camera_x=float(data.get("camera_x", 0.0)),
            camera_y=float(data.get("camera_y", 0.0)),
            zoom=float(data.get("zoom", 1.0)),
            timestamp=str(data.get("timestamp") or datetime.now().isoformat()),
        )


class NavigationHistoryService:
    """Service maintaining backward/forward navigation stacks and deduplicated recent nodes queue."""

    def __init__(self, max_history: int = 50, max_recents: int = 10):
        self._back_stack: List[NavigationEvent] = []
        self._forward_stack: List[NavigationEvent] = []
        self._recent_node_ids: List[str] = []
        self._max_history = max_history
        self._max_recents = max_recents
        self._is_navigating = False

    def push_event(self, event: NavigationEvent):
        """Push a navigation event to the history stack and update deduplicated recents."""
        if self._is_navigating:
            return

        # Avoid pushing duplicate consecutive events
        if self._back_stack:
            last = self._back_stack[-1]
            if last.board_id == event.board_id and last.node_id == event.node_id:
                return

        self._back_stack.append(event)
        if len(self._back_stack) > self._max_history:
            self._back_stack.pop(0)

        self._forward_stack.clear()

        # Update deduplicated recent nodes queue (LRU: B, C, A)
        if event.node_id:
            nid = str(event.node_id)
            if nid in self._recent_node_ids:
                self._recent_node_ids.remove(nid)
            self._recent_node_ids.insert(0, nid)
            if len(self._recent_node_ids) > self._max_recents:
                self._recent_node_ids.pop()

    def can_go_back(self) -> bool:
        return len(self._back_stack) > 1

    def can_go_forward(self) -> bool:
        return len(self._forward_stack) > 0

    def go_back(self) -> Optional[NavigationEvent]:
        """Pop current state and return previous navigation event."""
        if not self.can_go_back():
            return None

        self._is_navigating = True
        try:
            curr = self._back_stack.pop()
            self._forward_stack.append(curr)
            prev = self._back_stack[-1]
            return prev
        finally:
            self._is_navigating = False

    def go_forward(self) -> Optional[NavigationEvent]:
        """Pop from forward stack and return next navigation event."""
        if not self.can_go_forward():
            return None

        self._is_navigating = True
        try:
            next_evt = self._forward_stack.pop()
            self._back_stack.append(next_evt)
            return next_evt
        finally:
            self._is_navigating = False

    def get_recent_node_ids(self) -> List[str]:
        return list(self._recent_node_ids)

    def clear(self):
        self._back_stack.clear()
        self._forward_stack.clear()
        self._recent_node_ids.clear()
