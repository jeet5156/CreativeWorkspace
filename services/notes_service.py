from pathlib import Path
from datetime import datetime


class NotesService:

    # ---------------------------------------------------------
    # Notes
    # ---------------------------------------------------------

    def note_path(self, project):
        notes = Path(project.location) / "Notes"
        notes.mkdir(exist_ok=True)

        return notes / "Project.md"

    def load(self, project):

        path = self.note_path(project)

        if path.exists():
            return path.read_text(encoding="utf-8")

        return ""

    def save(self, project, text):

        path = self.note_path(project)

        path.write_text(
            text,
            encoding="utf-8",
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

    def save_image(self, project, image):

        folder = self.attachments_folder(project)

        filename = self.new_image_name()

        path = folder / filename

        image.save(path)

        return (
            filename,
            f"Attachments/{filename}"
        )