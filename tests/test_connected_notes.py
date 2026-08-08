import unittest
from PySide6.QtWidgets import QApplication

from core.markdown_document import MarkdownDocument
from ui.widgets.infinite_canvas import InfiniteCanvas
from ui.lab.nodes.node_registry import NodeRegistry

app = QApplication.instance() or QApplication([])


class TestConnectedNotes(unittest.TestCase):

    def test_wiki_link_existing_node_style(self):
        """Verify [[Enemy AI]] renders as an active chip when target node exists on canvas."""
        md = MarkdownDocument("See [[Enemy AI]] for behavior details")
        html = md.to_html(existing_node_titles={"Enemy AI"})

        self.assertIn("wiki_link:Enemy AI", html)
        self.assertIn("#312E81", html)  # Deep indigo active chip background
        self.assertIn("Enemy AI", html)

    def test_wiki_link_missing_node_style(self):
        """Verify [[Boss Phase 2]] renders in missing-link style (red background & dashed border) when node does not exist."""
        md = MarkdownDocument("Pending [[Boss Phase 2]] design")
        html = md.to_html(existing_node_titles=set())

        self.assertIn("wiki_link_missing:Boss Phase 2", html)
        self.assertIn("#450A0A", html)  # Dark red missing link background
        self.assertIn("#EF4444", html)  # Red dashed border
        self.assertIn("Boss Phase 2", html)

    def test_display_aliases(self):
        """Verify [[Enemy AI|AI]] targets 'Enemy AI' while displaying alias 'AI'."""
        md = MarkdownDocument("Check [[Enemy AI|AI]] notes")
        html = md.to_html(existing_node_titles={"Enemy AI"})

        self.assertIn("wiki_link:Enemy AI", html)
        self.assertIn("AI", html)

    def test_toc_generation_for_4_or_more_headings(self):
        """Verify TOC panel is automatically generated when note contains >= 4 headings."""
        content = "# Character\n## Sculpt\n### UV\n# Materials"
        md = MarkdownDocument(content)
        html = md.to_html()

        self.assertIn("Contents", html)
        self.assertIn("heading-0", html)
        self.assertIn("heading-1", html)
        self.assertIn("heading-2", html)
        self.assertIn("heading-3", html)
        self.assertIn("Character", html)
        self.assertIn("Materials", html)

    def test_toc_hidden_for_less_than_4_headings(self):
        """Verify TOC panel is hidden for short notes containing < 4 headings."""
        content = "# Character\n## Sculpt\n### UV"
        md = MarkdownDocument(content)
        html = md.to_html()

        self.assertNotIn("Contents", html)
        self.assertNotIn("heading-0", html)

    def test_create_linked_node(self):
        """Verify create_linked_node creates a new Blank Note for a missing wiki link on the canvas."""
        canvas = InfiniteCanvas()
        note = canvas.add_node({
            "type": "note.blank",
            "transform": {"x": 100.0, "y": 100.0, "width": 260.0, "height": 180.0},
            "payload": {"title": "Main Quest", "content": "Need [[Quest Notes]]"}
        })

        note.create_linked_node("Quest Notes")

        # Verify new node created on canvas with matching title
        linked_node = note._find_node_by_title(canvas, "Quest Notes")
        self.assertIsNotNone(linked_node)
        self.assertEqual(linked_node.payload.get("title"), "Quest Notes")


if __name__ == "__main__":
    unittest.main()
