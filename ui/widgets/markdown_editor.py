from PySide6.QtCore import Signal, Qt, QEvent
from PySide6.QtGui import (
    QAction,
    QTextCursor,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QWidget,
    QTextEdit,
    QVBoxLayout,
    QToolBar,
    QApplication,
)


class MarkdownEditor(QWidget):

    save_requested = Signal()
    text_changed = Signal()
    paste_image_requested = Signal()

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.toolbar = QToolBar()
        layout.addWidget(self.toolbar)

        self.editor = QTextEdit()
        self.editor.setAcceptRichText(False)
        self.editor.textChanged.connect(self.text_changed.emit)
        self.editor.installEventFilter(self)

        layout.addWidget(self.editor)

        self.create_toolbar()
        self.create_shortcuts()

    # ---------------------------------------------------------
    # Event Filter
    # ---------------------------------------------------------

    def eventFilter(self, obj, event):

        if obj is self.editor and event.type() == QEvent.KeyPress:

            if event.matches(QKeySequence.StandardKey.Paste):
                self.paste()
                return True

        return super().eventFilter(obj, event)

    # ---------------------------------------------------------
    # Clipboard
    # ---------------------------------------------------------

    def can_paste_image(self):

        mime = QApplication.clipboard().mimeData()

        return (
            mime is not None
            and mime.hasImage()
        )

    def paste(self):

        if self.can_paste_image():
            self.paste_image_requested.emit()
        else:
            self.editor.paste()

    # ---------------------------------------------------------
    # Toolbar
    # ---------------------------------------------------------

    def create_toolbar(self):

        items = [

            ("B", self.bold, "Bold"),
            ("I", self.italic, "Italic"),

            None,

            ("H1", lambda: self.heading(1), "Heading 1"),
            ("H2", lambda: self.heading(2), "Heading 2"),
            ("H3", lambda: self.heading(3), "Heading 3"),

            None,

            ("•", self.bullet_list, "Bullet List"),
            ("☑", self.checklist, "Checklist"),
            (">", self.quote, "Quote"),

            None,

            ("Save", self.save_requested.emit, "Save"),
        ]

        for item in items:

            if item is None:
                self.toolbar.addSeparator()
                continue

            text, slot, tooltip = item

            action = QAction(text, self)
            action.setToolTip(tooltip)
            action.triggered.connect(slot)

            self.toolbar.addAction(action)

    # ---------------------------------------------------------
    # Shortcuts
    # ---------------------------------------------------------

    def create_shortcuts(self):

        QShortcut(
            QKeySequence.StandardKey.Save,
            self,
            activated=self.save_requested.emit,
        )

        QShortcut(
            QKeySequence.Bold,
            self,
            activated=self.bold,
        )

        QShortcut(
            QKeySequence.Italic,
            self,
            activated=self.italic,
        )

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    def toggle_wrapper(self, wrapper):

        cursor = self.editor.textCursor()

        if not cursor.hasSelection():
            return

        text = cursor.selectedText()

        if text.startswith(wrapper) and text.endswith(wrapper):
            text = text[len(wrapper):-len(wrapper)]
        else:
            text = f"{wrapper}{text}{wrapper}"

        cursor.insertText(text)

    def prefix_selected_lines(self, prefix):

        cursor = self.editor.textCursor()

        if cursor.hasSelection():

            start = cursor.selectionStart()
            end = cursor.selectionEnd()

            cursor.setPosition(start)
            cursor.movePosition(QTextCursor.StartOfLine)

            while cursor.position() <= end:

                cursor.insertText(prefix)

                if not cursor.movePosition(QTextCursor.NextBlock):
                    break

                end += len(prefix)

        else:

            cursor.movePosition(QTextCursor.StartOfLine)
            cursor.insertText(prefix)

    # ---------------------------------------------------------
    # Formatting
    # ---------------------------------------------------------

    def bold(self):
        self.toggle_wrapper("**")

    def italic(self):
        self.toggle_wrapper("*")

    def heading(self, level):
        self.prefix_selected_lines("#" * level + " ")

    def bullet_list(self):
        self.prefix_selected_lines("- ")

    def checklist(self):
        self.prefix_selected_lines("- [ ] ")

    def quote(self):
        self.prefix_selected_lines("> ")

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def set_text(self, text):
        self.editor.setPlainText(text)

    def text(self):
        return self.editor.toPlainText()

    def insert_text(self, text):
        self.editor.insertPlainText(text)

    def clear(self):
        self.editor.clear()

    def set_focus(self):
        self.editor.setFocus()

    def block_signals(self, block):
        self.editor.blockSignals(block)