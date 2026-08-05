# CreativeWorkspace - Client Architecture

## Executive Overview

**CreativeWorkspace** is a desktop application built for digital artists, game developers, and creative directors to manage project assets, reference imagery, notes, and spatial moodboards.

The core architecture prioritizes **long-term maintainability**, **localized modifications**, **modular services**, and **clean composition**.

---

## Core Architecture Layers

```
┌────────────────────────────────────────────────────────────────────────┐
│                        MainWindow / UI Shell                           │
├───────────────────┬──────────────────────┬─────────────────────────────┤
│  Explorer Panel   │   Dashboard / Canvas  │       Inspector Panel       │
│ ("Where do I go?")│ ("What is happening?")│    ("What can I edit?")     │
└───────────────────┴──────────┬───────────┴─────────────────────────────┘
                               │ Delegates actions
                               ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Services Layer                                  │
├───────────────────┬──────────────────────┬─────────────────────────────┤
│   FolderService   │   ThumbnailService   │         LabService          │
│(FileSystem & Tree)│  (Async Thumbnails)  │  (Board & Node Storage)     │
└───────────────────┴──────────┬───────────┴─────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    Spatial Node System (Lab)                           │
├────────────────────────────────────────────────────────────────────────┤
│ • NodeRegistry (Single Source of Truth)                                 │
│ • NodeDefinition (Declarative Schema & Capabilities)                   │
│ • NodeItem (Spatial QGraphicsObject Base)                              │
│   ├── FrameNodeItem (Lightweight Geometric Container)                   │
│   ├── ImageNodeItem (Reference Imagery & Cache Engine)                │
│   └── NoteNodeItem  (Markdown / Annotation Notes)                     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Architectural Principles

### 1. Presentation Shell (`MainWindow`)
- `MainWindow` acts strictly as an orchestrator for panels and services.
- Zero business logic resides inside `MainWindow` or widget classes.
- UI components delegate filesystem operations, persistence, and thumbnail generation to specialized services.

### 2. Services Layer
- **`FolderService`**: Responsible for scanning project directories, constructing project file trees, and handling file system operations.
- **`ThumbnailService`**: Manages asynchronous thread-pool thumbnail generation, SHA-1 disk caching (`.creativeworkspace/thumbnails/`), and in-memory `QPixmap` caching.
- **`LabService`**: Handles JSON serialization and deserialization of canvas board states (`.creativeworkspace/lab/<board_name>.lab.json`).

### 3. Spatial Node System (`NodeRegistry` & `NodeCapability`)
- **Single Source of Truth**: All spatial node types are registered declaratively in `NodeRegistry`.
- **Capability Flags over Class Inheritance**: Node behavior (resizing, text editing, collapsing, locking, child hosting) is specified via `NodeCapability` bitflags rather than rigid class inheritance trees or type-checking switch statements.
- **Data-Driven Creation**: Canvas instantiation delegates directly to `NodeRegistry.create_node(type_id, data, node_context)` without `if/else` branching.

### 4. Lightweight Geometric Containers (`FrameNodeItem`)
- **Zero Parentage / Ownership**: Frame nodes organize spatial nodes purely through **geometric containment** (`sceneBoundingRect().contains(item.center())`).
- **No Scene Hierarchy Mutation**: Frames do not parent child `QGraphicsItem`s. This guarantees all current and future node types (Images, Notes, PDFs, Videos, Checklists) work inside Frames automatically without custom serialization or child handling.
- **Z-Order Layering**: Frames render at `zValue = -10` beneath regular spatial items (`zValue = 1`), allowing child interactions (selection, dragging, text editing) to pass directly to items without background interception.
