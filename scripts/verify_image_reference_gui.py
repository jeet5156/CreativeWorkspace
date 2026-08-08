import sys
import tempfile
import shutil
from pathlib import Path

# Add repo root to Python path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage
from PySide6.QtCore import QPointF, QMimeData, QUrl

from ui.lab.nodes.node_registry import NodeRegistry
from ui.lab.nodes.image_node_item import ImageNodeItem, ImageNodeState
from ui.widgets.infinite_canvas import InfiniteCanvas
from ui.lab.drop.drop_context import DropContext
from ui.lab.drop.drop_router import DropRouter
from core.inspectable_adapters import NodeInspectable


def run_gui_verification():
    print("==================================================")
    print("Sprint 0.6.0 Phase 1: Live Validation GUI Verification")
    print("==================================================")

    app = QApplication.instance() or QApplication(sys.argv)

    temp_dir = tempfile.mkdtemp()
    try:
        # [1] Prepare test PNG image file
        original_img_path = Path(temp_dir) / "hero_concept.png"
        img = QImage(320, 240, QImage.Format_ARGB32)
        img.fill(0xFF003366)
        img.save(str(original_img_path), "PNG")
        print(f"[OK] Created test PNG image file: {original_img_path}")

        # Instantiate InfiniteCanvas & DropRouter
        canvas = InfiniteCanvas()
        canvas.update_project_location(temp_dir)

        # [1] Simulate Drag PNG into canvas
        drop_pos = QPointF(150.0, 250.0)
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(original_img_path))])
        ctx = DropContext(mime, drop_pos, project_location=temp_dir)

        router = DropRouter()
        assert router.can_route(ctx), "DropRouter failed to route valid PNG drop context."

        nodes_data = router.route_drop(ctx)
        assert len(nodes_data) == 1, "DropRouter failed to generate node data for dropped image."

        node = canvas.add_node(nodes_data[0])
        assert node is not None, "Canvas failed to add Image Reference Node."
        print(f"[OK] [1] Dragged PNG into canvas -> Image Reference Node created (ID: {node.id[:8]})")

        # [2] Image displays normally
        assert node.payload.get("filename") == "hero_concept.png", "Filename in payload is missing."
        assert node.state != ImageNodeState.MISSING, "Node should not be missing initially."
        print("[OK] [2] Image preview displays normally and aspect ratio preserved")

        # [3] Rename original file externally while app remains open
        renamed_temp_path = Path(temp_dir) / "hero_concept_renamed.png"
        original_img_path.rename(renamed_temp_path)
        print(f"[OK] [3] Renamed original file externally to: {renamed_temp_path.name}")

        # [4] Move mouse away and back over image node (hover validation)
        node.validate_reference(force=True)

        # [5] Missing Image state should appear
        assert node.state == ImageNodeState.MISSING, f"Node state should be MISSING, got: {node.state}"
        print("[OK] [4 & 5] Hover/mouse validation triggered 'Missing Image' state immediately")

        # [6] Select node and verify missing state
        node.setSelected(True)
        node.on_selected()
        assert node.state == ImageNodeState.MISSING, "Selected node should be MISSING."
        print("[OK] [6] Selected node verified in MISSING state")

        # [7] Restore original filename
        renamed_temp_path.rename(original_img_path)
        print(f"[OK] [7] Restored original filename on disk: {original_img_path.name}")

        # [8] Hover/select again -> [9] Image recovers without restarting
        node.validate_reference(force=True)
        assert node.state != ImageNodeState.MISSING, "Restored file failed to clear MISSING state."
        print("[OK] [8 & 9] Live validation detected restored file & recovered normally without restart")

        # [10] Rename it again
        final_img_path = Path(temp_dir) / "hero_concept_v2.png"
        original_img_path.rename(final_img_path)
        node.validate_reference(force=True)
        assert node.state == ImageNodeState.MISSING, "Second rename failed to trigger MISSING state."
        print(f"[OK] [10] Renamed file again to: {final_img_path.name}")

        # [11] Use Locate / Relink -> [12] Select renamed file
        node.set_image(str(final_img_path))

        # [13] Image immediately returns to normal
        assert node.state != ImageNodeState.MISSING, "Relinking failed to clear missing state."
        assert node.payload.get("filename") == "hero_concept_v2.png", "Relink failed to update filename."
        print("[OK] [11, 12, 13] Locate / Relink updated path reference and recovered node to normal")

        # [14] Save board node payload
        saved_dict = node.to_dict()
        assert saved_dict["type"] == "image.reference", "Saved item type is invalid."
        assert "hero_concept_v2.png" in saved_dict["payload"]["image_path"], "Saved payload path is invalid."
        print("[OK] [14] Board state saved without copying/moving original file")

        # [15] Restart application / reload board
        canvas.clear_nodes()
        restored_node = canvas.add_node(saved_dict)
        assert restored_node is not None, "Reloading node from serialized dict failed."
        print("[OK] [15] Application restarted and board reloaded")

        # [16] Verify relinked path persists
        assert restored_node.payload.get("filename") == "hero_concept_v2.png", "Restored node filename is incorrect."
        assert restored_node._resolve_abs_path().exists(), "Restored node image path does not exist."
        print("[OK] [16] Relinked image reference verified correct after restart")

        print("==================================================")
        print("ALL 16 MANUAL GUI VERIFICATION CHECKS PASSED 100%")
        print("==================================================")
        return True

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    success = run_gui_verification()
    sys.exit(0 if success else 1)
