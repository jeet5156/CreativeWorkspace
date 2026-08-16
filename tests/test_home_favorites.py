"""Tests for Home Favorites & Pinned (Issue 2).

Covers:
- Favorite Knowledge note appears on Home
- Multiple favorite Knowledge notes appear
- Pinned Lab node appears
- Favorite/pinned Lab board appears
- Favorite Library asset still appears
- Pinned Projects still appear
- More than six eligible items render without truncation
- Lab note node derives readable title from content
- Clicking each item emits/navigates to the correct target
- Changing Knowledge favorite updates Home reactively
- Changing Lab pin/favorite updates Home reactively
- Repeated set_context() does not create duplicate signal connections
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtWidgets import QApplication, QLabel

app = QApplication.instance() or QApplication([])

from models.project import Project
from models.knowledge import KnowledgeDocument
from services.project_service import ProjectService
from services.lab_service import LabService
from services.knowledge_service import KnowledgeService
from services.library_service import LibraryService
from ui.panels.home_workspace_panel import HomeWorkspacePanel, PinnedCard
from core.navigation import NavigationPayload, NavigationTargetType


class MockWorkspaceManager:
    def __init__(self):
        self.navigated_payloads = []

    def navigate(self, payload):
        self.navigated_payloads.append(payload)
        return True


class TestHomeFavorites(unittest.TestCase):
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

        # Setup ProjectService
        self.project_svc = ProjectService()
        self.proj1_dir = str(Path(self.temp_dir) / "ProjectA")
        os.makedirs(self.proj1_dir, exist_ok=True)
        self.proj1 = Project(
            name="ProjectA",
            project_type="game",
            location=self.proj1_dir,
            is_pinned=True,
        )
        self.proj2_dir = str(Path(self.temp_dir) / "ProjectB")
        os.makedirs(self.proj2_dir, exist_ok=True)
        self.proj2 = Project(
            name="ProjectB",
            project_type="general",
            location=self.proj2_dir,
            is_pinned=False,
        )
        self.project_svc.projects = [self.proj1, self.proj2]

        # Setup LabService
        self.lab_svc = LabService(project_service=self.project_svc)

        # Setup KnowledgeService
        self.knowledge_storage = Path(self.temp_dir) / "knowledge"
        self.knowledge_storage.mkdir(parents=True, exist_ok=True)
        self.knowledge_svc = KnowledgeService(storage_dir=self.knowledge_storage)

        # Setup LibraryService
        self.library_dir = Path(self.temp_dir) / "library"
        self.library_dir.mkdir(parents=True, exist_ok=True)
        self.library_svc = LibraryService(storage_dir=self.library_dir)

        # Workspace Manager
        self.mock_wm = MockWorkspaceManager()

        class MockContext:
            def __init__(ctx_self, lab, proj, know, lib, wm):
                ctx_self.lab_service = lab
                ctx_self.project_service = proj
                ctx_self.knowledge_service = know
                ctx_self.library_service = lib
                ctx_self.workspace_manager = wm

        self.context = MockContext(
            self.lab_svc,
            self.project_svc,
            self.knowledge_svc,
            self.library_svc,
            self.mock_wm,
        )

    def tearDown(self):
        LabService.get_boards_dir = self.orig_get_boards_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_1_favorite_knowledge_notes_appear_on_home(self):
        """Verify that single and multiple favorite Knowledge notes appear on Home."""
        doc1 = self.knowledge_svc.create_document(title="Game Lore", content="Important story lore.", favorite=True)
        doc2 = self.knowledge_svc.create_document(title="Character Concept", content="Hero description.", favorite=True)
        doc3 = self.knowledge_svc.create_document(title="Unpinned Draft", content="Draft note.", favorite=False)

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        types = [item.get("type") for item in home._cached_pinned_items]
        ids = [item.get("id") for item in home._cached_pinned_items]

        self.assertIn("knowledge", types)
        self.assertIn(doc1.id, ids)
        self.assertIn(doc2.id, ids)
        self.assertNotIn(doc3.id, ids)

    def test_2_pinned_lab_nodes_and_boards_appear(self):
        """Verify that pinned Lab nodes and favorite/pinned Lab boards appear on Home."""
        # 1. Pinned Lab Board
        board = self.lab_svc.create_board(self.proj1, name="Concept Board")
        manifest = self.lab_svc.get_manifest(self.proj1)
        for b in manifest["boards"]:
            if b["id"] == board["id"]:
                b["favorite"] = True
        self.lab_svc.save_manifest(self.proj1, manifest)

        # 2. Pinned Lab Node
        node = self.lab_svc.save_item(
            self.proj1,
            {
                "id": "node_pin_123",
                "type": "note.problem",
                "is_pinned": True,
                "payload": {"content": "This is a critical blocker issue."},
            },
            board_id=board["id"],
        )

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        types = [item.get("type") for item in home._cached_pinned_items]
        self.assertIn("lab_board", types)
        self.assertIn("note.problem", types)

        board_item = next(it for it in home._cached_pinned_items if it.get("type") == "lab_board")
        self.assertEqual(board_item["payload"]["title"], "Concept Board")

    def test_3_favorite_library_asset_and_pinned_project_appear(self):
        """Verify favorite Library assets and pinned Projects appear on Home."""
        from models.library_models import LibraryAsset
        asset = LibraryAsset(
            id="lib_ast_123",
            filename="texture.png",
            favorite=True,
        )
        self.library_svc._assets[asset.id] = asset

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        types = [item.get("type") for item in home._cached_pinned_items]
        self.assertIn("library_asset", types)
        self.assertIn("project", types)

    def test_4_more_than_six_eligible_items_render_without_truncation(self):
        """Verify that when more than 6 items are eligible, all of them render in the grid."""
        # Create 3 favorite knowledge documents
        for i in range(3):
            self.knowledge_svc.create_document(title=f"Doc {i}", content=f"Content {i}", favorite=True)

        # Create 3 pinned lab nodes
        for i in range(3):
            self.lab_svc.save_item(
                self.proj1,
                {
                    "id": f"lab_node_{i}",
                    "type": "note.goal",
                    "is_pinned": True,
                    "payload": {"content": f"Sprint Goal {i}"},
                },
            )

        # Plus self.proj1 (pinned project) = total 7 items
        home = HomeWorkspacePanel()
        home.set_context(self.context)

        self.assertGreaterEqual(len(home._cached_pinned_items), 7)
        # Verify grid widget count equals the number of eligible items
        card_count = 0
        for i in range(home.pins_grid.count()):
            widget = home.pins_grid.itemAt(i).widget()
            if isinstance(widget, PinnedCard):
                card_count += 1

        self.assertEqual(card_count, len(home._cached_pinned_items))
        self.assertGreaterEqual(card_count, 7)

    def test_5_lab_node_title_derived_from_content(self):
        """Verify PinnedCard derives readable title from content when payload['title'] is absent."""
        # Case A: Content with checklist task prefix
        item_task = {
            "id": "node_chk_1",
            "type": "note.blank",
            "is_pinned": True,
            "payload": {"content": "- [ ] Refactor navigation pipeline\nExtra notes here."},
        }
        card_task = PinnedCard(item_task)
        labels = [l.text() for l in card_task.findChildren(QLabel)]
        self.assertTrue(any("Refactor navigation pipeline" in text for text in labels))

        # Case B: Content without title or prefix
        item_problem = {
            "id": "node_prob_1",
            "type": "note.problem",
            "is_pinned": True,
            "payload": {"content": "Render thread deadlock on exit"},
        }
        card_problem = PinnedCard(item_problem)
        labels_prob = [l.text() for l in card_problem.findChildren(QLabel)]
        self.assertTrue(any("Render thread deadlock on exit" in text for text in labels_prob))
        self.assertFalse(any("note.problem" in text for text in labels_prob))
        self.assertFalse(any("None" in text for text in labels_prob))

    def test_6_navigation_target_emissions(self):
        """Verify clicking each PinnedCard navigates to the exact target entity."""
        home = HomeWorkspacePanel()
        home.set_context(self.context)

        # Knowledge doc navigation
        home._on_pinned_card_clicked({"type": "knowledge", "id": "doc_xyz"})
        self.assertEqual(self.mock_wm.navigated_payloads[-1].target_type, NavigationTargetType.KNOWLEDGE_DOC.value)
        self.assertEqual(self.mock_wm.navigated_payloads[-1].target_id, "doc_xyz")

        # Lab board navigation
        home._on_pinned_card_clicked({"type": "lab_board", "_board_id": "board_123", "project": self.proj1})
        self.assertEqual(self.mock_wm.navigated_payloads[-1].target_type, NavigationTargetType.LAB_BOARD.value)
        self.assertEqual(self.mock_wm.navigated_payloads[-1].target_id, "board_123")

        # Lab node navigation
        home._on_pinned_card_clicked({"type": "note.blank", "id": "node_456", "_board_id": "board_123", "project": self.proj1})
        self.assertEqual(self.mock_wm.navigated_payloads[-1].target_type, NavigationTargetType.LAB_NODE.value)
        self.assertEqual(self.mock_wm.navigated_payloads[-1].sub_target_id, "node_456")

        # Library asset navigation
        home._on_pinned_card_clicked({"type": "library_asset", "id": "asset_789"})
        self.assertEqual(self.mock_wm.navigated_payloads[-1].target_type, NavigationTargetType.LIBRARY_ASSET.value)
        self.assertEqual(self.mock_wm.navigated_payloads[-1].target_id, "asset_789")

        # Project navigation
        home._on_pinned_card_clicked({"type": "project", "project": self.proj1})
        self.assertEqual(self.mock_wm.navigated_payloads[-1].target_type, NavigationTargetType.PROJECT.value)

    def test_7_live_reactivity_knowledge_signals(self):
        """Verify changing Knowledge favorite updates Home reactively via signals."""
        doc = self.knowledge_svc.create_document(title="Dynamic Doc", content="Testing reactive signal.", favorite=False)

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        ids_initial = [it.get("id") for it in home._cached_pinned_items]
        self.assertNotIn(doc.id, ids_initial)

        # Toggle favorite -> triggers document_updated signal
        self.knowledge_svc.set_favorite(doc.id, True)

        ids_updated = [it.get("id") for it in home._cached_pinned_items]
        self.assertIn(doc.id, ids_updated)

    def test_8_live_reactivity_lab_signals(self):
        """Verify changing Lab board favorite updates Home reactively via signals."""
        board = self.lab_svc.create_board(self.proj1, name="Dynamic Board")

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        board_ids_initial = [it.get("_board_id") for it in home._cached_pinned_items if it.get("type") == "lab_board"]
        self.assertNotIn(board["id"], board_ids_initial)

        # Favorite the board and save manifest -> emits manifest_updated
        manifest = self.lab_svc.get_manifest(self.proj1)
        for b in manifest["boards"]:
            if b["id"] == board["id"]:
                b["favorite"] = True
        self.lab_svc.save_manifest(self.proj1, manifest)

        board_ids_updated = [it.get("_board_id") for it in home._cached_pinned_items if it.get("type") == "lab_board"]
        self.assertIn(board["id"], board_ids_updated)

    def test_9_repeated_set_context_idempotent(self):
        """Verify calling set_context multiple times does not duplicate signal connections or state."""
        home = HomeWorkspacePanel()
        home.set_context(self.context)
        home.set_context(self.context)
        home.set_context(self.context)

        # Create document favorite
        doc = self.knowledge_svc.create_document(title="Idempotent Test", content="Test", favorite=True)
        # Should only be processed cleanly once
        matching = [it for it in home._cached_pinned_items if it.get("id") == doc.id]
        self.assertEqual(len(matching), 1)


if __name__ == "__main__":
    unittest.main()
