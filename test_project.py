from PySide6.QtWidgets import QApplication
from ui.widgets.markdown_preview import MarkdownPreview

app = QApplication([])

w = MarkdownPreview()

w.set_markdown("""
# Knight

**Helmet**

- Sculpt
- Bake

> Client feedback
""")

w.resize(900,700)
w.show()

app.exec()