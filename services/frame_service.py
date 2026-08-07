from typing import List, Union, Dict, Optional
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtWidgets import QGraphicsScene

FRAME_PADDING = 32.0
HEADER_HEIGHT = 42.0
MIN_FRAME_WIDTH = 260.0
MIN_FRAME_HEIGHT = 180.0


class FrameService:
    """Centralized manager for structural graph relationships and operations between Frame containers and spatial Node items.

    Decouples graph state management, clipboard re-linking, deletion cleanup, and auto-fit math
    from UI view rendering (FrameNodeItem).
    """

    @staticmethod
    def attach_node(frame, target_node_or_id: Union[object, str], scene: Optional[QGraphicsScene] = None) -> bool:
        """Attach a node to a frame. Synchronizes frame.child_node_ids and node.parent_frame_id."""
        if not frame or not hasattr(frame, "payload"):
            return False

        node_id = target_node_or_id.id if hasattr(target_node_or_id, "id") else str(target_node_or_id)
        node = target_node_or_id if hasattr(target_node_or_id, "payload") else None

        active_scene = scene or (frame.scene() if hasattr(frame, "scene") and callable(frame.scene) else None)
        if active_scene and not node:
            for item in active_scene.items():
                if hasattr(item, "id") and item.id == node_id:
                    node = item
                    break

        child_ids = frame.payload.get("child_node_ids", [])
        if not isinstance(child_ids, list):
            child_ids = []
            frame.payload["child_node_ids"] = child_ids

        if node_id not in child_ids:
            child_ids.append(node_id)
            frame.payload["child_node_ids"] = child_ids

        if node and hasattr(node, "payload") and isinstance(node.payload, dict):
            old_parent_id = node.payload.get("parent_frame_id")
            if old_parent_id and old_parent_id != frame.id and active_scene:
                for item in active_scene.items():
                    if hasattr(item, "id") and item.id == old_parent_id:
                        FrameService.detach_node(item, node_id, scene=active_scene)
                        break

            node.payload["parent_frame_id"] = frame.id
            if hasattr(node, "_emit_modified"):
                node._emit_modified()

        if hasattr(frame, "_emit_modified"):
            frame._emit_modified()
        if hasattr(frame, "update"):
            frame.update()
        return True

    @staticmethod
    def detach_node(frame, target_node_or_id: Union[object, str], scene: Optional[QGraphicsScene] = None) -> bool:
        """Detach a node from a frame. Clears parent_frame_id on node and removes ID from frame."""
        if not frame or not hasattr(frame, "payload"):
            return False

        node_id = target_node_or_id.id if hasattr(target_node_or_id, "id") else str(target_node_or_id)
        child_ids = frame.payload.get("child_node_ids", [])
        if isinstance(child_ids, list) and node_id in child_ids:
            child_ids.remove(node_id)
            frame.payload["child_node_ids"] = child_ids

        active_scene = scene or (frame.scene() if hasattr(frame, "scene") and callable(frame.scene) else None)
        if active_scene:
            for item in active_scene.items():
                if hasattr(item, "id") and item.id == node_id:
                    if hasattr(item, "payload") and isinstance(item.payload, dict):
                        if item.payload.get("parent_frame_id") == frame.id:
                            item.payload["parent_frame_id"] = None
                            if hasattr(item, "_emit_modified"):
                                item._emit_modified()
                    break

        if hasattr(frame, "_emit_modified"):
            frame._emit_modified()
        if hasattr(frame, "update"):
            frame.update()
        return True

    @staticmethod
    def detach_all(frame, scene: Optional[QGraphicsScene] = None) -> bool:
        """Detach all child nodes from a frame."""
        if not frame or not hasattr(frame, "payload"):
            return False

        attached = FrameService.get_attached_nodes(frame, scene=scene)
        for member in attached:
            FrameService.detach_node(frame, member, scene=scene)

        frame.payload["child_node_ids"] = []
        if hasattr(frame, "_emit_modified"):
            frame._emit_modified()
        if hasattr(frame, "update"):
            frame.update()
        return True

    @staticmethod
    def move_node_to_frame(node, source_frame, target_frame, scene: Optional[QGraphicsScene] = None) -> bool:
        """Transfer node from source frame to target frame."""
        if source_frame:
            FrameService.detach_node(source_frame, node, scene=scene)
        if target_frame:
            return FrameService.attach_node(target_frame, node, scene=scene)
        return True

    @staticmethod
    def get_attached_nodes(frame, scene: Optional[QGraphicsScene] = None) -> List[object]:
        """Return list of live NodeItem instances attached to frame."""
        if not frame or not hasattr(frame, "payload"):
            return []

        active_scene = scene or (frame.scene() if hasattr(frame, "scene") and callable(frame.scene) else None)
        if not active_scene:
            return []

        child_ids = set(frame.payload.get("child_node_ids", []))
        members = []
        for item in active_scene.items():
            if hasattr(item, "id") and item is not frame:
                parent_id = item.payload.get("parent_frame_id") if hasattr(item, "payload") and isinstance(item.payload, dict) else None
                if item.id in child_ids or parent_id == frame.id:
                    members.append(item)
                    if item.id not in child_ids:
                        frame.payload["child_node_ids"].append(item.id)

        # Cleanup deleted / missing node IDs
        live_ids = [m.id for m in members]
        if frame.payload.get("child_node_ids") != live_ids:
            frame.payload["child_node_ids"] = live_ids

        return members

    @staticmethod
    def set_collapsed(frame, collapsed: bool, scene: Optional[QGraphicsScene] = None) -> bool:
        """Collapse or expand a Frame container.

        Uses full payload["expanded_rect"] = {"x": pos.x(), "y": pos.y(), "width": w, "height": h}.
        When collapsed:
        - Stores current transform in payload["expanded_rect"].
        - Shrinks frame height to HEADER_HEIGHT.
        - Calls setVisible(False) and setSelected(False) on attached children.

        When expanded:
        - Restores dimensions from payload["expanded_rect"].
        - Calls setVisible(True) on attached children.
        """
        if not frame or not hasattr(frame, "payload"):
            return False

        if bool(frame.payload.get("collapsed", False)) == collapsed:
            return False

        frame.payload["collapsed"] = bool(collapsed)
        attached_members = FrameService.get_attached_nodes(frame, scene=scene)

        pos = frame.pos() if hasattr(frame, "pos") and callable(frame.pos) else QPointF(0, 0)
        curr_w = float(getattr(frame, "width", MIN_FRAME_WIDTH))
        curr_h = float(getattr(frame, "height", MIN_FRAME_HEIGHT))

        if collapsed:
            # Store full expanded_rect payload
            exp_rect = {
                "x": round(pos.x(), 2),
                "y": round(pos.y(), 2),
                "width": round(curr_w, 2),
                "height": round(max(MIN_FRAME_HEIGHT, curr_h), 2),
            }
            frame.payload["expanded_rect"] = exp_rect
            frame.height = HEADER_HEIGHT

            # Hide attached children and unselect them
            for member in attached_members:
                if hasattr(member, "setSelected") and member.isSelected():
                    member.setSelected(False)
                if hasattr(member, "setVisible"):
                    member.setVisible(False)
        else:
            # Restore full expanded_rect dimensions
            exp_rect = frame.payload.get("expanded_rect", {})
            if isinstance(exp_rect, dict) and "height" in exp_rect:
                target_h = float(exp_rect.get("height", MIN_FRAME_HEIGHT))
            else:
                target_h = float(getattr(frame, "_expanded_height", MIN_FRAME_HEIGHT))

            frame.height = max(HEADER_HEIGHT + 40.0, target_h)

            # Restore child visibility
            for member in attached_members:
                if hasattr(member, "setVisible"):
                    member.setVisible(True)

        if hasattr(frame, "_emit_modified"):
            frame._emit_modified()
        if hasattr(frame, "update"):
            frame.update()
        return True

    @staticmethod
    def fit_to_contents(frame, scene: Optional[QGraphicsScene] = None, padding: float = FRAME_PADDING, header_h: float = HEADER_HEIGHT) -> bool:
        """Auto-resize and reposition frame over 250ms to enclose attached member nodes with padding.

        Child spatial node positions are NEVER moved or altered.
        """
        if frame and hasattr(frame, "payload") and frame.payload.get("collapsed", False):
            FrameService.set_collapsed(frame, False, scene=scene)

        nodes = FrameService.get_attached_nodes(frame, scene=scene)
        if not nodes:
            return False

        min_x = min(node.sceneBoundingRect().left() for node in nodes)
        min_y = min(node.sceneBoundingRect().top() for node in nodes)
        max_x = max(node.sceneBoundingRect().right() for node in nodes)
        max_y = max(node.sceneBoundingRect().bottom() for node in nodes)

        target_x = min_x - padding
        target_y = min_y - header_h - padding
        target_w = max(MIN_FRAME_WIDTH, (max_x - min_x) + (padding * 2.0))
        target_h = max(MIN_FRAME_HEIGHT, (max_y - min_y) + header_h + (padding * 2.0))

        start_x = frame.pos().x()
        start_y = frame.pos().y()
        start_w = frame.width
        start_h = frame.height

        from PySide6.QtCore import QVariantAnimation, QEasingCurve
        anim = QVariantAnimation(frame)
        anim.setDuration(250)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)

        def _step(progress):
            cx = start_x + (target_x - start_x) * progress
            cy = start_y + (target_y - start_y) * progress
            cw = start_w + (target_w - start_w) * progress
            ch = start_h + (target_h - start_h) * progress

            if hasattr(frame, "setPos"):
                frame.setPos(cx, cy)
            frame.width = float(cw)
            frame.height = float(ch)
            frame.payload["layout"] = {"width": frame.width, "height": frame.height}
            if hasattr(frame, "update"):
                frame.update()

        def _done():
            if hasattr(frame, "_emit_modified"):
                frame._emit_modified()

        anim.valueChanged.connect(_step)
        anim.finished.connect(_done)
        anim.start()
        return True

    @staticmethod
    def cleanup_node_deletion(node_id: str, items_map_or_scene) -> None:
        """Garbage collect deleted node ID from parent frame child_node_ids."""
        items = []
        if isinstance(items_map_or_scene, dict):
            items = list(items_map_or_scene.values())
        elif hasattr(items_map_or_scene, "items"):
            items = list(items_map_or_scene.items())

        for item in items:
            if hasattr(item, "payload") and isinstance(item.payload, dict) and "child_node_ids" in item.payload:
                child_ids = item.payload.get("child_node_ids", [])
                if isinstance(child_ids, list) and node_id in child_ids:
                    child_ids.remove(node_id)
                    item.payload["child_node_ids"] = child_ids
                    if hasattr(item, "_emit_modified"):
                        item._emit_modified()
                    if hasattr(item, "update"):
                        item.update()

    @staticmethod
    def cleanup_frame_deletion(frame, items_map_or_scene) -> None:
        """Clear parent_frame_id on all attached child nodes when frame is deleted."""
        active_scene = items_map_or_scene if hasattr(items_map_or_scene, "items") else getattr(frame, "scene", lambda: None)()
        FrameService.detach_all(frame, scene=active_scene)

    @staticmethod
    def prepare_clipboard_nodes(selected_nodes: list) -> list:
        """Serialize nodes for clipboard, enforcing Figma-style frame copy rules.

        If a frame is copied without its children selected, child_node_ids is cleared on copy.
        If frame + children are copied together, relationship IDs are preserved for remapping on paste.
        """
        selected_ids = {n.id for n in selected_nodes if hasattr(n, "id")}
        serialized_nodes = []

        for node in selected_nodes:
            if not hasattr(node, "to_dict"):
                continue
            data = node.to_dict()
            payload = data.get("payload", {})

            # Frame node logic
            if "child_node_ids" in payload:
                orig_children = payload.get("child_node_ids", [])
                copied_children = [cid for cid in orig_children if cid in selected_ids]
                payload["child_node_ids"] = copied_children

            # Non-frame spatial node logic
            if "parent_frame_id" in payload:
                parent_id = payload.get("parent_frame_id")
                if parent_id not in selected_ids:
                    payload["parent_frame_id"] = None

            data["payload"] = payload
            serialized_nodes.append(data)

        return serialized_nodes

    @staticmethod
    def remap_pasted_memberships(pasted_nodes: list, old_to_new_id_map: Dict[str, str]) -> None:
        """Remap parent_frame_id and child_node_ids after pasting a set of nodes."""
        for node in pasted_nodes:
            if not hasattr(node, "payload") or not isinstance(node.payload, dict):
                continue
            payload = node.payload

            # Remap frame's child IDs
            if "child_node_ids" in payload and isinstance(payload["child_node_ids"], list):
                remapped_children = []
                for old_cid in payload["child_node_ids"]:
                    if old_cid in old_to_new_id_map:
                        remapped_children.append(old_to_new_id_map[old_cid])
                payload["child_node_ids"] = remapped_children

            # Remap child's parent frame ID
            if "parent_frame_id" in payload and payload.get("parent_frame_id"):
                old_pid = payload["parent_frame_id"]
                payload["parent_frame_id"] = old_to_new_id_map.get(old_pid, None)

            if hasattr(node, "_emit_modified"):
                node._emit_modified()
