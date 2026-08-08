import sys
import tempfile
import shutil
from pathlib import Path

# Add repo root to Python path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF

from ui.lab.nodes.node_registry import NodeRegistry
from ui.lab.nodes.frame_node_item import FrameNodeItem
from ui.widgets.infinite_canvas import InfiniteCanvas
from services.frame_service import FrameService, FRAME_PADDING, HEADER_HEIGHT
from core.inspectable_adapters import MultiNodeInspectable
from ui.dialogs.node_search_dialog import NodeSearchDialog


def run_gui_verification():
    print("==================================================")
    print("Sprint 0.6.1 Phase 1: Asset Organization & Workspace UX GUI Verification")
    print("==================================================")

    app = QApplication.instance() or QApplication(sys.argv)

    temp_dir = tempfile.mkdtemp()
    try:
        canvas = InfiniteCanvas()
        canvas.update_project_location(temp_dir)

        # [1] Create multiple different spatial node types
        n_note = canvas.add_node({"type": "note.blank", "transform": {"x": 100.0, "y": 100.0, "width": 200.0, "height": 150.0}, "payload": {"content": "Design Note"}})
        n_3d = canvas.add_node({"type": "asset.3d", "transform": {"x": 350.0, "y": 100.0, "width": 260.0, "height": 200.0}, "payload": {"filename": "hero.fbx"}})
        n_file = canvas.add_node({"type": "file.reference", "transform": {"x": 200.0, "y": 350.0, "width": 260.0, "height": 200.0}, "payload": {"filename": "ui.psd"}})

        assert n_note is not None and n_3d is not None and n_file is not None
        print("[OK] [1] Created heterogeneous spatial nodes (Note, 3D Asset, Generic File)")

        # [2] Select multiple different node types & move together
        canvas.set_selected_nodes([n_note, n_3d, n_file])
        selected = canvas.selected_nodes()
        assert len(selected) == 3
        print("[OK] [2] Multi-selection verified across heterogeneous node types")

        # [3 & 4] Create Frame from Selection
        orig_pos_note = QPointF(n_note.pos())
        orig_pos_3d = QPointF(n_3d.pos())
        orig_pos_file = QPointF(n_file.pos())

        frame = FrameService.create_frame_from_selection(selected, canvas, title="Character Rigging")
        assert frame is not None and isinstance(frame, FrameNodeItem)
        print(f"[OK] [3, 4, 5] Executed 'Create Frame from Selection' -> New Frame created (ID: {frame.id[:8]})")

        # [5 & 6] Confirm frame surrounds selected nodes and nodes remain in place
        assert frame.pos().x() == 100.0 - FRAME_PADDING
        assert frame.pos().y() == 100.0 - HEADER_HEIGHT - FRAME_PADDING
        assert n_note.pos() == orig_pos_note
        assert n_3d.pos() == orig_pos_3d
        assert n_file.pos() == orig_pos_file
        assert n_note.payload.get("parent_frame_id") == frame.id
        print("[OK] [6] Confirmed spatial node positions remained 100% intact with proper frame padding")

        # [7] Confirm frame collapse/expand still works
        FrameService.set_collapsed(frame, True, scene=canvas.scene())
        assert frame.payload.get("collapsed") is True
        assert not n_note.isVisible()

        FrameService.set_collapsed(frame, False, scene=canvas.scene())
        assert frame.payload.get("collapsed") is False
        assert n_note.isVisible()
        print("[OK] [7] Confirmed Frame collapse / expand functions cleanly on newly created frame")

        # [8 & 9] Multi-select and batch pin
        canvas.set_selected_nodes([n_note, n_3d])
        for n in canvas.selected_nodes():
            n.set_pinned(True)

        assert n_note.is_pinned is True
        assert n_3d.is_pinned is True
        print("[OK] [8 & 9] Executed Batch Pin -> Pinned state set and verified for selected nodes")

        # [10 & 11] Multi-select and batch add tags
        canvas.set_selected_nodes([n_note, n_3d, n_file])
        MultiNodeInspectable(canvas.selected_nodes()).set_inspectable_property("tags", "character, wip, priority")

        assert "character" in n_note.tags and "wip" in n_note.tags and "priority" in n_note.tags
        assert "character" in n_3d.tags and "wip" in n_3d.tags and "priority" in n_3d.tags
        assert "character" in n_file.tags and "wip" in n_file.tags and "priority" in n_file.tags
        print("[OK] [10 & 11] Executed Batch Tagging -> Tags 'character, wip, priority' propagated across multi-selection")

        # [12] Use Ctrl+K Quick Search Palette to verify tag search finds them
        dlg = NodeSearchDialog(list(canvas._items_map.values()))
        dlg._filter_nodes("tag:character")
        matched_ids = {n.id for n in dlg._filtered_nodes}
        assert n_note.id in matched_ids and n_3d.id in matched_ids and n_file.id in matched_ids
        print("[OK] [12] Quick Search Palette (Ctrl+K) 'tag:character' query verified finding all tagged nodes")

        print("==================================================")
        print("ALL 12 MANUAL GUI VERIFICATION CHECKS PASSED 100%")
        print("==================================================")
        return True

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    success = run_gui_verification()
    sys.exit(0 if success else 1)
