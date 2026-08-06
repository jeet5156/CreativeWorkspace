from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


# ==========================================================
# Base Block
# ==========================================================

@dataclass(slots=True)
class Block:

    id: str = field(default_factory=lambda: str(uuid4()))

    @property
    def type(self) -> str:
        return self.__class__.__name__.replace("Block", "").lower()

    @property
    def block_type(self) -> str:
        return self.type

    @property
    def content(self) -> str:
        return getattr(self, "text", getattr(self, "path", ""))

    def get(self, key: str, default=None):
        return getattr(self, key, default)


# ==========================================================
# Paragraph
# ==========================================================

@dataclass(slots=True)
class ParagraphBlock(Block):

    text: str = ""


# ==========================================================
# Heading
# ==========================================================

@dataclass(slots=True)
class HeadingBlock(Block):

    text: str = ""
    level: int = 1


# ==========================================================
# Image
# ==========================================================

@dataclass(slots=True)
class ImageBlock(Block):

    path: str = ""
    alt: str = ""
    caption: str = ""
    width: int | None = None


# ==========================================================
# Quote
# ==========================================================

@dataclass(slots=True)
class QuoteBlock(Block):

    text: str = ""


# ==========================================================
# Checklist
# ==========================================================

@dataclass(slots=True)
class ChecklistItem:

    text: str
    checked: bool = False


@dataclass(slots=True)
class ChecklistBlock(Block):

    items: list[ChecklistItem] = field(default_factory=list)