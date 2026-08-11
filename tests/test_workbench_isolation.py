import os
import shutil
import tempfile
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication, QTreeWidgetItem

app = QApplication.instance() or QApplication([])

from models.project import Project
from services.project_service import ProjectService
from services.lab_service import LabService
from ui.panels.explorer_panel import ExplorerPanel, ROLE_PROJECT, ROLE_SECTION, ROLE_NODE_TYPE
from ui.panels.home_workspace_panel import HomeWorkspacePanel
from ui.panels.lab_panel import LabPanel


class TestWorkbenchIsolation(unittest.TestCase):
    """Rigorous contract regression tests for Workbench vs Project board isolation and pinned aggregation."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.patch_global_dir = Path(self.temp_dir) / "global_workbench" / "boards"
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
        cyclops_dir = str(Path(self.temp_dir) / "Cyclops")
        os.makedirs(cyclops_dir, exist_ok=True)
        self.cyclops_project = Project(
            name="Cyclops",
            project_type="game",
            location=cyclops_dir,
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

    def test_1_explicit_list_boards_contract(self):
        """Verify list_boards(None) returns ONLY Workbench boards and list_boards(project) returns ONLY project boards."""
        wb_boards = self.lab_svc.list_boards(None)
        cyclops_boards = self.lab_svc.list_boards(self.cyclops_project)

        wb_ids = {b["id"] for b in wb_boards}
        cyclops_ids = {b["id"] for b in cyclops_boards}

        # Board IDs must be completely disjoint
        self.assertTrue(wb_ids.isdisjoint(cyclops_ids))
        self.assertEqual(len(wb_boards), 1)
        self.assertEqual(wb_boards[0]["name"], "Main")
        self.assertEqual(len(cyclops_boards), 1)
        self.assertEqual(cyclops_boards[0]["name"], "Main")

    def test_2_physical_storage_path_isolation(self):
        """Verify physical directory paths are distinct for Workbench vs Project."""
        wb_path = self.lab_svc.get_boards_dir(None)
        cyclops_path = self.lab_svc.get_boards_dir(self.cyclops_project)

        self.assertNotEqual(wb_path, cyclops_path)
        self.assertIn("global_workbench", str(wb_path))
        self.assertIn("Cyclops", str(cyclops_path))

    def test_3_creating_workbench_board_does_not_affect_project(self):
        """Verify adding a new Workbench board does not bleed into Cyclops project boards."""
        self.lab_svc.create_board(None, "Research Shader Nodes")

        wb_boards = [b["name"] for b in self.lab_svc.list_boards(None)]
        cyclops_boards = [b["name"] for b in self.lab_svc.list_boards(self.cyclops_project)]

        self.assertIn("Research Shader Nodes", wb_boards)
        self.assertNotIn("Research Shader Nodes", cyclops_boards)

    def test_4_creating_project_board_does_not_affect_workbench(self):
        """Verify adding a new Cyclops board does not bleed into Workbench."""
        self.lab_svc.create_board(self.cyclops_project, "Character Concepts")

        wb_boards = [b["name"] for b in self.lab_svc.list_boards(None)]
        cyclops_boards = [b["name"] for b in self.lab_svc.list_boards(self.cyclops_project)]

        self.assertIn("Character Concepts", cyclops_boards)
        self.assertNotIn("Character Concepts", wb_boards)

    def test_5_explorer_tree_expansion_workbench_isolation(self):
        """Verify ExplorerPanel tree expansion for top-level Workbench loads only Workbench boards."""
        explorer = ExplorerPanel()
        explorer.set_context(self.context)

        # Trigger expansion on lab_root
        explorer._on_item_expanded(explorer.lab_root)

        wb_children_names = [explorer.lab_root.child(i).text(0) for i in range(explorer.lab_root.childCount())]
        self.assertTrue(all("🎨" in name for name in wb_children_names))

        # Check child projects are None
        for i in range(explorer.lab_root.childCount()):
            child = explorer.lab_root.child(i)
            self.assertIsNone(child.data(0, ROLE_PROJECT))

    def test_6_explorer_tree_expansion_project_isolation(self):
        """Verify ExplorerPanel tree expansion for Cyclops Lab Boards loads ONLY Cyclops boards and NEVER global Workbench."""
        explorer = ExplorerPanel()
        explorer.set_context(self.context)
        explorer.add_project(self.cyclops_project)

        # Create a unique board in Cyclops
        self.lab_svc.create_board(self.cyclops_project, "Cyclops Unique Board")

        # Find Cyclops project item and its Lab Boards child
        cyclops_item = explorer._project_items[str(self.cyclops_project.location)]
        lab_boards_child = None
        for i in range(cyclops_item.childCount()):
            c = cyclops_item.child(i)
            if c.data(0, ROLE_SECTION) == "lab":
                lab_boards_child = c
                break

        self.assertIsNotNone(lab_boards_child)

        # Trigger expansion on Cyclops Lab Boards category
        explorer._on_item_expanded(lab_boards_child)

        child_names = [lab_boards_child.child(i).text(0) for i in range(lab_boards_child.childCount())]
        self.assertIn("🎨 Cyclops Unique Board", child_names)

        # Check all child items have ROLE_PROJECT == self.cyclops_project
        for i in range(lab_boards_child.childCount()):
            child = lab_boards_child.child(i)
            self.assertEqual(child.data(0, ROLE_PROJECT), self.cyclops_project)

    def test_7_home_pinned_nodes_global_aggregation(self):
        """Verify HomeWorkspacePanel aggregates pinned nodes across ALL Workbench boards and project boards."""
        # Add pinned note to Workbench
        wb_item = self.lab_svc.add_quick_capture_note("Three.js Shader Idea")

        # Add pinned note to Cyclops project
        cyclops_board_id = self.lab_svc.get_active_board_id(self.cyclops_project)
        c_board = self.lab_svc.load_board(self.cyclops_project, cyclops_board_id)
        c_board["items"] = [{
            "id": "cyclops_pin_node_1",
            "type": "note.blank",
            "is_pinned": True,
            "transform": {"x": 20, "y": 20, "width": 100, "height": 100},
            "payload": {"title": "Cyclops Ref Card"}
        }]
        self.lab_svc.save_board(self.cyclops_project, c_board, cyclops_board_id)

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        # Check pins grid count
        self.assertTrue(home.pins_grid.count() >= 2)

    def test_8_home_card_badge_formatting(self):
        """Verify Home pinned card badges display '🛠️ Workbench · <Board>' vs '📁 <Project> · <Board'."""
        self.lab_svc.add_quick_capture_note("Workbench Pin Badge Test")

        cyclops_board_id = self.lab_svc.get_active_board_id(self.cyclops_project)
        c_board = self.lab_svc.load_board(self.cyclops_project, cyclops_board_id)
        c_board["items"] = [{
            "id": "cyclops_badge_pin",
            "type": "note.blank",
            "is_pinned": True,
            "transform": {"x": 10, "y": 10, "width": 100, "height": 100},
            "payload": {"title": "Cyclops Badge Item"}
        }]
        self.lab_svc.save_board(self.cyclops_project, c_board, cyclops_board_id)

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        badges = []
        from PySide6.QtWidgets import QLabel
        for i in range(home.pins_grid.count()):
            card = home.pins_grid.itemAt(i).widget()
            for lbl in card.findChildren(QLabel):
                if "·" in lbl.text():
                    badges.append(lbl.text())

        self.assertTrue(any("🛠️ Workbench" in b for b in badges))
        self.assertTrue(any("📁 Cyclops" in b for b in badges))

    def test_9_clicking_workbench_pinned_card_routes_and_focuses(self):
        """Verify clicking a Workbench pinned item emits open_board_requested with (None, board_id, node_id)."""
        wb_item = self.lab_svc.add_quick_capture_note("Clickable Workbench Pin")
        home = HomeWorkspacePanel()
        home.set_context(self.context)

        emitted_args = []
        home.open_board_requested.connect(lambda p, b, n: emitted_args.append((p, b, n)))

        # Find card for Workbench note and simulate mouse click
        from PySide6.QtWidgets import QLabel
        for i in range(home.pins_grid.count()):
            card = home.pins_grid.itemAt(i).widget()
            labels = card.findChildren(QLabel)
            if any("Clickable Workbench Pin" in lbl.text() for lbl in labels):
                card.mousePressEvent(None)
                break

        self.assertTrue(len(emitted_args) > 0)
        proj, board_id, node_id = emitted_args[0]
        self.assertIsNone(proj)
        self.assertIsNotNone(board_id)
        self.assertEqual(node_id, wb_item["id"])

    def test_10_restart_persistence_for_workbench_pinned_nodes(self):
        """Verify Workbench pinned nodes persist across service reinstantiations."""
        wb_item = self.lab_svc.add_quick_capture_note("Persisted Workbench Pin")

        # Instantiate fresh service pointing to same directory
        new_svc = LabService(project_service=self.project_svc)
        summary = new_svc.get_project_summary_metadata(None)
        pinned_ids = [n["id"] for n in summary["pinned_nodes"]]
        self.assertIn(wb_item["id"], pinned_ids)


if __name__ == "__main__":
    unittest.main()
