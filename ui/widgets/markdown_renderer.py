from PySide6.QtGui import QTextDocument
from core.markdown_document import MarkdownDocument


class MarkdownRenderer:
    """Decoupled helper for applying rendered Markdown HTML formatting onto Qt Text objects."""

    @staticmethod
    def render_to_document(markdown_text: str, document: QTextDocument, existing_node_titles=None):
        """Parse raw markdown text and set styled HTML on a QTextDocument."""
        if not document:
            return
        doc_model = MarkdownDocument(markdown_text)
        formatted_html = doc_model.to_html(existing_node_titles=existing_node_titles)
        document.setHtml(formatted_html)

    @staticmethod
    def render_to_html(markdown_text: str, existing_node_titles=None) -> str:
        """Parse raw markdown text and return styled HTML string."""
        doc_model = MarkdownDocument(markdown_text)
        return doc_model.to_html(existing_node_titles=existing_node_titles)
