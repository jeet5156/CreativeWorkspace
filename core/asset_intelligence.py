import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Version regex: matches _v001, .v01, -v3, _V1, etc.
VERSION_PATTERN = re.compile(r'(?i)(?:^|[._-])(v\d{1,4})(?=[._-]|$)', re.IGNORECASE)

# LOD regex: matches _lod0, .LOD1, -lod2, _LOD0
LOD_PATTERN = re.compile(r'(?i)(?:^|[._-])(lod\d{1,2})(?=[._-]|$)', re.IGNORECASE)

# Frame Sequence regex: matches <prefix><sep><digits>.<ext>
# e.g., shot_01.0001.exr -> prefix="shot_01", sep=".", frame="0001", ext="exr"
SEQUENCE_PATTERN = re.compile(r'^(?P<prefix>.+?)(?P<sep>[._-])(?P<frame>\d{2,8})\.(?P<ext>[a-zA-Z0-9]+)$')


def detect_version(filename: str) -> Optional[str]:
    """Detect version token (e.g. 'v001', 'v02', 'v3') from filename."""
    stem = Path(filename).stem
    m = VERSION_PATTERN.search(stem)
    if m:
        return m.group(1).lower()
    return None


def detect_lod(filename: str) -> Optional[str]:
    """Detect LOD level token (e.g. 'LOD0', 'LOD1') from filename."""
    stem = Path(filename).stem
    m = LOD_PATTERN.search(stem)
    if m:
        return m.group(1).upper()
    return None


SEQUENCE_IMAGE_EXTS = {"exr", "png", "jpg", "jpeg", "tga", "tif", "tiff", "dpx", "hdr", "cin"}


def parse_sequence_component(filename: str) -> Optional[dict]:
    """Parse filename into sequence components if it matches frame pattern and is an image sequence format."""
    m = SEQUENCE_PATTERN.match(filename)
    if not m:
        return None
    ext = m.group("ext").lower()
    if ext not in SEQUENCE_IMAGE_EXTS:
        return None
    prefix = m.group("prefix")
    sep = m.group("sep")
    frame_str = m.group("frame")
    try:
        frame_num = int(frame_str)
    except ValueError:
        return None

    return {
        "prefix": prefix,
        "sep": sep,
        "frame_str": frame_str,
        "frame_num": frame_num,
        "padding": len(frame_str),
        "ext": ext,
        "key": (prefix, sep, len(frame_str), ext),
    }


def group_assets_and_sequences(assets: List[Dict]) -> List[Dict]:
    """Non-destructive presentation-layer grouping:
    - Identifies sets of 2+ sequential image frames and collapses them into a virtual sequence asset.
    - Single/isolated frame items remain individual assets.
    - Annotates all assets with detected `version` and `lod` if present.
    """
    # First annotate version and lod
    for a in assets:
        fn = a.get("filename", "")
        if "version" not in a:
            v = detect_version(fn)
            if v:
                a["version"] = v
        if "lod" not in a:
            l = detect_lod(fn)
            if l:
                a["lod"] = l

    # Group potential sequences
    candidates = {}
    non_sequence_assets = []

    for a in assets:
        fn = a.get("filename", "")
        parsed = parse_sequence_component(fn)
        # Sequence grouping applies to renders, assets, and references with 2+ frames
        if parsed and str(a.get("category", "")).lower() in ("renders", "assets", "references"):
            rp = (a.get("relative_path") or "").replace("\\", "/")
            parent_dir = rp.rsplit("/", 1)[0] if "/" in rp else ""
            key = (parent_dir, parsed["key"])
            if key not in candidates:
                candidates[key] = []
            candidates[key].append((parsed, a))
        else:
            non_sequence_assets.append(a)

    result = []

    for key, items in candidates.items():
        if len(items) >= 2:
            # Sort by frame number
            items.sort(key=lambda x: x[0]["frame_num"])
            frame_strs = [x[0]["frame_str"] for x in items]
            first_parsed, first_asset = items[0]
            last_parsed, last_asset = items[-1]

            prefix = first_parsed["prefix"]
            sep = first_parsed["sep"]
            pad = first_parsed["padding"]
            ext = first_parsed["ext"]
            pad_hashes = "#" * pad

            start_str = frame_strs[0]
            end_str = frame_strs[-1]
            frame_count = len(items)
            frame_range_str = f"{start_str} – {end_str} ({frame_count} frames)"

            seq_filename = f"{prefix}{sep}{pad_hashes}.{ext}"
            parent_dir = key[0]
            seq_rel_path = f"{parent_dir}/{seq_filename}" if parent_dir else seq_filename

            # Virtual sequence item
            seq_asset = {
                "id": f"seq_{first_asset.get('id')}",
                "filename": seq_filename,
                "relative_path": seq_rel_path,
                "absolute_path": first_asset.get("absolute_path"),
                "category": first_asset.get("category", "Renders"),
                "friendly_type": f"{ext.upper()} Sequence",
                "is_sequence": True,
                "frame_range": frame_range_str,
                "frame_count": frame_count,
                "start_frame": start_str,
                "end_frame": end_str,
                "first_frame_filename": first_asset.get("filename"),
                "last_frame_filename": last_asset.get("filename"),
                "frame_assets": [it[1] for it in items],
                "date_added": first_asset.get("date_added"),
                "created_at": first_asset.get("created_at"),
                "updated_at": first_asset.get("updated_at"),
                "size": sum(it[1].get("size", 0) or 0 for it in items),
                "tags": first_asset.get("tags", []),
                "notes": first_asset.get("notes", ""),
                "version": detect_version(seq_filename) or first_asset.get("version"),
            }
            result.append(seq_asset)
        else:
            for _, asset in items:
                result.append(asset)

    result.extend(non_sequence_assets)
    return result
