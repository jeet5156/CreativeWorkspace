from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem
)


class Explorer(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)

        layout.addWidget(self.tree)

        self.populate()

    def populate(self):
        projects = QTreeWidgetItem(["Projects"])
        ideas = QTreeWidgetItem(["Ideas"])
        clients = QTreeWidgetItem(["Clients"])
        assets = QTreeWidgetItem(["Assets"])
        learning = QTreeWidgetItem(["Learning"])

        self.tree.addTopLevelItem(projects)
        self.tree.addTopLevelItem(ideas)
        self.tree.addTopLevelItem(clients)
        self.tree.addTopLevelItem(assets)
        self.tree.addTopLevelItem(learning)

        self.tree.expandAll()