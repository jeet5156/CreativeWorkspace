from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


# ============================================================
# Base Block
# ============================================================

@dataclass
class Block:

    id: str = field(default_factory=lambda: str(uuid4()))

    @property
    def type(self):
        return self.__class__.__name__.replace("Block", "").lower()


# ============================================================
# Paragraph
# ============================================================

@dataclass
class ParagraphBlock(Block):

    text: str = ""


# ============================================================
# Heading
# ============================================================

@dataclass
class HeadingBlock(Block):

    text: str = ""

    level: int = 1


# ============================================================
# Image
# ============================================================

@dataclass
class ImageBlock(Block):

    path: str = ""

    alt: str = ""

    caption: str = ""

    width: int | None = None


# ============================================================
# Quote
# ============================================================

@dataclass
class QuoteBlock(Block):

    text: str = ""


# ============================================================
# Checklist
# ============================================================

@dataclass
class ChecklistItem:

    text: str

    checked: bool = False


@dataclass
class ChecklistBlock(Block):

    items: list[ChecklistItem] = field(default_factory=list)