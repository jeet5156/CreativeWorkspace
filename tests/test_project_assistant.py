"""Unit and Integration tests for ProjectAssistantService (Phase 5B)."""

import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import shutil

from models.project import Project
from models.project_context import (
    ProjectContext,
    ProjectAssetSummary,
    ProjectLibrarySummary,
    ProjectKnowledgeSummary,
    ProjectLabSummary,
    ProjectAvailabilitySummary,
    ProjectVersionSummary,
)
from models.project_assistant import (
    ProjectSourceType,
    TraceableSourceItem,
    ProjectAssistantResponse,
)
from models.ai import AIConfig, AIResponse
from services.ai_service import AIService
from services.ai.providers.mock_provider import MockProvider
from services.project_context_service import ProjectContextService
from services.project_assistant_service import ProjectAssistantService


class TestProjectAssistant(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_proj_asst_")

        # 1. Setup AIService with MockProvider
        self.ai_service = AIService(config_dir=Path(self.temp_dir) / "ai_cfg")
        self.ai_service.set_enabled(True)
        self.ai_service.set_active_provider("mock")

        # 2. Setup mock ProjectContextService
        self.project_context_service = MagicMock(spec=ProjectContextService)

        # 3. Build sample ProjectContext
        self.sample_context = ProjectContext(
            project_name="CyberRacer",
            project_path=str(Path(self.temp_dir) / "CyberRacer"),
            project_type="game",
            metadata={
                "priority": "high",
                "status": "active",
                "client": "Futuristic Studios",
                "deadline": "2026-12-31",
                "tags": ["cyberpunk", "racing", "unreal"],
                "description": "High-speed cyberpunk racing game in Neo Tokyo.",
            },
            asset_summary=ProjectAssetSummary(
                total_assets=14,
                by_category={"3D Models": 6, "Textures": 8},
                lod_counts={"LOD0": 2, "LOD1": 2},
                version_groups=[
                    {
                        "logical_name": "Hero_Vehicle",
                        "versions": ["v001", "v002", "v003"],
                        "latest": "v003",
                        "count": 3,
                    },
                    {
                        "logical_name": "Pilot_Character",
                        "versions": ["v001", "v002"],
                        "latest": "v002",
                        "count": 2,
                    },
                ],
            ),
            library_summary=ProjectLibrarySummary(
                total_linked_assets=4,
                available_assets=2,
                offline_assets=2,
                missing_assets=0,
                possibly_changed_assets=0,
                linked_assets=[
                    {
                        "id": "lib_ref_off_1",
                        "library_asset_id": "asset_neon_signs",
                        "filename": "NeoTokyo_Signs_Kit.fbx",
                        "drive_id": "EXT_DRIVE_A",
                        "drive_relative_path": "props/NeoTokyo_Signs_Kit.fbx",
                        "is_online": False,
                        "availability_status": "offline",
                    },
                    {
                        "id": "lib_ref_off_2",
                        "library_asset_id": "asset_engine_audio",
                        "filename": "Hover_Engine_Loop.wav",
                        "drive_id": "AUDIO_DRIVE_1",
                        "drive_relative_path": "sfx/Hover_Engine_Loop.wav",
                        "is_online": False,
                        "availability_status": "offline",
                    },
                ],
            ),
            availability_summary=ProjectAvailabilitySummary(
                online_library_assets=2,
                offline_library_assets=2,
                missing_library_assets=0,
                possibly_changed_assets=0,
            ),
            knowledge_summary=ProjectKnowledgeSummary(
                total_notes=2,
                favorite_notes=1,
                recent_notes=[
                    {
                        "id": "doc_lore_1",
                        "title": "Neo Tokyo Lore Bible",
                        "is_favorite": True,
                        "tags": ["lore", "worldbuilding"],
                        "modified": "2026-08-15T12:00:00",
                    },
                    {
                        "id": "doc_char_1",
                        "title": "Pilot Character Backstory",
                        "is_favorite": False,
                        "tags": ["character"],
                        "modified": "2026-08-14T10:00:00",
                    },
                ],
            ),
            lab_summary=ProjectLabSummary(
                total_boards=1,
                total_nodes=5,
                recent_boards=[
                    {"id": "board_art_1", "name": "Art Direction Board", "node_count": 5}
                ],
                task_status={"total": 4, "completed": 2, "pending": 2},
            ),
        )

        self.project_context_service.get_project_context.return_value = self.sample_context

        # 4. Instantiate ProjectAssistantService
        self.service = ProjectAssistantService(
            ai_service=self.ai_service,
            project_context_service=self.project_context_service,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Models Serialization
    # -------------------------------------------------------------------------

    def test_01_model_serialization(self):
        """Test TraceableSourceItem and ProjectAssistantResponse serialization."""
        source = TraceableSourceItem(
            source_type=ProjectSourceType.LIBRARY_ASSET.value,
            title="NeoTokyo_Signs_Kit.fbx",
            target_id="asset_neon_signs",
            target_path="props/NeoTokyo_Signs_Kit.fbx",
            status="offline",
            badge="Offline (EXT_DRIVE_A)",
            metadata={"drive_id": "EXT_DRIVE_A"},
        )
        s_dict = source.to_dict()
        self.assertEqual(s_dict["title"], "NeoTokyo_Signs_Kit.fbx")
        self.assertEqual(s_dict["status"], "offline")

        restored_s = TraceableSourceItem.from_dict(s_dict)
        self.assertEqual(restored_s.target_id, "asset_neon_signs")
        self.assertEqual(restored_s.badge, "Offline (EXT_DRIVE_A)")

        resp = ProjectAssistantResponse(
            answer="There are 2 offline library assets on external drives.",
            sources=[source],
            project_name="CyberRacer",
            project_path="/projects/CyberRacer",
            success=True,
        )
        r_dict = resp.to_dict()
        self.assertEqual(len(r_dict["sources"]), 1)
        self.assertEqual(r_dict["project_name"], "CyberRacer")

        restored_resp = ProjectAssistantResponse.from_dict(r_dict)
        self.assertEqual(restored_resp.answer, resp.answer)
        self.assertEqual(len(restored_resp.sources), 1)

    # -------------------------------------------------------------------------
    # 2. Prompt Grounding on Project Context
    # -------------------------------------------------------------------------

    def test_02_prompt_grounding_contains_project_context(self):
        """Test prompt construction partitions and includes complete structured project context."""
        req, ctx = self.service.build_ask_request("What is this project about?", "CyberRacer")
        self.assertIsNotNone(req)
        self.assertEqual(ctx.project_name, "CyberRacer")

        prompt_str = req.prompt
        # Project identity
        self.assertIn("CyberRacer", prompt_str)
        self.assertIn("Futuristic Studios", prompt_str)
        self.assertIn("Neo Tokyo", prompt_str)

        # Asset & Version groups
        self.assertIn("Hero_Vehicle", prompt_str)
        self.assertIn("v003", prompt_str)
        self.assertIn("Pilot_Character", prompt_str)

        # Library references & Offline items
        self.assertIn("NeoTokyo_Signs_Kit.fbx", prompt_str)
        self.assertIn("EXT_DRIVE_A", prompt_str)
        self.assertIn("Hover_Engine_Loop.wav", prompt_str)
        self.assertIn("AUDIO_DRIVE_1", prompt_str)

        # Knowledge notes
        self.assertIn("Neo Tokyo Lore Bible", prompt_str)
        self.assertIn("Pilot Character Backstory", prompt_str)

        # Lab & Tasks
        self.assertIn("Art Direction Board", prompt_str)
        self.assertIn("2 completed / 4 total", prompt_str)

        # Question
        self.assertIn("What is this project about?", prompt_str)

    # -------------------------------------------------------------------------
    # 3. Synchronous Ask Q&A with Mock Provider
    # -------------------------------------------------------------------------

    def test_03_ask_with_mock_provider(self):
        """Test asking a question returns a structured ProjectAssistantResponse."""
        resp = self.service.ask("Which library assets are offline?", "CyberRacer")
        self.assertTrue(resp.success)
        self.assertIsNotNone(resp.answer)
        self.assertEqual(resp.project_name, "CyberRacer")
        self.assertGreaterEqual(len(resp.sources), 1)

    # -------------------------------------------------------------------------
    # 4. Traceable Source Attribution
    # -------------------------------------------------------------------------

    def test_04_traceable_source_attribution(self):
        """Test source extraction produces categorized, clickable TraceableSourceItem references."""
        answer = "The project has 2 offline library assets: NeoTokyo_Signs_Kit.fbx on EXT_DRIVE_A and Hover_Engine_Loop.wav. The latest Hero_Vehicle version is v003. Related notes include Neo Tokyo Lore Bible."
        sources = self.service.extract_traceable_sources("Which assets and notes are in this project?", answer, self.sample_context)

        # Project root
        has_proj = any(s.source_type == ProjectSourceType.PROJECT.value and "CyberRacer" in s.title for s in sources)
        self.assertTrue(has_proj)

        # Offline library assets
        has_neon = any(s.source_type == ProjectSourceType.LIBRARY_ASSET.value and "NeoTokyo_Signs_Kit.fbx" in s.title and s.status == "offline" for s in sources)
        self.assertTrue(has_neon)

        # Versioned asset
        has_vehicle = any(s.source_type == ProjectSourceType.ASSET.value and "Hero_Vehicle" in s.title for s in sources)
        self.assertTrue(has_vehicle)

        # Knowledge note
        has_lore = any(s.source_type == ProjectSourceType.KNOWLEDGE.value and "Neo Tokyo Lore Bible" in s.title for s in sources)
        self.assertTrue(has_lore)

    # -------------------------------------------------------------------------
    # 5. Conversation History Management
    # -------------------------------------------------------------------------

    def test_05_conversation_history_bounded_and_resets_on_project_switch(self):
        """Test conversation history stores turns up to limit and resets when switching project."""
        self.service.set_active_project("CyberRacer")
        self.service.add_history_message("user", "Q1")
        self.service.add_history_message("assistant", "A1")
        self.assertEqual(len(self.service.get_history()), 2)

        # Exceed MAX_HISTORY_MESSAGES
        for i in range(15):
            self.service.add_history_message("user", f"Q{i}")
            self.service.add_history_message("assistant", f"A{i}")

        self.assertLessEqual(len(self.service.get_history()), ProjectAssistantService.MAX_HISTORY_MESSAGES)

        # Switch project -> history resets
        self.service.set_active_project("SecondProject")
        self.assertEqual(len(self.service.get_history()), 0)

    # -------------------------------------------------------------------------
    # 6. Quick Starter Suggestions
    # -------------------------------------------------------------------------

    def test_06_quick_starter_suggestions(self):
        """Test tailored suggestions are generated from project context."""
        suggestions = self.service.get_quick_suggestions("CyberRacer")
        self.assertGreaterEqual(len(suggestions), 2)
        # Should include offline question because offline assets exist
        has_offline_q = any("offline" in s.lower() for s in suggestions)
        self.assertTrue(has_offline_q)

    # -------------------------------------------------------------------------
    # 7. Disabled AI State Handling
    # -------------------------------------------------------------------------

    def test_07_disabled_ai_state_handled_gracefully(self):
        """Test asking when AI is disabled returns clean friendly response."""
        self.ai_service.set_enabled(False)
        resp = self.service.ask("What is this project about?", "CyberRacer")
        self.assertFalse(resp.success)
        self.assertIn("disabled", resp.answer.lower())

    # -------------------------------------------------------------------------
    # 8. Provider Errors Handled Gracefully
    # -------------------------------------------------------------------------

    def test_08_provider_errors_handled_gracefully(self):
        """Test network or provider exception returns safe error response without crashing."""
        with patch.object(self.ai_service, "generate", return_value=AIResponse(success=False, error_message="API connection timed out")):
            resp = self.service.ask("What is this project about?", "CyberRacer")
            self.assertFalse(resp.success)
            self.assertIn("API connection timed out", resp.error_message)

    # -------------------------------------------------------------------------
    # 9. Invariant: Zero Drive Scans
    # -------------------------------------------------------------------------

    def test_09_no_external_drive_scans(self):
        """Architectural Invariant: ProjectAssistantService must never invoke os.walk or rglob."""
        with patch("os.walk") as mock_walk:
            resp = self.service.ask("What assets are in this project?", "CyberRacer")
            mock_walk.assert_not_called()
            self.assertTrue(resp.success)

    # -------------------------------------------------------------------------
    # 10. Security Invariant: No API Keys in Prompt
    # -------------------------------------------------------------------------

    def test_10_no_api_key_in_prompt(self):
        """Security Invariant: API keys must never appear in prompt or system instructions."""
        self.ai_service.set_api_key("openai", "sk-secret-project-key-12345")
        req, ctx = self.service.build_ask_request("Tell me about the project", "CyberRacer")
        self.assertNotIn("sk-secret-project-key-12345", req.prompt)
        self.assertNotIn("sk-secret-project-key-12345", req.system_instruction)

    # -------------------------------------------------------------------------
    # 11. High-Level Operations (Phase 5B Foundation)
    # -------------------------------------------------------------------------

    def test_11_summarize_project(self):
        """Test summarize_project executes grounded summary."""
        resp = self.service.summarize_project("CyberRacer")
        self.assertTrue(resp.success)
        self.assertIsNotNone(resp.answer)
        self.assertEqual(resp.project_name, "CyberRacer")

    def test_12_ask_project_question(self):
        """Test ask_project_question passes targeted question."""
        resp = self.service.ask_project_question("CyberRacer", "What are the latest asset versions?")
        self.assertTrue(resp.success)
        self.assertEqual(resp.project_name, "CyberRacer")

    def test_13_analyze_project_status(self):
        """Test analyze_project_status assesses health, deadlines, and tasks."""
        resp = self.service.analyze_project_status("CyberRacer")
        self.assertTrue(resp.success)
        self.assertEqual(resp.project_name, "CyberRacer")

    def test_14_find_missing_assets(self):
        """Test find_missing_assets discovers offline/missing library references."""
        resp = self.service.find_missing_assets("CyberRacer")
        self.assertTrue(resp.success)
        # Should attribute offline sources
        has_offline = any(s.source_type == ProjectSourceType.LIBRARY_ASSET.value for s in resp.sources)
        self.assertTrue(has_offline)

    def test_15_summarize_project_knowledge(self):
        """Test summarize_project_knowledge focuses on documentation and notes."""
        resp = self.service.summarize_project_knowledge("CyberRacer")
        self.assertTrue(resp.success)
        has_knowledge = any(s.source_type == ProjectSourceType.KNOWLEDGE.value for s in resp.sources)
        self.assertTrue(has_knowledge)

    def test_16_summarize_project_lab(self):
        """Test summarize_project_lab focuses on boards and tasks."""
        resp = self.service.summarize_project_lab("CyberRacer")
        self.assertTrue(resp.success)
        has_lab = any(s.source_type in (ProjectSourceType.LAB_BOARD.value, ProjectSourceType.LAB_TASK.value) for s in resp.sources)
        self.assertTrue(has_lab)

    def test_17_project_ai_service_alias_and_import(self):
        """Verify ProjectAIService alias and module exports."""
        from services.project_ai_service import ProjectAIService as ImportedService
        self.assertIs(ImportedService, ProjectAssistantService)

    # -------------------------------------------------------------------------
    # 12. Production Intelligence & Deterministic Health (Phase 5B Step 3)
    # -------------------------------------------------------------------------

    def test_18_evaluate_project_health_deterministic(self):
        """Test deterministic project health evaluation on sample context."""
        findings = self.service.evaluate_project_health(self.sample_context)
        self.assertGreaterEqual(len(findings), 3)

        # Offline warning
        offline_f = next((f for f in findings if f.category == "library" and f.severity == "warning"), None)
        self.assertIsNotNone(offline_f)
        self.assertIn("Offline", offline_f.title)
        self.assertIn("EXT_DRIVE_A", offline_f.explanation)

        # Lab tasks
        lab_f = next((f for f in findings if f.category == "lab"), None)
        self.assertIsNotNone(lab_f)
        self.assertIn("2 Open Lab Checklist Task(s)", lab_f.title)

        # Knowledge notes
        k_f = next((f for f in findings if f.category == "knowledge"), None)
        self.assertIsNotNone(k_f)
        self.assertIn("2 Linked Documentation Note(s)", k_f.title)

    def test_19_what_needs_attention(self):
        """Test what_needs_attention triggers grounded query and returns findings."""
        resp = self.service.what_needs_attention("CyberRacer")
        self.assertTrue(resp.success)
        self.assertEqual(resp.project_name, "CyberRacer")
        self.assertGreaterEqual(len(resp.findings), 1)

    def test_20_analyze_asset_dependencies(self):
        """Test analyze_asset_dependencies executes grounded analysis."""
        resp = self.service.analyze_asset_dependencies("CyberRacer")
        self.assertTrue(resp.success)
        self.assertEqual(resp.project_name, "CyberRacer")

    def test_21_summarize_documentation_overview(self):
        """Test summarize_documentation_overview executes grounded documentation summary."""
        resp = self.service.summarize_documentation_overview("CyberRacer")
        self.assertTrue(resp.success)
        self.assertEqual(resp.project_name, "CyberRacer")

    def test_22_critical_missing_library_assets_finding(self):
        """Test critical severity finding when missing library references exist."""
        ctx_with_missing = ProjectContext(
            project_name="MissingAssetsProject",
            project_path="/proj/missing",
            library_summary=ProjectLibrarySummary(
                total_linked_assets=1,
                missing_assets=1,
                linked_assets=[{
                    "id": "ref_m_1",
                    "filename": "Hero_Prop_Missing.fbx",
                    "availability_status": "missing",
                }],
            ),
            availability_summary=ProjectAvailabilitySummary(missing_library_assets=1),
        )
        findings = self.service.evaluate_project_health(ctx_with_missing)
        crit_f = next((f for f in findings if f.severity == "critical"), None)
        self.assertIsNotNone(crit_f)
        self.assertIn("Missing Library Asset", crit_f.title)
        self.assertIn("Hero_Prop_Missing.fbx", crit_f.explanation)


if __name__ == "__main__":
    unittest.main()
