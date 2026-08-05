# CreativeWorkspace - Client UI/UX Design

## Design Philosophy

CreativeWorkspace delivers a state-of-the-art visual environment tailored for creative artists and designers.

- **Vibrant & Tailored Dark Mode**: Custom dark palette (`#14161D` canvas, `#1E2029` cards, `#1E2E4A` accents) avoiding harsh plain blacks and generic browser defaults.
- **Modern Typography**: Clear font hierarchy using `Segoe UI` and clean system fonts.
- **Micro-Animations & Visual Feedback**: Hover highlights, interactive resize cursors, smooth drag glows, and loading states.
- **Zero Ambiguity**: Clear distinction between Explorer (*"Where do I go?"*), Canvas (*"What is happening?"*), and Inspector (*"What can I edit?"*).

---

## Workspace Layout Components

### 1. Explorer Panel
- Displays project folder hierarchies, boards, and reference libraries.
- Features context menus for creating new boards, importing assets, and revealing files in OS file manager.

### 2. Infinite Canvas (`InfiniteCanvas`)
- **Camera Navigation**: Smooth pan (Hold `Spacebar` or Middle-Click drag) and zoom.
- **Infinite Grid Overlay**: Dot grid overlay drawn dynamically in scene coordinates.
- **Selection & Multi-Select**: Drag selection rectangle (`QRubberBand`) and shift-click multi-selection.

### 3. Inspector Panel (`NodeInspectable`)
- Contextual property inspector adapting automatically based on the selected node:
  - **Reference Image Nodes**: Title, caption, fit mode (`fit` / `fill`), resolution, file size, relative path.
  - **Frame Section Nodes**: Title, color theme (`purple`, `blue`, `green`, `amber`, `red`, `gray`), collapse state, lock state.
  - **Note Nodes**: Content text, accent color, locked state.

---

## Spatial Node UX Specs

### Reference Image Node (`image.reference`)
- **Interaction Model**:
  - Double-click: Triggers file dialog to choose or replace reference image.
  - Context Menu: `🖼 Open Original Image`, `📍 Reveal in Explorer`, `📋 Copy Relative Path`, `🔄 Replace Image...`, `❌ Clear Image`, `🗑 Delete Node`.
- **State Machine Rendering**:
  - `EMPTY`: Renders `"🖼 Double Click to Choose Image"`.
  - `LOADING`: Renders `"⏳ Loading Preview..."`.
  - `READY`: Renders smooth scaled thumbnail pixmap with aspect-ratio preservation.
  - `MISSING`: Renders `"⚠️ Image Missing"`.
  - `ERROR`: Renders `"❌ Failed to Load"`.

### Frame Section Node (`frame.section`)
- **Visual Hierarchy**:
  - `12px` rounded corner radius (`CORNER_RADIUS = 12.0`).
  - Translucent body fill (`alpha = 30`) revealing canvas grid dots.
  - Darker theme header bar with `3px` top/left accent bar and horizontal divider line.
  - Interactive `◢` grip handle in bottom-right corner.
- **Interaction Model**:
  - **Double-Click Header**: Instantiates seamless inline `QLineEdit` directly over header text for rapid renaming.
  - **Bottom-Right Resize Handle**: Displays diagonal resize cursor (`Qt.SizeFDiagCursor`) on hover; live resizes on mouse drag enforcing `240x180` minimum bounds.
  - **Drag Hover Highlight**: Highlights with a `3px` theme accent glow border when spatial nodes are dragged over its bounds.
  - **Context Menu**: `✏️ Rename Frame...`, `🎨 Change Color Theme` (Purple, Blue, Green, Amber, Red, Gray), `↔️ Collapse / ↕️ Expand`, `🔒 Lock`, `🗑 Delete Frame`.
