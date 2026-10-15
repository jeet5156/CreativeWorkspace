"""Dynamic portable path resolution for CreativeWorkspace.

Resolves all application and shared paths relative to the canonical module location,
ensuring zero dependency on working directory, hardcoded drive letters, or usernames.
"""

import os
from pathlib import Path
from typing import Optional


def get_app_root() -> Path:
    """Return the absolute root directory of the application repository.

    Dynamically resolved from this file's location: <root>/core/paths.py -> <root>.
    Can be overridden via CREATIVE_WORKSPACE_APP_ROOT environment variable for testing.
    """
    override = os.environ.get("CREATIVE_WORKSPACE_APP_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parent.parent


def get_shared_data_dir() -> Path:
    """Return the shared application-managed data directory (<APP_ROOT>/data).

    Can be overridden via CREATIVE_WORKSPACE_SHARED_DATA_DIR environment variable.
    """
    override = os.environ.get("CREATIVE_WORKSPACE_SHARED_DATA_DIR")
    if override:
        path = Path(override).resolve()
    else:
        path = get_app_root() / "data"
    return path


def get_shared_clients_dir() -> Path:
    """Return the shared clients directory (<APP_ROOT>/data/clients)."""
    return get_shared_data_dir() / "clients"


def get_shared_workbench_boards_dir() -> Path:
    """Return the shared global Workbench boards directory (<APP_ROOT>/data/workbench/boards)."""
    return get_shared_data_dir() / "workbench" / "boards"


def get_shared_workbench_images_dir() -> Path:
    """Return the shared global Workbench images directory (<APP_ROOT>/data/workbench/images)."""
    return get_shared_data_dir() / "workbench" / "images"


def get_shared_knowledge_dir() -> Path:
    """Return the shared Knowledge base directory (<APP_ROOT>/data/knowledge)."""
    return get_shared_data_dir() / "knowledge"


def get_shared_markups_dir() -> Path:
    """Return the shared Visual Markups directory (<APP_ROOT>/data/markups)."""
    return get_shared_data_dir() / "markups"


def get_shared_library_dir() -> Path:
    """Return the shared Global Asset Library directory (<APP_ROOT>/data/library)."""
    return get_shared_data_dir() / "library"


def get_local_config_dir() -> Path:
    """Return the machine-local user configuration directory (~/.creativeworkspace).

    Used strictly for machine-specific settings (window geometry, recent projects,
    local AI endpoints, and local activity log).
    Can be overridden via CREATIVE_WORKSPACE_LOCAL_CONFIG_DIR environment variable.
    """
    override = os.environ.get("CREATIVE_WORKSPACE_LOCAL_CONFIG_DIR")
    if override:
        path = Path(override).resolve()
    else:
        path = Path.home() / ".creativeworkspace"
    return path


def get_local_cache_dir() -> Path:
    """Return the machine-local cache directory (~/.creativeworkspace/cache).

    Used for regenerable derived binary caches such as thumbnails.
    """
    return get_local_config_dir() / "cache"
