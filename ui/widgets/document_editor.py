from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSplitter,
)

from engines.document.document import Document
from engines.document.markdown_reader import MarkdownReader
from engines.document.markdown_writer import MarkdownWriter

from ui.widgets.document_canvas import DocumentCanvas
from ui.widgets.document_toolbar import DocumentToolbar
from ui.widgets.markdown_preview import MarkdownPreview


class DocumentEditor(QWidget):

    save_requested = Signal()
    text_changed = Signal()
    paste_image_requested = Signal()

    def __init__(self):
        super().__init__()

        self.base_path = None

        self.reader = MarkdownReader()
        self.writer = MarkdownWriter()

        self._document = Document()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)

        self.toolbar = DocumentToolbar()
        main_layout.addWidget(self.toolbar)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_edit = QPushButton("Edit")
        self.btn_split = QPushButton("Split")
        self.btn_preview = QPushButton("Preview")

        toolbar_layout.addWidget(self.btn_edit)
        toolbar_layout.addWidget(self.btn_split)
        toolbar_layout.addWidget(self.btn_preview)
        toolbar_layout.addStretch()

        main_layout.addLayout(toolbar_layout)

        self.splitter = QSplitter(Qt.Horizontal)

        self.canvas = DocumentCanvas()
        self.preview = MarkdownPreview()

        self.splitter.addWidget(self.canvas)
        self.splitter.addWidget(self.preview)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)

        main_layout.addWidget(self.splitter, 1)

        self._connect_toolbar()
        self._connect_signals()

        self.show_split()

    # ----------------------------------------------------------
    # Connections
    # ----------------------------------------------------------

    def _connect_toolbar(self):

        self.toolbar.undo_requested.connect(self.canvas.undo)
        self.toolbar.redo_requested.connect(self.canvas.redo)

        self.toolbar.bold_requested.connect(self.canvas.apply_bold)
        self.toolbar.italic_requested.connect(self.canvas.apply_italic)
        self.toolbar.heading_requested.connect(self.canvas.apply_heading)
        self.toolbar.bullet_requested.connect(self.canvas.apply_bullet)
        self.toolbar.checklist_requested.connect(self.canvas.apply_checklist)
        self.toolbar.quote_requested.connect(self.canvas.apply_quote)

        self.toolbar.image_requested.connect(
            self.paste_image_requested.emit
        )

        self.toolbar.link_requested.connect(
            self.canvas.insert_link
        )

        self.toolbar.divider_requested.connect(
            self.canvas.insert_divider
        )

        self.toolbar.save_requested.connect(
            self.save_requested.emit
        )

    def _connect_signals(self):

        self.canvas.text_changed.connect(
            self._canvas_changed
        )

        self.canvas.save_requested.connect(
            self.save_requested.emit
        )

        self.canvas.paste_image_requested.connect(
            self.paste_image_requested.emit
        )

        self.btn_edit.clicked.connect(
            self.show_edit
        )

        self.btn_split.clicked.connect(
            self.show_split
        )

        self.btn_preview.clicked.connect(
            self.show_preview
        )

    # ----------------------------------------------------------
    # Internal
    # ----------------------------------------------------------

    def _canvas_changed(self):

        self._document = self.reader.load(
            self.canvas.text()
        )

        self._update_preview()

        self.text_changed.emit()

    def _update_preview(self):

        markdown = self.writer.save(
            self._document
        )

        self.preview.set_markdown(
            markdown,
            self.base_path,
        )

    # ----------------------------------------------------------
    # Configuration
    # ----------------------------------------------------------

    def set_base_path(self, path):

        self.base_path = path

        self._update_preview()

    # ----------------------------------------------------------
    # Document API
    # ----------------------------------------------------------

    def set_document(self, document):

        self._document = document

        markdown = self.writer.save(document)

        self.canvas.block_signals(True)
        self.canvas.set_text(markdown)
        self.canvas.block_signals(False)

        self._update_preview()

    def document(self):

        return self._document

    # ----------------------------------------------------------
    # Compatibility
    # ----------------------------------------------------------

    def set_text(self, markdown):

        self.set_document(
            self.reader.load(markdown)
        )

    def text(self):

        return self.writer.save(
            self._document
        )

    def insert_text(self, text):

        self.canvas.insert_text(text)

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------

    def clear(self):

        self.set_document(Document())

    def block_signals(self, block):

        self.canvas.block_signals(block)

    def set_focus(self):

        self.canvas.set_focus()

    # ----------------------------------------------------------
    # View Modes
    # ----------------------------------------------------------

    def show_edit(self):

        self.canvas.show()
        self.preview.hide()

    def show_preview(self):

        self.canvas.hide()
        self.preview.show()
        self.preview.raise_()

    def show_split(self):

        self.canvas.show()
        self.preview.show()