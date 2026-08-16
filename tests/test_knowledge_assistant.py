"""Test suite for Knowledge AI Assistant / Ask AI (Phase 4C).

Verifies:
1. Basic free-form question execution with MockProvider.
2. User question is passed into ContextQuery for question-driven retrieval.
3. Related context is retrieved and formatted into the prompt.
4. Current document is prioritized as primary subject.
5. Explicit relationships are included and prioritized.
6. Project context is included.
7. Library assets are included with path and metadata.
8. Project assets are included.
9. Lab nodes and boards are included.
10. Related Knowledge notes are included with snippets.
11. Offline library assets are represented accurately with Offline status.
12. Empty retrieval safely falls back to grounded current subject.
13. NONE mode avoids context retrieval.
14. Follow-up questions preserve multi-turn conversation history.
15. Conversation history is strictly bounded in-memory.
16. Primary subject is preserved across follow-ups and resets on subject change.
17. WORKSPACE mode respects context compactness and source limits.
18. Large context documents are compacted rather than dumped in full.
19. Prompt cleanly partitions SYSTEM INSTRUCTION, SUBJECT, HISTORY, WORKSPACE CONTEXT, QUESTION.
20. Security invariant: Prompt contains no API keys or credentials.
21. AI disabled state returns early without calling context retrieval.
22. Provider errors are handled safely without corrupting note data.
23. Architectural invariant: No filesystem-wide scanning (os.walk) occurs.
24. Synchronous and Asynchronous execution paths work flawlessly.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.app_context import AppContext
from models.ai import AIConfig, AIContext, AIMessage, AIRequest, AIResponse
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
from services.knowledge_ai_service import KnowledgeAIContextMode
from services.knowledge_assistant_service import KnowledgeAssistantService
from services.knowledge_service import KnowledgeService
from services.lab_service import LabService
from services.library_service import LibraryService
from services.project_service import ProjectService


class TestKnowledgeAssistant(unittest.TestCase):
    """Test suite covering Knowledge Assistant Q&A and question-driven context retrieval."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.storage_dir = Path(self.test_dir)

        # 1. AI Infrastructure
        self.config_dir = self.storage_dir / ".creativeworkspace"
        self.config_dir.mkdir(parents=True)
        self.ai_service = AIService(config_dir=self.config_dir)
        self.mock_provider = MockProvider(canned_response="The CyberRacer engine utilizes dual plasma thrusters.", echo_prompt=False)
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
            description="Futuristic high-speed racing title",
        )

        # 3. Knowledge Service
        self.knowledge_dir = self.storage_dir / "knowledge"
        self.knowledge_service = KnowledgeService(storage_dir=self.knowledge_dir)
        self.doc_vehicle = self.knowledge_service.create_document(
            title="CyberRacer Propulsion System",
            content="Propulsion specs for the main vehicle chassis, detailing heat dissipation.",
            tags=["vehicle", "propulsion", "cyberracer"],
        )
        self.doc_pilot = self.knowledge_service.create_document(
            title="Pilot Roster",
            content="Biographical profiles of competing anti-gravity racers.",
            tags=["pilot", "character"],
        )

        # 4. Library Service
        self.library_dir = self.storage_dir / "library"
        self.library_service = LibraryService(storage_dir=self.library_dir)
        drive = LibraryDrive(
            drive_id="drv_ext_1",
            name="External SSD",
            last_known_mount="/mnt/fast_ssd",
        )
        self.library_service._drives[drive.drive_id] = drive

        self.lib_asset_chassis = LibraryAsset(
            id="lib_asset_chassis_01",
            drive_id="drv_ext_1",
            location_id="loc_1",
            filename="CyberRacer_Chassis_v04.blend",
            drive_relative_path="Vehicles/Chassis/CyberRacer_Chassis_v04.blend",
            category="3D Models",
            tags=["cyberracer", "vehicle", "chassis"],
            notes="Low-drag aerodynamic body model",
            friendly_type="Blender Scene",
        )
        self.lib_asset_offline = LibraryAsset(
            id="lib_asset_offline_99",
            drive_id="drv_detached_404",
            location_id="loc_2",
            filename="NitroTurbine_Special.fbx",
            drive_relative_path="Engines/NitroTurbine_Special.fbx",
            category="3D Models",
            tags=["engine", "turbo"],
            notes="Offline experimental booster",
            friendly_type="FBX Model",
        )
        self.library_service._assets[self.lib_asset_chassis.id] = self.lib_asset_chassis
        self.library_service._assets[self.lib_asset_offline.id] = self.lib_asset_offline

        # 5. Asset Service
        self.asset_service = AssetService(self.project_service)
        p2_assets = [
            {
                "id": "pa_001",
                "filename": "propulsion_heat_map.png",
                "relative_path": "Assets/Textures/propulsion_heat_map.png",
                "category": "Textures",
                "tags": ["propulsion", "thermal", "texture"],
                "notes": "Thermal emission texture map",
            }
        ]
        self.asset_service._indices[self.proj_p2.location] = p2_assets

        # 6. Lab Service
        self.lab_service = LabService(self.project_service)
        board = self.lab_service.create_board(self.proj_p2, name="Engine Development")
        board_id = board["id"]
        board_file = self.lab_service.get_boards_dir(self.proj_p2) / f"{board_id}.lab.json"
        board_data = {
            "version": "1.0",
            "board_id": board_id,
            "name": "Engine Development",
            "items": [
                {
                    "id": "lab_node_turbines",
                    "name": "Turbine Calibration",
                    "type": "task_card",
                    "text": "Calibrate plasma injection curve for peak thrust",
                    "tags": ["engine", "thrust"],
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

        # 8. Knowledge Assistant Service
        self.assistant_service = KnowledgeAssistantService(
            ai_service=self.ai_service,
            knowledge_service=self.knowledge_service,
            context_retrieval_service=self.context_retrieval_service,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_1_basic_question_works(self):
        """1. Verify Ask AI returns a successful response via MockProvider."""
        resp = self.assistant_service.ask(
            question="What propulsion system is used?",
            document=self.doc_vehicle,
        )
        self.assertTrue(resp.success)
        self.assertEqual(resp.text, self.mock_provider.canned_response)

    def test_2_question_passed_into_context_query(self):
        """2. Verify the exact user question drives the ContextQuery."""
        with patch.object(self.context_retrieval_service, "retrieve", wraps=self.context_retrieval_service.retrieve) as mock_ret:
            self.assistant_service.ask(
                question="What thermal textures exist for propulsion?",
                document=self.doc_vehicle,
            )
            mock_ret.assert_called_once()
            called_query: ContextQuery = mock_ret.call_args[0][0]
            self.assertEqual(called_query.text, "What thermal textures exist for propulsion?")

    def test_3_related_context_retrieved_and_formatted(self):
        """3. Verify retrieved context is partitioned and included in the prompt."""
        self.knowledge_service.update_document(
            self.doc_vehicle.id,
            library_asset_ids=[self.lib_asset_chassis.id],
        )
        req = self.assistant_service.build_ask_request(
            question="What models are used?",
            document=self.doc_vehicle,
        )
        self.assertIn("WORKSPACE CONTEXT:", req.prompt)
        self.assertIn("CyberRacer_Chassis_v04.blend", req.prompt)

    def test_4_current_document_is_prioritized(self):
        """4. Verify current document is framed as the primary subject anchor."""
        req = self.assistant_service.build_ask_request(
            question="Summarize this note",
            document=self.doc_vehicle,
        )
        self.assertIn("CURRENT DOCUMENT (PRIMARY SUBJECT):", req.prompt)
        self.assertIn("CyberRacer Propulsion System", req.prompt)

    def test_5_explicit_relationships_prioritized(self):
        """5. Verify explicit relationships from the document receive priority."""
        self.knowledge_service.update_document(
            self.doc_vehicle.id,
            library_asset_ids=[self.lib_asset_chassis.id],
            project_ids=[self.proj_p2.name],
            lab_node_ids=["lab_node_turbines"],
        )
        req = self.assistant_service.build_ask_request(
            question="What is linked to this system?",
            document=self.doc_vehicle,
        )
        prompt = req.prompt
        self.assertIn("CyberRacer_Chassis_v04.blend", prompt)
        self.assertIn("CyberRacer", prompt)
        self.assertIn("Turbine Calibration", prompt)

    def test_6_project_context_included(self):
        """6. Verify project metadata is included in workspace context."""
        req = self.assistant_service.build_ask_request(
            question="What project is this for?",
            document=self.doc_vehicle,
            project_id=self.proj_p2.name,
            context_mode=KnowledgeAIContextMode.PROJECT,
        )
        self.assertIn("PROJECT:", req.prompt)
        self.assertIn("CyberRacer", req.prompt)

    def test_7_library_assets_included(self):
        """7. Verify Library assets appear with file paths in context."""
        self.knowledge_service.update_document(
            self.doc_vehicle.id,
            library_asset_ids=[self.lib_asset_chassis.id],
        )
        req = self.assistant_service.build_ask_request(
            question="Which 3D asset corresponds to the chassis?",
            document=self.doc_vehicle,
        )
        self.assertIn("LIBRARY ASSETS:", req.prompt)
        self.assertIn("CyberRacer_Chassis_v04.blend", req.prompt)
        self.assertIn("Location: Vehicles/Chassis/CyberRacer_Chassis_v04.blend", req.prompt)

    def test_8_project_assets_included(self):
        """8. Verify project-local assets appear in context."""
        self.knowledge_service.update_document(
            self.doc_vehicle.id,
            project_asset_refs=[{"asset_id": "pa_001", "relative_path": "Assets/Textures/propulsion_heat_map.png"}],
        )
        req = self.assistant_service.build_ask_request(
            question="What textures do we have?",
            document=self.doc_vehicle,
        )
        self.assertIn("PROJECT ASSETS:", req.prompt)
        self.assertIn("propulsion_heat_map.png", req.prompt)

    def test_9_lab_nodes_included(self):
        """9. Verify Lab boards and nodes are included in context."""
        self.knowledge_service.update_document(
            self.doc_vehicle.id,
            lab_node_ids=["lab_node_turbines"],
        )
        req = self.assistant_service.build_ask_request(
            question="What engine tasks are in Lab?",
            document=self.doc_vehicle,
        )
        self.assertIn("LAB:", req.prompt)
        self.assertIn("Engine Development", req.prompt)
        self.assertIn("Turbine Calibration", req.prompt)

    def test_10_related_knowledge_notes_included(self):
        """10. Verify related Knowledge documents appear with tag/snippet metadata."""
        query = ContextQuery(text="Propulsion heat dissipation", scope=ContextScope.WORKSPACE)
        result = self.context_retrieval_service.retrieve(query)
        compact = self.assistant_service._compact_context_result(result)
        self.assertIn("RELATED KNOWLEDGE:", compact)
        self.assertIn("CyberRacer Propulsion System", compact)

    def test_11_offline_assets_represented_correctly(self):
        """11. Verify offline assets are included with Offline status without error."""
        self.knowledge_service.update_document(
            self.doc_vehicle.id,
            library_asset_ids=[self.lib_asset_offline.id],
        )
        req = self.assistant_service.build_ask_request(
            question="What turbo boosters are available?",
            document=self.doc_vehicle,
        )
        self.assertIn("NitroTurbine_Special.fbx", req.prompt)
        self.assertIn("Status: Offline", req.prompt)

    def test_12_empty_retrieval_grounded_response(self):
        """12. Verify empty context retrieval falls back cleanly to the current document."""
        isolated_doc = self.knowledge_service.create_document(title="Secret Recipe", content="Flour and sugar.")
        req = self.assistant_service.build_ask_request(
            question="What ingredients are listed?",
            document=isolated_doc,
        )
        self.assertIn("CURRENT DOCUMENT (PRIMARY SUBJECT):", req.prompt)
        self.assertIn("Secret Recipe", req.prompt)
        self.assertNotIn("WORKSPACE CONTEXT:", req.prompt)

    def test_13_none_mode_no_retrieval(self):
        """13. Verify NONE mode bypasses context retrieval entirely."""
        with patch.object(self.context_retrieval_service, "retrieve") as mock_ret:
            req = self.assistant_service.build_ask_request(
                question="What is the title?",
                document=self.doc_vehicle,
                context_mode=KnowledgeAIContextMode.NONE,
            )
            mock_ret.assert_not_called()
            self.assertIsNone(req.context.workspace_context)

    def test_14_followup_preserves_conversation_history(self):
        """14. Verify multi-turn follow-up questions include prior conversation in prompt."""
        # Turn 1
        resp1 = self.assistant_service.ask(
            question="What assets are associated with this craft?",
            document=self.doc_vehicle,
        )
        self.assertTrue(resp1.success)

        # Turn 2
        req2 = self.assistant_service.build_ask_request(
            question="Which one is the latest version?",
            document=self.doc_vehicle,
        )
        prompt2 = req2.prompt
        self.assertIn("CONVERSATION HISTORY:", prompt2)
        self.assertIn("User: What assets are associated with this craft?", prompt2)
        self.assertIn("Assistant: The CyberRacer engine utilizes dual plasma thrusters.", prompt2)
        self.assertIn("USER QUESTION:\nWhich one is the latest version?", prompt2)

    def test_15_conversation_history_is_bounded(self):
        """15. Verify history does not grow unbounded beyond MAX_HISTORY_MESSAGES."""
        for i in range(15):
            self.assistant_service.add_history_message("user", f"Question {i}")
            self.assistant_service.add_history_message("assistant", f"Answer {i}")

        hist = self.assistant_service.get_history()
        self.assertEqual(len(hist), KnowledgeAssistantService.MAX_HISTORY_MESSAGES)
        # Should retain the most recent message
        self.assertEqual(hist[-1].content, "Answer 14")

    def test_16_primary_subject_preserved_and_resets_on_change(self):
        """16. Verify primary subject is tracked and resets conversation on switch."""
        self.assistant_service.set_primary_subject("knowledge", self.doc_vehicle.id)
        self.assistant_service.add_history_message("user", "First question on vehicle")
        self.assertEqual(len(self.assistant_service.get_history()), 1)

        # Same subject: keeps history
        self.assistant_service.set_primary_subject("knowledge", self.doc_vehicle.id)
        self.assertEqual(len(self.assistant_service.get_history()), 1)

        # Different subject: resets history
        self.assistant_service.set_primary_subject("knowledge", self.doc_pilot.id)
        self.assertEqual(len(self.assistant_service.get_history()), 0)

    def test_17_workspace_mode_respects_limits(self):
        """17. Verify WORKSPACE mode query respects maximum candidate limits."""
        req = self.assistant_service.build_ask_request(
            question="List all files in workspace",
            document=self.doc_vehicle,
            context_mode=KnowledgeAIContextMode.WORKSPACE,
        )
        ctx_dict = req.context.extra.get("context_result")
        if ctx_dict and "items" in ctx_dict:
            self.assertLessEqual(len(ctx_dict["items"]), 15)

    def test_18_large_context_is_compacted(self):
        """18. Verify large note descriptions are truncated to compact snippets in context."""
        huge_doc = self.knowledge_service.create_document(
            title="Massive Lore Codex",
            content="Lore " * 3000,
        )
        item = ContextItem(
            id=huge_doc.id,
            source_type=ContextSource.KNOWLEDGE,
            title=huge_doc.title,
            description=huge_doc.content,
        )
        res = ContextResult(items=[item])
        compact = self.assistant_service._compact_context_result(res)
        self.assertLess(len(compact), 300)
        self.assertIn("Massive Lore Codex", compact)

    def test_19_prompt_partitions_sections_clearly(self):
        """19. Verify prompt structure cleanly demarcates instruction, subject, context, question."""
        self.assistant_service.add_history_message("user", "Prior question")
        self.assistant_service.add_history_message("assistant", "Prior answer")

        req = self.assistant_service.build_ask_request(
            question="New question?",
            document=self.doc_vehicle,
        )
        prompt = req.prompt
        self.assertIn("CURRENT DOCUMENT (PRIMARY SUBJECT):", prompt)
        self.assertIn("CONVERSATION HISTORY:", prompt)
        self.assertIn("USER QUESTION:\nNew question?", prompt)
        self.assertIn("Do not invent assets, projects, files, nodes, relationships, or facts.", req.system_instruction)

    def test_20_prompt_contains_no_api_credentials(self):
        """20. Security invariant: API key is never exposed in prompt, context, or instruction."""
        req = self.assistant_service.build_ask_request(
            question="Test credentials exposure",
            document=self.doc_vehicle,
        )
        secret = "secret_key_never_in_prompt"
        self.assertNotIn(secret, req.prompt)
        self.assertNotIn(secret, req.system_instruction)
        self.assertNotIn(secret, str(req.context.to_dict()))

    def test_21_ai_disabled_avoids_unnecessary_retrieval(self):
        """21. Verify disabled AI state returns clean error without invoking retrieval."""
        self.ai_service.set_enabled(False)
        with patch.object(self.context_retrieval_service, "retrieve") as mock_ret:
            resp = self.assistant_service.ask("Test question", document=self.doc_vehicle)
            self.assertFalse(resp.success)
            self.assertTrue("disabled" in resp.error_message.lower() or "not configured" in resp.error_message.lower())
            mock_ret.assert_not_called()

    def test_22_provider_errors_handled_safely(self):
        """22. Verify provider errors are handled gracefully without corrupting document."""
        self.mock_provider.custom_responder = lambda req: AIResponse(success=False, error_message="API Rate Limit")
        orig_content = self.doc_vehicle.content

        resp = self.assistant_service.ask("Question during error", document=self.doc_vehicle)
        self.assertFalse(resp.success)
        self.assertIn("API Rate Limit", resp.error_message)

        # Document unmodified
        refreshed = self.knowledge_service.get_document(self.doc_vehicle.id)
        self.assertEqual(refreshed.content, orig_content)

    def test_23_no_filesystem_wide_scan_occurs(self):
        """23. Architectural Invariant: Verify os.walk is never called during Ask AI operations."""
        with patch("os.walk") as mock_walk:
            mock_walk.side_effect = AssertionError("os.walk should NEVER be called during Ask AI!")
            resp = self.assistant_service.ask(
                question="Search all assets and projects",
                document=self.doc_vehicle,
                context_mode=KnowledgeAIContextMode.WORKSPACE,
            )
            self.assertTrue(resp.success)
            mock_walk.assert_not_called()

    def test_24_async_ask_execution(self):
        """24. Verify asynchronous ask_async generates response and executes callback."""
        finished_called = []
        error_called = []

        def _on_finished(q, resp):
            finished_called.append((q, resp))

        def _on_error(err):
            error_called.append(err)

        worker = self.assistant_service.ask_async(
            question="Async question?",
            on_finished=_on_finished,
            on_error=_on_error,
            document=self.doc_vehicle,
        )
        self.assertIsNotNone(worker)

        # Execute worker synchronously for test verification
        worker.run()

        self.assertEqual(len(finished_called), 1)
        q, resp = finished_called[0]
        self.assertEqual(q, "Async question?")
        self.assertTrue(resp.success)
        self.assertEqual(len(error_called), 0)


if __name__ == "__main__":
    unittest.main()
