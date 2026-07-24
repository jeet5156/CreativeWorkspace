from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
)

from PySide6.QtCore import QTimer

from services.notes_service import NotesService
from ui.widgets.document_editor import DocumentEditor


class NotesPanel(QWidget):

    def __init__(self):
        super().__init__()

        self.project = None

        self.notes = NotesService()

        layout = QVBoxLayout(self)

        self.status = QLabel("")

        self.editor = DocumentEditor()

        layout.addWidget(self.status)
        layout.addWidget(self.editor)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)

        self.timer.timeout.connect(self.autosave)

        # Autosave after typing
        self.editor.editor.textChanged.connect(self.restart_timer)

        # Ctrl+S / Save button
        self.editor.save_requested.connect(self.autosave)

    # ---------------------------------------------------------

    def show_project(self, project):

        self.project = project

        self.editor.editor.blockSignals(True)

        self.editor.set_text(
            self.notes.load(project)
        )

        self.editor.editor.blockSignals(False)

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