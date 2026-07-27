from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QToolBar


class DocumentToolbar(QToolBar):

    # ---------------------------------------------------------
    # Signals
    # ---------------------------------------------------------

    undo_requested = Signal()
    redo_requested = Signal()

    save_requested = Signal()

    bold_requested = Signal()
    italic_requested = Signal()
    underline_requested = Signal()

    heading_requested = Signal(int)

    bullet_requested = Signal()
    checklist_requested = Signal()
    quote_requested = Signal()

    image_requested = Signal()
    link_requested = Signal()
    divider_requested = Signal()

    # ---------------------------------------------------------

    def __init__(self):
        super().__init__("Document")

        self.setMovable(False)

        self.build()

    # ---------------------------------------------------------

    def build(self):

        self.clear()

        # ---------- Undo / Redo ----------

        self.add_action(
            "↶",
            "Undo",
            self.undo_requested.emit,
        )

        self.add_action(
            "↷",
            "Redo",
            self.redo_requested.emit,
        )

        self.addSeparator()

        # ---------- Headings ----------

        self.add_action(
            "H1",
            "Heading 1",
            lambda: self.heading_requested.emit(1),
        )

        self.add_action(
            "H2",
            "Heading 2",
            lambda: self.heading_requested.emit(2),
        )

        self.add_action(
            "H3",
            "Heading 3",
            lambda: self.heading_requested.emit(3),
        )

        self.addSeparator()

        # ---------- Text ----------

        self.add_action(
            "B",
            "Bold",
            self.bold_requested.emit,
        )

        self.add_action(
            "I",
            "Italic",
            self.italic_requested.emit,
        )

        self.add_action(
            "U",
            "Underline",
            self.underline_requested.emit,
        )

        self.addSeparator()

        # ---------- Lists ----------

        self.add_action(
            "•",
            "Bullet List",
            self.bullet_requested.emit,
        )

        self.add_action(
            "☑",
            "Checklist",
            self.checklist_requested.emit,
        )

        self.add_action(
            ">",
            "Quote",
            self.quote_requested.emit,
        )

        self.addSeparator()

        # ---------- Insert ----------

        self.add_action(
            "🖼",
            "Insert Image",
            self.image_requested.emit,
        )

        self.add_action(
            "🔗",
            "Insert Link",
            self.link_requested.emit,
        )

        self.add_action(
            "―",
            "Divider",
            self.divider_requested.emit,
        )

        self.addSeparator()

        # ---------- Save ----------

        self.add_action(
            "💾",
            "Save",
            self.save_requested.emit,
        )

    # ---------------------------------------------------------

    def add_action(
        self,
        text,
        tooltip,
        slot,
    ):

        action = QAction(text, self)

        action.setToolTip(tooltip)

        action.triggered.connect(slot)

        self.addAction(action)

        return action