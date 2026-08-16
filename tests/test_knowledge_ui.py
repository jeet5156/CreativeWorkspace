"""Focused unit and UI integration tests for Knowledge Workspace UI."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

from core.app_context import AppContext
from core.inspectable_adapters import (
    AssetInspectable,
    KnowledgeDocumentInspectable,
    ProjectInspectable,
)
from models.knowledge import KnowledgeDocument, KnowledgeFolder
from models.project import Project
from services.knowledge_service import KnowledgeService
from ui.panels.inspector_panel import InspectorPanel
from ui.panels.knowledge_workspace_panel import KnowledgeWorkspacePanel
from ui.widgets.knowledge_card import KnowledgeCard

app = QApplication.instance() or QApplication([])


class TestKnowledgeWorkspaceUI(unittest.TestCase):
    """Test suite covering KnowledgeWorkspacePanel, card widgets, editor, and Inspector integration."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.storage_dir = Path(self.test_dir) / "knowledge"
        self.storage_dir.mkdir(parents=True)

        self.knowledge_service = KnowledgeService(storage_dir=self.storage_dir)

        self.context = AppContext()
        self.context.knowledge_service = self.knowledge_service

        self.inspector = InspectorPanel()
        self.inspector.set_context(self.context)
        self.context.inspector_panel = self.inspector

        self.panel = KnowledgeWorkspacePanel(self.context)
        self.panel.document_selected.connect(self.inspector.show_knowledge_document)

        self.panel.show()
        self.inspector.show()

    def tearDown(self):
        self.panel.deleteLater()
        self.inspector.deleteLater()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_workspace_creation_and_initial_empty_state(self):
        """1. Verify workspace initializes cleanly with empty states."""
        self.assertIsNotNone(self.panel)
        self.assertEqual(len(self.panel._cards), 0)
        self.assertTrue(self.panel.empty_state_label.isVisible())
        self.assertTrue(self.panel.editor_placeholder.isVisible())
        self.assertFalse(self.panel.editor_controls_widget.isVisible())

    def test_new_document_appears_and_selects_immediately(self):
        """2. Verify creating a note adds a card, selects it, and populates editor immediately."""
        self.panel.create_new_note()

        self.assertEqual(len(self.panel._cards), 1)
        self.assertFalse(self.panel.empty_state_label.isVisible())
        self.assertTrue(self.panel.editor_controls_widget.isVisible())
        self.assertFalse(self.panel.editor_placeholder.isVisible())

        # Editor should have "Untitled Note"
        self.assertEqual(self.panel.editor_title.text(), "Untitled Note")
        self.assertEqual(self.panel.editor_content.toPlainText(), "")

    def test_document_selection_reaches_inspector(self):
        """3. Verify selecting a note populates the Inspector with KnowledgeDocumentInspectable."""
        doc = self.knowledge_service.create_document(
            title="Inspector Integration Note",
            content="Some details for testing inspector.",
            tags=["ui", "test"],
            favorite=True,
        )
        self.panel.refresh()

        # Click the card
        card = self.panel._cards[doc.id]
        card.clicked.emit(doc)

        # Verify Inspector state
        self.assertIsInstance(self.inspector._current_inspectable, KnowledgeDocumentInspectable)
        self.assertIn("Inspector Integration Note", self.inspector.header_title.text())
        self.assertIn("⭐📝", self.inspector.header_title.text())

    def test_title_and_content_editing_persists(self):
        """4. Verify editing title and content persists to KnowledgeService and updates card preview."""
        self.panel.create_new_note()
        doc_id = self.panel._current_doc_id

        # Edit title and content in the editor
        self.panel.editor_title.setText("GDD - Combat Mechanics")
        self.panel.editor_content.setPlainText("Detailed combat mechanics outline with combos.")
        self.panel._save_active_document()

        # Check in KnowledgeService
        saved_doc = self.knowledge_service.get_document(doc_id)
        self.assertEqual(saved_doc.title, "GDD - Combat Mechanics")
        self.assertEqual(saved_doc.content, "Detailed combat mechanics outline with combos.")

        # Check card preview
        card = self.panel._cards[doc_id]
        self.assertIn("GDD - Combat Mechanics", card.title_label.text())
        self.assertIn("Detailed combat mechanics", card.snippet_label.text())

    def test_tags_and_favorite_editing_persists(self):
        """5. Verify tags and favorite toggles update service and UI immediately."""
        doc = self.knowledge_service.create_document(title="Tagged Note", tags=["initial"])
        self.panel.refresh()

        # Toggle favorite in editor
        self.panel._select_document(doc.id)
        self.panel._toggle_active_favorite()

        self.assertTrue(self.knowledge_service.get_document(doc.id).favorite)
        self.assertEqual(self.panel.editor_fav_btn.text(), "⭐")
        self.assertEqual(self.panel._cards[doc.id].fav_btn.text(), "⭐")

        # Edit tags
        self.panel.editor_tags.setText("mechanics, combat, vfx")
        self.panel._save_active_document()

        saved_doc = self.knowledge_service.get_document(doc.id)
        self.assertEqual(saved_doc.tags, ["mechanics", "combat", "vfx"])
        self.assertIn("#mechanics", self.panel._cards[doc.id].tags_label.text())

    def test_folder_navigation_and_filtering(self):
        """6. Verify folder hierarchy navigation and folder document filtering."""
        fld_a = self.knowledge_service.create_folder(name="Design")
        fld_b = self.knowledge_service.create_folder(name="Art")

        doc_a = self.knowledge_service.create_document(title="Design Doc", folder_id=fld_a.id)
        doc_b = self.knowledge_service.create_document(title="Art Doc", folder_id=fld_b.id)
        doc_root = self.knowledge_service.create_document(title="Root Doc")

        self.panel.refresh()
        self.assertEqual(len(self.panel._cards), 3)

        # Select Folder A in tree
        item_a = self.panel._folder_tree_items[fld_a.id]
        self.panel._on_folder_tree_clicked(item_a, 0)

        self.assertEqual(len(self.panel._cards), 1)
        self.assertIn(doc_a.id, self.panel._cards)
        self.assertNotIn(doc_b.id, self.panel._cards)

        # Select All Notes
        self.panel.btn_all_notes.click()
        self.assertEqual(len(self.panel._cards), 3)

    def test_empty_folder_state(self):
        """7. Verify empty folder shows appropriate empty state message."""
        empty_fld = self.knowledge_service.create_folder(name="Empty Folder")
        self.panel.refresh()

        item = self.panel._folder_tree_items[empty_fld.id]
        self.panel._on_folder_tree_clicked(item, 0)

        self.assertEqual(len(self.panel._cards), 0)
        self.assertTrue(self.panel.empty_state_label.isVisible())
        self.assertIn("No notes in this folder", self.panel.empty_state_label.text())

    def test_search_by_title_content_and_tag(self):
        """8. Verify search filters the cards list in real-time."""
        d1 = self.knowledge_service.create_document(title="World Lore", content="Deep backstory", tags=["lore"])
        d2 = self.knowledge_service.create_document(title="Shader Math", content="HLSL tricks", tags=["rendering"])
        d3 = self.knowledge_service.create_document(title="Quest 1", content="Speak with elder", tags=["quest"])
        self.panel.refresh()

        # Search title
        self.panel.search_edit.setText("shader")
        self.assertEqual(len(self.panel._cards), 1)
        self.assertIn(d2.id, self.panel._cards)

        # Search content
        self.panel.search_edit.setText("backstory")
        self.assertEqual(len(self.panel._cards), 1)
        self.assertIn(d1.id, self.panel._cards)

        # Search tag
        self.panel.search_edit.setText("quest")
        self.assertEqual(len(self.panel._cards), 1)
        self.assertIn(d3.id, self.panel._cards)

        # Clear search
        self.panel.search_edit.setText("")
        self.assertEqual(len(self.panel._cards), 3)

    def test_favorites_view(self):
        """9. Verify Favorites view isolates starred documents."""
        d1 = self.knowledge_service.create_document(title="Fav 1", favorite=True)
        d2 = self.knowledge_service.create_document(title="Non-Fav", favorite=False)
        d3 = self.knowledge_service.create_document(title="Fav 2", favorite=True)

        self.panel.btn_favorites.click()
        self.assertEqual(len(self.panel._cards), 2)
        self.assertIn(d1.id, self.panel._cards)
        self.assertIn(d3.id, self.panel._cards)
        self.assertNotIn(d2.id, self.panel._cards)

    def test_recent_view_sorting(self):
        """10. Verify Recent view displays and sorts deterministically."""
        d1 = self.knowledge_service.create_document(title="Old Note")
        d2 = self.knowledge_service.create_document(title="New Note")
        d1.modified = "2026-01-01T10:00:00"
        d2.modified = "2026-01-02T10:00:00"

        self.panel.btn_recent.click()
        card_ids = list(self.panel._cards.keys())
        self.assertEqual(card_ids[0], d2.id)

    def test_long_title_truncation_without_layout_distortion(self):
        """11. Verify very long titles are safely elided and do not exceed card geometry."""
        long_title = "A" * 300 + " Extremely Long Title That Could Break Layout If Not Elided"
        doc = self.knowledge_service.create_document(title=long_title, content="Short snippet")
        card = KnowledgeCard(doc)

        self.assertLessEqual(card.maximumWidth(), 320)
        self.assertEqual(card.height(), 120)
        # Verify text was elided
        self.assertTrue("..." in card.title_label.text() or len(card.title_label.text()) < len(long_title))
        self.assertEqual(card.title_label.toolTip(), long_title)
        card.deleteLater()

    def test_inspector_transitions_lifecycle(self):
        """12. Verify Project → Knowledge → Asset → Knowledge transitions cleanly without stale widgets."""
        doc = self.knowledge_service.create_document(title="Knowledge Document Note")
        proj = Project(name="Project Alpha", project_type="game", location=self.test_dir)

        # 1. Inspect Project
        self.inspector.show_project(proj)
        self.assertIsInstance(self.inspector._current_inspectable, ProjectInspectable)
        self.assertIn("Project Alpha", self.inspector.header_title.text())

        # 2. Inspect Knowledge Document
        self.inspector.show_knowledge_document(doc)
        self.assertIsInstance(self.inspector._current_inspectable, KnowledgeDocumentInspectable)
        self.assertIn("Knowledge Document Note", self.inspector.header_title.text())

        # 3. Inspect Project again
        self.inspector.show_project(proj)
        self.assertIsInstance(self.inspector._current_inspectable, ProjectInspectable)
        self.assertIn("Project Alpha", self.inspector.header_title.text())

        # 4. Inspect None / Clear
        self.inspector.inspect(None)
        self.assertIsNone(self.inspector._current_inspectable)
        self.assertTrue(self.inspector.placeholder.isVisible())

    def test_live_ui_updates_without_navigating_away(self):
        """13. Verify UI updates live during note creation and deletion without page reloads."""
        # Create
        self.panel.create_new_note()
        self.assertEqual(len(self.panel._cards), 1)

        # Delete with mock confirmation
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            self.panel._delete_active_document()

        self.assertEqual(len(self.panel._cards), 0)
        self.assertTrue(self.panel.empty_state_label.isVisible())
        self.assertTrue(self.panel.editor_placeholder.isVisible())

    def test_search_content_inspector_exact_scenario(self):
        """14. Regression test for searching a word ('Inspector') appearing strictly in document content."""
        # 1. Create a Knowledge document in a folder
        fld = self.knowledge_service.create_folder(name="Architecture")
        doc = self.knowledge_service.create_document(
            title="UI Layout Specification",
            content="This section details how the Inspector panel connects to the workspace.",
            tags=["ui", "layout"],
            folder_id=fld.id,
        )

        # Create another doc with unrelated content
        doc_other = self.knowledge_service.create_document(
            title="Audio Assets",
            content="Sound effects and background music.",
            tags=["audio"],
        )

        # 5. Open/refresh the Knowledge workspace (in All Notes view)
        self.panel.btn_all_notes.click()
        self.assertEqual(len(self.panel._cards), 2)

        # 6. Search for "Inspector" (exact case)
        self.panel.search_edit.setText("Inspector")
        self.assertEqual(len(self.panel._cards), 1)
        self.assertIn(doc.id, self.panel._cards)
        self.assertNotIn(doc_other.id, self.panel._cards)

        # Search for lowercase "inspector"
        self.panel.search_edit.setText("inspector")
        self.assertEqual(len(self.panel._cards), 1)
        self.assertIn(doc.id, self.panel._cards)

        # Word appearing only in tags
        self.panel.search_edit.setText("layout")
        self.assertEqual(len(self.panel._cards), 1)
        self.assertIn(doc.id, self.panel._cards)

        # Word appearing only in title
        self.panel.search_edit.setText("Specification")
        self.assertEqual(len(self.panel._cards), 1)
        self.assertIn(doc.id, self.panel._cards)

        # Clearing search restores the full list
        self.panel.search_edit.setText("")
        self.assertEqual(len(self.panel._cards), 2)

    def test_search_immediately_after_editing_content(self):
        """15. Regression test for typing in editor and searching immediately before debounce timer expires."""
        self.panel.create_new_note()
        self.panel.editor_title.setText("Unrelated Title")
        self.panel.editor_content.setPlainText("Configuring the Inspector properties.")

        # Immediately type into search box while autosave timer is pending
        self.panel.search_edit.setText("Inspector")
        self.assertEqual(len(self.panel._cards), 1)
        self.assertIn("Unrelated Title", self.panel._cards[self.panel._current_doc_id].title_label.text())


if __name__ == "__main__":
    unittest.main()
