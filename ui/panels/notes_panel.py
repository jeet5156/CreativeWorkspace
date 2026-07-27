from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)

from services.clipboard_service import ClipboardService
from services.notes_service import NotesService
from ui.widgets.document_editor import DocumentEditor


class NotesPanel(QWidget):

    def __init__(self):
        super().__init__()

        self.project = None

        self.notes = NotesService()
        self.clipboard = ClipboardService()

        layout = QVBoxLayout(self)

        self.status = QLabel("")

        self.editor = DocumentEditor()

        layout.addWidget(self.status)
        layout.addWidget(self.editor)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.autosave)

        self.editor.text_changed.connect(self.restart_timer)
        self.editor.save_requested.connect(self.autosave)
        self.editor.paste_image_requested.connect(
            self.paste_image
        )

    # ---------------------------------------------------------
    # Project
    # ---------------------------------------------------------

    def show_project(self, project):

        self.project = project

        notes_folder = (
            Path(project.location)
            / "Notes"
        )

        self.editor.set_base_path(
            str(notes_folder)
        )

        # Load Document instead of Markdown
        document = self.notes.load_document(project)

        self.editor.set_document(document)

        self.status.setText("")

    # ---------------------------------------------------------
    # Autosave
    # ---------------------------------------------------------

    def restart_timer(self):

        self.timer.start()

    def autosave(self):

        self.timer.stop()

        if self.project is None:
            return

        # Save Document instead of Markdown
        self.notes.save_document(
            self.project,
            self.editor.document(),
        )

        self.status.setText("✓ Auto Saved")

    # ---------------------------------------------------------
    # Clipboard
    # ---------------------------------------------------------

    def paste_image(self):

        if self.project is None:
            return

        success, image = self.clipboard.get_image()

        if not success:
            return

        _, markdown_path = self.notes.save_image(
            self.project,
            image,
        )

        self.editor.insert_text(
            f"![]({markdown_path})\n"
        )

        self.autosave()