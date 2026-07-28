from __future__ import annotations

from .blocks import (
    ParagraphBlock,
    HeadingBlock,
    ImageBlock,
    QuoteBlock,
    ChecklistBlock,
)
from .serializer import DocumentWriter


class MarkdownWriter(DocumentWriter):

    def save(self, document) -> str:

        lines = []

        for block in document:

            # -------------------------------------------------
            # Heading
            # -------------------------------------------------

            if isinstance(block, HeadingBlock):

                level = max(1, min(block.level, 6))

                lines.append(
                    f'{"#" * level} {block.text}'
                )

            # -------------------------------------------------
            # Paragraph
            # -------------------------------------------------

            elif isinstance(block, ParagraphBlock):

                text = block.text.rstrip()

                if text:
                    lines.append(text)

            # -------------------------------------------------
            # Image
            # -------------------------------------------------

            elif isinstance(block, ImageBlock):

                lines.append(
                    f'![{block.alt}]({block.path})'
                )

                if block.caption.strip():

                    lines.append(block.caption.strip())

            # -------------------------------------------------
            # Quote
            # -------------------------------------------------

            elif isinstance(block, QuoteBlock):

                for line in block.text.splitlines():

                    lines.append(f"> {line}")

            # -------------------------------------------------
            # Checklist
            # -------------------------------------------------

            elif isinstance(block, ChecklistBlock):

                for item in block.items:

                    mark = "x" if item.checked else " "

                    lines.append(
                        f"- [{mark}] {item.text}"
                    )

            else:

                raise TypeError(
                    f"Unsupported block: {type(block).__name__}"
                )

            lines.append("")

        while lines and lines[-1] == "":
            lines.pop()

        return "\n".join(lines)