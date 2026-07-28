from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout

from engines.document.blocks import Block


class BlockWidget(QFrame):
    """
    Base class for every editable block in the document editor.

    Every widget owns exactly one document Block.
    """

    changed = Signal()
    selected = Signal(object)

    def __init__(self, block: Block):
        super().__init__()

        self._block = block

        self.setFrameShape(QFrame.NoFrame)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 2, 0, 2)
        self.layout.setSpacing(0)

    # -------------------------------------------------
    # Model
    # -------------------------------------------------

    @property
    def block(self):

        return self._block

    def update_block(self):

        """
        Override in subclasses.
        Copies widget state into Block.
        """
        return self._block

    def load_block(self):

        """
        Override in subclasses.
        Copies Block into widget.
        """
        pass

    # -------------------------------------------------
    # Selection
    # -------------------------------------------------

    def mousePressEvent(self, event):

        self.selected.emit(self)

        super().mousePressEvent(event)