# CreativeWorkspace - Client Development Roadmap

## Roadmap Overview

This document tracks completed milestones, current progress, and upcoming sprints for the CreativeWorkspace desktop application.

---

## Completed Milestones & Sprints

### ✅ Sprint 1 – Core Canvas & Node Registry Architecture
- Established declarative `NodeRegistry` as single source of truth.
- Implemented `NodeCapability` bitflags replacing inheritance branching.
- Created `InfiniteCanvas` with camera panning (spacebar/middle-drag), zooming, and dynamic dot grid (`#14161D`).

### ✅ Sprint 2 – Asset & Thumbnail Service Pipeline
- Implemented asynchronous thread-pool `ThumbnailService`.
- SHA-1 disk caching under `.creativeworkspace/thumbnails/`.
- Relative project path resolution for portable workspace folders.

### ✅ Sprint 3 – Frame Node Foundation
- Created `FrameNodeItem` lightweight organizational container.
- Implemented **pure geometric membership** (`contained_nodes()`) without child parentage.
- Synchronized drag movement for contained spatial items.
- Added 6 color themes (**Purple**, **Blue**, **Green**, **Amber**, **Red**, **Gray**).
- Added header collapse / expand functionality.

### ✅ Sprint 3.5A – Image Node Stabilization
- Established explicit 5-state rendering machine (`ImageNodeState`: `EMPTY`, `LOADING`, `READY`, `MISSING`, `ERROR`).
- Overrode `from_dict()` in `ImageNodeItem` to trigger `_request_thumbnail()` deterministically on project reload, canvas reload, undo/redo, and copy/paste.
- Muted internal telemetry with toggleable `DEBUG_LOGGING = False`.
- Added permanent **10-node save & reopen regression test** in `tests/test_image_node.py`.

### ✅ Sprint 3.5B – Frame UX
- Added interactive `14px` bottom-right resize handle (`◢`) with diagonal resize cursor (`Qt.SizeFDiagCursor`) and live dragging enforcing `240x180` minimum bounds.
- Implemented seamless inline header title editing (`QLineEdit` overlay).
- Polished visual hierarchy (`12px` radius, translucent fill `alpha = 30`, `3px` top/left accent bar, horizontal header divider line).
- Implemented dynamic drag hover highlight feedback (accent glow border when dragging spatial nodes over a Frame).

---

## Active & Upcoming Sprints

### 🚀 Sprint 3.5C – Canvas Polish (In Planning)
- **Autosave Debounce**: Set 500ms single-shot debounce timer (`_item_save_timer`) on `LabPanel` to prevent disk thrashing during rapid node dragging/resizing.
- **Board Dirty State Indicator**: Add `✓ Saved` / `● Unsaved Changes` visual badge to `LabPanel` header.
- **Selection Visuals & Resize Handles**: Polish selection rings and corner handles across spatial node items (`NodeItem.draw_selection_outline()`).
- **Context Menu Polish**: Standardize context menus with consistent styling, separators, icons, and keyboard shortcuts across canvas items.

### 🔮 Sprint 3.6 – Advanced Frame Features & Auto-Expand
- **Auto-Expand Section Bounds**: Automatically expand Frame dimensions when dragging spatial nodes near the right or bottom edges of a Frame (Figma Sections style).
- **Multi-Frame Layout Snapping**: Alignment guides and snapping when moving multiple Frames.

### 🔮 Sprint 4 – Rich Media & Reference Node Types
- **Video Player Nodes**: Embedded video playback for animation clips (`.mp4`, `.webm`).
- **PDF Document Nodes**: Multi-page document preview cards.
- **Audio Clip Nodes**: Waveform reference audio cards.
- **Interactive Checklist Nodes**: To-do task list cards.

### 🔮 Sprint 5 – Workspace Collaboration & Export
- Multi-board template presets (Character Concept Board, Environment Reference Board, Production Moodboard).
- High-resolution canvas PNG export.
- Workspace export and archive packaging.
