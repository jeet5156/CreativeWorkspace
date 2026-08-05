# CreativeWorkspace - Client Development & Verification Workflow

## Development Philosophy

Development on CreativeWorkspace strictly adheres to the core rules outlined in `GEMINI.md`:

1. **Inspect Existing Implementation First**: Study current architecture, modules, and tests before writing code.
2. **Design Approval Before Implementation**: Always present a clear design proposal (summarize understanding, explain proposed design, list affected files, explain trade-offs) and obtain user approval before making changes.
3. **Minimize Edits**: Modify the minimum number of files necessary. Prefer extending existing services (`ThumbnailService`, `FolderService`, `LabService`) over creating redundant utilities.
4. **No Superficial Symptom Patches**: Fix underlying root causes rather than masking errors with fallbacks or commenting out failing tests.
5. **Empirical Verification**: Never declare success without executing automated unit test suites (`unittest`).

---

## Pair-Programming & Implementation Workflow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Study & Research Codebase                                │
│    - Inspect source files, schemas, and existing tests      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Propose Technical Design                                 │
│    - Write implementation plan artifact                     │
│    - Detail user review required items & open questions     │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Obtain User Approval                                     │
│    - Wait for explicit user confirmation                    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Execute Code Modifications                               │
│    - Apply surgical edits using replacement tools           │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Automated Verification & Walkthrough                     │
│    - Run complete unittest suite                            │
│    - Document changes and test results in walkthrough.md    │
└─────────────────────────────────────────────────────────────┘
```

---

## Test Automation Guidelines

All feature work must be accompanied or validated by automated headless PySide6 `unittest` test suites:

- **Node State Isolation Tests**: Verify distinct node objects own independent payload dictionaries, pixmaps, and UUIDs (`tests/test_image_node.py`).
- **Geometric Containment Tests**: Verify `FrameNodeItem.contained_nodes()` returns correct items based on bounding rect center coordinates (`tests/test_frame_node.py`).
- **UX & Interaction Tests**: Verify bottom-right handle hit-testing, resize minimum constraints, inline editing, and drag hover highlight state (`tests/test_frame_ux.py`).
- **Permanent Regression Tests**: Permanent multi-node save/reopen persistence tests (e.g. 10-node board reload test) ensuring no hidden initialization-order bugs return.

To execute full test suite:
```powershell
python -m unittest discover tests
```
