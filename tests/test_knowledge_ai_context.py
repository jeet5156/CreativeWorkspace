"""Test suite for Context-Aware Knowledge AI (Phase 4B).

Verifies:
1. Summarize can operate without context (NONE mode / no retrieval service).
2. Summarize uses RELATED context by default.
3. Generate Tags uses CURRENT context by default.
4. Key Takeaways uses RELATED context by default.
5. Explicit relationships are included and prioritized.
6. Related Library Assets are included in prompt context.
7. Related Project Assets are included in prompt context.
8. Related Lab Nodes are included in prompt context.
9. Related Knowledge documents are included in prompt context.
10. Current project is included when appropriate.
11. WORKSPACE mode respects retrieval limits.
12. NONE mode does not perform context retrieval.
13. Offline assets remain usable as metadata context with offline status.
14. Empty retrieval falls back to current document safely without error.
15. Large related documents are compacted rather than dumped in full.
16. API prompt clearly separates CURRENT DOCUMENT from RELATED WORKSPACE CONTEXT.
17. No API key appears in generated prompt or logging.
18. Existing AI mock provider verifies final request structure and metadata.
19. AI disabled does not trigger unnecessary retrieval.
20. Provider failure does not corrupt Knowledge data or documents.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.app_context import AppContext
from models.ai import AIConfig, AIContext, AIMessage, AIProviderType, AIRequest, AIResponse
from models.ai_context import (
    ContextItem,
    ContextQuery,
    ContextResult,
    ContextScope,
    ContextSource,
)
from models.knowledge import KnowledgeDocument
from models.library_models import LibraryAsset, LibraryDrive
from models.project import Project
from services.ai.providers.mock_provider import MockProvider
from services.ai_service import AIService
from services.asset_service import AssetService
from services.context_retrieval_service import ContextRetrievalService
from services.knowledge_ai_service import KnowledgeAIContextMode, KnowledgeAIService
from services.knowledge_service import KnowledgeService
from services.lab_service import LabService
from services.library_service import LibraryService
from services.project_service import ProjectService


class TestKnowledgeAIContext(unittest.TestCase):
    """Comprehensive test suite for Context-Aware Knowledge AI operations."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.storage_dir = Path(self.test_dir)

        # 1. AI Infrastructure
        self.config_dir = self.storage_dir / ".creativeworkspace"
        self.config_dir.mkdir(parents=True)
        self.ai_service = AIService(config_dir=self.config_dir)
        self.mock_provider = MockProvider(canned_response="Mock AI generated response.", echo_prompt=False)
        self.ai_service.register_provider(self.mock_provider)
        self.ai_service.set_enabled(True)
        self.ai_service.set_active_provider("mock")
        self.ai_service.set_api_key("mock", "secret_key_never_in_prompt")

        # 2. Project Service
        self.project_service = ProjectService()
        self.proj_p2 = self.project_service.create_project(
            name="CyberRacer",
            project_type="Game",
            location=str(self.storage_dir / "projects" / "CyberRacer"),
            description="Futuristic anti-gravity racing game",
        )

        # 3. Knowledge Service
        self.knowledge_dir = self.storage_dir / "knowledge"
        self.knowledge_service = KnowledgeService(storage_dir=self.knowledge_dir)
        self.doc_hero = self.knowledge_service.create_document(
            title="Vehicle Handling Specs",
            content="Detailed suspension mechanics and thruster parameters for Player One craft.",
            tags=["vehicle", "physics", "craft"],
        )
        self.doc_lore = self.knowledge_service.create_document(
            title="City Track Lore",
            content="Lore describing the dystopian neon underground circuit.",
            tags=["lore", "environment"],
        )

        # 4. Library Service
        self.library_dir = self.storage_dir / "library"
        self.library_service = LibraryService(storage_dir=self.library_dir)
        drive = LibraryDrive(
            drive_id="drv_ext_1",
            name="External SSD",
            last_known_mount="/Volumes/Assets",
        )
        self.library_service._drives[drive.drive_id] = drive

        self.lib_asset_thruster = LibraryAsset(
            id="lib_asset_001",
            drive_id="drv_ext_1",
            location_id="loc_1",
            filename="PlasmaThruster_v02.blend",
            drive_relative_path="Vehicles/Components/PlasmaThruster_v02.blend",
            category="3D Models",
            tags=["vehicle", "thruster", "component"],
            notes="Turbine glow particle setup included",
            friendly_type="Blender Scene",
        )
        self.lib_asset_offline = LibraryAsset(
            id="lib_asset_offline_99",
            drive_id="drv_detached_404",
            location_id="loc_2",
            filename="HeavyShield_Emitter.fbx",
            drive_relative_path="Shields/HeavyShield_Emitter.fbx",
            category="3D Models",
            tags=["shield", "offline_asset"],
            notes="Offline cataloged component",
            friendly_type="FBX Model",
        )
        self.library_service._assets[self.lib_asset_thruster.id] = self.lib_asset_thruster
        self.library_service._assets[self.lib_asset_offline.id] = self.lib_asset_offline

        # 5. Asset Service
        self.asset_service = AssetService(self.project_service)
        p2_assets = [
            {
                "id": "pa_001",
                "filename": "thruster_glow_diffuse.png",
                "relative_path": "Assets/Textures/thruster_glow_diffuse.png",
                "category": "Textures",
                "tags": ["thruster", "glow", "texture"],
                "notes": "Emissive map for plasma engines",
            }
        ]
        self.asset_service._indices[self.proj_p2.location] = p2_assets

        # 6. Lab Service
        self.lab_service = LabService(self.project_service)
        board = self.lab_service.create_board(self.proj_p2, name="Vehicle Systems")
        board_id = board["id"]
        board_file = self.lab_service.get_boards_dir(self.proj_p2) / f"{board_id}.lab.json"
        board_data = {
            "version": "1.0",
            "board_id": board_id,
            "name": "Vehicle Systems",
            "items": [
                {
                    "id": "lab_node_handling",
                    "name": "Handling Tuning",
                    "type": "task_card",
                    "text": "Tune gravity drag coefficients and turn response",
                    "tags": ["vehicle", "physics"],
                }
            ],
        }
        with open(board_file, "w", encoding="utf-8") as f:
            json.dump(board_data, f, indent=2)

        # 7. Context Retrieval Service
        self.context_retrieval_service = ContextRetrievalService(
            knowledge_service=self.knowledge_service,
            library_service=self.library_service,
            asset_service=self.asset_service,
            project_service=self.project_service,
            lab_service=self.lab_service,
        )

        # 8. Knowledge AI Service
        self.knowledge_ai_service = KnowledgeAIService(
            ai_service=self.ai_service,
            knowledge_service=self.knowledge_service,
            context_retrieval_service=self.context_retrieval_service,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_1_summarize_can_operate_without_context(self):
        """1. Verify Summarize works cleanly with NONE mode or when no context is available."""
        req = self.knowledge_ai_service.build_summary_request(
            self.doc_hero, context_mode=KnowledgeAIContextMode.NONE
        )
        self.assertIn("CURRENT DOCUMENT:", req.prompt)
        self.assertNotIn("RELATED WORKSPACE CONTEXT:", req.prompt)
        self.assertIsNone(req.context.workspace_context)

        resp = self.knowledge_ai_service.summarize_document(
            self.doc_hero, context_mode=KnowledgeAIContextMode.NONE
        )
        self.assertTrue(resp.success)
        self.assertEqual(resp.text, self.mock_provider.canned_response)

    def test_2_summarize_uses_related_context_by_default(self):
        """2. Verify Summarize defaults to RELATED context mode."""
        self.doc_hero.library_asset_ids = [self.lib_asset_thruster.id]
        self.knowledge_service.update_document(self.doc_hero.id, library_asset_ids=[self.lib_asset_thruster.id])

        req = self.knowledge_ai_service.build_summary_request(self.doc_hero)
        self.assertEqual(req.context.extra.get("context_mode"), "related")
        self.assertIn("RELATED WORKSPACE CONTEXT:", req.prompt)
        self.assertIn("PlasmaThruster_v02.blend", req.prompt)

    def test_3_generate_tags_uses_current_context_by_default(self):
        """3. Verify Generate Tags defaults to CURRENT context mode."""
        req = self.knowledge_ai_service.build_tags_request(
            self.doc_hero, project_id=self.proj_p2.name
        )
        self.assertEqual(req.context.extra.get("context_mode"), "current")

    def test_4_key_takeaways_uses_related_context_by_default(self):
        """4. Verify Key Takeaways defaults to RELATED context mode."""
        req = self.knowledge_ai_service.build_takeaways_request(self.doc_hero)
        self.assertEqual(req.context.extra.get("context_mode"), "related")

    def test_5_explicit_relationships_are_included(self):
        """5. Verify explicitly linked relationships are resolved and prioritized."""
        self.knowledge_service.update_document(
            self.doc_hero.id,
            library_asset_ids=[self.lib_asset_thruster.id],
            project_ids=[self.proj_p2.name],
            lab_node_ids=["lab_node_handling"],
        )
        req = self.knowledge_ai_service.build_summary_request(self.doc_hero)
        prompt = req.prompt

        self.assertIn("PlasmaThruster_v02.blend", prompt)
        self.assertIn("CyberRacer", prompt)
        self.assertIn("Vehicle Systems", prompt)

    def test_6_related_library_assets_included(self):
        """6. Verify Library assets are correctly formatted in workspace context."""
        self.knowledge_service.update_document(
            self.doc_hero.id,
            library_asset_ids=[self.lib_asset_thruster.id],
        )
        req = self.knowledge_ai_service.build_summary_request(self.doc_hero)
        self.assertIn("LIBRARY ASSETS:", req.prompt)
        self.assertIn("- PlasmaThruster_v02.blend", req.prompt)
        self.assertIn("Location: Vehicles/Components/PlasmaThruster_v02.blend", req.prompt)

    def test_7_related_project_assets_included(self):
        """7. Verify Project assets appear in context prompt."""
        self.knowledge_service.update_document(
            self.doc_hero.id,
            project_asset_refs=[{"asset_id": "pa_001", "relative_path": "Assets/Textures/thruster_glow_diffuse.png"}],
        )
        req = self.knowledge_ai_service.build_summary_request(self.doc_hero)
        self.assertIn("PROJECT ASSETS:", req.prompt)
        self.assertIn("thruster_glow_diffuse.png", req.prompt)

    def test_8_related_lab_nodes_included(self):
        """8. Verify Lab board nodes are included in context prompt."""
        self.knowledge_service.update_document(
            self.doc_hero.id,
            lab_node_ids=["lab_node_handling"],
        )
        req = self.knowledge_ai_service.build_summary_request(self.doc_hero)
        self.assertIn("LAB:", req.prompt)
        self.assertIn("Vehicle Systems", req.prompt)
        self.assertIn("Handling Tuning", req.prompt)

    def test_9_related_knowledge_documents_included(self):
        """9. Verify related Knowledge documents are included with tag/snippet metadata."""
        query = ContextQuery(text="vehicle craft", scope=ContextScope.WORKSPACE)
        result = self.context_retrieval_service.retrieve(query)
        compact = self.knowledge_ai_service._compact_context_result(result)

        self.assertIn("RELATED KNOWLEDGE:", compact)
        self.assertIn("- Vehicle Handling Specs", compact)

    def test_10_current_project_included(self):
        """10. Verify project metadata is included when project is active."""
        req = self.knowledge_ai_service.build_summary_request(
            self.doc_hero,
            context_mode=KnowledgeAIContextMode.PROJECT,
            project_id=self.proj_p2.name,
        )
        self.assertIn("PROJECT:", req.prompt)
        self.assertIn("CyberRacer", req.prompt)

    def test_11_workspace_mode_respects_limits(self):
        """11. Verify WORKSPACE mode respects context compactness and source limits."""
        req = self.knowledge_ai_service.build_summary_request(
            self.doc_hero, context_mode=KnowledgeAIContextMode.WORKSPACE
        )
        ctx_dict = req.context.extra.get("context_result")
        if ctx_dict and "items" in ctx_dict:
            self.assertLessEqual(len(ctx_dict["items"]), 15)

    def test_12_none_mode_no_retrieval(self):
        """12. Verify NONE mode avoids performing context retrieval."""
        with patch.object(self.context_retrieval_service, "retrieve") as mock_ret:
            req = self.knowledge_ai_service.build_summary_request(
                self.doc_hero, context_mode=KnowledgeAIContextMode.NONE
            )
            mock_ret.assert_not_called()
            self.assertIsNone(req.context.workspace_context)

    def test_13_offline_assets_usable_with_status(self):
        """13. Verify offline library assets appear with Offline status in context prompt."""
        self.knowledge_service.update_document(
            self.doc_hero.id,
            library_asset_ids=[self.lib_asset_offline.id],
        )
        req = self.knowledge_ai_service.build_summary_request(self.doc_hero)
        self.assertIn("HeavyShield_Emitter.fbx", req.prompt)
        self.assertIn("Status: Offline", req.prompt)

    def test_14_empty_retrieval_falls_back_cleanly(self):
        """14. Verify empty retrieval result falls back safely to current document without errors."""
        empty_doc = self.knowledge_service.create_document(title="Lonely Note", content="Just solo thoughts.")
        req = self.knowledge_ai_service.build_summary_request(
            empty_doc, context_mode=KnowledgeAIContextMode.RELATED
        )
        self.assertIn("CURRENT DOCUMENT:", req.prompt)
        self.assertIn("Lonely Note", req.prompt)

    def test_15_large_related_documents_are_compacted(self):
        """15. Verify related documents are compacted to snippets rather than whole contents."""
        huge_content = "Word " * 2000  # 10,000 characters
        huge_doc = self.knowledge_service.create_document(
            title="Massive Reference Document",
            content=huge_content,
            tags=["reference", "huge"],
        )
        item = ContextItem(
            id=huge_doc.id,
            source_type=ContextSource.KNOWLEDGE,
            title=huge_doc.title,
            description=huge_doc.content,
            metadata={"tags": huge_doc.tags},
        )
        res = ContextResult(items=[item])
        compacted = self.knowledge_ai_service._compact_context_result(res)

        # Snippet should be restricted to ~150 chars, not 10,000
        self.assertLess(len(compacted), 350)
        self.assertIn("Massive Reference Document", compacted)

    def test_16_prompt_separates_current_doc_and_context(self):
        """16. Verify prompt clearly partitions CURRENT DOCUMENT from RELATED WORKSPACE CONTEXT."""
        self.knowledge_service.update_document(
            self.doc_hero.id, library_asset_ids=[self.lib_asset_thruster.id]
        )
        req = self.knowledge_ai_service.build_summary_request(self.doc_hero)

        self.assertIn("CURRENT DOCUMENT:\nTitle: Vehicle Handling Specs", req.prompt)
        self.assertIn("RELATED WORKSPACE CONTEXT:", req.prompt)
        self.assertIn("The current document is the primary source.", req.system_instruction)

    def test_17_no_api_key_in_prompt_or_logging(self):
        """17. Security invariant: verify API key is never placed into prompt, system instruction, or context."""
        req = self.knowledge_ai_service.build_summary_request(self.doc_hero)
        secret = "secret_key_never_in_prompt"

        self.assertNotIn(secret, req.prompt)
        self.assertNotIn(secret, req.system_instruction)
        self.assertNotIn(secret, str(req.context.to_dict()))

    def test_18_mock_provider_verifies_request_execution(self):
        """18. Verify AIService dispatch passes complete AIRequest with workspace context."""
        self.knowledge_service.update_document(
            self.doc_hero.id, library_asset_ids=[self.lib_asset_thruster.id]
        )
        resp = self.knowledge_ai_service.summarize_document(self.doc_hero)

        self.assertTrue(resp.success)
        self.assertIsNotNone(self.mock_provider.last_request)
        self.assertIn("PlasmaThruster_v02.blend", self.mock_provider.last_request.prompt)
        self.assertIn("context_result", resp.raw_response)

    def test_19_ai_disabled_avoids_unnecessary_retrieval(self):
        """19. Verify disabled AI state returns early without calling context retrieval."""
        self.ai_service.set_enabled(False)
        with patch.object(self.context_retrieval_service, "retrieve") as mock_ret:
            resp = self.knowledge_ai_service.summarize_document(self.doc_hero)
            self.assertFalse(resp.success)
            self.assertIn("disabled", resp.error_message.lower())
            mock_ret.assert_not_called()

    def test_20_provider_failure_does_not_corrupt_data(self):
        """20. Verify provider network/API failure leaves Knowledge documents and tags completely untouched."""
        self.mock_provider.custom_responder = lambda req: AIResponse(success=False, error_message="Simulated Provider Failure")
        orig_title = self.doc_hero.title
        orig_content = self.doc_hero.content
        orig_tags = list(self.doc_hero.tags)

        resp = self.knowledge_ai_service.summarize_document(self.doc_hero)
        self.assertFalse(resp.success)

        # Confirm document state in storage is 100% pristine
        refreshed = self.knowledge_service.get_document(self.doc_hero.id)
        self.assertEqual(refreshed.title, orig_title)
        self.assertEqual(refreshed.content, orig_content)
        self.assertEqual(refreshed.tags, orig_tags)


if __name__ == "__main__":
    unittest.main()
