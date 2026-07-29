# Changelog

All notable changes to Creative Workspace are documented here.

---

## [0.2.0] - 2026-07-29

### Added

- Drag & Drop asset import from Windows Explorer
- AssetService for centralized asset management
- Automatic asset indexing (.asset_index.json)
- Asset Workspace panel
- Asset cards with thumbnails
- Friendly file type labels
- Date Added metadata
- Asset categories
- Inspector support
- Asset count display
- Responsive asset grid
- Automatic asset index rebuild
- Tools → Rebuild Asset Index

### Changed

- Workspace now switches between Dashboard and Asset Browser
- Asset metadata is now managed through AssetService
- Refreshes are event-driven using `assets_changed`

### Fixed

- Drag & Drop duplicate handling
- Thumbnail path resolution
- Empty asset browser state
- Rapid asset selection crash
- Project switching refresh issues

---

## [0.1.0] - 2026-07-20

### Added

- Project creation
- Project Explorer
- Dashboard
- Snapshot preview
- Project metadata