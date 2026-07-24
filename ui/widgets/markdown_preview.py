from PySide6.QtWidgets import QTextBrowser
import markdown


class MarkdownPreview(QTextBrowser):

    def __init__(self):
        super().__init__()

        self.setOpenExternalLinks(True)
        self.setReadOnly(True)

    def set_markdown(self, text):

        html = markdown.markdown(
            text,
            extensions=[
                "fenced_code",
                "tables",
            ],
        )

        self.setHtml(html)