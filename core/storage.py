"""Atomic file storage utilities for CreativeWorkspace.

Provides safe atomic JSON write/read operations using temporary file replacement
and Windows file-lock retry handling.

Note: Atomic writes prevent partially-written / corrupted files on disk during power loss
or sync read-locks, but do not by themselves resolve concurrent multi-user edit conflicts.
"""

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Optional, Tuple, Union


def atomic_write_json(
    target_path: Union[str, Path],
    data: Any,
    indent: int = 2,
    max_retries: int = 3,
    retry_delay: float = 0.05,
    ensure_ascii: bool = False,
) -> Path:
    """Atomically write JSON data to target_path using a temporary file in the same folder.

    Includes retry backoff for transient Windows file locks (e.g., from cloud sync engines).
    """
    target = Path(target_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    # Use a unique temp file in the same directory to ensure atomic rename on the same filesystem
    temp_fd, temp_path_str = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f"tmp_{target.stem}_",
        suffix=".tmp",
    )
    temp_path = Path(temp_path_str)

    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass  # fsync may not be supported on some virtual/network filesystems

        # Attempt atomic replace with retry on Windows lock errors
        last_error = None
        for attempt in range(max_retries):
            try:
                os.replace(str(temp_path), str(target))
                last_error = None
                break
            except (PermissionError, OSError) as err:
                last_error = err
                time.sleep(retry_delay * (2 ** attempt))

        if last_error is not None:
            raise last_error

        return target
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def safe_read_json(
    target_path: Union[str, Path],
    default: Any = None,
) -> Tuple[Any, Optional[str]]:
    """Safely read and parse a JSON file.

    Returns:
        (data, None) if successful.
        (default, error_message) if file is missing, empty, or malformed.
    """
    path = Path(target_path)
    if not path.exists():
        return default, "File not found"

    if path.stat().st_size == 0:
        return default, "File is empty"

    try:
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
        return data, None
    except json.JSONDecodeError as err:
        return default, f"JSON decode error: {err}"
    except Exception as err:
        return default, f"Read error: {err}"
