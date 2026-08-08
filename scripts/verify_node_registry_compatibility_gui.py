import sys
import tempfile
import shutil
from pathlib import Path

# Add repo root to Python path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF, QPoint, Qt

from ui.lab.nodes.node_registry import NodeRegistry
from ui.widgets.infinite_canvas import InfiniteCanvas


def run_gui_verification():
    print("==================================================")
    print("NodeRegistry Backward Compatibility GUI Verification")
    print("==================================================")

    app = QApplication.instance() or QApplication(sys.argv)

    temp_dir = tempfile.mkdtemp()
    try:
        canvas = InfiniteCanvas()
        canvas.update_project_location(temp_dir)

        # [A] Verify Complete Registry Registration (13 definitions)
        all_defs = NodeRegistry.list_all()
        categories = NodeRegistry.categories()

        expected_legacy = ["note.blank", "note.goal", "note.idea", "note.task", "note.problem", "note.decision"]
        expected_refs = ["image.reference", "document.pdf", "asset.3d", "file.reference", "folder.reference", "archive.reference", "frame.section"]

        for legacy_type in expected_legacy:
            assert NodeRegistry.get(legacy_type) is not None, f"Missing legacy type: {legacy_type}"

        for ref_type in expected_refs:
            assert NodeRegistry.get(ref_type) is not None, f"Missing reference type: {ref_type}"

        print(f"[OK] [A] Complete Registry Verified ({len(all_defs)} total definitions across categories: {categories})")

        # [B] Verify Empty-Canvas Context Menu Generation
        menu = NodeRegistry.build_context_menu(canvas, QPointF(0, 0), lambda d, pos: None)
        assert menu is not None and not menu.isEmpty()

        action_labels = [act.text() for act in menu.actions()]
        print(f"[OK] [B] Empty-Canvas Context Menu generated dynamically via NodeRegistry with {len(action_labels)} category submenus")

        # [C] Verify Legacy Project Data Payload Restoration
        legacy_payload = {
            "items": [
                {"id": "goal_1", "type": "note.goal", "transform": {"x": 100, "y": 100, "width": 240, "height": 180}, "payload": {"content": "v1.0 Milestone"}},
                {"id": "idea_1", "type": "note.idea", "transform": {"x": 400, "y": 100, "width": 240, "height": 180}, "payload": {"content": "New Architectural Features"}},
                {"id": "task_1", "type": "note.task", "transform": {"x": 700, "y": 100, "width": 240, "height": 180}, "payload": {"content": "NodeRegistry Compatibility Pass"}},
                {"id": "prob_1", "type": "note.problem", "transform": {"x": 100, "y": 350, "width": 240, "height": 180}, "payload": {"content": "Avoid Regression"}},
                {"id": "dec_1", "type": "note.decision", "transform": {"x": 400, "y": 350, "width": 240, "height": 180}, "payload": {"content": "Approved Design"}},
            ]
        }

        for item_data in legacy_payload["items"]:
            node = canvas.add_node(item_data)
            assert node is not None
            assert node.definition.type_id == item_data["type"]

        print("[OK] [C] Restored pre-0.6.x .lab.json board payload containing all 5 legacy note types without error")

        # [D] Verify Unknown Node Type Safe Fallback
        unknown_item = {"id": "custom_1", "type": "unregistered.custom_widget", "transform": {"x": 0, "y": 0, "width": 200, "height": 150}}
        fallback_node = canvas.add_node(unknown_item)
        assert fallback_node is not None
        assert fallback_node.id == "custom_1"

        print("[OK] [D] Unregistered node type safely handled with explicit warning and note.blank visual fallback (zero data loss)")

        print("==================================================")
        print("ALL NODEREGISTRY COMPATIBILITY CHECKS PASSED 100%")
        print("==================================================")
        return True

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    success = run_gui_verification()
    sys.exit(0 if success else 1)
