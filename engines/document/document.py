from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator

from .blocks import Block


@dataclass(slots=True)
class Document:

    title: str = ""

    metadata: dict = field(default_factory=dict)

    blocks: list[Block] = field(default_factory=list)

    created: datetime = field(default_factory=datetime.now)

    modified: datetime = field(default_factory=datetime.now)

    def touch(self):

        self.modified = datetime.now()

    def append(self, block: Block):

        self.blocks.append(block)
        self.touch()

    def add(self, block: Block):
        self.append(block)

    def extend(self, blocks):

        self.blocks.extend(blocks)
        self.touch()

    def insert(self, index: int, block: Block):

        self.blocks.insert(index, block)
        self.touch()

    def remove(self, block: Block):

        self.blocks.remove(block)
        self.touch()

    def clear(self):

        self.blocks.clear()
        self.touch()

    def __iter__(self) -> Iterator[Block]:

        return iter(self.blocks)

    def __getitem__(self, index):

        return self.blocks[index]

    def __len__(self):

        return len(self.blocks)