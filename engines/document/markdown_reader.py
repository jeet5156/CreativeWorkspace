from __future__ import annotations

import re

from .blocks import Block
from .document import Document
from .serializer import DocumentReader


IMAGE_RE = re.compile(r"!\[(.*?)\]\((.*?)\)")


class MarkdownReader(DocumentReader):

    def load(self, text: str) -> Document:

        document = Document()

        paragraph = []

        def flush_paragraph():
            if paragraph:
                document.add(
                    Block(
                        block_type="paragraph",
                        content="\n".join(paragraph).strip()
                    )
                )
                paragraph.clear()

        for line in text.splitlines():

            stripped = line.strip()

            if not stripped:
                flush_paragraph()
                continue

            if stripped.startswith("#"):

                flush_paragraph()

                level = len(stripped) - len(stripped.lstrip("#"))

                title = stripped[level:].strip()

                document.add(
                    Block(
                        block_type="heading",
                        content=title,
                        properties={
                            "level": level
                        }
                    )
                )

                continue

            match = IMAGE_RE.fullmatch(stripped)

            if match:

                flush_paragraph()

                alt, path = match.groups()

                document.add(
                    Block(
                        block_type="image",
                        content=path,
                        properties={
                            "alt": alt
                        }
                    )
                )

                continue

            paragraph.append(line)

        flush_paragraph()

        return document