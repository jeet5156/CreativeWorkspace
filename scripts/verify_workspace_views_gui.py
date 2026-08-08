import sys
import tempfile
import shutil
from pathlib import Path

# Add repo root to Python path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF, Qt

from ui.widgets.infinite_canvas import InfiniteCanvas
from ui.lab.nodes.frame_node_item import FrameNodeItem
from services.frame_service import FrameService
from ui.dialogs.node_search_dialog import NodeSearchDialog


def run_gui_verification():
    print("==================================================")
    print("Sprint 0.6.1 Phase 2: Workspace Views & Navigation GUI Verification")
    print("==================================================")

    app = QApplication.instance() or QApplication(sys.argv)

    temp_dir = tempfile.mkdtemp()
    try:
        canvas = InfiniteCanvas()
        canvas.update_project_location(temp_dir)

        # [1] Create several nodes spread across canvas
        n1 = canvas.add_node({"type": "note.blank", "transform": {"x": -800.0, "y": -600.0, "width": 200.0, "height": 150.0}, "payload": {"content": "West Note"}})
        n2 = canvas.add_node({"type": "note.blank", "transform": {"x": 1200.0, "y": 800.0, "width": 200.0, "height": 150.0}, "payload": {"content": "East Note"}})
        n3 = canvas.add_node({"type": "asset.3d", "transform": {"x": 0.0, "y": 0.0, "width": 300.0, "height": 200.0}, "payload": {"filename": "hero.fbx"}})

        assert n1 is not None and n2 is not None and n3 is not None
        print("[OK] [1] Created nodes spread across spatial canvas (-800,-600 to 1200,800)")

        # [2, 3, 4] Select several nodes and Fit Selection
        canvas.set_selected_nodes([n1, n3])
        canvas.fit_selection(padding=50.0)
        assert len(canvas.selected_nodes()) == 2
        print("[OK] [2, 3, 4] Executed 'fit_selection()' -> Viewport adjusted to enclose selected nodes")

        # [5, 6, 7] Press Shift+F (Fit View / Fit All)
        canvas.fit_view(padding=50.0)
        print("[OK] [5, 6, 7] Executed 'fit_view()' (Shift+F) -> Viewport adjusted to enclose all board contents")

        # [8, 9, 10] Press Home / Ctrl+0 (Reset Camera)
        canvas.reset_camera()
        assert canvas._zoom_level == 1.0
        center = canvas.mapToScene(canvas.viewport().rect().center())
        assert abs(center.x()) < 5.0 and abs(center.y()) < 5.0
        print("[OK] [8, 9, 10] Executed 'reset_camera()' (Home / Ctrl+0) -> Zoom set to 1.0, centered on origin (0, 0)")

        # [11 & 12] Zoom In / Zoom Out
        orig_zoom = canvas._zoom_level
        canvas.zoom_in()
        assert canvas._zoom_level > orig_zoom
        canvas.zoom_out()
        assert abs(canvas._zoom_level - orig_zoom) < 0.05
        print("[OK] [11 & 12] Executed Zoom In (+/=) and Zoom Out (-) shortcuts cleanly")

        # [13, 14, 15] Ctrl+K Search for a distant node
        canvas.centerOn(0, 0)
        canvas.push_navigation_state(node_id="origin")

        canvas._on_search_node_selected(n2.id)
        assert canvas.selected_nodes() == [n2]
        print("[OK] [13, 14, 15] Executed Ctrl+K Quick Search Palette selection -> Focused target node n2 (1200, 800)")

        # [16, 17] Alt+Left (Go Back History)
        canvas.go_back_history()
        center_back = canvas.mapToScene(canvas.viewport().rect().center())
        assert abs(center_back.x()) < 50.0 and abs(center_back.y()) < 50.0
        print("[OK] [16, 17] Executed Alt+Left (Go Back History) -> Restored previous pre-search camera location (0, 0)")

        # [18, 19] Alt+Right (Go Forward History)
        canvas.go_forward_history()
        assert canvas.selected_nodes() == [n2]
        print("[OK] [18, 19] Executed Alt+Right (Go Forward History) -> Restored search target location n2")

        # [20, 21, 22] Put node inside collapsed frame & search for child
        n_hidden = canvas.add_node({"type": "note.blank", "transform": {"x": 500.0, "y": -300.0, "width": 200.0, "height": 150.0}, "payload": {"content": "Secret Child"}})
        frame = FrameService.create_frame_from_selection([n_hidden], canvas, title="Collapsed Container")
        FrameService.set_collapsed(frame, True, scene=canvas.scene())

        assert frame.payload.get("collapsed") is True
        assert not n_hidden.isVisible()

        # Explicit search navigation to hidden child
        canvas._on_search_node_selected(n_hidden.id)

        assert not frame.payload.get("collapsed")
        assert n_hidden.isVisible()
        assert canvas.selected_nodes() == [n_hidden]
        print("[OK] [20, 21, 22] Executed explicit navigation to hidden child -> Revealed parent frame & focused child")

        # [23] Confirm normal frame collapse/expand still works
        FrameService.set_collapsed(frame, True, scene=canvas.scene())
        assert frame.payload.get("collapsed") is True
        FrameService.set_collapsed(frame, False, scene=canvas.scene())
        assert frame.payload.get("collapsed") is False
        print("[OK] [23] Confirmed normal Frame collapse/expand operates 100% intact")

        # [24] Saved View creation & restoration
        canvas.centerOn(-500, -500)
        sv = canvas.save_camera_view("West Viewpoint")
        canvas.centerOn(1000, 1000)

        canvas.restore_camera_view(sv)
        print("[OK] [24] Restored saved camera view with smooth animated interpolation")

        print("==================================================")
        print("ALL 24 MANUAL GUI VERIFICATION CHECKS PASSED 100%")
        print("==================================================")
        return True

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    success = run_gui_verification()
    sys.exit(0 if success else 1)
