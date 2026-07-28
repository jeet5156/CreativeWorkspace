from __future__ import annotations

import re

from .blocks import (
    ParagraphBlock,
    HeadingBlock,
    ImageBlock,
    QuoteBlock,
    ChecklistBlock,
    ChecklistItem,
)
from .document import Document
from .serializer import DocumentReader


HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
IMAGE_RE = re.compile(r"^!\[(.*?)\]\((.*?)\)$")
QUOTE_RE = re.compile(r"^>\s?(.*)$")
CHECK_RE = re.compile(r"^- \[( |x|X)\] (.*)$")


class MarkdownReader(DocumentReader):

    def load(self, markdown: str) -> Document:

        document = Document()

        paragraph = []
        checklist = []

        def flush_paragraph():

            nonlocal paragraph

            if not paragraph:
                return

            text = "\n".join(paragraph).rstrip()

            if text:
                document.append(
                    ParagraphBlock(
                        text=text
                    )
                )

            paragraph = []

        def flush_checklist():

            nonlocal checklist

            if not checklist:
                return

            document.append(
                ChecklistBlock(
                    items=checklist
                )
            )

            checklist = []

        for raw_line in markdown.splitlines():

            line = raw_line.rstrip()

            # -------------------------------------------------
            # Blank Line
            # -------------------------------------------------

            if line.strip() == "":

                flush_paragraph()
                flush_checklist()

                continue

            # -------------------------------------------------
            # Heading
            # -------------------------------------------------

            match = HEADING_RE.match(line)

            if match:

                flush_paragraph()
                flush_checklist()

                hashes, title = match.groups()

                document.append(
                    HeadingBlock(
                        text=title,
                        level=len(hashes),
                    )
                )

                continue

            # -------------------------------------------------
            # Image
            # -------------------------------------------------

            match = IMAGE_RE.match(line.strip())

            if match:

                flush_paragraph()
                flush_checklist()

                alt, path = match.groups()

                document.append(
                    ImageBlock(
                        path=path,
                        alt=alt,
                    )
                )

                continue

            # -------------------------------------------------
            # Quote
            # -------------------------------------------------

            match = QUOTE_RE.match(line)

            if match:

                flush_paragraph()
                flush_checklist()

                document.append(
                    QuoteBlock(
                        text=match.group(1)
                    )
                )

                continue

            # -------------------------------------------------
            # Checklist
            # -------------------------------------------------

            match = CHECK_RE.match(line)

            if match:

                flush_paragraph()

                checked, text = match.groups()

                checklist.append(
                    ChecklistItem(
                        text=text,
                        checked=checked.lower() == "x",
                    )
                )

                continue

            # -------------------------------------------------
            # Normal Paragraph
            # -------------------------------------------------

            flush_checklist()

            paragraph.append(line)

        flush_paragraph()
        flush_checklist()

        return document