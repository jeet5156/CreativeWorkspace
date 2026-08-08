import os
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import QMimeData, QPointF


class DropContext:
    """Encapsulates drag/drop metadata for spatial canvas drop routing.

    Extracts file URLs, local file paths, scene coordinates, and project location context
    without mutating source files or performing file operations.
    """

    def __init__(self, mime_data: QMimeData, scene_pos: QPointF, project_location: Optional[str] = None):
        self.mime_data = mime_data
        self.scene_pos = scene_pos
        self.project_location = project_location

        self.paths: List[Path] = []
        if mime_data and mime_data.hasUrls():
            for url in mime_data.urls():
                if url.isLocalFile():
                    local_path = url.toLocalFile()
                    if local_path:
                        self.paths.append(Path(local_path))

    def has_files(self) -> bool:
        return len(self.paths) > 0

    def file_paths(self) -> List[str]:
        return [str(p) for p in self.paths if p.exists()]
