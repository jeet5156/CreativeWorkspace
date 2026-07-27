from enum import Enum


class BlockType(str, Enum):
    """
    All supported document block types.
    """

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    IMAGE = "image"

    CHECKLIST = "checklist"
    QUOTE = "quote"
    CODE = "code"
    DIVIDER = "divider"

    CALLOUT = "callout"

    TABLE = "table"

    GALLERY = "gallery"

    ASSET = "asset"

    TIMELINE = "timeline"

    EMBED = "embed"