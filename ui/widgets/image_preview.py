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

        from PySide6.QtGui import QImageReader

        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        size = reader.size()

        if not size.isValid():
            self.clear()
            return

        w, h = size.width(), size.height()
        est_mb = (w * h * 4) / (1024 * 1024)
        if est_mb > 256.0:
            print(f"[IMAGE PREVIEW] Skipping oversized image (>256MB decoding limit): {path} ({w}x{h}, est. {est_mb:.1f} MB)")
            self.clear()
            return

        target_size = size.scaled(self.size() if self.size().width() > 10 else QSize(400, 300), Qt.KeepAspectRatio)
        reader.setScaledSize(target_size)
        img = reader.read()

        if img.isNull():
            self.clear()
            return

        self._pixmap = QPixmap.fromImage(img)
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