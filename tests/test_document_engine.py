import unittest

from engines.document.blocks import Block
from engines.document.document import Document
from engines.document.markdown_reader import MarkdownReader
from engines.document.markdown_writer import MarkdownWriter


class TestDocument(unittest.TestCase):

    def test_create_document(self):

        doc = Document(title="My Document")

        self.assertEqual(doc.title, "My Document")
        self.assertEqual(len(doc), 0)

    def test_add_block(self):

        doc = Document()

        block = Block(
            block_type="paragraph",
            content="Hello World"
        )

        doc.add(block)

        self.assertEqual(len(doc), 1)
        self.assertEqual(doc.blocks[0].content, "Hello World")

    def test_remove_block(self):

        doc = Document()

        block = Block(
            block_type="paragraph",
            content="Delete me"
        )

        doc.add(block)
        doc.remove(block)

        self.assertEqual(len(doc), 0)


class TestMarkdown(unittest.TestCase):

    def test_heading(self):

        md = "# Title"

        doc = MarkdownReader().load(md)

        self.assertEqual(len(doc), 1)

        block = doc.blocks[0]

        self.assertEqual(block.block_type, "heading")
        self.assertEqual(block.content, "Title")
        self.assertEqual(block.get("level"), 1)

    def test_paragraph(self):

        md = "Hello World"

        doc = MarkdownReader().load(md)

        self.assertEqual(len(doc), 1)
        self.assertEqual(doc.blocks[0].block_type, "paragraph")
        self.assertEqual(doc.blocks[0].content, "Hello World")

    def test_image(self):

        md = "![Front](Attachments/head.png)"

        doc = MarkdownReader().load(md)

        self.assertEqual(len(doc), 1)

        block = doc.blocks[0]

        self.assertEqual(block.block_type, "image")
        self.assertEqual(block.content, "Attachments/head.png")
        self.assertEqual(block.get("alt"), "Front")

    def test_writer(self):

        doc = Document()

        doc.add(
            Block(
                block_type="heading",
                content="Guardian",
                properties={"level": 1}
            )
        )

        doc.add(
            Block(
                block_type="paragraph",
                content="Ancient protector."
            )
        )

        text = MarkdownWriter().save(doc)

        self.assertIn("# Guardian", text)
        self.assertIn("Ancient protector.", text)

    def test_round_trip(self):

        original = """# Guardian

Ancient protector.

![Front](Attachments/head.png)
"""

        reader = MarkdownReader()
        writer = MarkdownWriter()

        doc = reader.load(original)

        markdown = writer.save(doc)

        doc2 = reader.load(markdown)

        self.assertEqual(len(doc.blocks), len(doc2.blocks))

        for b1, b2 in zip(doc.blocks, doc2.blocks):
            self.assertEqual(b1.block_type, b2.block_type)
            self.assertEqual(b1.content, b2.content)


if __name__ == "__main__":
    unittest.main()