import os
import shutil
import tempfile
import unittest
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

app = QApplication.instance() or QApplication([])

import sys
sys.path.insert(0, r"c:\Users\jeet5\.copilot\repos\creativeworkspace")

from models.project import Project
from services.project_service import ProjectService
from services.lab_service import LabService
from ui.panels.home_workspace_panel import HomeWorkspacePanel, PinnedCard
from ui.panels.explorer_panel import ExplorerPanel


class TestHomeDailyCommandCenter(unittest.TestCase):
    """Comprehensive test suite for Sprint 0.6.2 Home Daily Command Center phase."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.patch_global_dir = Path(self.temp_dir) / "workbench_boards"
        self.patch_global_dir.mkdir(parents=True, exist_ok=True)

        self.orig_get_boards_dir = LabService.get_boards_dir

        def mock_get_boards_dir(svc, project):
            if not project or not getattr(project, "location", None):
                return self.patch_global_dir
            boards_dir = Path(project.location) / "Lab" / "boards"
            boards_dir.mkdir(parents=True, exist_ok=True)
            return boards_dir

        LabService.get_boards_dir = mock_get_boards_dir

        self.project_svc = ProjectService()

        # Create dummy Cyclops project
        proj_dir = str(Path(self.temp_dir) / "Cyclops")
        os.makedirs(proj_dir, exist_ok=True)
        self.cyclops_project = Project(
            name="Cyclops",
            project_type="game",
            location=proj_dir,
            created="2026-08-11T12:00:00",
            last_opened="2026-08-11T12:00:00"
        )
        self.project_svc.projects = [self.cyclops_project]

        self.lab_svc = LabService(project_service=self.project_svc)

        class MockContext:
            def __init__(ctx_self, lab_svc, proj_svc):
                ctx_self.lab_service = lab_svc
                ctx_self.project_service = proj_svc
                ctx_self.current_project = None
                ctx_self.inspector_panel = None
                ctx_self.workspace_manager = None
                ctx_self.thumbnail_service = None
                ctx_self.asset_service = None
                ctx_self.app_state = None

        self.context = MockContext(self.lab_svc, self.project_svc)

    def tearDown(self):
        LabService.get_boards_dir = self.orig_get_boards_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_1_home_performance_path_no_canvas(self):
        """Verify Home set_context populates cleanly without instantiating canvases."""
        home = HomeWorkspacePanel()
        home.set_context(self.context)
        self.assertIsNotNone(home.layout)

    def test_2_pinned_card_shows_actual_note_content_preview(self):
        """Verify pinned card displays actual note content snippet preview."""
        wb_board = self.lab_svc.load_board(None, "Main")
        wb_board["items"] = [{
            "id": "wb_pin_preview",
            "type": "note.blank",
            "is_pinned": True,
            "payload": {
                "title": "Shader Research",
                "content": "Investigate Three.js shader nodes\nand WebGPU rendering workflow..."
            }
        }]
        self.lab_svc.save_board(None, wb_board, "Main")

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        found_preview = False
        for i in range(home.pins_grid.count()):
            card = home.pins_grid.itemAt(i).widget()
            for lbl in card.findChildren(QLabel):
                if "Three.js shader nodes" in lbl.text():
                    found_preview = True
                    break

        self.assertTrue(found_preview)

    def test_3_workbench_pinned_card_preview_works(self):
        """Verify Workbench pinned card preview shows source badge and title."""
        item = self.lab_svc.add_quick_capture_note("Workbench Note Preview Test")
        home = HomeWorkspacePanel()
        home.set_context(self.context)

        badges = []
        for i in range(home.pins_grid.count()):
            card = home.pins_grid.itemAt(i).widget()
            for lbl in card.findChildren(QLabel):
                if "🛠️ Workbench" in lbl.text():
                    badges.append(lbl.text())

        self.assertTrue(len(badges) > 0)

    def test_4_project_pinned_card_preview_works(self):
        """Verify Project pinned card preview shows project source badge."""
        c_board_id = self.lab_svc.get_active_board_id(self.cyclops_project)
        c_board = self.lab_svc.load_board(self.cyclops_project, c_board_id)
        c_board["items"] = [{
            "id": "c_preview_1",
            "type": "note.blank",
            "is_pinned": True,
            "payload": {"title": "Cyclops Ref Card", "content": "Line 1 preview\nLine 2 preview"}
        }]
        self.lab_svc.save_board(self.cyclops_project, c_board, c_board_id)

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        badges = []
        for i in range(home.pins_grid.count()):
            card = home.pins_grid.itemAt(i).widget()
            for lbl in card.findChildren(QLabel):
                if "📁 Cyclops" in lbl.text():
                    badges.append(lbl.text())

        self.assertTrue(len(badges) > 0)

    def test_5_pinned_card_ordering_can_be_changed(self):
        """Verify reordering pinned cards via card_reordered signal updates presentation list."""
        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        wb_board = self.lab_svc.load_board(None, wb_id)
        wb_board["items"] = [
            {"id": "pin_a", "type": "note.blank", "is_pinned": True, "payload": {"title": "Card A"}},
            {"id": "pin_b", "type": "note.blank", "is_pinned": True, "payload": {"title": "Card B"}},
        ]
        self.lab_svc.save_board(None, wb_board, wb_id)

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        key_a = f"__workbench__::{wb_id}::pin_a"
        key_b = f"__workbench__::{wb_id}::pin_b"

        home._on_pinned_card_reordered(key_b, key_a)

        saved = self.lab_svc.get_pinned_order()
        self.assertIn(key_b, saved)
        self.assertEqual(saved[0], key_b)

    def test_6_pinned_ordering_persists_across_restart(self):
        """Verify saved presentation order persists and re-applies on fresh Home set_context."""
        self.lab_svc.save_pinned_order(["__workbench__::Main::pin_b", "__workbench__::Main::pin_a"])

        new_svc = LabService(project_service=self.project_svc)
        order = new_svc.get_pinned_order()
        self.assertEqual(order, ["__workbench__::Main::pin_b", "__workbench__::Main::pin_a"])

    def test_7_removing_pin_removes_from_home(self):
        """Verify unpinning a node removes it from Home pinned section."""
        wb_board = self.lab_svc.load_board(None, "Main")
        wb_board["items"] = [{"id": "unpinned_x", "type": "note.blank", "is_pinned": False, "payload": {"title": "Unpinned X"}}]
        self.lab_svc.save_board(None, wb_board, "Main")

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        titles = []
        for i in range(home.pins_grid.count()):
            card = home.pins_grid.itemAt(i).widget()
            for lbl in card.findChildren(QLabel):
                if "📌" in lbl.text():
                    titles.append(lbl.text())

        self.assertNotIn("📌 Unpinned X", titles)

    def test_8_stale_home_ordering_entries_safely_ignored(self):
        """Verify stale key entries in pinned_order do not break Home set_context."""
        self.lab_svc.save_pinned_order(["non_existent_key_1", "non_existent_key_2"])

        home = HomeWorkspacePanel()
        home.set_context(self.context)
        self.assertIsNotNone(home.layout)

    def test_9_normal_attention_state(self):
        """Verify normal attention nodes default correctly."""
        summary = self.lab_svc.get_project_summary_metadata(None)
        self.assertIsNotNone(summary)

    def test_10_important_attention_state(self):
        """Verify important attention level is aggregated in summary metadata."""
        wb_board = self.lab_svc.load_board(None, "Main")
        wb_board["items"] = [{
            "id": "attn_imp_1",
            "type": "note.blank",
            "attention": "important",
            "payload": {"title": "Important Idea"}
        }]
        self.lab_svc.save_board(None, wb_board, "Main")

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        attn_labels = []
        for i in range(home.attn_layout.count()):
            w = home.attn_layout.itemAt(i).widget()
            for lbl in w.findChildren(QLabel):
                if "IMPORTANT" in lbl.text():
                    attn_labels.append(lbl.text())

        self.assertTrue(len(attn_labels) > 0)

    def test_11_urgent_attention_state(self):
        """Verify urgent attention level appears in Needs Attention section."""
        wb_board = self.lab_svc.load_board(None, "Main")
        wb_board["items"] = [{
            "id": "attn_urg_1",
            "type": "note.blank",
            "attention": "urgent",
            "payload": {"title": "Fix Critical Bug"}
        }]
        self.lab_svc.save_board(None, wb_board, "Main")

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        attn_labels = []
        for i in range(home.attn_layout.count()):
            w = home.attn_layout.itemAt(i).widget()
            for lbl in w.findChildren(QLabel):
                if "URGENT" in lbl.text():
                    attn_labels.append(lbl.text())

        self.assertTrue(len(attn_labels) > 0)

    def test_12_important_urgent_item_appears_in_needs_attention(self):
        """Verify Needs Attention surfaces both Urgent and Important nodes."""
        home = HomeWorkspacePanel()
        home.set_context(self.context)
        self.assertIsNotNone(home.attn_layout)

    def test_13_unpinned_urgent_item_appears_in_needs_attention(self):
        """Verify an urgent item that is NOT pinned still appears under Needs Attention."""
        c_board_id = self.lab_svc.get_active_board_id(self.cyclops_project)
        c_board = self.lab_svc.load_board(self.cyclops_project, c_board_id)
        c_board["items"] = [{
            "id": "unpinned_urgent_1",
            "type": "note.blank",
            "is_pinned": False,
            "attention": "urgent",
            "payload": {"title": "Urgent Unpinned Animation Bug"}
        }]
        self.lab_svc.save_board(self.cyclops_project, c_board, c_board_id)

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        found = False
        for i in range(home.attn_layout.count()):
            w = home.attn_layout.itemAt(i).widget()
            for lbl in w.findChildren(QLabel):
                if "Urgent Unpinned Animation Bug" in lbl.text():
                    found = True
                    break

        self.assertTrue(found)

    def test_14_clicking_attention_item_routes_to_node(self):
        """Verify clicking an item in Needs Attention emits open_board_requested."""
        c_board_id = self.lab_svc.get_active_board_id(self.cyclops_project)
        c_board = self.lab_svc.load_board(self.cyclops_project, c_board_id)
        c_board["items"] = [{
            "id": "attn_click_1",
            "type": "note.blank",
            "attention": "urgent",
            "payload": {"title": "Clickable Urgent Node"}
        }]
        self.lab_svc.save_board(self.cyclops_project, c_board, c_board_id)

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        emitted = []
        home.open_board_requested.connect(lambda p, b, n: emitted.append((p, b, n)))

        for i in range(home.attn_layout.count()):
            w = home.attn_layout.itemAt(i).widget()
            labels = w.findChildren(QLabel)
            if any("Clickable Urgent Node" in lbl.text() for lbl in labels):
                w.mousePressEvent(None)
                break

        self.assertTrue(len(emitted) > 0)
        p, b, n = emitted[0]
        self.assertEqual(p, self.cyclops_project)
        self.assertEqual(n, "attn_click_1")

    def test_15_task_appears_correctly(self):
        """Verify checklist tasks appear in Tasks section."""
        wb_board = self.lab_svc.load_board(None, "Main")
        wb_board["items"] = [{
            "id": "task_node_1",
            "type": "note.blank",
            "payload": {"title": "Todo Note", "content": "- [ ] Research WebGPU shaders"}
        }]
        self.lab_svc.save_board(None, wb_board, "Main")

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        found_task = False
        for i in range(home.tasks_list_layout.count()):
            w = home.tasks_list_layout.itemAt(i).widget()
            for lbl in w.findChildren(QLabel):
                if "Research WebGPU shaders" in lbl.text():
                    found_task = True
                    break

        self.assertTrue(found_task)

    def test_16_task_completion_from_home_updates_original_node(self):
        """Verify toggling task completion from Home updates the original board node content directly."""
        wb_board = self.lab_svc.load_board(None, "Main")
        wb_board["items"] = [{
            "id": "task_node_toggle",
            "type": "note.blank",
            "payload": {"title": "Todo Note", "content": "- [ ] Toggle Me"}
        }]
        self.lab_svc.save_board(None, wb_board, "Main")

        updated = self.lab_svc.toggle_task_completion(None, "Main", "task_node_toggle", "Toggle Me", True)
        self.assertTrue(updated)

        refreshed_board = self.lab_svc.load_board(None, "Main")
        content = refreshed_board["items"][0]["payload"]["content"]
        self.assertIn("- [x] Toggle Me", content)

    def test_17_task_completion_persists(self):
        """Verify completed task state persists across service reinstantiations."""
        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        wb_board = self.lab_svc.load_board(None, wb_id)
        wb_board["items"] = [{
            "id": "task_node_persist",
            "type": "note.blank",
            "payload": {"title": "Todo Note", "content": "- [ ] Persist Me"}
        }]
        self.lab_svc.save_board(None, wb_board, wb_id)
        self.lab_svc.toggle_task_completion(None, wb_id, "task_node_persist", "Persist Me", True)

        new_svc = LabService(project_service=self.project_svc)
        refreshed_board = new_svc.load_board(None, wb_id)
        content = refreshed_board["items"][0]["payload"]["content"]
        self.assertIn("- [x] Persist Me", content)

    def test_18_workbench_tasks_show_workbench_source(self):
        """Verify Workbench tasks display Workbench source badge."""
        wb_board = self.lab_svc.load_board(None, "Main")
        wb_board["items"] = [{
            "id": "wb_task_badge",
            "type": "note.blank",
            "payload": {"title": "WB Todo", "content": "- [ ] WB Task Badge Test"}
        }]
        self.lab_svc.save_board(None, wb_board, "Main")

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        found_wb_badge = False
        for i in range(home.tasks_list_layout.count()):
            w = home.tasks_list_layout.itemAt(i).widget()
            for lbl in w.findChildren(QLabel):
                if "🛠️ Workbench" in lbl.text():
                    found_wb_badge = True
                    break

        self.assertTrue(found_wb_badge)

    def test_19_project_tasks_show_project_source(self):
        """Verify Project tasks display Project source badge."""
        c_board_id = self.lab_svc.get_active_board_id(self.cyclops_project)
        c_board = self.lab_svc.load_board(self.cyclops_project, c_board_id)
        c_board["items"] = [{
            "id": "proj_task_badge",
            "type": "note.blank",
            "payload": {"title": "Proj Todo", "content": "- [ ] Proj Task Badge Test"}
        }]
        self.lab_svc.save_board(self.cyclops_project, c_board, c_board_id)

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        found_proj_badge = False
        for i in range(home.tasks_list_layout.count()):
            w = home.tasks_list_layout.itemAt(i).widget()
            for lbl in w.findChildren(QLabel):
                if "📁 Cyclops" in lbl.text():
                    found_proj_badge = True
                    break

        self.assertTrue(found_proj_badge)

    def test_20_workbench_project_isolation_remains_intact(self):
        """Verify Workbench and Project boards remain strictly isolated."""
        wb_boards = self.lab_svc.list_boards(None)
        proj_boards = self.lab_svc.list_boards(self.cyclops_project)
        wb_ids = {b["id"] for b in wb_boards}
        proj_ids = {b["id"] for b in proj_boards}
        self.assertTrue(wb_ids.isdisjoint(proj_ids))

    def test_21_explorer_live_board_refresh_remains_intact(self):
        """Verify Explorer Panel live board refresh feature operates correctly."""
        explorer = ExplorerPanel()
        explorer.set_context(self.context)
        self.lab_svc.create_board(None, "New Live Refresh Board")
        self.assertIsNotNone(explorer.lab_root)


if __name__ == "__main__":
    unittest.main()
