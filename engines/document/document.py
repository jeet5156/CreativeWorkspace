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

    # ----------------------------

    def touch(self):

        self.modified = datetime.now()

    # ----------------------------

    def append(self, block: Block):

        self.blocks.append(block)
        self.touch()

    def insert(self, index: int, block: Block):

        self.blocks.insert(index, block)
        self.touch()

    def remove(self, block: Block):

        self.blocks.remove(block)
        self.touch()

    def replace(
        self,
        old: Block,
        new: Block,
    ):

        index = self.blocks.index(old)

        self.blocks[index] = new

        self.touch()

    def move(
        self,
        old_index,
        new_index,
    ):

        block = self.blocks.pop(old_index)

        self.blocks.insert(
            new_index,
            block,
        )

        self.touch()

    def clear(self):

        self.blocks.clear()

        self.touch()

    # ----------------------------

    def __iter__(self):
        return iter(self.blocks)

    def __len__(self):
        return len(self.blocks)

    def __getitem__(self, index):
        return self.blocks[index]