from __future__ import annotations

from .serializer import DocumentWriter


class MarkdownWriter(DocumentWriter):

    def save(self, document):

        output = []

        for block in document:

            if block.block_type == BlockType.HEADING:

                level = block.get("level", 1)

                output.append(
                    "#" * level + " " + str(block.content)
                )

            elif block.block_type == "paragraph":

                output.append(str(block.content))

            elif block.block_type == "image":

                alt = block.get("alt", "")

                output.append(
                    f"![{alt}]({block.content})"
                )

            output.append("")

        return "\n".join(output)