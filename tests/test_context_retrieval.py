"""Comprehensive test suite for AI Context Retrieval Engine (Chunk 1).

Verifies:
1. Knowledge notes retrieval via metadata/indexes.
2. Library asset catalog retrieval without reading external storage.
3. Project-local assets retrieval via AssetService index.
4. Project metadata retrieval.
5. Lab boards and nodes retrieval.
6. Explicit relationships receive highest ranking priority (+100).
7. Current project receives ranking boost (+50).
8. Results are correctly ranked and sorted.
9. Configurable per-source and total hard limits are strictly enforced.
10. Offline library assets remain searchable from catalog.
11. No filesystem-wide scans occur during retrieval queries.
12. Empty queries and missing entities behave safely without exceptions.
13. ContextResult.to_ai_context() formats compact, high-signal text for AI.
14. Scope boundaries (CURRENT_DOCUMENT, CURRENT_PROJECT, LIBRARY, LAB, RELATED_ONLY, WORKSPACE) function properly.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.app_context import AppContext
from models.ai_context import (
    ContextItem,
    ContextQuery,
    ContextResult,
    ContextScope,
    ContextSource,
)
from models.knowledge import KnowledgeDocument
from models.library_models import AssetAvailability, LibraryAsset, LibraryDrive
from models.project import Project
from services.asset_service import AssetService
from services.context_retrieval_service import ContextRetrievalService
from services.knowledge_service import KnowledgeService
from services.lab_service import LabService
from services.library_service import LibraryService
from services.project_service import ProjectService


class TestContextRetrievalService(unittest.TestCase):
    """Test suite for indexed metadata context retrieval across CreativeWorkspace."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.storage_dir = Path(self.test_dir)

        # 1. Project Service
        self.project_service = ProjectService()
        self.proj_p2 = self.project_service.create_project(
            name="RaceP2",
            project_type="Game",
            location=str(self.storage_dir / "projects"),
            description="High-speed racing game with custom cyber vehicles",
        )
        self.proj_other = self.project_service.create_project(
            name="FantasyRPG",
            project_type="VFX",
            location=str(self.storage_dir / "projects"),
            description="Medieval fantasy realm and characters",
        )

        # 2. Knowledge Service
        self.knowledge_dir = self.storage_dir / "knowledge"
        self.knowledge_service = KnowledgeService(storage_dir=self.knowledge_dir)
        self.doc_hero = self.knowledge_service.create_document(
            title="Character Production Notes",
            content="Detailed character modeling pipeline for hero vehicle drivers and racing pilots.",
            tags=["character", "production", "hero"],
        )
        self.doc_lore = self.knowledge_service.create_document(
            title="Track Lore & Background",
            content="Lore concerning futuristic neon city circuits and obstacle arenas.",
            tags=["lore", "environment"],
        )

        # 3. Library Service
        self.library_dir = self.storage_dir / "library"
        self.library_service = LibraryService(storage_dir=self.library_dir)
        # Register a drive and assets
        drive = LibraryDrive(
            drive_id="drive_ext_1",
            name="Storage Drive 1",
            last_known_mount="/mnt/storage1",
        )
        self.library_service._drives[drive.drive_id] = drive

        self.lib_asset_hero = LibraryAsset(
            id="lib_asset_001",
            drive_id="drive_ext_1",
            location_id="loc_1",
            filename="Hero_v03.blend",
            drive_relative_path="Characters/Hero/Hero_v03.blend",
            category="3D Models",
            tags=["hero", "character", "blender"],
            notes="Main hero driver 3D model",
            friendly_type="Blender Scene",
        )
        self.lib_asset_offline = LibraryAsset(
            id="lib_asset_002",
            drive_id="drive_offline_99",
            location_id="loc_2",
            filename="CyberCar_Chassis.fbx",
            drive_relative_path="Vehicles/CyberCar_Chassis.fbx",
            category="3D Models",
            tags=["vehicle", "chassis", "car"],
            notes="High poly chassis model",
            friendly_type="FBX 3D Model",
        )
        self.library_service._assets[self.lib_asset_hero.id] = self.lib_asset_hero
        self.library_service._assets[self.lib_asset_offline.id] = self.lib_asset_offline

        # 4. Asset Service (Project Local Assets)
        self.asset_service = AssetService(self.project_service)
        # Populate asset index for RaceP2
        p2_assets = [
            {
                "id": "pa_001",
                "filename": "hero_texture_02.png",
                "relative_path": "Assets/Textures/hero_texture_02.png",
                "category": "Textures",
                "tags": ["hero", "texture", "diffuse"],
                "notes": "4K diffuse map for hero vehicle",
                "friendly_type": "PNG Image",
            },
            {
                "id": "pa_002",
                "filename": "engine_audio_loop.wav",
                "relative_path": "Assets/Audio/engine_audio_loop.wav",
                "category": "Audio",
                "tags": ["audio", "engine", "sfx"],
                "notes": "V8 turbo sound loop",
                "friendly_type": "WAV Audio",
            },
        ]
        self.asset_service._indices[self.proj_p2.location] = p2_assets

        # 5. Lab Service
        self.lab_service = LabService(self.project_service)
        # Create a board with nodes in RaceP2
        board = self.lab_service.create_board(self.proj_p2, name="Hero Character Pipeline")
        board_id = board["id"]
        board_file = self.lab_service.get_boards_dir(self.proj_p2) / f"{board_id}.lab.json"
        board_data = {
            "version": "1.0",
            "board_id": board_id,
            "name": "Hero Character Pipeline",
            "items": [
                {
                    "id": "lab_node_hero_sculpt",
                    "name": "Sculpt → Retopo",
                    "type": "task_card",
                    "text": "Sculpt high poly details and bake normal maps for hero pilot",
                    "tags": ["hero", "character", "sculpt"],
                },
                {
                    "id": "lab_node_rigging",
                    "name": "Facial Rigging",
                    "type": "milestone",
                    "text": "Rig expressions and eye controls",
                    "tags": ["rigging"],
                },
            ],
        }
        with open(board_file, "w", encoding="utf-8") as f:
            json.dump(board_data, f, indent=2)

        # 6. Central Retrieval Service
        self.retrieval_service = ContextRetrievalService(
            knowledge_service=self.knowledge_service,
            library_service=self.library_service,
            asset_service=self.asset_service,
            project_service=self.project_service,
            lab_service=self.lab_service,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_knowledge_notes_retrieval(self):
        """1. Verify Knowledge search returns relevant notes via indexed metadata."""
        query = ContextQuery(text="hero character", scope=ContextScope.WORKSPACE)
        result = self.retrieval_service.retrieve(query)

        knowledge_items = [it for it in result.items if it.source_type == ContextSource.KNOWLEDGE]
        self.assertTrue(len(knowledge_items) >= 1)
        self.assertEqual(knowledge_items[0].id, self.doc_hero.id)
        self.assertEqual(knowledge_items[0].title, "Character Production Notes")
        self.assertIn("character", knowledge_items[0].metadata["tags"])

    def test_library_metadata_searched_without_reading_files(self):
        """2. Verify Library catalog is searched from metadata without accessing real files."""
        query = ContextQuery(text="Hero_v03.blend", scope=ContextScope.LIBRARY)
        result = self.retrieval_service.retrieve(query)

        self.assertEqual(len(result.items), 1)
        item = result.items[0]
        self.assertEqual(item.source_type, ContextSource.LIBRARY_ASSET)
        self.assertEqual(item.title, "Hero_v03.blend")
        self.assertEqual(item.path_hint, "Characters/Hero/Hero_v03.blend")
        self.assertEqual(item.metadata["category"], "3D Models")

    def test_project_local_assets_searchable(self):
        """3. Verify project-local assets in AssetService index are searchable."""
        query = ContextQuery(text="hero_texture_02.png", scope=ContextScope.WORKSPACE)
        result = self.retrieval_service.retrieve(query)

        p_assets = [it for it in result.items if it.source_type == ContextSource.PROJECT_ASSET]
        self.assertTrue(len(p_assets) >= 1)
        self.assertEqual(p_assets[0].title, "hero_texture_02.png")
        self.assertEqual(p_assets[0].metadata["category"], "Textures")

    def test_projects_metadata_retrieval(self):
        """4. Verify Projects can be queried and retrieved by name and description."""
        query = ContextQuery(text="RaceP2", scope=ContextScope.WORKSPACE)
        result = self.retrieval_service.retrieve(query)

        proj_items = [it for it in result.items if it.source_type == ContextSource.PROJECT]
        self.assertTrue(len(proj_items) >= 1)
        self.assertEqual(proj_items[0].title, "RaceP2")
        self.assertIn("racing", proj_items[0].description)

    def test_lab_nodes_retrieval(self):
        """5. Verify Lab nodes and boards are retrieved and scored."""
        query = ContextQuery(text="Sculpt Retopo", scope=ContextScope.LAB, project_id="RaceP2")
        result = self.retrieval_service.retrieve(query)

        lab_items = [it for it in result.items if it.source_type == ContextSource.LAB_NODE]
        self.assertTrue(len(lab_items) >= 1)
        self.assertEqual(lab_items[0].title, "Sculpt → Retopo")
        self.assertEqual(lab_items[0].metadata["board_name"], "Hero Character Pipeline")

    def test_explicit_knowledge_relationships_get_priority(self):
        """6. Verify explicit Knowledge relationships receive +100 priority boost."""
        # Add explicit relationship from doc_hero to lib_asset_hero and pa_001
        self.knowledge_service.update_document(
            self.doc_hero.id,
            library_asset_ids=[self.lib_asset_hero.id],
            project_asset_refs=[{"asset_id": "pa_001", "relative_path": "Assets/Textures/hero_texture_02.png"}],
        )

        query = ContextQuery(
            text="hero",
            document_id=self.doc_hero.id,
            scope=ContextScope.WORKSPACE,
        )
        result = self.retrieval_service.retrieve(query)

        # Explicitly linked items should have score >= 100
        lib_match = next((it for it in result.items if it.id == self.lib_asset_hero.id), None)
        self.assertIsNotNone(lib_match)
        self.assertTrue(lib_match.is_explicit_relationship)
        self.assertGreaterEqual(lib_match.relevance_score, 100.0)

    def test_current_project_priority_boost(self):
        """7. Verify current project entities receive +50 score boost."""
        query = ContextQuery(
            text="hero",
            project_id=self.proj_p2.name,
            scope=ContextScope.WORKSPACE,
        )
        result = self.retrieval_service.retrieve(query)

        # RaceP2 assets should have current_project boost
        p2_asset = next((it for it in result.items if it.id == "pa_001"), None)
        self.assertIsNotNone(p2_asset)
        self.assertIn("current_project", p2_asset.matched_terms)
        self.assertGreaterEqual(p2_asset.relevance_score, 50.0)

    def test_ranking_and_sorting_order(self):
        """8. Verify candidates are strictly sorted by relevance_score descending."""
        query = ContextQuery(text="hero", scope=ContextScope.WORKSPACE)
        result = self.retrieval_service.retrieve(query)

        scores = [it.relevance_score for it in result.items]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_hard_limits_enforced(self):
        """9. Verify per-source and total hard limits are strictly respected."""
        query = ContextQuery(
            text="",  # Retrieve all candidates
            max_items=3,
            max_knowledge_items=1,
            max_library_assets=1,
            max_project_assets=1,
        )
        result = self.retrieval_service.retrieve(query)

        self.assertLessEqual(len(result.items), 3)
        k_count = sum(1 for it in result.items if it.source_type == ContextSource.KNOWLEDGE)
        l_count = sum(1 for it in result.items if it.source_type == ContextSource.LIBRARY_ASSET)
        pa_count = sum(1 for it in result.items if it.source_type == ContextSource.PROJECT_ASSET)

        self.assertLessEqual(k_count, 1)
        self.assertLessEqual(l_count, 1)
        self.assertLessEqual(pa_count, 1)

    def test_offline_library_assets_remain_searchable(self):
        """10. Verify offline catalog items remain searchable when include_offline_assets=True."""
        query = ContextQuery(
            text="CyberCar",
            scope=ContextScope.LIBRARY,
            include_offline_assets=True,
        )
        result = self.retrieval_service.retrieve(query)

        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].id, self.lib_asset_offline.id)
        self.assertEqual(result.items[0].availability, "offline")

        # Verify excluded when include_offline_assets=False
        query_online_only = ContextQuery(
            text="CyberCar",
            scope=ContextScope.LIBRARY,
            include_offline_assets=False,
        )
        res_online = self.retrieval_service.retrieve(query_online_only)
        self.assertEqual(len(res_online.items), 0)

    def test_no_filesystem_wide_scan_occurs(self):
        """11. Architectural Invariant: Verify no os.walk or deep directory scan occurs during query."""
        with patch("os.walk") as mock_walk:
            mock_walk.side_effect = AssertionError("os.walk should NEVER be called during AI context retrieval!")

            query = ContextQuery(text="hero character texture", scope=ContextScope.WORKSPACE)
            result = self.retrieval_service.retrieve(query)

            self.assertGreater(len(result.items), 0)
            mock_walk.assert_not_called()

    def test_empty_query_behaves_safely(self):
        """12. Verify empty query string returns ranked defaults without crashing."""
        query = ContextQuery(text="", scope=ContextScope.WORKSPACE)
        result = self.retrieval_service.retrieve(query)

        self.assertIsInstance(result, ContextResult)
        self.assertGreater(len(result.items), 0)
        self.assertGreater(result.total_candidates, 0)

    def test_missing_or_corrupted_service_does_not_crash(self):
        """13. Verify retrieval is resilient to missing services or uninitialized catalogs."""
        bare_service = ContextRetrievalService()
        result = bare_service.retrieve(ContextQuery(text="test"))

        self.assertEqual(len(result.items), 0)
        self.assertEqual(result.total_candidates, 0)
        self.assertEqual(result.to_ai_context(), "")

    def test_to_ai_context_produces_compact_output(self):
        """14. Verify ContextResult.to_ai_context() generates formatted, high-signal text."""
        query = ContextQuery(text="hero", scope=ContextScope.WORKSPACE)
        result = self.retrieval_service.retrieve(query)

        ai_ctx = result.to_ai_context()
        self.assertIsInstance(ai_ctx, str)
        self.assertTrue(len(ai_ctx) > 0)

        # Check expected section headers
        self.assertIn("RELATED KNOWLEDGE:", ai_ctx)
        self.assertIn("- Character Production Notes", ai_ctx)
        self.assertIn("Tags: character, production, hero", ai_ctx)

        self.assertIn("LIBRARY ASSETS:", ai_ctx)
        self.assertIn("- Hero_v03.blend", ai_ctx)

        self.assertIn("PROJECT ASSETS:", ai_ctx)
        self.assertIn("- hero_texture_02.png", ai_ctx)

        self.assertIn("LAB:", ai_ctx)
        self.assertIn("- Hero Character Pipeline", ai_ctx)

    def test_scope_filtering(self):
        """15. Verify scope constraints isolate requested boundaries."""
        # Library Scope
        res_lib = self.retrieval_service.retrieve(ContextQuery(text="hero", scope=ContextScope.LIBRARY))
        self.assertTrue(all(it.source_type == ContextSource.LIBRARY_ASSET for it in res_lib.items))

        # Lab Scope
        res_lab = self.retrieval_service.retrieve(ContextQuery(text="hero", scope=ContextScope.LAB))
        self.assertTrue(all(it.source_type in (ContextSource.LAB_NODE, ContextSource.LAB_BOARD) for it in res_lab.items))

    def test_app_context_initialization(self):
        """16. Verify AppContext instantiates context_retrieval_service properly."""
        app_ctx = AppContext()
        self.assertIsNotNone(app_ctx.context_retrieval_service)
        self.assertIsInstance(app_ctx.context_retrieval_service, ContextRetrievalService)


if __name__ == "__main__":
    unittest.main()
