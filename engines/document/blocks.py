from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class Block:
    """
    Base block for every document element.

    Examples:
        heading
        paragraph
        image
        checklist
        quote
        code
        callout
        gallery
        asset
    """

    block_type: str

    content: Any = None

    properties: dict[str, Any] = field(default_factory=dict)

    id: str = field(default_factory=lambda: str(uuid4()))

    def get(self, key: str, default=None):
        return self.properties.get(key, default)

    def set(self, key: str, value):
        self.properties[key] = value