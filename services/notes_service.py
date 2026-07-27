from pathlib import Path
from datetime import datetime

from engines.document.document import Document
from engines.document.markdown_reader import MarkdownReader
from engines.document.markdown_writer import MarkdownWriter


class NotesService:

    def __init__(self):

        self.reader = MarkdownReader()
        self.writer = MarkdownWriter()

    # ---------------------------------------------------------
    # Paths
    # ---------------------------------------------------------

    def note_path(self, project):

        notes = Path(project.location) / "Notes"
        notes.mkdir(exist_ok=True)

        return notes / "Project.md"

    # ---------------------------------------------------------
    # Document API
    # ---------------------------------------------------------

    def load_document(self, project) -> Document:

        path = self.note_path(project)

        if not path.exists():
            return Document(title="Project Notes")

        markdown = path.read_text(
            encoding="utf-8"
        )

        return self.reader.load(markdown)

    def save_document(
        self,
        project,
        document: Document,
    ):

        markdown = self.writer.save(document)

        path = self.note_path(project)

        path.write_text(
            markdown,
            encoding="utf-8",
        )

    # ---------------------------------------------------------
    # Temporary Compatibility Layer
    #
    # These methods keep the current UI working while we
    # migrate DocumentEditor and NotesPanel.
    # Remove them after the migration.
    # ---------------------------------------------------------

    def load(self, project):

        document = self.load_document(project)

        return self.writer.save(document)

    def save(self, project, text):

        document = self.reader.load(text)

        self.save_document(
            project,
            document,
        )

    # ---------------------------------------------------------
    # Attachments
    # ---------------------------------------------------------

    def attachments_folder(self, project):

        folder = (
            Path(project.location)
            / "Notes"
            / "Attachments"
        )

        folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        return folder

    def new_image_name(self):

        return datetime.now().strftime(
            "image_%Y%m%d_%H%M%S.png"
        )

    def save_image(
        self,
        project,
        image,
    ):

        folder = self.attachments_folder(project)

        filename = self.new_image_name()

        path = folder / filename

        image.save(path)

        return (
            filename,
            f"Attachments/{filename}",
        )