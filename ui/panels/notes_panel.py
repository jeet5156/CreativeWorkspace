from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
)
from PySide6.QtCore import QTimer
from pathlib import Path

from services.notes_service import NotesService
from services.clipboard_service import ClipboardService
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

        # Existing signals
        self.editor.text_changed.connect(self.restart_timer)
        self.editor.save_requested.connect(self.autosave)

        # New signal
        self.editor.paste_image_requested.connect(
            self.paste_image
        )

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

        self.editor.set_text(
            self.notes.load(project)
        )

        self.status.setText("")

    # ---------------------------------------------------------

    def restart_timer(self):
        self.timer.start()

    # ---------------------------------------------------------

    def autosave(self):

        self.timer.stop()

        if self.project is None:
            return

        self.notes.save(
            self.project,
            self.editor.text(),
        )

        self.status.setText("✓ Auto Saved")

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

        # Save immediately
        self.autosave()