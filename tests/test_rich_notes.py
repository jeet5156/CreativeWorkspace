import unittest
from PySide6.QtWidgets import QApplication

from core.markdown_document import MarkdownDocument
from ui.lab.nodes.node_registry import NodeRegistry
from ui.lab.nodes.note_node_item import NoteNodeItem
from ui.widgets.markdown_renderer import MarkdownRenderer

app = QApplication.instance() or QApplication([])


class TestRichNotes(unittest.TestCase):

    def test_info_callout_rendering(self):
        """Verify > [!INFO] renders as styled rounded callout panel with blue border and info icon."""
        md = MarkdownDocument("> [!INFO]\n> Important project info")
        html = md.to_html()

        self.assertIn("INFO", html)
        self.assertIn("ℹ️", html)
        self.assertIn("#3B82F6", html)  # Blue border
        self.assertIn("Important project info", html)

    def test_warning_callout_rendering(self):
        """Verify > [!WARNING] renders with warning icon and amber border."""
        md = MarkdownDocument("> [!WARNING]\n> Critical system alert")
        html = md.to_html()

        self.assertIn("WARNING", html)
        self.assertIn("⚠️", html)
        self.assertIn("#F59E0B", html)  # Orange/amber border
        self.assertIn("Critical system alert", html)

    def test_decision_callout_rendering(self):
        """Verify > [!DECISION] renders with target icon and cyan border."""
        md = MarkdownDocument("> [!DECISION]\n> Final architecture selected")
        html = md.to_html()

        self.assertIn("DECISION", html)
        self.assertIn("🎯", html)
        self.assertIn("#06B6D4", html)  # Cyan border
        self.assertIn("Final architecture selected", html)

    def test_unknown_callout_fallback(self):
        """Verify unknown callout types fall back gracefully to INFO styling with uppercase title."""
        md = MarkdownDocument("> [!CUSTOM]\n> Custom callout content")
        html = md.to_html()

        self.assertIn("CUSTOM", html)
        self.assertIn("ℹ️", html)
        self.assertIn("#3B82F6", html)

    def test_mention_chips_rendering(self):
        """Verify @Client, @Team, @Rana render as styled rounded mention chips while preserving raw markdown."""
        md = MarkdownDocument("Assigned to @Rana and reviewed by @Client for @Team")
        html = md.to_html()

        self.assertIn("@Rana", html)
        self.assertIn("@Client", html)
        self.assertIn("@Team", html)
        self.assertIn("#312E81", html)  # Deep indigo mention chip background
        self.assertEqual(md.raw_text, "Assigned to @Rana and reviewed by @Client for @Team")

    def test_smart_date_chips_rendering(self):
        """Verify @today, @tomorrow, @yesterday render as highlighted date chips while preserving raw markdown."""
        md = MarkdownDocument("Task due @today and follow-up @tomorrow")
        html = md.to_html()

        self.assertIn("@today", html)
        self.assertIn("@tomorrow", html)
        self.assertIn("#1E3A8A", html)  # Deep blue date chip background
        self.assertEqual(md.raw_text, "Task due @today and follow-up @tomorrow")

    def test_checklist_toggling(self):
        """Verify toggle_checkbox_at_line toggles - [ ] <-> - [x] in raw markdown."""
        raw_text = "- [ ] Task 1\n- [x] Task 2"

        # Toggle first item (unchecked -> checked)
        toggled1 = MarkdownDocument.toggle_checkbox_at_line(raw_text, 0)
        self.assertEqual(toggled1, "- [x] Task 1\n- [x] Task 2")

        # Toggle second item (checked -> unchecked)
        toggled2 = MarkdownDocument.toggle_checkbox_at_line(toggled1, 1)
        self.assertEqual(toggled2, "- [x] Task 1\n- [ ] Task 2")

    def test_note_node_item_rich_markdown_workflow(self):
        """Verify NoteNodeItem maintains raw markdown authority and Ctrl+Enter preview workflow."""
        note = NodeRegistry.create_node("note.blank")
        content = "# Sprint Notes\n> [!TIP]\n> Remember @today to update @Client\n- [ ] Review PR"
        note.payload["content"] = content

        MarkdownRenderer.render_to_document(content, note.editor.document())

        html = note.editor.document().toHtml()
        self.assertIn("Sprint Notes", html)
        self.assertIn("TIP", html)
        self.assertIn("@today", html)
        self.assertIn("@Client", html)

        # Raw markdown source remains unchanged in payload
        self.assertEqual(note.payload["content"], content)


if __name__ == "__main__":
    unittest.main()
