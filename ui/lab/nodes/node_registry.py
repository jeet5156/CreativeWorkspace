from typing import Dict, Optional, List
from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction

from ui.lab.nodes.node_definition import NodeDefinition
from ui.lab.nodes.node_capability import NodeCapability
from ui.lab.nodes.node_item import NodeItem
from ui.lab.nodes.note_node_item import NoteNodeItem


class NodeRegistry:
    """Central registry and single source of truth for spatial node definitions, factories, and context menus.

    Eliminates switch statements and hardcoded type checks across the Lab engine.
    """

    _registry: Dict[str, NodeDefinition] = {}

    @classmethod
    def register(cls, definition: NodeDefinition):
        cls._registry[definition.type_id] = definition

    @classmethod
    def get(cls, type_id: str) -> Optional[NodeDefinition]:
        return cls._registry.get(type_id)

    @classmethod
    def list_all(cls) -> List[NodeDefinition]:
        return list(cls._registry.values())

    @classmethod
    def list_by_category(cls, category: str) -> List[NodeDefinition]:
        return [d for d in cls._registry.values() if d.category == category]

    @classmethod
    def categories(cls) -> List[str]:
        return sorted(list({d.category for d in cls._registry.values()}))

    @classmethod
    def create_node(cls, type_id: str, data: dict = None, node_context=None) -> NodeItem:
        defn = cls.get(type_id)
        if not defn:
            # Fallback to note.blank if unknown type_id
            defn = cls.get("note.blank")

        if defn and defn.factory:
            node = defn.factory(defn, data)
        else:
            node = NoteNodeItem(definition=defn)

        if node_context:
            node.set_node_context(node_context)

        if data:
            node.from_dict(data)
            try:
                node.on_loaded()
            except Exception:
                pass
        else:
            try:
                node.on_created()
            except Exception:
                pass
        return node

    @classmethod
    def build_context_menu(cls, parent_widget, scene_pos, create_callback) -> QMenu:
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

        categories = cls.categories()
        for cat in categories:
            cat_title = "Add Note" if cat == "note" else f"Add {cat.capitalize()}"
            sub_menu = menu.addMenu(f"➕ {cat_title}")

            defs = cls.list_by_category(cat)
            for defn in defs:
                label = f"{defn.icon}  {defn.title}"
                action = QAction(label, parent_widget)
                action.triggered.connect(
                    lambda checked=False, d=defn: create_callback(d, scene_pos)
                )
                sub_menu.addAction(action)

        return menu


# Register Built-in Node Definitions
NOTE_CAPABILITIES = NodeCapability.CAN_EDIT_TEXT | NodeCapability.CAN_LOCK | NodeCapability.CAN_DUPLICATE

NodeRegistry.register(NodeDefinition(
    type_id="note.blank",
    category="note",
    title="Blank Note",
    icon="📝",
    accent_color="#94A3B8",
    background_color="#1E2029",
    badge_bg="#1E293B",
    badge_text="#94A3B8",
    capabilities=NOTE_CAPABILITIES,
    payload_schema={"content": ""},
    search_keywords=("note", "blank", "memo"),
    factory=lambda defn, data=None: NoteNodeItem(definition=defn)
))

NodeRegistry.register(NodeDefinition(
    type_id="note.goal",
    category="note",
    title="Goal Card",
    icon="🎯",
    accent_color="#3B82F6",
    background_color="#1E2029",
    badge_bg="#1E2E4A",
    badge_text="#60A5FA",
    capabilities=NOTE_CAPABILITIES,
    payload_schema={"content": "", "target_date": None},
    search_keywords=("goal", "objective", "target"),
    factory=lambda defn, data=None: NoteNodeItem(definition=defn)
))

NodeRegistry.register(NodeDefinition(
    type_id="note.idea",
    category="note",
    title="Idea Card",
    icon="💡",
    accent_color="#F59E0B",
    background_color="#1E2029",
    badge_bg="#3B2D1B",
    badge_text="#FBBF24",
    capabilities=NOTE_CAPABILITIES,
    payload_schema={"content": "", "tags": []},
    search_keywords=("idea", "brainstorm", "concept"),
    factory=lambda defn, data=None: NoteNodeItem(definition=defn)
))

NodeRegistry.register(NodeDefinition(
    type_id="note.task",
    category="note",
    title="Task Card",
    icon="📌",
    accent_color="#22C55E",
    background_color="#1E2029",
    badge_bg="#14382B",
    badge_text="#34D399",
    capabilities=NOTE_CAPABILITIES,
    payload_schema={"content": "", "completed": False},
    search_keywords=("task", "todo", "action"),
    factory=lambda defn, data=None: NoteNodeItem(definition=defn)
))

NodeRegistry.register(NodeDefinition(
    type_id="note.problem",
    category="note",
    title="Problem Card",
    icon="⚠️",
    accent_color="#EF4444",
    background_color="#1E2029",
    badge_bg="#3F1D24",
    badge_text="#F87171",
    capabilities=NOTE_CAPABILITIES,
    payload_schema={"content": "", "severity": "medium"},
    search_keywords=("problem", "issue", "bug", "risk"),
    factory=lambda defn, data=None: NoteNodeItem(definition=defn)
))

NodeRegistry.register(NodeDefinition(
    type_id="note.decision",
    category="note",
    title="Decision Card",
    icon="✦",
    accent_color="#A855F7",
    background_color="#1E2029",
    badge_bg="#2E1C48",
    badge_text="#C084FC",
    capabilities=NOTE_CAPABILITIES,
    payload_schema={"content": "", "decided_by": ""},
    search_keywords=("decision", "resolved", "approved"),
    factory=lambda defn, data=None: NoteNodeItem(definition=defn)
))

# Register Media Node Definitions
IMAGE_CAPABILITIES = NodeCapability.CAN_LOCK | NodeCapability.CAN_RESIZE | NodeCapability.CAN_DUPLICATE

from ui.lab.nodes.image_node_item import ImageNodeItem

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
    capabilities=IMAGE_CAPABILITIES,
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

# Register Frame Container Node Definition
FRAME_CAPABILITIES = (
    NodeCapability.CAN_EDIT_TEXT
    | NodeCapability.CAN_RESIZE
    | NodeCapability.CAN_LOCK
    | NodeCapability.CAN_DUPLICATE
    | NodeCapability.CAN_COLLAPSE
    | NodeCapability.CAN_HAVE_CHILDREN
)

from ui.lab.nodes.frame_node_item import FrameNodeItem

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
