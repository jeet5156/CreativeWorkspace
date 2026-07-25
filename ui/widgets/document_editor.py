from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSplitter,
)

from ui.widgets.markdown_editor import MarkdownEditor
from ui.widgets.markdown_preview import MarkdownPreview


class DocumentEditor(QWidget):

    save_requested = Signal()
    text_changed = Signal()
    paste_image_requested = Signal()

    def __init__(self):
        super().__init__()

        self.base_path = None

        # --------------------------------------------------
        # Main Layout
        # --------------------------------------------------

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)

        # --------------------------------------------------
        # View Toolbar
        # --------------------------------------------------

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

        # --------------------------------------------------
        # Splitter
        # --------------------------------------------------

        self.splitter = QSplitter(Qt.Horizontal)

        self.editor = MarkdownEditor()
        self.preview = MarkdownPreview()

        self.editor.paste_image_requested.connect(
            self.paste_image_requested.emit
        )

        self.splitter.addWidget(self.editor)
        self.splitter.addWidget(self.preview)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)

        main_layout.addWidget(self.splitter, 1)

        # --------------------------------------------------
        # Signals
        # --------------------------------------------------

        self.editor.text_changed.connect(
            self._editor_text_changed
        )

        self.editor.save_requested.connect(
            self.save_requested.emit
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

        # Default view
        self.show_split()

    # --------------------------------------------------
    # Configuration
    # --------------------------------------------------

    def set_base_path(self, path):
        self.base_path = path
        print("Base Path:", self.base_path)
    # --------------------------------------------------
    # Internal
    # --------------------------------------------------

    def _editor_text_changed(self):

        text = self.editor.text()

        self.preview.set_markdown(
            text,
            self.base_path,
        )

        self.text_changed.emit()

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def set_text(self, text):

        self.editor.block_signals(True)
        self.editor.set_text(text)
        self.editor.block_signals(False)

        self.preview.set_markdown(
            text,
            self.base_path,
        )

    def text(self):
        return self.editor.text()

    def insert_text(self, text):

        self.editor.insert_text(text)

        self.preview.set_markdown(
            self.editor.text(),
            self.base_path,
        )

        self.text_changed.emit()

    def clear(self):
        self.editor.clear()

    def block_signals(self, block):
        self.editor.block_signals(block)

    def set_focus(self):
        self.editor.set_focus()

    # --------------------------------------------------
    # View Modes
    # --------------------------------------------------

    def show_edit(self):
        self.editor.show()
        self.preview.hide()

    def show_preview(self):
        print("Preview clicked")
        self.editor.hide()
        self.preview.show()
        self.preview.raise_()

    def show_split(self):
        self.editor.show()
        self.preview.show()