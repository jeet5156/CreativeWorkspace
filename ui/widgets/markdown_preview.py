from pathlib import Path

import markdown

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">

<style>

body{
    font-family: "Segoe UI", sans-serif;
    background:#2b2b2b;
    color:#dddddd;
    margin:24px;
    line-height:1.6;
}

h1,h2,h3{
    border-bottom:1px solid #444;
    padding-bottom:4px;
}

pre{
    background:#1e1e1e;
    padding:12px;
    border-radius:6px;
    overflow-x:auto;
}

code{
    background:#3b3b3b;
    padding:2px 4px;
    border-radius:4px;
}

blockquote{
    border-left:4px solid #5a9bd5;
    margin-left:0;
    padding-left:12px;
    color:#bbbbbb;
}

table{
    border-collapse:collapse;
}

th,td{
    border:1px solid #555;
    padding:6px;
}

img{
    max-width:100%;
    height:auto;
    display:block;
    margin:12px 0;
}

a{
    color:#6cb8ff;
    text-decoration:none;
}

a:hover{
    text-decoration:underline;
}

</style>

</head>

<body>

__CONTENT__

</body>
</html>
"""


class MarkdownPreview(QWebEngineView):

    def __init__(self):
        super().__init__()

    def set_markdown(self, text: str, base_path: str | None = None):

        html = markdown.markdown(
            text,
            extensions=[
                "tables",
                "fenced_code",
            ]
        )

        page = HTML_TEMPLATE.replace("__CONTENT__", html)

        if base_path:
            base_url = QUrl.fromLocalFile(
                str(Path(base_path).resolve()) + "/"
            )
        else:
            base_url = QUrl()

        self.setHtml(page, base_url)