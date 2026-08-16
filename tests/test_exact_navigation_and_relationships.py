"""Comprehensive Test Suite for Exact Entity Navigation, Unified Navigation Payload,
Relationship Resolution, Reference Segregation, Home Favorites, and Dashboard Polish.
"""

import sys
import unittest
from pathlib import Path
import tempfile
import shutil

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from core.navigation import NavigationPayload, NavigationTargetType
from core.app_context import AppContext
from models.project import Project
from models.knowledge import KnowledgeDocument
from models.library_models import LibraryAsset, AssetAvailability
from services.project_service import ProjectService
from services.asset_service import AssetService
from services.library_service import LibraryService
from services.knowledge_service import KnowledgeService
from services.lab_service import LabService
from services.project_context_service import ProjectContextService
from services.project_assistant_service import ProjectAssistantService

from ui.workspace_manager import WorkspaceManager
from ui.panels.workspace_panel import WorkspacePanel
from ui.panels.knowledge_workspace_panel import KnowledgeWorkspacePanel
from ui.panels.library_workspace_panel import LibraryWorkspacePanel
from ui.panels.lab_panel import LabPanel
from ui.panels.dashboard_panel import DashboardPanel
from ui.panels.home_workspace_panel import HomeWorkspacePanel, PinnedCard
from ui.widgets.relationship_chip import RelationshipChip
from ui.widgets.project_ai_assistant_widget import ProjectAIAssistantWidget
from ui.panels.inspector_panel import InspectorPanel


app = QApplication.instance() or QApplication(sys.argv)


class TestNavigationPayload(unittest.TestCase):
    """Test NavigationPayload data model and factory helpers."""

    def test_for_project(self):
        payload = NavigationPayload.for_project("Cyclops")
        self.assertEqual(payload.target_type, NavigationTargetType.PROJECT.value)
        self.assertEqual(payload.project_id, "Cyclops")
        self.assertEqual(payload.section, "dashboard")

    def test_for_project_asset(self):
        payload = NavigationPayload.for_project_asset(
            "Cyclops",
            "ChatGPT Image Jul 31, 2026, 02_42_41 PM.png",
            rel_path="References/ChatGPT Image Jul 31, 2026, 02_42_41 PM.png"
        )
        self.assertEqual(payload.target_type, NavigationTargetType.PROJECT_ASSET.value)
        self.assertEqual(payload.project_id, "Cyclops")
        self.assertEqual(payload.section, "references")
        self.assertEqual(payload.rel_path, "References")
        self.assertEqual(payload.target_id, "ChatGPT Image Jul 31, 2026, 02_42_41 PM.png")

    def test_for_library_asset(self):
        payload = NavigationPayload.for_library_asset("lib_asset_123")
        self.assertEqual(payload.target_type, NavigationTargetType.LIBRARY_ASSET.value)
        self.assertEqual(payload.target_id, "lib_asset_123")
        self.assertEqual(payload.section, "assets_lib")

    def test_for_knowledge_doc(self):
        payload = NavigationPayload.for_knowledge_doc("doc_456")
        self.assertEqual(payload.target_type, NavigationTargetType.KNOWLEDGE_DOC.value)
        self.assertEqual(payload.target_id, "doc_456")
        self.assertEqual(payload.section, "knowledge")

    def test_for_lab_node(self):
        payload = NavigationPayload.for_lab_node("node_789", board_id="board_1", project_or_name="Cyclops")
        self.assertEqual(payload.target_type, NavigationTargetType.LAB_NODE.value)
        self.assertEqual(payload.project_id, "Cyclops")
        self.assertEqual(payload.target_id, "board_1")
        self.assertEqual(payload.sub_target_id, "node_789")

    def test_serialization_roundtrip(self):
        payload = NavigationPayload.for_project_asset("ProjA", "asset_1", rel_path="Assets/Hero/model.fbx")
        d = payload.to_dict()
        reconstructed = NavigationPayload.from_dict(d)
        self.assertEqual(reconstructed.target_type, payload.target_type)
        self.assertEqual(reconstructed.project_id, payload.project_id)
        self.assertEqual(reconstructed.rel_path, payload.rel_path)
        self.assertEqual(reconstructed.target_id, payload.target_id)


class TestExactNavigationAndRelationships(unittest.TestCase):
    """Comprehensive tests for exact entity navigation and relationship chip resolution."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="cw_exact_nav_test_")
        self.temp_path = Path(self.temp_dir)

        # Initialize services
        self.project_svc = ProjectService()
        self.asset_svc = AssetService(self.project_svc)
        self.lib_svc = LibraryService(storage_dir=self.temp_path / "lib")
        self.knowledge_svc = KnowledgeService(storage_dir=self.temp_path / "knowledge")
        self.lab_svc = LabService(self.project_svc)
        self.pcs = ProjectContextService(
            project_service=self.project_svc,
            asset_service=self.asset_svc,
            library_service=self.lib_svc,
            knowledge_service=self.knowledge_svc,
            lab_service=self.lab_svc,
        )
        self.pas = ProjectAssistantService(
            project_context_service=self.pcs,
        )

        # Create AppContext
        self.context = AppContext()
        self.context.project_service = self.project_svc
        self.context.asset_service = self.asset_svc
        self.context.library_service = self.lib_svc
        self.context.knowledge_service = self.knowledge_svc
        self.context.lab_service = self.lab_svc
        self.context.project_context_service = self.pcs
        self.context.project_assistant_service = self.pas

        # Setup Cyclops Project with References
        self.cyclops_dir = self.temp_path / "Cyclops"
        self.cyclops_dir.mkdir(parents=True, exist_ok=True)
        (self.cyclops_dir / "References").mkdir(parents=True, exist_ok=True)
        (self.cyclops_dir / "Assets").mkdir(parents=True, exist_ok=True)

        # Create exact image file from user scenario
        self.image_filename = "ChatGPT Image Jul 31, 2026, 02_42_41 PM.png"
        self.ref_image_path = self.cyclops_dir / "References" / self.image_filename
        self.ref_image_path.write_bytes(b"PNG_MOCK_DATA")

        self.cyclops_proj = self.project_svc.create_project(
            name="Cyclops",
            project_type="game",
            location=str(self.temp_path),
            description="Cyclops game",
        )
        self.asset_svc.rebuild_index(self.cyclops_proj, force=True)

        # Create Library Asset
        self.lib_folder = self.temp_path / "global_lib"
        self.lib_folder.mkdir(parents=True, exist_ok=True)
        self.lib_file_path = self.lib_folder / "global_lib_character.png"
        self.lib_file_path.write_bytes(b"LIB_MOCK_DATA")
        self.lib_location = self.lib_svc.add_library_location(self.lib_folder, display_name="Main Lib")
        self.lib_asset = next(iter(self.lib_svc.get_all_assets()))

        # Build UI Panels and WorkspaceManager
        self.workspace_panel = WorkspacePanel()
        self.workspace_panel.set_context(self.context)
        self.context.workspace = self.workspace_panel

        self.inspector_panel = InspectorPanel()
        self.inspector_panel.set_context(self.context)
        self.context.inspector_panel = self.inspector_panel

        self.wm = WorkspaceManager(self.workspace_panel, self.context)
        self.library_panel = self.wm.library_panel
        self.knowledge_panel = self.wm.knowledge_panel
        self.lab_panel = self.wm.lab_panel
        self.context.workspace_manager = self.wm

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_project_local_asset_resolution_and_chip_status(self):
        """Verify project-local asset resolves to Available and finds exact asset by ID or path."""
        asset_entry = self.asset_svc.get_asset(self.cyclops_proj, self.image_filename)
        self.assertIsNotNone(asset_entry)
        self.assertEqual(asset_entry["filename"], self.image_filename)

        # Test RelationshipChip resolution
        chip = RelationshipChip(
            "project_asset",
            {
                "project_id": "Cyclops",
                "asset_id": asset_entry["id"],
                "relative_path": f"References/{self.image_filename}",
            },
            context=self.context,
        )
        icon, title, status, color = chip._resolve_entity_info()
        self.assertEqual(status, "Available")
        self.assertIn(self.image_filename, title)
        self.assertEqual(color, "#10B981")

    def test_acceptance_scenario_a_project_local_asset_navigation(self):
        """Acceptance Test A:
        Knowledge note -> relationship chip -> ChatGPT Image Jul 31, 2026, 02_42_41 PM.png
        -> opens Cyclops, expands/selects References, selects exact image, shows in Inspector.
        """
        # Create Knowledge Doc linking the project asset
        doc = self.knowledge_svc.create_document(title="Cyclops Concept Art Note", content="References for Cyclops")
        doc = self.knowledge_svc.add_project_asset_relationship(
            doc.id,
            project_id="Cyclops",
            asset_id=self.image_filename,
            relative_path=f"References/{self.image_filename}",
        )

        # Trigger navigation via unified payload
        payload = NavigationPayload.for_project_asset(
            "Cyclops",
            self.image_filename,
            rel_path=f"References/{self.image_filename}",
        )
        nav_success = self.wm.navigate(payload)
        self.assertTrue(nav_success)

        # Verify active project is Cyclops
        self.assertEqual(self.context.current_project.name, "Cyclops")
        self.assertEqual(self.workspace_panel._current_section, "references")

        # Verify asset card is selected in AssetWorkspacePanel
        asset_wp = self.workspace_panel.asset_workspace
        selected_ids = asset_wp.get_selected_ids()
        self.assertTrue(len(selected_ids) > 0)
        selected_card = asset_wp._cards.get(next(iter(selected_ids)))
        self.assertIsNotNone(selected_card)
        self.assertEqual(selected_card.asset["filename"], self.image_filename)

        # Verify Inspector is displaying the exact asset
        self.assertIsNotNone(self.inspector_panel._current_inspectable)
        self.assertEqual(self.inspector_panel._current_inspectable.get_display_name(), self.image_filename)

    def test_cyclops_reference_regression_resolution_and_navigation(self):
        """Regression test for Issue 1:
        Knowledge document linked to an image located under Cyclops References folder.
        - Relationship status: Available
        - Category: References
        - Duplicate prevention on re-adding
        - Clicking opens Cyclops References location (never Assets root)
        - Exact image selected and shown in Inspector
        - Stale/unindexed ID and path-only variants resolve correctly
        """
        # 1. Create Knowledge document and link Cyclops reference
        doc = self.knowledge_svc.create_document(title="Cyclops Storyboard & Ref", content="Design references")
        doc = self.knowledge_svc.add_project_asset_relationship(
            doc.id,
            project_id="Cyclops",
            asset_id=self.image_filename,
            relative_path=f"References/{self.image_filename}",
            category="References",
        )
        self.assertEqual(len(doc.project_asset_refs), 1)
        ref_record = doc.project_asset_refs[0]
        self.assertEqual(ref_record.get("category"), "References")
        self.assertEqual(ref_record.get("relative_path"), f"References/{self.image_filename}")

        # 2. Idempotency test: Adding same reference again must not duplicate records
        doc = self.knowledge_svc.add_project_asset_relationship(
            doc.id,
            project_id="Cyclops",
            asset_id=self.image_filename,
            relative_path=f"References/{self.image_filename}",
            category="References",
        )
        self.assertEqual(len(doc.project_asset_refs), 1)

        # 3. Test RelationshipChip resolution
        chip = RelationshipChip("project_asset", ref_record, context=self.context)
        icon, title, status, color = chip._resolve_entity_info()
        self.assertEqual(status, "Available")
        self.assertEqual(color, "#10B981")
        self.assertEqual(icon, "🖼️")
        self.assertIn(self.image_filename, title)

        # Test stale ID resolution variant (e.g. hash mismatch from old session)
        stale_chip = RelationshipChip(
            "project_asset",
            {
                "project_id": "Cyclops",
                "asset_id": "stale_hash_pa_999",
                "relative_path": f"References/{self.image_filename}",
                "category": "References",
            },
            context=self.context,
        )
        _, _, stale_stat, _ = stale_chip._resolve_entity_info()
        self.assertEqual(stale_stat, "Available")

        # Test filename-only variant
        fn_chip = RelationshipChip(
            "project_asset",
            {
                "project_id": "Cyclops",
                "asset_id": self.image_filename,
            },
            context=self.context,
        )
        _, _, fn_stat, _ = fn_chip._resolve_entity_info()
        self.assertEqual(fn_stat, "Available")

        # 4. Test exact navigation via Knowledge chip click flow
        payload = NavigationPayload.for_project_asset(
            "Cyclops",
            self.image_filename,
            rel_path=f"References/{self.image_filename}",
            category="References",
            metadata=ref_record,
        )
        nav_result = self.wm.navigate(payload)
        self.assertTrue(nav_result)

        # Must navigate to References section, NOT Assets root
        self.assertEqual(self.context.current_project.name, "Cyclops")
        self.assertEqual(self.workspace_panel._current_section, "references")
        self.assertNotEqual(self.workspace_panel._current_section, "assets")

        # Exact referenced image must be selected in AssetWorkspacePanel
        asset_wp = self.workspace_panel.asset_workspace
        selected_ids = asset_wp.get_selected_ids()
        self.assertTrue(len(selected_ids) > 0)
        selected_card = asset_wp._cards.get(next(iter(selected_ids)))
        self.assertIsNotNone(selected_card)
        self.assertEqual(selected_card.asset["filename"], self.image_filename)
        self.assertEqual(selected_card.asset.get("category"), "References")

        # Inspector must show the exact asset
        self.assertIsNotNone(self.inspector_panel._current_inspectable)
        self.assertEqual(self.inspector_panel._current_inspectable.get_display_name(), self.image_filename)

    def test_cyclops_stale_index_reconciliation_and_migration(self):
        """Regression test for Issue 1B:
        Reproduces the exact Cyclops index failure state:
        - .asset_index.json contains a stale record pointing to non-existent Assets/...
        - .asset_index.json contains a live record pointing to existing References/...
        - Knowledge document has a relationship with the stale asset ID and Assets/... path.
        Verifies:
        - Stale record is not returned as Available
        - Live References record is found and returned
        - RelationshipChip status becomes Available with category References
        - Knowledge relationship is migrated to live asset ID/path
        - NavigationPayload points to references section
        - WorkspaceManager opens References, selects the exact image
        - Inspector displays the image
        - No duplicate relationships are created
        """
        stale_id = "-3018712308071128280"
        live_id = "-1754921827663742618"
        stale_abs = str(self.cyclops_dir / "Assets" / self.image_filename)
        live_abs = str(self.cyclops_dir / "References" / self.image_filename)

        # Inject stale and live entries into Cyclops asset index
        stale_entry = {
            "id": stale_id,
            "filename": self.image_filename,
            "relative_path": f"Assets/{self.image_filename}",
            "absolute_path": stale_abs,
            "category": "References",
            "friendly_type": "PNG Image",
            "size": 2321393,
            "favorite": False,
            "tags": [],
            "notes": "",
        }
        live_entry = {
            "id": live_id,
            "filename": self.image_filename,
            "relative_path": f"References/{self.image_filename}",
            "absolute_path": live_abs,
            "category": "References",
            "friendly_type": "PNG Image",
            "size": 2321393,
            "favorite": False,
            "tags": [],
            "notes": "",
        }
        self.asset_svc._indices[self.cyclops_proj.location] = [stale_entry, live_entry]
        self.asset_svc._save_index(self.cyclops_proj)

        # Create Knowledge document with stale reference record
        doc = self.knowledge_svc.create_document(title="DaddyPNB", content="Concept note")
        doc.project_asset_refs = [
            {
                "project_id": "Cyclops",
                "asset_id": stale_id,
                "relative_path": f"Assets/{self.image_filename}",
                "category": "References",
            }
        ]
        self.knowledge_svc._persist_document(doc)

        # 1. Verify AssetService.get_asset prefers the live physical file over stale record
        resolved_entry = self.asset_svc.get_asset(self.cyclops_proj, stale_id)
        self.assertIsNotNone(resolved_entry)
        self.assertEqual(resolved_entry["id"], live_id)
        self.assertEqual(resolved_entry["relative_path"], f"References/{self.image_filename}")
        self.assertEqual(resolved_entry["category"], "References")

        # 2. Verify RelationshipChip resolution succeeds with Available and References category
        chip = RelationshipChip("project_asset", doc.project_asset_refs[0], context=self.context)
        icon, title, status, color = chip._resolve_entity_info()
        self.assertEqual(status, "Available")
        self.assertEqual(color, "#10B981")
        self.assertEqual(icon, "🖼️")
        self.assertIn(self.image_filename, title)

        # 3. Verify Knowledge document relationship was migrated in-place to live ID and path
        refreshed_doc = self.knowledge_svc.get_document(doc.id)
        self.assertEqual(len(refreshed_doc.project_asset_refs), 1)
        migrated_ref = refreshed_doc.project_asset_refs[0]
        self.assertEqual(migrated_ref["asset_id"], live_id)
        self.assertEqual(migrated_ref["relative_path"], f"References/{self.image_filename}")
        self.assertEqual(migrated_ref["category"], "References")

        # 4. Verify clicking the chip constructs payload pointing to References
        payload = NavigationPayload.for_project_asset(
            chip.data.get("project_id", ""),
            chip.data.get("asset_id", "") or chip.data.get("relative_path", ""),
            rel_path=chip.data.get("relative_path"),
            category=chip.data.get("category"),
            metadata=chip.data,
        )
        self.assertEqual(payload.section, "references")
        self.assertEqual(payload.rel_path, "References")

        # 5. Verify WorkspaceManager navigates to References and selects exact image
        nav_success = self.wm.navigate(payload)
        self.assertTrue(nav_success)
        self.assertEqual(self.context.current_project.name, "Cyclops")
        self.assertEqual(self.workspace_panel._current_section, "references")
        self.assertNotEqual(self.workspace_panel._current_section, "assets")

        # Verify selected card in AssetWorkspacePanel
        asset_wp = self.workspace_panel.asset_workspace
        selected_ids = asset_wp.get_selected_ids()
        self.assertTrue(len(selected_ids) > 0)
        selected_card = asset_wp._cards.get(next(iter(selected_ids)))
        self.assertIsNotNone(selected_card)
        self.assertEqual(selected_card.asset["filename"], self.image_filename)

        # Verify Inspector is displaying the exact asset
        self.assertIsNotNone(self.inspector_panel._current_inspectable)
        self.assertEqual(self.inspector_panel._current_inspectable.get_display_name(), self.image_filename)

        # Verify no duplicate relationships exist
        final_doc = self.knowledge_svc.get_document(doc.id)
        self.assertEqual(len(final_doc.project_asset_refs), 1)

    def test_acceptance_scenario_b_library_asset_navigation(self):
        """Acceptance Test B:
        Knowledge note -> global Library relationship -> opens Asset Library,
        selects exact linked library asset, and shows it in Inspector.
        """
        doc = self.knowledge_svc.create_document(title="Global Library Note", content="Uses global character")
        doc = self.knowledge_svc.add_library_asset_relationship(doc.id, asset_id=self.lib_asset.id)

        # Trigger navigation
        payload = NavigationPayload.for_library_asset(self.lib_asset.id)
        nav_success = self.wm.navigate(payload)
        self.assertTrue(nav_success)

        # Verify current workspace module is Asset Library
        self.assertEqual(self.workspace_panel.stack.currentWidget(), self.library_panel)

        # Verify Inspector is displaying the library asset
        self.assertIsNotNone(self.inspector_panel._current_inspectable)
        self.assertEqual(self.inspector_panel._current_inspectable.get_display_name(), self.lib_asset.filename)

    def test_library_asset_offline_missing_states(self):
        """Verify correct Offline vs Missing status on library relationship chips."""
        # Available
        chip_avail = RelationshipChip("library_asset", {"asset_id": self.lib_asset.id}, context=self.context)
        _, _, stat_avail, _ = chip_avail._resolve_entity_info()
        self.assertEqual(stat_avail, "Available")

        # Missing asset ID
        chip_missing = RelationshipChip("library_asset", {"asset_id": "non_existent_id"}, context=self.context)
        _, _, stat_missing, _ = chip_missing._resolve_entity_info()
        self.assertEqual(stat_missing, "Missing")

    def test_references_vs_library_references_segregation(self):
        """Verify strict segregation: local files stay under References, library links under Library References."""
        # Add library reference into Cyclops
        self.asset_svc.add_library_reference(
            self.cyclops_proj,
            self.lib_asset,
            target_category="Library References",
            library_service=self.lib_svc,
        )

        local_refs = self.asset_svc.get_assets(self.cyclops_proj, category="references")
        lib_refs = self.asset_svc.get_assets(self.cyclops_proj, category="library_references")

        # Local references should contain only local files
        self.assertTrue(any(a["filename"] == self.image_filename for a in local_refs))
        self.assertFalse(any(a.get("is_library_reference") for a in local_refs))

        # Library references should contain only global linked library items
        self.assertTrue(any(a["filename"] == self.lib_asset.filename for a in lib_refs))
        self.assertTrue(all(a.get("is_library_reference") for a in lib_refs))

        # Dashboard Context reflects clean separate counts
        ctx = self.pcs.get_project_context(self.cyclops_proj)
        self.assertEqual(ctx.library_summary.total_linked_assets, 1)

    def test_home_favorites_and_pinned_expansion(self):
        """Verify Home workspace discovers and renders pinned Projects, Knowledge Notes, and Lab items."""
        # Pin Cyclops
        self.cyclops_proj.is_pinned = True

        # Favorite Knowledge Note
        fav_doc = self.knowledge_svc.create_document(title="Favorite Production Guidelines", content="Important steps")
        self.knowledge_svc.toggle_favorite(fav_doc.id)

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        # Verify cached pinned items includes project and knowledge
        pinned_types = [p.get("type") for p in home._cached_pinned_items]
        self.assertIn("project", pinned_types)
        self.assertIn("knowledge", pinned_types)

        # Verify exact click routing on pinned card
        know_pin = next(p for p in home._cached_pinned_items if p.get("type") == "knowledge")
        home._on_pinned_card_clicked(know_pin)
        self.assertEqual(self.workspace_panel.stack.currentWidget(), self.knowledge_panel)

    def test_dashboard_polish_and_ai_assistant_resizing(self):
        """Verify Project Dashboard polish, count consistency, and AI Assistant expanding."""
        self.asset_svc.add_library_reference(
            self.cyclops_proj,
            self.lib_asset,
            target_category="Library References",
            library_service=self.lib_svc,
        )

        dash = DashboardPanel()
        dash.set_context(self.context)
        dash.show_project(self.cyclops_proj)

        # Verify metric card counts
        self.assertEqual(dash.card_library.count_lbl.text(), "1")
        self.assertEqual(dash.card_assets.count_lbl.text(), "1")

        # Verify AI Assistant widget resizing
        ai_w = dash.ai_assistant_widget
        self.assertEqual(ai_w.scroll_area.minimumHeight(), 320)
        ai_w._toggle_expand()
        self.assertEqual(ai_w.scroll_area.minimumHeight(), 480)
        self.assertIn("Expanded", ai_w.resize_btn.text())
        ai_w._toggle_expand()
        self.assertEqual(ai_w.scroll_area.minimumHeight(), 680)
        self.assertIn("Tall", ai_w.resize_btn.text())
        ai_w._toggle_expand()
        self.assertEqual(ai_w.scroll_area.minimumHeight(), 320)


if __name__ == "__main__":
    unittest.main()
