from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSplitter,
)
from PySide6.QtCore import Qt

from ui.widgets.markdown_editor import MarkdownEditor
from ui.widgets.markdown_preview import MarkdownPreview


class DocumentEditor(QWidget):

    save_requested = Signal()

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # -------------------------------------------------
        # View mode buttons
        # -------------------------------------------------

        button_layout = QHBoxLayout()

        self.edit_btn = QPushButton("Edit")
        self.split_btn = QPushButton("Split")
        self.preview_btn = QPushButton("Preview")

        button_layout.addWidget(self.edit_btn)
        button_layout.addWidget(self.split_btn)
        button_layout.addWidget(self.preview_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        # -------------------------------------------------
        # Splitter
        # -------------------------------------------------

        self.splitter = QSplitter(Qt.Horizontal)

        self.editor = MarkdownEditor()
        self.preview = MarkdownPreview()

        self.splitter.addWidget(self.editor)
        self.splitter.addWidget(self.preview)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)

        layout.addWidget(self.splitter)

        # -------------------------------------------------

        self.editor.editor.textChanged.connect(self.update_preview)

        self.editor.save_requested.connect(
            self.save_requested.emit
        )

        self.edit_btn.clicked.connect(self.show_edit)
        self.split_btn.clicked.connect(self.show_split)
        self.preview_btn.clicked.connect(self.show_preview)

        self.show_split()

    # -------------------------------------------------

    def update_preview(self):

        self.preview.set_markdown(
            self.text()
        )

    # -------------------------------------------------

    def set_text(self, text):

        self.editor.set_text(text)
        self.preview.set_markdown(text)

    def text(self):

        return self.editor.text()

    # -------------------------------------------------

    def show_edit(self):

        self.editor.show()
        self.preview.hide()

    def show_preview(self):

        self.editor.hide()
        self.preview.show()

    def show_split(self):

        self.editor.show()
        self.preview.show()