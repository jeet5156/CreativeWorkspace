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

    @classmethod
    def register(cls, definition: NodeDefinition) -> None:
        """Register a new NodeDefinition."""
        cls._registry[definition.type_id] = definition

    @classmethod
    def get(cls, type_id: str) -> Optional[NodeDefinition]:
        """Retrieve a NodeDefinition by its type_id."""
        return cls._registry.get(type_id)

    @classmethod
    def get_all(cls) -> List[NodeDefinition]:
        """Retrieve all registered NodeDefinitions."""
        return list(cls._registry.values())

    @classmethod
    def get_by_category(cls, category: str) -> List[NodeDefinition]:
        """Retrieve NodeDefinitions filtered by category."""
        return [defn for defn in cls._registry.values() if defn.category == category]

    @classmethod
    def create_node(cls, type_id: str, data: Optional[dict] = None, node_context=None):
        """Instantiate a spatial node item from registered factory."""
        defn = cls.get(type_id)
        if not defn:
            raise ValueError(f"Unknown node type_id: '{type_id}'")

        node = defn.factory(defn, data)
        if node_context:
            node.set_node_context(node_context)

        if data:
            node.from_dict(data)

        return node


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
    category="asset",
    title="File Reference",
    icon="🎨",
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
    category="asset",
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
    category="asset",
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
