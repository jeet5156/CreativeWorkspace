from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .blocks import Block


@dataclass
class Document:

    title: str = ""

    blocks: list[Block] = field(default_factory=list)

    metadata: dict = field(default_factory=dict)

    created: datetime = field(default_factory=datetime.now)

    modified: datetime = field(default_factory=datetime.now)

    def clear(self):

        self.blocks.clear()

    def add(self, block: Block):

        self.blocks.append(block)

        self.modified = datetime.now()

    def remove(self, block: Block):

        self.blocks.remove(block)

        self.modified = datetime.now()

    def __iter__(self):

        return iter(self.blocks)

    def __len__(self):

        return len(self.blocks)