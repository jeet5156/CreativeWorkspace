import sys
import unittest
import tempfile
import shutil
from pathlib import Path
import os
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox, QInputDialog
from PySide6.QtGui import QImage, QColor, QGuiApplication, QPainter, QPixmap
from PySide6.QtCore import Qt, QPointF, QRectF, QSize

from core.app_context import AppContext
from models.project import Project
from core.paths import get_shared_workbench_boards_dir
from core.storage import atomic_write_json, safe_read_json
from services.lab_service import LabService
from services.project_service import ProjectService
from ui.workspace_manager import WorkspaceManager
from ui.panels.explorer_panel import (
    ExplorerPanel,
    ROLE_PROJECT,
    ROLE_SECTION,
    ROLE_REL_PATH,
    ROLE_NODE_TYPE,
)
from ui.panels.workspace_panel import WorkspacePanel
from ui.widgets.infinite_canvas import InfiniteCanvas
from ui.lab.nodes.image_node_item import ImageNodeItem, ImageNodeState
from ui.lab.nodes.node_registry import NodeRegistry

app = QApplication.instance() or QApplication(sys.argv)


class TestWorkbenchBoardManagementAndCanvasPerf(unittest.TestCase):
    """Rigorous tests for Workbench board management, safety guards, and canvas performance."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="cw_mgmt_test_")
        self.root_path = Path(self.tmp_dir)
        self.shared_data = self.root_path / "data"
        self.shared_data.mkdir(parents=True, exist_ok=True)
        os.environ["CREATIVE_WORKSPACE_SHARED_DATA_DIR"] = str(self.shared_data)

        self.project_svc = ProjectService()
        self.lab_svc = LabService(project_service=self.project_svc)

        # Create dummy project
        proj_dir = self.root_path / "TestProject"
        proj_dir.mkdir(parents=True, exist_ok=True)
        self.project = Project(name="TestProject", project_type="general", location=str(proj_dir))
        self.project_svc.add_project(self.project)

        self.context = AppContext()
        self.context.lab_service = self.lab_svc
        self.context.project_service = self.project_svc

        self.ws_panel = WorkspacePanel()
        self.ws_panel._context = self.context
        self.wm = WorkspaceManager(self.ws_panel, self.context)
        self.context.workspace_manager = self.wm

        self.explorer = ExplorerPanel()
        self.explorer.set_context(self.context)
        self.explorer.add_project(self.project)

    def tearDown(self):
        if "CREATIVE_WORKSPACE_SHARED_DATA_DIR" in os.environ:
            del os.environ["CREATIVE_WORKSPACE_SHARED_DATA_DIR"]
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_workbench_root_has_new_board_action(self):
        """Workbench root in Explorer has New Board action in context menu."""
        wb_item = self.explorer.lab_root
        self.explorer.tree.setCurrentItem(wb_item)
        self.assertEqual(wb_item.data(0, ROLE_SECTION), "workbench")
        self.assertIsNotNone(self.explorer.new_board_action)

    def test_create_workbench_board_from_tree(self):
        """Creating a new board via tree action adds it to manifest and disk with stable UUID."""
        with patch.object(QInputDialog, "getText", return_value=("Inspiration Board", True)):
            self.explorer.tree.setCurrentItem(self.explorer.lab_root)
            self.explorer._request_new_board()

        wb_boards = self.lab_svc.list_boards(None)
        names = [b["name"] for b in wb_boards]
        self.assertIn("Inspiration Board", names)

        new_b = [b for b in wb_boards if b["name"] == "Inspiration Board"][0]
        wb_dir = self.lab_svc.get_boards_dir(None)
        self.assertTrue((wb_dir / f"{new_b['id']}.lab.json").exists())

        # Project boards must be completely unaffected
        proj_boards = self.lab_svc.list_boards(self.project)
        self.assertNotIn("Inspiration Board", [b["name"] for b in proj_boards])

    def test_explorer_presents_collections_without_individual_boards(self):
        """Explorer tree displays Workbench root and collections, but does NOT display individual boards underneath."""
        self.lab_svc.create_board(None, "Canvas A")
        self.lab_svc.create_board(None, "Canvas B")
        self.explorer.refresh_lab_node(None)

        self.assertEqual(self.explorer.lab_root.childCount(), 1)
        col_item = self.explorer.lab_root.child(0)
        self.assertEqual(col_item.data(0, ROLE_NODE_TYPE), "collection")
        self.assertTrue(col_item.text(0).startswith("🗂️"), "Workbench collections must use distinct collection icon 🗂️")
        self.assertFalse(col_item.text(0).startswith("📁"), "Workbench collections must not use ordinary project folder icon 📁")
        self.assertEqual(col_item.childCount(), 0, "Individual boards must not appear under collections in Explorer tree")

    def test_rename_board_preserves_stable_id(self):
        """Renaming a Workbench board updates display name but leaves board ID and disk file stable."""
        b_entry = self.lab_svc.create_board(None, "Initial Title")
        b_id = b_entry["id"]

        self.wm.lab_panel.show_project(None, board_id=b_id)

        with patch.object(QInputDialog, "getText", return_value=("Renamed Title", True)):
            self.wm.lab_panel._on_rename_board_clicked(b_id, "Initial Title")

        # Check manifest
        updated = self.lab_svc.get_board_entry(None, b_id)
        self.assertEqual(updated["name"], "Renamed Title")
        self.assertEqual(updated["id"], b_id)

        # Check disk file
        wb_dir = self.lab_svc.get_boards_dir(None)
        self.assertTrue((wb_dir / f"{b_id}.lab.json").exists())
        file_data, _ = safe_read_json(wb_dir / f"{b_id}.lab.json")
        self.assertEqual(file_data["name"], "Renamed Title")
        self.assertEqual(file_data["board_id"], b_id)

    def test_duplicate_workbench_board(self):
        """Duplicating a board creates an isolated copy with fresh UUID."""
        original = self.lab_svc.create_board(None, "Style Reference")
        orig_id = original["id"]

        self.wm.lab_panel.show_project(None, board_id=orig_id)
        self.wm.lab_panel._on_duplicate_board_clicked(orig_id)

        boards = self.lab_svc.list_boards(None)
        names = [b["name"] for b in boards]
        self.assertIn("Style Reference", names)
        self.assertIn("Style Reference (Copy)", names)

    def test_delete_sole_board_protection(self):
        """Deleting the final remaining board is blocked with a warning dialog."""
        # Ensure only 1 board exists
        manifest = self.lab_svc.get_manifest(None)
        self.assertEqual(len(manifest["boards"]), 1)
        sole_id = manifest["boards"][0]["id"]

        self.wm.lab_panel.show_project(None, board_id=sole_id)

        with patch.object(QMessageBox, "warning") as mock_warn:
            self.wm.lab_panel._on_delete_board_clicked(sole_id, "Main")
            mock_warn.assert_called_once()

        # Board still exists
        self.assertEqual(len(self.lab_svc.list_boards(None)), 1)

    def test_delete_active_board_with_safe_fallback(self):
        """Deleting the active board falls back to nearest remaining board safely."""
        b2 = self.lab_svc.create_board(None, "Second Board")
        b2_id = b2["id"]
        self.lab_svc.set_active_board_id(None, b2_id)
        self.wm.lab_panel.show_project(None, board_id=b2_id)

        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            self.wm.lab_panel._on_delete_board_clicked(b2_id, "Second Board")

        # Active board falls back safely
        active_id = self.lab_svc.get_active_board_id(None)
        self.assertNotEqual(active_id, b2_id)
        self.assertIsNotNone(active_id)

        # b2 file is removed
        wb_dir = self.lab_svc.get_boards_dir(None)
        self.assertFalse((wb_dir / f"{b2_id}.lab.json").exists())

    def test_get_orphaned_boards_reporting_only(self):
        """get_orphaned_boards identifies unmanifested files without deleting or altering them."""
        wb_dir = self.lab_svc.get_boards_dir(None)

        # Create orphan empty file
        atomic_write_json(wb_dir / "orphan_empty.lab.json", {"board_id": "orphan_empty", "name": "Empty Orphan", "items": []})
        # Create orphan with user content
        atomic_write_json(wb_dir / "orphan_content.lab.json", {"board_id": "orphan_content", "name": "Content Orphan", "items": [{"id": "c1"}]})

        orphans = self.lab_svc.get_orphaned_boards(None)
        orphan_ids = [o["id"] for o in orphans]
        self.assertIn("orphan_empty", orphan_ids)
        self.assertIn("orphan_content", orphan_ids)

        # Files remain on disk (not deleted)
        self.assertTrue((wb_dir / "orphan_empty.lab.json").exists())
        self.assertTrue((wb_dir / "orphan_content.lab.json").exists())

        # Content flag correctly recognized
        content_orphan = [o for o in orphans if o["id"] == "orphan_content"][0]
        self.assertTrue(content_orphan["has_content"])
        empty_orphan = [o for o in orphans if o["id"] == "orphan_empty"][0]
        self.assertFalse(empty_orphan["has_content"])

    def test_save_viewport_does_not_emit_reload_signals(self):
        """save_viewport updates viewport without triggering manifest_updated or board_updated."""
        emitted_signals = []
        self.lab_svc.manifest_updated.connect(lambda p: emitted_signals.append("manifest_updated"))
        self.lab_svc.board_updated.connect(lambda p, b: emitted_signals.append("board_updated"))

        vp = {"zoom": 1.45, "pan_x": 250.0, "pan_y": -80.0}
        success = self.lab_svc.save_viewport(None, vp)
        self.assertTrue(success)

        # Signals should NOT be emitted for camera viewport change
        self.assertEqual(len(emitted_signals), 0)

        # Viewport persisted correctly in manifest
        manifest = self.lab_svc.get_manifest(None)
        self.assertEqual(manifest["last_view"]["zoom"], 1.45)

    def test_image_node_scaling_cache_performance(self):
        """ImageNodeItem caches scaled pixmap and avoids repeated smooth scaling on paint."""
        defn = NodeRegistry.get("image.reference")
        item = ImageNodeItem(defn)
        item.width = 300
        item.height = 200

        pm = QPixmap(1000, 800)
        pm.fill(QColor("magenta"))
        item._pixmap = pm
        item.state = ImageNodeState.READY

        img = QImage(300, 200, QImage.Format_ARGB32)
        p = QPainter(img)
        item.paint(p, None, None)
        p.end()

        # Cache should be populated
        self.assertIsNotNone(item._cached_scaled_pixmap)
        first_cache = item._cached_scaled_pixmap

        # Second paint reuses cached pixmap
        p2 = QPainter(img)
        item.paint(p2, None, None)
        p2.end()
        self.assertIs(item._cached_scaled_pixmap, first_cache)

    def test_show_workbench_direct_board_id_navigation(self):
        """show_workbench(board_id=...) navigates directly to requested board."""
        b2 = self.lab_svc.create_board(None, "Direct Board")
        self.wm.show_workbench(board_id=b2["id"])

        self.assertEqual(self.wm.lab_panel._current_board_id, b2["id"])
        self.assertIsNone(self.wm.lab_panel._current_project)


if __name__ == "__main__":
    unittest.main()
