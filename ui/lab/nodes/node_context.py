from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class NodeContext:
    """Standardized shared context object passed to all spatial Lab NodeItems.

    Provides a clean, uniform contract for shared services (ThumbnailService, AssetService,
    project location, app context) without hardcoding individual setters per node type.
    """

    project_location: Optional[str] = None
    thumbnail_service: Optional[Any] = None
    asset_service: Optional[Any] = None
    app_context: Optional[Any] = None
    project: Optional[Any] = None
    board_id: Optional[str] = None
