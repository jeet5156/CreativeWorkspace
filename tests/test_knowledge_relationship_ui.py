"""Focused integration and UI tests for Knowledge Phase Chunk 3B: Relationship UI."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from models.knowledge import KnowledgeDocument
from models.library_models import LibraryAsset, AssetAvailability
from models.project import Project
from services.knowledge_service import KnowledgeService
from ui.panels.knowledge_workspace_panel import KnowledgeWorkspacePanel
from ui.widgets.relationship_chip import RelationshipChip
from ui.dialogs.add_knowledge_relationship_dialog import AddKnowledgeRelationshipDialog


app = QApplication.instance() or QApplication([])


class TestKnowledgeRelationshipUI(unittest.TestCase):
    """Test suite covering Knowledge Relationship UI widgets, chips, dialogs, status badges, and navigation."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.storage_dir = Path(self.test_dir) / "knowledge"
        self.storage_dir.mkdir(parents=True)

        self.knowledge_service = KnowledgeService(storage_dir=self.storage_dir)

        # Mock Services and AppContext
        self.mock_project_service = MagicMock()
        self.mock_library_service = MagicMock()
        self.mock_asset_service = MagicMock()
        self.mock_lab_service = MagicMock()
        self.mock_workspace_manager = MagicMock()
        self.mock_inspector = MagicMock()

        self.mock_context = MagicMock()
        self.mock_context.knowledge_service = self.knowledge_service
        self.mock_context.project_service = self.mock_project_service
        self.mock_context.library_service = self.mock_library_service
        self.mock_context.asset_service = self.mock_asset_service
        self.mock_context.lab_service = self.mock_lab_service
        self.mock_context.workspace_manager = self.mock_workspace_manager
        self.mock_context.inspector_panel = self.mock_inspector

        # Create panel
        self.panel = KnowledgeWorkspacePanel(context=self.mock_context)
        self.panel.show()

    def tearDown(self):
        self.panel.close()
        self.panel.deleteLater()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Displaying Relationships in Editor
    # -------------------------------------------------------------------------

    def test_relationship_chips_display_all_types(self):
        """Verify that selecting a note with various relationships renders interactive chips for each."""
        # Setup mock project
        test_proj_dir = Path(self.test_dir) / "TestProject"
        test_proj_dir.mkdir()
        proj = Project(name="TestProject", project_type="general", location=str(test_proj_dir))
        self.mock_project_service.all_projects.return_value = [proj]

        # Setup mock library asset
        lib_asset = LibraryAsset(
            id="lib_hero_model",
            filename="Hero_Mesh.fbx",
            category="3D Models",
            friendly_type="FBX 3D Model",
            drive_id="drive_main",
            drive_relative_path="Characters/Hero_Mesh.fbx",
        )
        self.mock_library_service.get_asset.return_value = lib_asset
        self.mock_library_service.get_asset_availability.return_value = AssetAvailability.AVAILABLE

        # Setup mock project asset
        self.mock_asset_service.get_asset.return_value = {
            "id": "asset_sword_01",
            "filename": "Sword.fbx",
            "relative_path": "Assets/Weapons/Sword.fbx",
            "absolute_path": str(test_proj_dir / "Assets" / "Weapons" / "Sword.fbx"),
        }

        # Create document with all 4 relationship types
        doc = self.knowledge_service.create_document(
            title="Hero Combat Spec",
            project_ids=["TestProject"],
            library_asset_ids=["lib_hero_model"],
            project_asset_refs=[{"project_id": "TestProject", "asset_id": "asset_sword_01", "relative_path": "Assets/Weapons/Sword.fbx"}],
            lab_node_ids=["node_combo_system"],
        )

        # Select document in panel
        self.panel._select_document(doc.id)

        # Assert count badge
        self.assertEqual(self.panel.rel_count_badge.text(), "4")
        self.assertFalse(self.panel.rel_placeholder_label.isVisible())

        # Assert chips in layout
        chips = [
            self.panel.rel_chips_layout.itemAt(i).widget()
            for i in range(self.panel.rel_chips_layout.count())
            if isinstance(self.panel.rel_chips_layout.itemAt(i).widget(), RelationshipChip)
        ]
        self.assertEqual(len(chips), 4)

        types = [c.rel_type for c in chips]
        self.assertIn("project", types)
        self.assertIn("library_asset", types)
        self.assertIn("project_asset", types)
        self.assertIn("lab_node", types)

    # -------------------------------------------------------------------------
    # 2. Removing Relationships via UI
    # -------------------------------------------------------------------------

    def test_relationship_removal_via_chip(self):
        """Verify clicking the remove button on a chip removes the relationship from model and UI."""
        doc = self.knowledge_service.create_document(
            title="Note to Disconnect",
            project_ids=["ProjectAlpha", "ProjectBeta"],
        )

        self.panel._select_document(doc.id)
        self.assertEqual(self.panel.rel_count_badge.text(), "2")

        # Simulate removing ProjectAlpha
        self.panel._on_relationship_chip_removed("project", {"project_id": "ProjectAlpha"})

        # Check UI update
        self.assertEqual(self.panel.rel_count_badge.text(), "1")
        # Check service persistence
        reloaded = self.knowledge_service.get_document(doc.id)
        self.assertEqual(reloaded.project_ids, ["ProjectBeta"])

        # Remove the last project
        self.panel._on_relationship_chip_removed("project", {"project_id": "ProjectBeta"})
        self.assertEqual(self.panel.rel_count_badge.text(), "0")
        self.assertTrue(self.panel.rel_placeholder_label.isVisible())
        self.assertEqual(self.knowledge_service.get_document(doc.id).project_ids, [])

    # -------------------------------------------------------------------------
    # 3. Adding Relationships via Dialog
    # -------------------------------------------------------------------------

    def test_relationship_adding_via_dialog_mock(self):
        """Verify adding relationship via AddKnowledgeRelationshipDialog updates service and UI."""
        doc = self.knowledge_service.create_document(title="Blank Note")
        self.panel._select_document(doc.id)
        self.assertEqual(self.panel.rel_count_badge.text(), "0")

        # Mock dialog accept returning a library asset
        with patch.object(AddKnowledgeRelationshipDialog, "exec", return_value=QDialog.Accepted):
            with patch.object(
                AddKnowledgeRelationshipDialog,
                "get_selected_relationship",
                return_value=("library_asset", {"asset_id": "lib_shield_01"}),
            ):
                self.panel._on_add_relationship_clicked()

        self.assertEqual(self.panel.rel_count_badge.text(), "1")
        reloaded = self.knowledge_service.get_document(doc.id)
        self.assertEqual(reloaded.library_asset_ids, ["lib_shield_01"])

    # -------------------------------------------------------------------------
    # 4. Missing / Offline References Status Badges
    # -------------------------------------------------------------------------

    def test_status_badges_for_available_offline_and_missing(self):
        """Verify chips correctly render Available, Offline, and Missing status badges."""
        # 1. Available Library Asset
        lib_avail = LibraryAsset(id="lib_avail", filename="Avail.png", drive_id="d1")
        self.mock_library_service.get_asset.side_effect = lambda a_id: lib_avail if a_id == "lib_avail" else None
        self.mock_library_service.get_asset_availability.return_value = AssetAvailability.AVAILABLE

        chip_avail = RelationshipChip("library_asset", {"asset_id": "lib_avail"}, context=self.mock_context)
        _, title1, status1, color1 = chip_avail._resolve_entity_info()
        self.assertEqual(status1, "Available")
        self.assertEqual(color1, "#10B981")

        # 2. Offline Library Asset (drive unmounted)
        self.mock_library_service.get_asset_availability.return_value = AssetAvailability.OFFLINE
        chip_offline = RelationshipChip("library_asset", {"asset_id": "lib_avail"}, context=self.mock_context)
        _, title2, status2, color2 = chip_offline._resolve_entity_info()
        self.assertEqual(status2, "Offline")
        self.assertEqual(color2, "#F59E0B")

        # 3. Missing Library Asset (deleted completely)
        self.mock_library_service.get_asset.return_value = None
        chip_missing = RelationshipChip("library_asset", {"asset_id": "lib_gone"}, context=self.mock_context)
        _, title3, status3, color3 = chip_missing._resolve_entity_info()
        self.assertEqual(status3, "Missing")
        self.assertEqual(color3, "#EF4444")

    # -------------------------------------------------------------------------
    # 5. Clickable Navigation to Referenced Objects
    # -------------------------------------------------------------------------

    def test_navigation_to_referenced_objects(self):
        """Verify clicking chips calls workspace_manager unified navigate method."""
        proj = Project(name="ProjectOmega", project_type="general", location=str(Path(self.test_dir) / "ProjectOmega"))
        self.mock_project_service.all_projects.return_value = [proj]

        # 1. Project Navigation
        self.panel._on_relationship_chip_clicked("project", {"project_id": "ProjectOmega"})
        self.mock_workspace_manager.navigate.assert_called()
        last_payload = self.mock_workspace_manager.navigate.call_args[0][0]
        self.assertEqual(last_payload.project_id, "ProjectOmega")
        self.assertEqual(last_payload.target_type, "project")

        # 2. Library Asset Navigation
        self.panel._on_relationship_chip_clicked("library_asset", {"asset_id": "lib_tree"})
        self.mock_workspace_manager.navigate.assert_called()
        last_payload = self.mock_workspace_manager.navigate.call_args[0][0]
        self.assertEqual(last_payload.target_id, "lib_tree")
        self.assertEqual(last_payload.target_type, "library_asset")

        # 3. Project Asset Navigation
        self.panel._on_relationship_chip_clicked("project_asset", {
            "project_id": "ProjectOmega",
            "asset_id": "asset_123",
            "relative_path": "References/Concept.png",
        })
        self.mock_workspace_manager.navigate.assert_called()
        last_payload = self.mock_workspace_manager.navigate.call_args[0][0]
        self.assertEqual(last_payload.project_id, "ProjectOmega")
        self.assertEqual(last_payload.target_type, "project_asset")
        self.assertEqual(last_payload.rel_path, "References")

    # -------------------------------------------------------------------------
    # 6. Duplicate Relationship Prevention
    # -------------------------------------------------------------------------

    def test_duplicate_relationship_addition_prevention(self):
        """Verify adding duplicate relationships through UI does not create duplicates in UI or service."""
        doc = self.knowledge_service.create_document(title="Duplication Test")
        self.panel._select_document(doc.id)

        # Add project once
        self.knowledge_service.add_project_relationship(doc.id, "Proj_Unique")
        self.panel._refresh_relationships_display(self.knowledge_service.get_document(doc.id))
        self.assertEqual(self.panel.rel_count_badge.text(), "1")

        # Add same project again
        self.knowledge_service.add_project_relationship(doc.id, "Proj_Unique")
        self.panel._refresh_relationships_display(self.knowledge_service.get_document(doc.id))
        self.assertEqual(self.panel.rel_count_badge.text(), "1")

    # -------------------------------------------------------------------------
    # 7. AddKnowledgeRelationshipDialog Runtime Regression Test
    # -------------------------------------------------------------------------

    def test_add_relationship_dialog_runtime_lifecycle(self):
        """Regression test: AddKnowledgeRelationshipDialog initializes all tabs cleanly without AttributeError and links assets."""
        # 1. Create/load a Knowledge document
        doc = self.knowledge_service.create_document(title="Asset Integration Note")
        self.panel._select_document(doc.id)

        # Setup mock services with realistic responses
        proj = Project(name="GameProject", project_type="unreal", location=str(Path(self.test_dir) / "GameProject"))
        self.mock_project_service.all_projects.return_value = [proj]

        lib_asset1 = LibraryAsset(id="lib_env_rock", filename="Rock_Cliff.fbx", category="3D Models", friendly_type="FBX 3D Model", drive_id="d1", drive_relative_path="Environment/Rock_Cliff.fbx")
        lib_asset2 = LibraryAsset(id="lib_env_tree", filename="Oak_Tree.fbx", category="3D Models", friendly_type="FBX 3D Model", drive_id="d1", drive_relative_path="Environment/Oak_Tree.fbx")

        # Mock query_assets and get_asset_availability
        self.mock_library_service.query_assets.side_effect = lambda query=None: [
            a for a in [lib_asset1, lib_asset2]
            if not query or query.lower() in a.filename.lower()
        ]
        self.mock_library_service.get_asset_availability.return_value = AssetAvailability.AVAILABLE

        self.mock_asset_service.get_assets.return_value = [
            {"id": "asset_local_01", "filename": "Texture.png", "relative_path": "Assets/Texture.png", "category": "Assets"}
        ]

        self.mock_lab_service.list_boards.return_value = [{"id": "board_1", "name": "Main Board"}]
        self.mock_lab_service.load_board.return_value = {
            "items": [{"id": "node_99", "type": "note", "payload": {"title": "Combat Mechanics"}}]
        }

        # 2. Open AddKnowledgeRelationshipDialog
        dlg = AddKnowledgeRelationshipDialog(self.mock_context, self.panel, current_doc=doc)

        # 3. Successfully initializes all relationship tabs without crashing
        self.assertEqual(dlg.tabs.count(), 4)
        self.assertEqual(dlg.projects_list.count(), 1)
        self.assertEqual(dlg.library_list.count(), 2)
        self.assertEqual(dlg.proj_asset_list.count(), 1)
        self.assertEqual(dlg.lab_nodes_list.count(), 1)

        # 4. Filter Library assets
        dlg.tabs.setCurrentIndex(1)
        dlg.lib_search.setText("Cliff")
        self.assertEqual(dlg.library_list.count(), 1)
        self.assertEqual(dlg.library_list.item(0).data(Qt.UserRole), "lib_env_rock")

        # 5. Select asset and accept dialog
        dlg.library_list.setCurrentRow(0)
        dlg._on_link_clicked()
        self.assertEqual(dlg.result(), QDialog.Accepted)

        result = dlg.get_selected_relationship()
        self.assertIsNotNone(result)
        rel_type, target_data = result
        self.assertEqual(rel_type, "library_asset")
        self.assertEqual(target_data.get("asset_id"), "lib_env_rock")

        # 6. Apply to KnowledgeService
        self.knowledge_service.add_library_asset_relationship(doc.id, target_data.get("asset_id"))

        # 7. Confirm relationship is persisted
        reloaded = self.knowledge_service.get_document(doc.id)
        self.assertIn("lib_env_rock", reloaded.library_asset_ids)

        dlg.close()
        dlg.deleteLater()


if __name__ == "__main__":
    unittest.main()
