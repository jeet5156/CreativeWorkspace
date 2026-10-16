import sys
import unittest
import tempfile
import shutil
from pathlib import Path
import os
import time

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QColor, QGuiApplication, QPainter, QPixmap
from PySide6.QtCore import Qt, QPointF, QRectF

from core.app_context import AppContext
from models.project import Project
from core.paths import get_shared_data_dir, get_shared_workbench_boards_dir, get_shared_workbench_images_dir
from services.lab_service import LabService
from services.navigation_service import NavigationService
from ui.workspace_manager import WorkspaceManager
from ui.panels.explorer_panel import ExplorerPanel
from ui.widgets.infinite_canvas import InfiniteCanvas
from ui.lab.nodes.image_node_item import ImageNodeItem, ImageNodeState
from ui.lab.nodes.node_definition import NodeDefinition

app = QApplication.instance() or QApplication(sys.argv)


class TestWorkbenchNavigationAndClipboard(unittest.TestCase):
    """Targeted verification for Workbench navigation, performance guards, and clipboard image pasting."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="cw_wb_test_")
        self.root_path = Path(self.tmp_dir)
        self.shared_data = self.root_path / "data"
        self.shared_data.mkdir(parents=True, exist_ok=True)
        os.environ["CREATIVE_WORKSPACE_SHARED_DATA_DIR"] = str(self.shared_data)

    def tearDown(self):
        if "CREATIVE_WORKSPACE_SHARED_DATA_DIR" in os.environ:
            del os.environ["CREATIVE_WORKSPACE_SHARED_DATA_DIR"]
        try:
            QApplication.processEvents()
            clip = QGuiApplication.clipboard()
            if clip:
                clip.clear()
            QApplication.processEvents()
        except Exception:
            pass
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Navigation Key and Signal Single-Dispatch
    # -------------------------------------------------------------------------
    def test_navigation_service_workbench_key_routing(self):
        """Verify NavigationService.handle_navigation('workbench') dispatches to show_workbench."""
        called = {"show_wb": False}

        class MockWM:
            def show_workbench(self):
                called["show_wb"] = True
            def show_module(self, key):
                pass

        mock_wm = MockWM()
        nav_svc = NavigationService(workspace_manager=mock_wm, explorer=None, context=None)

        nav_svc.handle_navigation("workbench")
        self.assertTrue(called["show_wb"], "NavigationService should call show_workbench on 'workbench' key")

    def test_workspace_manager_show_module_workbench_alias(self):
        """Verify WorkspaceManager.show_module('workbench') routes to show_workbench."""
        class MockWorkspace:
            pass

        wm = WorkspaceManager(workspace_panel=MockWorkspace(), context=None)
        called = {"show_wb": False}
        wm.show_workbench = lambda: called.update({"show_wb": True})

        wm.show_module("workbench")
        self.assertTrue(called["show_wb"], "show_module('workbench') must delegate to show_workbench()")

    def test_lab_service_active_board_id_idempotent_guard(self):
        """Verify set_active_board_id returns True early without disk writes or signals if already active."""
        lab_svc = LabService(global_storage_dir=self.shared_data / "workbench" / "boards")
        board_entry = lab_svc.create_board(None, "Global Test")
        board_id = board_entry["id"]

        # Ensure board is active
        lab_svc.set_active_board_id(None, board_id)

        manifest_path = self.shared_data / "workbench" / "boards" / "board_manifest.json"
        self.assertTrue(manifest_path.exists())
        mtime_before = manifest_path.stat().st_mtime_ns

        signal_emitted = []
        lab_svc.manifest_updated.connect(lambda: signal_emitted.append(True))

        # Re-set same active board id
        result = lab_svc.set_active_board_id(None, board_id)
        self.assertTrue(result)

        mtime_after = manifest_path.stat().st_mtime_ns
        self.assertEqual(mtime_before, mtime_after, "File modification time should not change when board is already active")
        self.assertEqual(len(signal_emitted), 0, "manifest_updated signal must NOT be emitted when board is already active")

    # -------------------------------------------------------------------------
    # 2. Clipboard Image Pasting and Persistence
    # -------------------------------------------------------------------------
    def test_clipboard_image_pasting_project_board(self):
        """Verify pasting an image into an ImageNodeItem in a project board saves to <Project>/Lab/images/."""
        from ui.lab.nodes.node_registry import NodeRegistry
        proj_dir = self.root_path / "Projects" / "ProjectAlpha"
        proj_dir.mkdir(parents=True, exist_ok=True)
        proj = Project(name="ProjectAlpha", location=str(proj_dir), project_type="General")

        node_defn = NodeRegistry.get("image")
        node = ImageNodeItem(node_defn)
        node.set_context_services(project_location=str(proj_dir))

        # Put a test image on the system clipboard
        test_img = QImage(160, 120, QImage.Format_ARGB32)
        test_img.fill(QColor("#FF4500"))
        clipboard = QGuiApplication.clipboard()
        clipboard.setImage(test_img)
        QApplication.processEvents()

        # Paste from clipboard
        success = node.paste_image_from_clipboard()
        self.assertTrue(success, "Pasting a valid image from clipboard should succeed")

        expected_images_dir = proj_dir / "Lab" / "images"
        self.assertTrue(expected_images_dir.exists(), "Project Lab/images directory should be created")
        created_files = list(expected_images_dir.glob("pasted_*.png"))
        self.assertEqual(len(created_files), 1, "Exactly one pasted image file should be created")

        # Verify relative path storage
        stored_path = node.payload.get("image_path")
        self.assertTrue(stored_path.startswith("Lab/images/pasted_"), f"Stored path must be relative: {stored_path}")
        self.assertNotIn(":", stored_path, "Stored path should not contain drive letters")

        # Verify resolution
        abs_resolved = node._resolve_abs_path()
        self.assertIsNotNone(abs_resolved)
        self.assertTrue(abs_resolved.exists())
        self.assertEqual(abs_resolved.resolve(), created_files[0].resolve())

    def test_clipboard_image_pasting_global_workbench_board(self):
        """Verify pasting an image into an ImageNodeItem in global workbench saves to data/workbench/images/."""
        from ui.lab.nodes.node_registry import NodeRegistry
        node_defn = NodeRegistry.get("image")
        node = ImageNodeItem(node_defn)
        node.set_context_services(project_location=None)

        test_img = QImage(200, 150, QImage.Format_ARGB32)
        test_img.fill(QColor("#00CED1"))
        clipboard = QGuiApplication.clipboard()
        clipboard.setImage(test_img)
        QApplication.processEvents()

        success = node.paste_image_from_clipboard()
        self.assertTrue(success, "Pasting into global workbench card should succeed")

        expected_images_dir = self.shared_data / "workbench" / "images"
        self.assertTrue(expected_images_dir.exists(), "Shared workbench images directory should exist")
        created_files = list(expected_images_dir.glob("pasted_*.png"))
        self.assertEqual(len(created_files), 1)

        stored_path = node.payload.get("image_path")
        self.assertTrue(stored_path.startswith("workbench/images/pasted_"), f"Stored path: {stored_path}")

        # Portable resolution
        abs_resolved = node._resolve_abs_path()
        self.assertIsNotNone(abs_resolved)
        self.assertTrue(abs_resolved.exists())
        self.assertEqual(abs_resolved.resolve(), created_files[0].resolve())

    def test_clipboard_empty_or_non_image_handling(self):
        """Verify non-image clipboard data gracefully fails without error and leaves card untouched."""
        from ui.lab.nodes.node_registry import NodeRegistry
        node_defn = NodeRegistry.get("image")
        node = ImageNodeItem(node_defn)
        
        # Put plain text on clipboard
        clipboard = QGuiApplication.clipboard()
        clipboard.setText("Just plain text, not an image")
        QApplication.processEvents()

        success = node.paste_image_from_clipboard()
        self.assertFalse(success, "paste_image_from_clipboard should return False when clipboard has no image")
        self.assertEqual(node.payload.get("image_path"), "")

    def test_canvas_background_grid_brush_performance(self):
        """Verify InfiniteCanvas uses cached QBrush and SmartViewportUpdate for optimal rendering."""
        from PySide6.QtWidgets import QGraphicsView
        canvas = InfiniteCanvas()
        self.assertEqual(canvas.viewportUpdateMode(), QGraphicsView.SmartViewportUpdate)

        # Check cached brush generation
        brush1 = canvas._get_grid_brush(20)
        brush2 = canvas._get_grid_brush(20)
        self.assertIs(brush1, brush2, "Grid brush must be cached for the same grid size")

        brush_other = canvas._get_grid_brush(30)
        self.assertIsNot(brush1, brush_other, "New brush should be created if grid size changes")

    def test_canvas_paste_image_as_new_card(self):
        """Verify InfiniteCanvas.paste_image_as_new_card creates a new Image node at specified scene position."""
        canvas = InfiniteCanvas()
        test_img = QImage(120, 90, QImage.Format_ARGB32)
        test_img.fill(QColor("#32CD32"))
        clipboard = QGuiApplication.clipboard()
        clipboard.setImage(test_img)
        QApplication.processEvents()

        target_pos = QPointF(250.0, 350.0)
        new_node = canvas.paste_image_as_new_card(scene_pos=target_pos)

        self.assertIsNotNone(new_node)
        self.assertIsInstance(new_node, ImageNodeItem)
        self.assertEqual(new_node.pos().x(), 250.0)
        self.assertEqual(new_node.pos().y(), 350.0)
        self.assertEqual(canvas.selected_nodes(), [new_node])
        self.assertTrue(new_node.payload.get("image_path").startswith("workbench/images/pasted_"))

    def test_image_collision_resolution(self):
        """Verify consecutive pastes generate non-colliding unique filenames."""
        from ui.lab.nodes.node_registry import NodeRegistry
        node_defn = NodeRegistry.get("image")
        node1 = ImageNodeItem(node_defn)
        node2 = ImageNodeItem(node_defn)

        test_img = QImage(50, 50, QImage.Format_ARGB32)
        test_img.fill(QColor("#FF1493"))
        QGuiApplication.clipboard().setImage(test_img)
        QApplication.processEvents()

        self.assertTrue(node1.paste_image_from_clipboard())
        self.assertTrue(node2.paste_image_from_clipboard())

        path1 = node1.payload.get("image_path")
        path2 = node2.payload.get("image_path")
        self.assertNotEqual(path1, path2, "Consecutive pastes must not overwrite existing images")

    def test_explorer_repeated_refreshes_no_duplicate_entries(self):
        """Verify repeated calls to refresh_lab_node clear previous items and do not accumulate duplicate entries."""
        lab_svc = LabService(global_storage_dir=self.shared_data / "workbench" / "boards")
        lab_svc.create_board(None, "Alpha")
        lab_svc.create_board(None, "Beta")

        app_ctx = AppContext()
        app_ctx.lab_service = lab_svc
        explorer = ExplorerPanel()
        explorer.set_context(app_ctx)

        # Refresh once
        explorer.refresh_lab_node(None)
        boards_first = [explorer.lab_root.child(i).text(0) for i in range(explorer.lab_root.childCount())]

        # Refresh again
        explorer.refresh_lab_node(None)
        boards_second = [explorer.lab_root.child(i).text(0) for i in range(explorer.lab_root.childCount())]

        self.assertEqual(boards_first, boards_second, "Repeated refresh must produce identical child item list without duplicates")
        self.assertEqual(len(boards_second), len(set(boards_second)), "All board entries in tree must be distinct")

    def test_ctrl_v_preserves_node_copy_paste_when_canvas_clipboard_has_nodes(self):
        """Verify Ctrl+V pastes internal copied nodes and does NOT overwrite with system image when nodes are in clipboard."""
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        from core.canvas_command import CanvasCommand

        canvas = InfiniteCanvas()
        # Create a note node and copy it to canvas clipboard
        note = canvas.add_node({"id": "note-1", "type": "note.blank", "transform": {"x": 50, "y": 50, "width": 200, "height": 100}, "payload": {"content": "Test Note"}})
        note.setSelected(True)
        canvas.execute_command(CanvasCommand.COPY)
        self.assertTrue(canvas.clipboard.has_content())

        # Put an image on the system clipboard at the same time
        test_img = QImage(100, 100, QImage.Format_ARGB32)
        test_img.fill(QColor("#FF00FF"))
        QGuiApplication.clipboard().setImage(test_img)
        QApplication.processEvents()

        # Deselect all nodes on canvas
        canvas.clear_selection()
        self.assertEqual(len(canvas.selected_nodes()), 0)

        # Send Ctrl+V key event to canvas
        key_event = QKeyEvent(QEvent.KeyPress, Qt.Key_V, Qt.ControlModifier)
        canvas.keyPressEvent(key_event)

        # Verify that the pasted node is a copy of the Note, NOT an image card!
        selected = canvas.selected_nodes()
        self.assertEqual(len(selected), 1)
        pasted_node = selected[0]
        self.assertNotEqual(pasted_node.id, "note-1")
        self.assertEqual(pasted_node.definition.type_id, "note.blank")
        self.assertEqual(pasted_node.payload.get("content"), "Test Note")

    def test_image_card_compatibility_existing_absolute_and_relative_paths(self):
        """Verify ImageNodeItem resolves local project paths, shared workbench paths, and existing absolute paths."""
        from ui.lab.nodes.node_registry import NodeRegistry
        node_defn = NodeRegistry.get("image")

        # 1. Project path
        proj_dir = self.root_path / "Projects" / "ProjectBeta"
        (proj_dir / "Lab" / "images").mkdir(parents=True, exist_ok=True)
        proj_img_file = proj_dir / "Lab" / "images" / "concept.png"
        proj_img_file.write_bytes(b"dummy")

        node_proj = ImageNodeItem(node_defn)
        node_proj.set_context_services(project_location=str(proj_dir))
        node_proj.payload["image_path"] = "Lab/images/concept.png"

        resolved_proj = node_proj._resolve_abs_path()
        self.assertIsNotNone(resolved_proj)
        self.assertEqual(resolved_proj.resolve(), proj_img_file.resolve())

        # 2. Shared global Workbench path
        wb_images_dir = self.shared_data / "workbench" / "images"
        wb_images_dir.mkdir(parents=True, exist_ok=True)
        wb_img_file = wb_images_dir / "shared_ref.png"
        wb_img_file.write_bytes(b"dummy")

        node_wb = ImageNodeItem(node_defn)
        node_wb.set_context_services(project_location=None)
        node_wb.payload["image_path"] = "workbench/images/shared_ref.png"

        resolved_wb = node_wb._resolve_abs_path()
        self.assertIsNotNone(resolved_wb)
        self.assertEqual(resolved_wb.resolve(), wb_img_file.resolve())

        # 3. Cross-machine compatibility: absolute path from Machine 1 (does not exist locally),
        # but relative file exists under shared data dir -> resolves seamlessly via relative fallback
        node_cross = ImageNodeItem(node_defn)
        node_cross.set_context_services(project_location=None)
        node_cross.payload["absolute_path"] = "X:\\OtherMachine\\CreativeWorkspace\\data\\workbench\\images\\shared_ref.png"
        node_cross.payload["image_path"] = "workbench/images/shared_ref.png"

        resolved_cross = node_cross._resolve_abs_path()
        self.assertIsNotNone(resolved_cross)
        self.assertEqual(resolved_cross.resolve(), wb_img_file.resolve())

    def test_grid_brush_updates_on_grid_size_and_visibility_change(self):
        """Verify cached grid brush recreates tile when grid size changes and obeys grid visibility."""
        canvas = InfiniteCanvas()
        self.assertTrue(canvas._grid_visible)
        self.assertEqual(canvas._grid_size, 20)

        brush_20_a = canvas._get_grid_brush(20)
        brush_20_b = canvas._get_grid_brush(20)
        self.assertIs(brush_20_a, brush_20_b)

        # Change grid size to 40
        canvas._grid_size = 40
        brush_40 = canvas._get_grid_brush(40)
        self.assertIsNot(brush_20_a, brush_40)
        self.assertEqual(canvas._cached_grid_size, 40)

        # Toggle visibility
        canvas._grid_visible = False
        self.assertFalse(canvas._grid_visible)


    def test_cross_machine_legacy_absolute_paths_project_and_global(self):
        """Verify boards containing absolute paths from Machine 1 resolve safely on Machine 2 and normalize to relative paths."""
        from ui.lab.nodes.node_registry import NodeRegistry
        node_defn = NodeRegistry.get("image")

        # Case A: Legacy project image saved with Machine 1 absolute path
        proj_dir = self.root_path / "Projects" / "LegacyAlpha"
        (proj_dir / "Lab" / "images").mkdir(parents=True, exist_ok=True)
        img_on_disk = proj_dir / "Lab" / "images" / "char_sketch.png"
        img_on_disk.write_bytes(b"image_content_here")

        node_proj = ImageNodeItem(node_defn)
        node_proj.set_context_services(project_location=str(proj_dir))
        # Machine 1 absolute path that does NOT exist on this machine
        machine1_proj_path = "C:\\Users\\Artist1\\AppData\\Local\\Projects\\LegacyAlpha\\Lab\\images\\char_sketch.png"
        self.assertFalse(Path(machine1_proj_path).exists(), "Precondition: Machine 1 absolute path must NOT exist locally")
        self.assertTrue(img_on_disk.exists(), "Precondition: Corresponding file must exist at project location on Machine 2")

        node_proj.payload["image_path"] = machine1_proj_path
        node_proj.payload["absolute_path"] = machine1_proj_path

        resolved_proj = node_proj._resolve_abs_path()
        self.assertIsNotNone(resolved_proj, "Must resolve legacy Machine 1 project absolute path on Machine 2")
        self.assertEqual(resolved_proj.resolve(), img_on_disk.resolve())

        # Normalization should convert it to portable relative path
        node_proj._normalize_image_path()
        self.assertEqual(node_proj.payload.get("image_path"), "Lab/images/char_sketch.png")

        # Case B: Legacy global workbench image saved with Machine 1 absolute path
        wb_dir = self.shared_data / "workbench" / "images"
        wb_dir.mkdir(parents=True, exist_ok=True)
        wb_img_disk = wb_dir / "palette.png"
        wb_img_disk.write_bytes(b"palette_content")

        node_wb = ImageNodeItem(node_defn)
        node_wb.set_context_services(project_location=None)
        # Machine 1 absolute path that does NOT exist on this machine
        machine1_wb_path = "D:\\SharedDrive\\CreativeWorkspace\\data\\workbench\\images\\palette.png"
        self.assertFalse(Path(machine1_wb_path).exists(), "Precondition: Machine 1 workbench path must NOT exist locally")
        self.assertTrue(wb_img_disk.exists(), "Precondition: Corresponding file must exist at shared workbench location on Machine 2")

        node_wb.payload["image_path"] = machine1_wb_path
        node_wb.payload["absolute_path"] = machine1_wb_path

        resolved_wb = node_wb._resolve_abs_path()
        self.assertIsNotNone(resolved_wb, "Must resolve legacy Machine 1 workbench absolute path on Machine 2")
        self.assertEqual(resolved_wb.resolve(), wb_img_disk.resolve())

        node_wb._normalize_image_path()
        self.assertEqual(node_wb.payload.get("image_path"), "workbench/images/palette.png")

        # Case C: Genuinely missing file (does not exist anywhere)
        node_missing = ImageNodeItem(node_defn)
        node_missing.set_context_services(project_location=str(proj_dir))
        ghost_path = "C:\\NonExistentPath\\Lab\\images\\ghost.png"
        self.assertFalse(Path(ghost_path).exists())
        node_missing.payload["image_path"] = ghost_path
        node_missing.payload["absolute_path"] = ghost_path
        self.assertIsNone(node_missing._resolve_abs_path())
        self.assertFalse(node_missing.validate_reference(force=True))
        self.assertEqual(node_missing.state, ImageNodeState.MISSING)

        # Case D: Local external absolute image (not inside project or workbench) is preserved
        ext_img = self.root_path / "Downloads" / "stock_photo.png"
        ext_img.parent.mkdir(parents=True, exist_ok=True)
        ext_img.write_bytes(b"stock")
        node_ext = ImageNodeItem(node_defn)
        node_ext.set_context_services(project_location=str(proj_dir))
        node_ext.set_image(str(ext_img))
        self.assertEqual(node_ext.payload.get("image_path"), str(ext_img.resolve()))
        self.assertEqual(node_ext._resolve_abs_path().resolve(), ext_img.resolve())

    def test_explorer_single_dispatch_item_expanded(self):
        """Verify Explorer tree expansion fires single dispatch, populates children, and does not duplicate."""
        lab_svc = LabService(global_storage_dir=self.shared_data / "workbench" / "boards")
        lab_svc.create_board(None, "Global Test Board")

        app_ctx = AppContext()
        app_ctx.lab_service = lab_svc

        # Subclass ExplorerPanel to instrument callbacks BEFORE signals are connected in __init__
        class InstrumentedExplorer(ExplorerPanel):
            def __init__(self, *args, **kwargs):
                self.tree_expanded_callbacks = []
                self.item_expanded_callbacks = []
                super().__init__(*args, **kwargs)

            def _on_tree_item_expanded(self, item):
                self.tree_expanded_callbacks.append(item)
                super()._on_tree_item_expanded(item)

            def _on_item_expanded(self, item):
                self.item_expanded_callbacks.append(item)
                super()._on_item_expanded(item)

        explorer = InstrumentedExplorer()
        explorer.set_context(app_ctx)

        # Confirm 1-to-1 parity between tree signal and expansion handler on initial setup
        self.assertEqual(
            len(explorer.tree_expanded_callbacks), len(explorer.item_expanded_callbacks),
            "Initial expansion events must have exact 1-to-1 dispatch"
        )

        # Clear recording lists to isolate the Workbench expansion event
        explorer.tree_expanded_callbacks.clear()
        explorer.item_expanded_callbacks.clear()

        # Trigger expansion on Workbench root
        explorer.lab_root.setExpanded(True)
        QApplication.processEvents()

        # Verify each handler was invoked exactly once (single-dispatch)
        self.assertEqual(
            len(explorer.tree_expanded_callbacks), 1,
            "_on_tree_item_expanded must be called exactly once per itemExpanded event"
        )
        self.assertEqual(
            len(explorer.item_expanded_callbacks), 1,
            "_on_item_expanded must be called exactly once per itemExpanded event without duplicate dispatch"
        )
        self.assertEqual(explorer.tree_expanded_callbacks[0], explorer.lab_root)
        self.assertEqual(explorer.item_expanded_callbacks[0], explorer.lab_root)

        # Verify children populated cleanly: collections under Workbench root, no boards in Explorer tree
        col_names = [explorer.lab_root.child(i).text(0) for i in range(explorer.lab_root.childCount())]
        self.assertTrue(any("General" in name for name in col_names))
        for i in range(explorer.lab_root.childCount()):
            self.assertEqual(explorer.lab_root.child(i).childCount(), 0, "Individual boards must not appear under collections in Explorer tree")


if __name__ == "__main__":
    unittest.main()

