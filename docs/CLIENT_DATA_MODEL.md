# CreativeWorkspace - Client Data Model & Serialization

## Storage Schema Overview

Project data is stored locally within each creative project folder inside a hidden metadata directory `.creativeworkspace/`.

```
<project_root>/
├── Assets/
├── References/
└── .creativeworkspace/
    ├── lab/
    │   ├── Main.lab.json          <-- Board canvas item state
    │   └── Environment.lab.json
    └── thumbnails/
        ├── 71e077a5044e5eb0...jpg  <-- SHA-1 hashed thumbnail cache
        └── da8071395d213be...jpg
```

---

## Board Persistence Format (`<board_name>.lab.json`)

```json
{
  "version": 1,
  "name": "Main",
  "created_at": "2026-08-05T14:00:00",
  "updated_at": "2026-08-05T20:30:00",
  "viewport": {
    "zoom": 1.0,
    "pan_x": 0.0,
    "pan_y": 0.0
  },
  "items": [
    {
      "id": "e10faa8e-86d2-4c8f-b037-7685c5d96801",
      "type": "frame.section",
      "transform": {
        "x": 100.0,
        "y": 80.0,
        "z": -10.0,
        "width": 480.0,
        "height": 360.0,
        "rotation": 0.0
      },
      "style": {
        "background": "#1E2029",
        "accent": "#A855F7"
      },
      "metadata": {
        "version": 1,
        "locked": false
      },
      "payload": {
        "title": "Character Exploration",
        "color_theme": "purple",
        "collapsed": false
      }
    },
    {
      "id": "df89052a-2543-43ac-b1be-68db5064e0a9",
      "type": "image.reference",
      "transform": {
        "x": 140.0,
        "y": 140.0,
        "z": 1.0,
        "width": 320.0,
        "height": 260.0,
        "rotation": 0.0
      },
      "style": {
        "background": "#1E2029",
        "accent": "#38BDF8"
      },
      "metadata": {
        "version": 1,
        "locked": false
      },
      "payload": {
        "image_path": "References/concept.png",
        "filename": "concept.png",
        "title": "Hero Key Art",
        "caption": "Primary environment plate",
        "fit_mode": "fit",
        "layout": {
          "aspect_ratio": 1.23,
          "width": 320.0,
          "height": 260.0,
          "raw_width": 1920,
          "raw_height": 1080
        }
      }
    }
  ]
}
```

---

## Serialization & Deserialization Lifecycle

### 1. `to_dict()`
- Converts `NodeItem` state into Python dict using `copy.deepcopy()` on nested dictionaries (`payload`, `layout`).
- Ensures payload dictionaries are completely isolated per node instance.

### 2. `from_dict(data)`
- Restores `id`, `transform` (`x`, `y`, `width`, `height`), `metadata.locked`, and `payload`.
- **Preserves Unique UUIDs**: Ensures `data.get("id")` is assigned only if valid and non-empty, preventing `"None"` string key collisions in canvas `_items_map`.
- **Post-Deserialization Hook**: In `ImageNodeItem.from_dict()`, automatically triggers `_request_thumbnail()` so images restore immediately when boards are loaded from disk.
