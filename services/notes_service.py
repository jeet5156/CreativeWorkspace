from pathlib import Path


class NotesService:

    def note_path(self, project):

        notes_folder = Path(project.location) / "Notes"
        notes_folder.mkdir(exist_ok=True)

        return notes_folder / "Project.md"

    def load(self, project):

        path = self.note_path(project)

        if path.exists():
            return path.read_text(encoding="utf-8")

        return ""

    def save(self, project, text):

        path = self.note_path(project)

        path.write_text(text, encoding="utf-8")