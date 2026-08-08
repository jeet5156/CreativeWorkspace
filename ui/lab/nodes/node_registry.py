from typing import Dict, Optional, List, Type
from ui.lab.nodes.node_definition import NodeDefinition, NodeCapability

# Specialized and Universal Spatial Node Item Imports
from ui.lab.nodes.note_node_item import NoteNodeItem
from ui.lab.nodes.image_node_item import ImageNodeItem
from ui.lab.nodes.pdf_node_item import PdfNodeItem
from ui.lab.nodes.threed_node_item import ThreeDNodeItem
from ui.lab.nodes.generic_file_node_item import GenericFileNodeItem
from ui.lab.nodes.folder_node_item import FolderNodeItem
from ui.lab.nodes.archive_node_item import ArchiveNodeItem
from ui.lab.nodes.frame_node_item import FrameNodeItem


class NodeRegistry:
    """Central registry for spatial canvas NodeDefinitions.

    Maps node type IDs (e.g. 'note.blank', 'image.reference', 'document.pdf', 'asset.3d',
    'file.reference', 'folder.reference', 'archive.reference') to their NodeDefinitions
    and instantiates node visual items.
    """

    _registry: Dict[str, NodeDefinition] = {}
    _type_aliases: Dict[str, str] = {
        "image": "image.reference",
        "note": "note.blank",
    }

    @classmethod
    def register(cls, definition: NodeDefinition) -> None:
        """Register a new NodeDefinition."""
        cls._registry[definition.type_id] = definition

    @classmethod
    def get(cls, type_id: str) -> Optional[NodeDefinition]:
        """Retrieve a NodeDefinition by its type_id (handling legacy aliases)."""
        resolved_type = cls._type_aliases.get(type_id, type_id)
        return cls._registry.get(resolved_type)

    @classmethod
    def get_all(cls) -> List[NodeDefinition]:
        """Retrieve all registered NodeDefinitions."""
        return list(cls._registry.values())

    @classmethod
    def get_by_category(cls, category: str) -> List[NodeDefinition]:
        """Retrieve NodeDefinitions filtered by category."""
        return [defn for defn in cls._registry.values() if defn.category == category]

    @classmethod
    def list_all(cls) -> List[NodeDefinition]:
        """Retrieve all registered NodeDefinitions (backward compatibility alias)."""
        return cls.get_all()

    @classmethod
    def list_by_category(cls, category: str) -> List[NodeDefinition]:
        """Retrieve NodeDefinitions filtered by category (backward compatibility alias)."""
        return cls.get_by_category(category)

    @classmethod
    def categories(cls) -> List[str]:
        """Retrieve sorted list of all registered category keys."""
        return sorted(list({defn.category for defn in cls._registry.values()}))

    @classmethod
    def create_node(cls, type_id: str, data: Optional[dict] = None, node_context=None):
        """Instantiate a spatial node item from registered factory."""
        import logging
        logger = logging.getLogger(__name__)

        defn = cls.get(type_id)
        if not defn:
            logger.warning(
                f"[NodeRegistry] Unknown or unsupported node type_id '{type_id}'. "
                f"Preserving serialized node data payload and explicitly falling back to 'note.blank' visual item."
            )
            defn = cls.get("note.blank")

        if defn and defn.factory:
            node = defn.factory(defn, data)
        else:
            node = NoteNodeItem(definition=defn)

        if node_context:
            node.set_node_context(node_context)

        if data:
            node.from_dict(data)

        return node

    @classmethod
    def build_context_menu(cls, parent_widget, scene_pos, create_callback):
        """Build Create Node context menu dynamically from registered definitions with category icons."""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction

        menu = QMenu(parent_widget)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1E2029;
                border: 1px solid #343847;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                color: #CBD5E1;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 12px;
            }
            QMenu::item:selected {
                background-color: #343847;
                color: #F1F5F9;
            }
        """)

        CATEGORY_ICONS = {
            "asset": "🧊",
            "document": "📄",
            "media": "🖼️",
            "note": "📝",
            "folder": "📁",
            "archive": "📦",
            "frame": "🖼️",
        }

        CATEGORY_LABELS = {
            "asset": "Add Asset",
            "document": "Add Document",
            "media": "Add Media",
            "note": "Add Note",
            "folder": "Add Folder",
            "archive": "Add Archive",
            "frame": "Add Frame",
        }

        DIRECT_SINGLE_CATEGORIES = {"folder", "archive", "frame"}
        ORDERED_CATEGORIES = ["asset", "document", "media", "note", "folder", "archive", "frame"]

        all_cats = cls.categories()
        for c in all_cats:
            if c not in ORDERED_CATEGORIES:
                ORDERED_CATEGORIES.append(c)

        for cat in ORDERED_CATEGORIES:
            defs = cls.list_by_category(cat)
            if not defs:
                continue

            icon = CATEGORY_ICONS.get(cat, defs[0].icon if defs else "✨")
            label = CATEGORY_LABELS.get(cat, f"Add {cat.capitalize()}")

            if len(defs) == 1 and cat in DIRECT_SINGLE_CATEGORIES:
                action_title = f"{icon}  {label}"
                action = QAction(action_title, parent_widget)
                action.triggered.connect(
                    lambda checked=False, d=defs[0]: create_callback(d, scene_pos)
                )
                menu.addAction(action)
            else:
                sub_menu = menu.addMenu(f"{icon}  {label}")
                for defn in defs:
                    item_label = f"{defn.icon}  {defn.title}"
                    action = QAction(item_label, parent_widget)
                    action.triggered.connect(
                        lambda checked=False, d=defn: create_callback(d, scene_pos)
                    )
                    sub_menu.addAction(action)

        return menu


# -----------------------------------------------------------------------------
# DEFAULT CREATIVE LAB NODE REGISTRATIONS
# -----------------------------------------------------------------------------

# 1. Blank Note Node
NOTE_CAPABILITIES = (
    NodeCapability.CAN_EDIT_TEXT
    | NodeCapability.CAN_RESIZE
    | NodeCapability.CAN_LOCK
    | NodeCapability.CAN_DUPLICATE
)

# Legacy Note Capabilities
LEGACY_NOTE_CAPABILITIES = NodeCapability.CAN_EDIT_TEXT | NodeCapability.CAN_LOCK | NodeCapability.CAN_DUPLICATE

NodeRegistry.register(NodeDefinition(
    type_id="note.blank",
    category="note",
    title="Sticky Note",
    icon="📝",
    accent_color="#FACC15",
    background_color="#1E2029",
    badge_bg="#3A3216",
    badge_text="#FACC15",
    default_size=(240.0, 180.0),
    minimum_size=(140.0, 100.0),
    capabilities=NOTE_CAPABILITIES,
    payload_schema={
        "content": "",
        "color_theme": "yellow",
        "target_date": "",
        "formatting": {}
    },
    search_keywords=("note", "sticky", "text", "memo", "idea"),
    factory=lambda defn, data=None: NoteNodeItem(definition=defn)
))

# 2. Legacy Goal Card
NodeRegistry.register(NodeDefinition(
    type_id="note.goal",
    category="note",
    title="Goal Card",
    icon="🎯",
    accent_color="#3B82F6",
    background_color="#1E2029",
    badge_bg="#1E2E4A",
    badge_text="#60A5FA",
    capabilities=LEGACY_NOTE_CAPABILITIES,
    payload_schema={"content": "", "target_date": None},
    search_keywords=("goal", "objective", "target"),
    factory=lambda defn, data=None: NoteNodeItem(definition=defn)
))

# 3. Legacy Idea Card
NodeRegistry.register(NodeDefinition(
    type_id="note.idea",
    category="note",
    title="Idea Card",
    icon="💡",
    accent_color="#F59E0B",
    background_color="#1E2029",
    badge_bg="#3B2D1B",
    badge_text="#FBBF24",
    capabilities=LEGACY_NOTE_CAPABILITIES,
    payload_schema={"content": "", "tags": []},
    search_keywords=("idea", "brainstorm", "concept"),
    factory=lambda defn, data=None: NoteNodeItem(definition=defn)
))

# 4. Legacy Task Card
NodeRegistry.register(NodeDefinition(
    type_id="note.task",
    category="note",
    title="Task Card",
    icon="📌",
    accent_color="#22C55E",
    background_color="#1E2029",
    badge_bg="#14382B",
    badge_text="#34D399",
    capabilities=LEGACY_NOTE_CAPABILITIES,
    payload_schema={"content": "", "completed": False},
    search_keywords=("task", "todo", "action"),
    factory=lambda defn, data=None: NoteNodeItem(definition=defn)
))

# 5. Legacy Problem Card
NodeRegistry.register(NodeDefinition(
    type_id="note.problem",
    category="note",
    title="Problem Card",
    icon="⚠️",
    accent_color="#EF4444",
    background_color="#1E2029",
    badge_bg="#3F1D24",
    badge_text="#F87171",
    capabilities=LEGACY_NOTE_CAPABILITIES,
    payload_schema={"content": "", "severity": "medium"},
    search_keywords=("problem", "issue", "bug", "risk"),
    factory=lambda defn, data=None: NoteNodeItem(definition=defn)
))

# 6. Legacy Decision Card
NodeRegistry.register(NodeDefinition(
    type_id="note.decision",
    category="note",
    title="Decision Card",
    icon="✦",
    accent_color="#A855F7",
    background_color="#1E2029",
    badge_bg="#2E1C48",
    badge_text="#C084FC",
    capabilities=LEGACY_NOTE_CAPABILITIES,
    payload_schema={"content": "", "decided_by": ""},
    search_keywords=("decision", "resolved", "approved"),
    factory=lambda defn, data=None: NoteNodeItem(definition=defn)
))

# Shared Asset Capabilities
ASSET_CAPABILITIES = NodeCapability.CAN_LOCK | NodeCapability.CAN_RESIZE | NodeCapability.CAN_DUPLICATE

# 2. Image Reference Node
NodeRegistry.register(NodeDefinition(
    type_id="image.reference",
    category="media",
    title="Reference",
    icon="🖼",
    accent_color="#38BDF8",
    background_color="#1E2029",
    badge_bg="#13374A",
    badge_text="#38BDF8",
    default_size=(320.0, 260.0),
    minimum_size=(180.0, 140.0),
    capabilities=ASSET_CAPABILITIES,
    payload_schema={
        "image_path": "",
        "filename": "",
        "title": "",
        "caption": "",
        "fit_mode": "fit",
        "layout": {
            "aspect_ratio": 1.23,
            "width": 320.0,
            "height": 260.0,
        }
    },
    search_keywords=("image", "reference", "picture", "photo", "media"),
    factory=lambda defn, data=None: ImageNodeItem(definition=defn)
))

# 3. PDF Reference Node
NodeRegistry.register(NodeDefinition(
    type_id="document.pdf",
    category="document",
    title="PDF Reference",
    icon="📄",
    accent_color="#EF4444",
    background_color="#1E2029",
    badge_bg="#3F1D24",
    badge_text="#F87171",
    default_size=(320.0, 260.0),
    minimum_size=(180.0, 140.0),
    capabilities=ASSET_CAPABILITIES,
    payload_schema={
        "pdf_path": "",
        "image_path": "",
        "absolute_path": "",
        "filename": "",
        "file_name": "",
        "extension": ".pdf",
        "file_size_str": "",
        "page_count": 0,
        "display_mode": "icon",
        "title": "",
        "caption": "",
        "layout": {
            "aspect_ratio": 1.23,
            "width": 320.0,
            "height": 260.0,
        }
    },
    search_keywords=("pdf", "document", "file", "paper", "reference"),
    factory=lambda defn, data=None: PdfNodeItem(definition=defn)
))

# 4. 3D Asset Reference Node
NodeRegistry.register(NodeDefinition(
    type_id="asset.3d",
    category="asset",
    title="3D Asset Reference",
    icon="🧊",
    accent_color="#10B981",
    background_color="#1E2029",
    badge_bg="#13382C",
    badge_text="#34D399",
    default_size=(320.0, 260.0),
    minimum_size=(180.0, 140.0),
    capabilities=ASSET_CAPABILITIES,
    payload_schema={
        "asset_path": "",
        "image_path": "",
        "absolute_path": "",
        "filename": "",
        "file_name": "",
        "extension": "",
        "format_label": "",
        "file_size_str": "",
        "display_mode": "icon",
        "title": "",
        "caption": "",
        "layout": {
            "aspect_ratio": 1.23,
            "width": 320.0,
            "height": 260.0,
        }
    },
    search_keywords=("3d", "asset", "mesh", "model", "fbx", "obj", "blend", "usd", "gltf"),
    factory=lambda defn, data=None: ThreeDNodeItem(definition=defn)
))

# 5. Generic File Reference Node
NodeRegistry.register(NodeDefinition(
    type_id="file.reference",
    category="document",
    title="File Reference",
    icon="📄",
    accent_color="#6366F1",
    background_color="#1E2029",
    badge_bg="#25284A",
    badge_text="#818CF8",
    default_size=(320.0, 260.0),
    minimum_size=(180.0, 140.0),
    capabilities=ASSET_CAPABILITIES,
    payload_schema={
        "file_path": "",
        "image_path": "",
        "absolute_path": "",
        "filename": "",
        "file_name": "",
        "extension": "",
        "format_label": "",
        "file_size_str": "",
        "display_mode": "icon",
        "title": "",
        "caption": "",
        "layout": {
            "aspect_ratio": 1.23,
            "width": 320.0,
            "height": 260.0,
        }
    },
    search_keywords=("file", "reference", "psd", "c4d", "asset", "generic", "document"),
    factory=lambda defn, data=None: GenericFileNodeItem(definition=defn)
))

# 6. Folder Reference Node
NodeRegistry.register(NodeDefinition(
    type_id="folder.reference",
    category="folder",
    title="Folder Reference",
    icon="📁",
    accent_color="#F59E0B",
    background_color="#1E2029",
    badge_bg="#3B2D1B",
    badge_text="#FBBF24",
    default_size=(320.0, 260.0),
    minimum_size=(180.0, 140.0),
    capabilities=ASSET_CAPABILITIES,
    payload_schema={
        "folder_path": "",
        "image_path": "",
        "absolute_path": "",
        "foldername": "",
        "filename": "",
        "file_name": "",
        "display_mode": "icon",
        "title": "",
        "caption": "",
        "layout": {
            "aspect_ratio": 1.23,
            "width": 320.0,
            "height": 260.0,
        }
    },
    search_keywords=("folder", "directory", "reference", "path", "assets"),
    factory=lambda defn, data=None: FolderNodeItem(definition=defn)
))

# 7. Archive Reference Node
NodeRegistry.register(NodeDefinition(
    type_id="archive.reference",
    category="archive",
    title="Archive Reference",
    icon="📦",
    accent_color="#EC4899",
    background_color="#1E2029",
    badge_bg="#3F1D2C",
    badge_text="#F472B6",
    default_size=(320.0, 260.0),
    minimum_size=(180.0, 140.0),
    capabilities=ASSET_CAPABILITIES,
    payload_schema={
        "archive_path": "",
        "image_path": "",
        "absolute_path": "",
        "filename": "",
        "file_name": "",
        "extension": "",
        "format_label": "",
        "file_size_str": "",
        "display_mode": "icon",
        "title": "",
        "caption": "",
        "layout": {
            "aspect_ratio": 1.23,
            "width": 320.0,
            "height": 260.0,
        }
    },
    search_keywords=("archive", "zip", "rar", "7z", "package", "compressed"),
    factory=lambda defn, data=None: ArchiveNodeItem(definition=defn)
))

# 8. Frame Section Container Node
FRAME_CAPABILITIES = (
    NodeCapability.CAN_EDIT_TEXT
    | NodeCapability.CAN_RESIZE
    | NodeCapability.CAN_LOCK
    | NodeCapability.CAN_DUPLICATE
    | NodeCapability.CAN_COLLAPSE
    | NodeCapability.CAN_HAVE_CHILDREN
)

NodeRegistry.register(NodeDefinition(
    type_id="frame.section",
    category="frame",
    title="Frame",
    icon="🖼️",
    accent_color="#A855F7",
    background_color="#1E2029",
    badge_bg="#2E1C48",
    badge_text="#C084FC",
    default_size=(480.0, 360.0),
    minimum_size=(240.0, 180.0),
    capabilities=FRAME_CAPABILITIES,
    payload_schema={
        "title": "Section Frame",
        "color_theme": "purple",
        "collapsed": False,
    },
    search_keywords=("frame", "section", "group", "container", "box"),
    factory=lambda defn, data=None: FrameNodeItem(definition=defn)
))
