from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy


class ImagePreview(QLabel):
    """
    Reusable image preview widget.

    Features
    --------
    • Smooth scaling
    • Keeps aspect ratio
    • Automatically rescales on resize
    • Placeholder when no image exists
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._pixmap = None

        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(220, 220)
        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )

        self.setStyleSheet("""
            QLabel{
                border:1px solid #555;
                border-radius:6px;
                background:#262626;
                color:#999;
            }
        """)

        self.clear()

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def load_image(self, image_path):

        path = Path(image_path)

        if not path.exists():
            self.clear()
            return

        # Decode from the file on every load. QPixmap(filename) can reuse a
        # cached image when a snapshot is replaced at the same path.
        pixmap = QPixmap.fromImage(QImage(str(path)))

        if pixmap.isNull():
            self.clear()
            return

        self._pixmap = pixmap
        self._update_pixmap()

    def clear(self):

        self._pixmap = None
        self.setText("No Snapshot Available")

    # ---------------------------------------------------------
    # Internal
    # ---------------------------------------------------------

    def resizeEvent(self, event):

        super().resizeEvent(event)

        if self._pixmap:
            self._update_pixmap()

    def _update_pixmap(self):

        if not self._pixmap:
            return

        scaled = self._pixmap.scaled(
            self.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        self.setPixmap(scaled)