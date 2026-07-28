from PySide6.QtCore import Signal, QEvent
from PySide6.QtGui import (
    QTextCursor,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QInputDialog,
)


class DocumentCanvas(QWidget):

    save_requested = Signal()
    text_changed = Signal()
    paste_image_requested = Signal()

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.editor = QTextEdit()
        self.editor.setAcceptRichText(False)

        self.editor.textChanged.connect(
            self.text_changed.emit
        )

        self.editor.installEventFilter(self)

        layout.addWidget(self.editor)

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
            activated=self.apply_bold,
        )

        QShortcut(
            QKeySequence.Italic,
            self,
            activated=self.apply_italic,
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
        cursor.beginEditBlock()
        try:
            if cursor.hasSelection():
                start = cursor.selectionStart()
                end = cursor.selectionEnd()
                doc=self.editor.document()
                start_block=doc.findBlock(start)
                end_block=doc.findBlock(max(start,end-1))
                block=start_block
                while block.isValid():
                    tc=QTextCursor(block)
                    tc.select(QTextCursor.LineUnderCursor)
                    line=tc.selectedText()
                    new_line=line[len(prefix):] if line.startswith(prefix) else prefix+line
                    tc.insertText(new_line)
                    if block==end_block:
                        break
                    block=block.next()
            else:
                cursor.movePosition(QTextCursor.StartOfLine)
                cursor.select(QTextCursor.LineUnderCursor)
                line=cursor.selectedText()
                cursor.insertText(line[len(prefix):] if line.startswith(prefix) else prefix+line)
        finally:
            cursor.endEditBlock()

    # ---------------------------------------------------------
    # Formatting
    # ---------------------------------------------------------

    def apply_bold(self):
        self.toggle_wrapper("**")

    def apply_italic(self):
        self.toggle_wrapper("*")

    def apply_heading(self, level):
        self.prefix_selected_lines("#" * level + " ")

    def apply_bullet(self):
        self.prefix_selected_lines("- ")

    def apply_checklist(self):
        self.prefix_selected_lines("- [ ] ")

    def apply_quote(self):
        self.prefix_selected_lines("> ")


    def insert_divider(self):
        cursor=self.editor.textCursor()
        cursor.insertText("\n---\n")

    def insert_link(self):
        url,ok=QInputDialog.getText(self,"Insert Link","URL:")
        if not ok or not url:
            return
        cursor=self.editor.textCursor()
        text=cursor.selectedText() or "Link"
        cursor.insertText(f"[{text}]({url})")

    # ---------------------------------------------------------
    # Editing
    # ---------------------------------------------------------

    def undo(self):
        self.editor.undo()

    def redo(self):
        self.editor.redo()

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