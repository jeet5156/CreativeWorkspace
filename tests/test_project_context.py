"""Unit and architectural tests for ProjectContext models and ProjectContextService (Phase 5A)."""

import os
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from datetime import datetime
import tempfile
import shutil

from models.project import Project
from models.project_context import (
    ProjectContext,
    ProjectKnowledgeSummary,
    ProjectAssetSummary,
    ProjectLibrarySummary,
    ProjectLabSummary,
    ProjectAvailabilitySummary,
    ProjectVersionSummary,
)
from models.knowledge import KnowledgeDocument
from models.library_models import LibraryAsset, AssetAvailability
from services.project_service import ProjectService
from services.asset_service import AssetService
from services.library_service import LibraryService
from services.knowledge_service import KnowledgeService
from services.lab_service import LabService
from services.project_context_service import ProjectContextService


class TestProjectContext(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_proj_ctx_")
        self.proj_dir = Path(self.temp_dir) / "CyberRacer"
        self.proj_dir.mkdir(parents=True, exist_ok=True)

        self.project_service = ProjectService()
        self.asset_service = AssetService(self.project_service)
        self.library_service = LibraryService(storage_dir=Path(self.temp_dir) / "lib")
        self.knowledge_service = KnowledgeService(storage_dir=Path(self.temp_dir) / "know")
        self.lab_service = LabService(self.project_service)

        self.service = ProjectContextService(
            project_service=self.project_service,
            asset_service=self.asset_service,
            library_service=self.library_service,
            knowledge_service=self.knowledge_service,
            lab_service=self.lab_service,
        )

        self.project = self.project_service.create_project(
            name="CyberRacer",
            project_type="game",
            location=str(self.temp_dir),
            description="High-speed futuristic cyber racing game.",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Serialization Tests
    # -------------------------------------------------------------------------

    def test_01_model_serialization(self):
        """Test ProjectContext and supporting summary models serialization to/from dict."""
        ctx = ProjectContext(
            project_id="CyberRacer",
            project_name="CyberRacer",
            project_path="/path/to/CyberRacer",
            project_type="game",
            created=datetime.now().isoformat(),
            modified=datetime.now().isoformat(),
            metadata={"priority": "high", "status": "active"},
            knowledge_summary=ProjectKnowledgeSummary(total_notes=5, favorite_notes=2),
            asset_summary=ProjectAssetSummary(total_assets=42, total_size=1024),
            library_summary=ProjectLibrarySummary(total_linked_assets=10, available_assets=8, offline_assets=2),
            lab_summary=ProjectLabSummary(total_boards=3, total_nodes=15),
            availability_summary=ProjectAvailabilitySummary(online_library_assets=8, offline_library_assets=2),
            version_summary=ProjectVersionSummary(total_versioned_assets=6),
            related_entity_counts={"knowledge": 5, "assets": 42},
        )

        data = ctx.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["project_name"], "CyberRacer")
        self.assertEqual(data["knowledge_summary"]["total_notes"], 5)
        self.assertEqual(data["asset_summary"]["total_assets"], 42)
        self.assertEqual(data["library_summary"]["offline_assets"], 2)

        restored = ProjectContext.from_dict(data)
        self.assertEqual(restored.project_name, "CyberRacer")
        self.assertEqual(restored.knowledge_summary.total_notes, 5)
        self.assertEqual(restored.knowledge_summary.favorite_notes, 2)
        self.assertEqual(restored.asset_summary.total_assets, 42)
        self.assertEqual(restored.library_summary.offline_assets, 2)
        self.assertEqual(restored.availability_summary.offline_library_assets, 2)
        self.assertEqual(restored.version_summary.total_versioned_assets, 6)

    # -------------------------------------------------------------------------
    # 2. Context Loading from ProjectService
    # -------------------------------------------------------------------------

    def test_02_context_loads_from_project_service(self):
        """Test project context loads core metadata from ProjectService."""
        ctx = self.service.get_project_context(self.project)
        self.assertEqual(ctx.project_name, "CyberRacer")
        self.assertEqual(ctx.project_type, "game")
        self.assertEqual(ctx.metadata.get("status"), "active")
        self.assertEqual(ctx.metadata.get("priority"), "medium")
        self.assertIn("CyberRacer", ctx.project_path)

    # -------------------------------------------------------------------------
    # 3. Knowledge Relationships Included
    # -------------------------------------------------------------------------

    def test_03_knowledge_relationships_included(self):
        """Test Knowledge notes linked to project are aggregated into context."""
        doc1 = self.knowledge_service.create_document(title="Character Production", content="Hero models notes")
        doc2 = self.knowledge_service.create_document(title="Vehicle Design", content="Hovercar physics")
        doc3 = self.knowledge_service.create_document(title="Unrelated Note", content="Global memo")

        # Link doc1 and doc2 to CyberRacer
        self.knowledge_service.add_project_relationship(doc1.id, "CyberRacer")
        self.knowledge_service.add_project_relationship(doc2.id, "CyberRacer")
        self.knowledge_service.set_favorite(doc1.id, True)

        ctx = self.service.get_project_context(self.project)
        self.assertEqual(ctx.knowledge_summary.total_notes, 2)
        self.assertEqual(ctx.knowledge_summary.favorite_notes, 1)
        recent_titles = [n["title"] for n in ctx.knowledge_summary.recent_notes]
        self.assertIn("Character Production", recent_titles)
        self.assertIn("Vehicle Design", recent_titles)
        self.assertNotIn("Unrelated Note", recent_titles)

    def test_03b_knowledge_relationships_via_project_asset_refs(self):
        """Test Knowledge notes linked only via project_asset_refs (Cyclops pattern) are aggregated into context."""
        # Note linked ONLY to a project asset (References image)
        doc_asset_only = self.knowledge_service.create_document(
            title="Cyclops Reference Note",
            content="Details about reference image",
            favorite=True,
            project_asset_refs=[{
                "project_id": "CyberRacer",
                "asset_id": "-1754921827663742618",
                "relative_path": "References/ref_img.png",
                "category": "References"
            }]
        )

        # Note linked with both direct project and asset ref
        doc_both = self.knowledge_service.create_document(
            title="Cyber Track Layout",
            content="Track blueprint",
            favorite=False,
            project_ids=["CyberRacer"],
            project_asset_refs=[{
                "project_id": "CyberRacer",
                "asset_id": "track_model_1",
                "relative_path": "Assets/track.obj",
                "category": "Assets"
            }]
        )

        # Unrelated note for another project
        doc_other = self.knowledge_service.create_document(
            title="Other Project Note",
            content="Other notes",
            project_asset_refs=[{
                "project_id": "UnrelatedProject",
                "asset_id": "other_asset",
                "relative_path": "Assets/other.png",
                "category": "Assets"
            }]
        )

        ctx = self.service.get_project_context(self.project)
        self.assertEqual(ctx.knowledge_summary.total_notes, 2)
        self.assertEqual(ctx.knowledge_summary.favorite_notes, 1)
        recent_titles = [n["title"] for n in ctx.knowledge_summary.recent_notes]
        self.assertIn("Cyclops Reference Note", recent_titles)
        self.assertIn("Cyber Track Layout", recent_titles)
        self.assertNotIn("Other Project Note", recent_titles)

    # -------------------------------------------------------------------------
    # 4. Project Assets Included
    # -------------------------------------------------------------------------

    def test_04_project_assets_included(self):
        """Test project-local assets are aggregated and grouped by category."""
        hero_file = self.proj_dir / "Assets" / "hero.fbx"
        hero_file.write_text("dummy 3d data")
        tex_file = self.proj_dir / "Assets" / "hero_diffuse.png"
        tex_file.write_text("dummy img data")

        self.asset_service.rebuild_index(self.project, force=True)

        ctx = self.service.get_project_context(self.project)
        self.assertEqual(ctx.asset_summary.total_assets, 2)
        self.assertIn("Assets", ctx.asset_summary.by_category)
        self.assertEqual(ctx.asset_summary.by_category["Assets"], 2)

    # -------------------------------------------------------------------------
    # 5-9. Library References & Availability Breakdown
    # -------------------------------------------------------------------------

    def test_05_library_references_and_availability_counts(self):
        """Test available, offline, missing, and changed library references are counted accurately."""
        # Create library reference entries in project index
        ref_available = {
            "id": "lib_ref_1",
            "filename": "Engine_Block.fbx",
            "category": "References",
            "is_library_reference": True,
            "library_asset_id": "asset_1",
            "drive_id": "drive_a",
            "drive_relative_path": "models/Engine_Block.fbx",
        }
        ref_offline = {
            "id": "lib_ref_2",
            "filename": "Texture_Pack.zip",
            "category": "References",
            "is_library_reference": True,
            "library_asset_id": "asset_2",
            "drive_id": "drive_b",
            "drive_relative_path": "textures/Texture_Pack.zip",
        }
        ref_missing = {
            "id": "lib_ref_3",
            "filename": "Old_Soundtrack.wav",
            "category": "References",
            "is_library_reference": True,
            "library_asset_id": "asset_3",
            "drive_id": "drive_a",
            "drive_relative_path": "audio/Old_Soundtrack.wav",
        }
        ref_changed = {
            "id": "lib_ref_4",
            "filename": "Sky_Dome.hdr",
            "category": "References",
            "is_library_reference": True,
            "library_asset_id": "asset_4",
            "drive_id": "drive_a",
            "drive_relative_path": "hdri/Sky_Dome.hdr",
        }

        # Mock library_service.get_asset and get_asset_availability
        def mock_get_asset(lib_id):
            return MagicMock(id=lib_id, drive_id="drive_a" if lib_id != "asset_2" else "drive_b", drive_relative_path=f"path/{lib_id}")

        def mock_get_asset_availability(asset_obj):
            if asset_obj.id == "asset_1":
                return AssetAvailability.AVAILABLE
            elif asset_obj.id == "asset_2":
                return AssetAvailability.OFFLINE
            elif asset_obj.id == "asset_3":
                return AssetAvailability.MISSING
            elif asset_obj.id == "asset_4":
                return AssetAvailability.POSSIBLY_CHANGED
            return AssetAvailability.AVAILABLE

        self.library_service.get_asset = mock_get_asset
        self.library_service.get_asset_availability = mock_get_asset_availability

        # Inject references into project asset index
        self.asset_service._indices[self.project.location] = [ref_available, ref_offline, ref_missing, ref_changed]
        self.asset_service._save_index(self.project)

        ctx = self.service.get_project_context(self.project)

        self.assertEqual(ctx.library_summary.total_linked_assets, 4)
        self.assertEqual(ctx.library_summary.available_assets, 1)
        self.assertEqual(ctx.library_summary.offline_assets, 1)
        self.assertEqual(ctx.library_summary.missing_assets, 1)
        self.assertEqual(ctx.library_summary.possibly_changed_assets, 1)

        self.assertEqual(ctx.availability_summary.online_library_assets, 1)
        self.assertEqual(ctx.availability_summary.offline_library_assets, 1)
        self.assertEqual(ctx.availability_summary.missing_library_assets, 1)
        self.assertEqual(ctx.availability_summary.possibly_changed_assets, 1)

    # -------------------------------------------------------------------------
    # 10-12. Lab Boards, Node Counts & Task Status
    # -------------------------------------------------------------------------

    def test_10_lab_boards_and_tasks_summarized(self):
        """Test Lab boards, node counts, and task checklist statuses are summarized."""
        b1 = self.lab_service.create_board(self.project, "Character Development")
        b2 = self.lab_service.create_board(self.project, "Vehicle Systems")

        # Save some items on b1 with checklist tasks
        b1_data = self.lab_service.load_board(self.project, b1["id"])
        b1_data["items"] = [
            {
                "id": "node_1",
                "type": "note.blank",
                "payload": {
                    "content": "- [x] Model low-poly hero\n- [ ] Bake normal maps\n- [x] Rig skeleton",
                },
            },
            {
                "id": "node_2",
                "type": "image.reference",
                "payload": {"filename": "concept.png"},
            }
        ]
        self.lab_service.save_board(self.project, b1_data, board_id=b1["id"])

        ctx = self.service.get_project_context(self.project)
        # default board + b1 + b2 = 3 boards
        self.assertGreaterEqual(ctx.lab_summary.total_boards, 2)
        self.assertGreaterEqual(ctx.lab_summary.total_nodes, 2)
        self.assertEqual(ctx.lab_summary.task_status.get("total"), 3)
        self.assertEqual(ctx.lab_summary.task_status.get("completed"), 2)
        self.assertEqual(ctx.lab_summary.task_status.get("pending"), 1)

    # -------------------------------------------------------------------------
    # 13-14. Asset Version Grouping
    # -------------------------------------------------------------------------

    def test_13_version_information_grouped_correctly(self):
        """Test versioned assets are grouped by logical identity with latest version exposed."""
        f1 = self.proj_dir / "Assets" / "Character_Hero_v001.fbx"
        f2 = self.proj_dir / "Assets" / "Character_Hero_v002.fbx"
        f3 = self.proj_dir / "Assets" / "Character_Hero_v003.fbx"
        f4 = self.proj_dir / "Assets" / "Environment_Tree_LOD0.blend"
        f1.write_text("v1")
        f2.write_text("v2")
        f3.write_text("v3")
        f4.write_text("env")

        self.asset_service.rebuild_index(self.project, force=True)

        ctx = self.service.get_project_context(self.project)
        self.assertEqual(ctx.version_summary.total_versioned_assets, 3)

        hero_group = next((g for g in ctx.version_summary.groups if "Character_Hero" in g["logical_name"]), None)
        self.assertIsNotNone(hero_group)
        self.assertEqual(hero_group["latest"], "v003")
        self.assertEqual(hero_group["count"], 3)
        self.assertEqual(hero_group["versions"], ["v001", "v002", "v003"])

        # Check LOD count
        self.assertEqual(ctx.asset_summary.lod_counts.get("LOD0"), 1)

    def test_14_no_fabricated_version_information(self):
        """Test unversioned files do not create fabricated versions."""
        f_plain = self.proj_dir / "Assets" / "unversioned_file.txt"
        f_plain.write_text("plain")

        self.asset_service.rebuild_index(self.project, force=True)

        ctx = self.service.get_project_context(self.project)
        unversioned_group = next((g for g in ctx.version_summary.groups if g["logical_name"] == "unversioned_file"), None)
        self.assertIsNone(unversioned_group)

    # -------------------------------------------------------------------------
    # 15-16. Empty and Unknown Project Safety
    # -------------------------------------------------------------------------

    def test_15_empty_project_produces_valid_empty_context(self):
        """Test empty project produces complete, non-null, valid context."""
        empty_proj = self.project_service.create_project(
            name="EmptyProject",
            project_type="portfolio",
            location=str(self.temp_dir),
            description="",
        )
        ctx = self.service.get_project_context(empty_proj)
        self.assertEqual(ctx.project_name, "EmptyProject")
        self.assertEqual(ctx.knowledge_summary.total_notes, 0)
        self.assertEqual(ctx.asset_summary.total_assets, 0)
        self.assertEqual(ctx.library_summary.total_linked_assets, 0)
        self.assertEqual(ctx.availability_summary.online_library_assets, 0)
        self.assertIsInstance(ctx.related_entity_counts, dict)

    def test_16_unknown_project_handled_safely(self):
        """Test unknown project string or None returns safe fallback context without crashing."""
        ctx_none = self.service.get_project_context(None)
        self.assertIsInstance(ctx_none, ProjectContext)
        self.assertEqual(ctx_none.project_name, "No Project Selected")

        ctx_unknown = self.service.get_project_context("NonExistent_Project_12345")
        self.assertIsInstance(ctx_unknown, ProjectContext)
        self.assertEqual(ctx_unknown.project_name, "Unknown Project")

    # -------------------------------------------------------------------------
    # 17. ZERO Drive Scan Performance Invariant
    # -------------------------------------------------------------------------

    def test_17_no_external_drive_scans(self):
        """Performance / Invariant: get_project_context must never invoke os.walk or drive-wide discovery."""
        with patch("os.walk") as mock_walk:
            ctx = self.service.get_project_context(self.project)
            mock_walk.assert_not_called()
            self.assertIsNotNone(ctx)

    # -------------------------------------------------------------------------
    # 18. ZERO AI Invocation Invariant
    # -------------------------------------------------------------------------

    def test_18_no_ai_invocations(self):
        """Invariant: Project Context aggregation is purely deterministic metadata and must not invoke AI."""
        # Ensure no AI calls happen
        with patch("services.ai_service.AIService.generate", side_effect=AssertionError("AI call forbidden")):
            with patch("services.ai_service.AIService.generate_async", side_effect=AssertionError("AI call forbidden")):
                ctx = self.service.get_project_context(self.project)
                self.assertEqual(ctx.project_name, "CyberRacer")


if __name__ == "__main__":
    unittest.main()
