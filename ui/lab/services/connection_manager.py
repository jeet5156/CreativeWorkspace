import uuid
import copy
from typing import Dict, List, Set, Optional, Tuple
from PySide6.QtCore import QObject, Signal

from ui.lab.models.relationship import Relationship
from ui.lab.models.relationship_registry import RelationshipRegistry
from ui.lab.connectors.connector_item import ConnectorItem


class ConnectionManager(QObject):
    """Exclusive Graph Domain Service managing the Lab spatial knowledge graph.

    Owns all Relationship domain objects, node attachment index lookups,
    signals, and QGraphicsItem presentation lifecycles.
    No UI code should mutate Relationship objects directly.
    """

    relationship_created = Signal(object)
    relationship_updated = Signal(object)
    relationship_deleted = Signal(str)
    relationship_reversed = Signal(object)

    def __init__(self, canvas=None):
        super().__init__()
        self._canvas = canvas
        
        # Domain Truth Storage: relationship_id -> Relationship
        self._relationships: Dict[str, Relationship] = {}

        # View Presentation Storage: relationship_id -> ConnectorItem
        self._connectors: Dict[str, ConnectorItem] = {}

        # Fast O(1) Node Attachment Index: node_id -> set(relationship_ids)
        self._node_relationships: Dict[str, Set[str]] = {}

    def set_canvas(self, canvas):
        """Bind InfiniteCanvas scene orchestrator."""
        self._canvas = canvas

    # -------------------------------------------------------------------------
    # Exclusive Domain CRUD API
    # -------------------------------------------------------------------------

    def create_relationship(
        self,
        source_node_id: str,
        target_node_id: str,
        source_anchor: str = "center",
        target_anchor: str = "center",
        relationship_type: str = "related_to",
        title: str = "",
        notes: str = "",
        weight: float = 1.0,
        created_by: str = "manual",
        rel_id: str = None,
        **kwargs
    ) -> Optional[Relationship]:
        """Exclusive API to construct, register, and visualize a new semantic Relationship."""
        if not source_node_id or not target_node_id or source_node_id == target_node_id:
            return None

        rel = Relationship(
            id=str(rel_id or uuid.uuid4()),
            source_node_id=str(source_node_id),
            target_node_id=str(target_node_id),
            source_anchor=str(source_anchor or "center"),
            target_anchor=str(target_anchor or "center"),
            relationship_type=str(relationship_type or "related_to"),
            title=str(title or ""),
            notes=str(notes or ""),
            weight=float(weight),
            created_by=str(created_by or "manual"),
        )
        if kwargs:
            rel.metadata.update(kwargs)

        self._relationships[rel.id] = rel
        self._node_relationships.setdefault(rel.source_node_id, set()).add(rel.id)
        self._node_relationships.setdefault(rel.target_node_id, set()).add(rel.id)

        # Create presentation ConnectorItem view
        item = ConnectorItem(rel, manager=self)
        self._connectors[rel.id] = item

        # Attach to scene if canvas bound
        if self._canvas and hasattr(self._canvas, "_scene") and self._canvas._scene:
            scene = self._canvas._scene
            if item not in scene.items():
                scene.addItem(item)
            item.update_path()

        self.relationship_created.emit(rel)
        return rel

    def update_relationship(self, rel_id: str, **kwargs) -> Optional[Relationship]:
        """Exclusive API to update properties on an existing Relationship."""
        rel = self._relationships.get(str(rel_id))
        if not rel:
            return None

        for k, v in kwargs.items():
            if hasattr(rel, k):
                setattr(rel, k, v)
            else:
                rel.metadata[k] = v

        item = self._connectors.get(rel.id)
        if item:
            item.update_path()
            item.update()

        self.relationship_updated.emit(rel)
        return rel

    def change_type(self, rel_id: str, new_type: str) -> Optional[Relationship]:
        """Exclusive API to change the relationship type of a connection."""
        return self.update_relationship(rel_id, relationship_type=new_type)

    def reverse_relationship(self, rel_id: str) -> Optional[Relationship]:
        """Exclusive API to swap source and target endpoints without destroying relationship identity."""
        rel = self._relationships.get(str(rel_id))
        if not rel:
            return None

        # Clean old index references
        if rel.source_node_id in self._node_relationships:
            self._node_relationships[rel.source_node_id].discard(rel.id)
        if rel.target_node_id in self._node_relationships:
            self._node_relationships[rel.target_node_id].discard(rel.id)

        # Swap endpoints and anchors
        rel.source_node_id, rel.target_node_id = rel.target_node_id, rel.source_node_id
        rel.source_anchor, rel.target_anchor = rel.target_anchor, rel.source_anchor

        # Re-index
        self._node_relationships.setdefault(rel.source_node_id, set()).add(rel.id)
        self._node_relationships.setdefault(rel.target_node_id, set()).add(rel.id)

        item = self._connectors.get(rel.id)
        if item:
            item.update_path()
            item.update()

        self.relationship_reversed.emit(rel)
        return rel

    def delete_relationship(self, rel_id: str) -> bool:
        """Exclusive API to delete a relationship from domain storage and graphics scene."""
        cid = str(rel_id)
        rel = self._relationships.pop(cid, None)
        if not rel:
            return False

        # Remove index references
        if rel.source_node_id in self._node_relationships:
            self._node_relationships[rel.source_node_id].discard(cid)
        if rel.target_node_id in self._node_relationships:
            self._node_relationships[rel.target_node_id].discard(cid)

        item = self._connectors.pop(cid, None)
        if item:
            if self._canvas and hasattr(self._canvas, "_scene") and self._canvas._scene:
                scene = self._canvas._scene
                if item in scene.items():
                    scene.removeItem(item)

        self.relationship_deleted.emit(cid)
        return True

    def duplicate_relationship(self, rel_id: str) -> Optional[Relationship]:
        """Exclusive API to duplicate a relationship with new unique ID."""
        rel = self._relationships.get(str(rel_id))
        if not rel:
            return None

        return self.create_relationship(
            source_node_id=rel.source_node_id,
            target_node_id=rel.target_node_id,
            source_anchor=rel.source_anchor,
            target_anchor=rel.target_anchor,
            relationship_type=rel.relationship_type,
            title=f"{rel.title} (Copy)" if rel.title else "",
            notes=rel.notes,
            weight=rel.weight,
            created_by=rel.created_by,
        )

    # -------------------------------------------------------------------------
    # Backward Compatibility & Query Helpers
    # -------------------------------------------------------------------------

    def add_connector(self, data_or_item) -> Optional[ConnectorItem]:
        """Compatibility adapter for legacy connector dictionaries or items."""
        if isinstance(data_or_item, dict):
            rel = Relationship.from_dict(data_or_item)
            res_rel = self.create_relationship(
                source_node_id=rel.source_node_id,
                target_node_id=rel.target_node_id,
                source_anchor=rel.source_anchor,
                target_anchor=rel.target_anchor,
                relationship_type=rel.relationship_type,
                title=rel.title,
                notes=rel.notes,
                weight=rel.weight,
                created_by=rel.created_by,
                rel_id=rel.id,
            )
            return self._connectors.get(res_rel.id) if res_rel else None
        elif isinstance(data_or_item, ConnectorItem):
            rel = data_or_item.relationship
            self._relationships[rel.id] = rel
            self._connectors[rel.id] = data_or_item
            return data_or_item
        return None

    def remove_connector(self, connector_id: str) -> bool:
        return self.delete_relationship(connector_id)

    def connect_nodes(self, source_id: str, target_id: str, **kwargs) -> Optional[ConnectorItem]:
        rel = self.create_relationship(source_id, target_id, **kwargs)
        return self._connectors.get(rel.id) if rel else None

    def get_relationship(self, rel_id: str) -> Optional[Relationship]:
        return self._relationships.get(str(rel_id))

    def get_connector(self, rel_id: str) -> Optional[ConnectorItem]:
        return self._connectors.get(str(rel_id))

    def connectors(self) -> List[ConnectorItem]:
        return list(self._connectors.values())

    def relationships(self) -> List[Relationship]:
        return list(self._relationships.values())

    def get_node_relationships(self, node_id: str) -> List[Relationship]:
        rids = self._node_relationships.get(str(node_id), set())
        return [self._relationships[r] for r in rids if r in self._relationships]

    def remove_all_for_node(self, node_id: str) -> int:
        """Remove all attached relationships for a given node (deletion cleanup)."""
        rids = list(self._node_relationships.get(str(node_id), set()))
        count = 0
        for rid in rids:
            if self.delete_relationship(rid):
                count += 1
        return count

    def update_node_connectors(self, node_id: str):
        """Update path geometry for all connectors attached to node_id."""
        rids = self._node_relationships.get(str(node_id), set())
        for rid in rids:
            item = self._connectors.get(rid)
            if item:
                item.update_path()

    def remap_pasted_relationships(self, pasted_nodes: list, old_to_new_map: dict) -> List[Relationship]:
        """Remap relationship endpoint IDs upon multi-node paste."""
        pasted_node_ids = set(old_to_new_map.keys())
        pasted_rels = []

        seen_rids = set()
        for old_id in pasted_node_ids:
            rids = self._node_relationships.get(old_id, set())
            for rid in rids:
                if rid in seen_rids:
                    continue
                seen_rids.add(rid)
                rel = self._relationships.get(rid)
                if rel and rel.source_node_id in old_to_new_map and rel.target_node_id in old_to_new_map:
                    new_rel = self.create_relationship(
                        source_node_id=old_to_new_map[rel.source_node_id],
                        target_node_id=old_to_new_map[rel.target_node_id],
                        source_anchor=rel.source_anchor,
                        target_anchor=rel.target_anchor,
                        relationship_type=rel.relationship_type,
                        title=rel.title,
                        notes=rel.notes,
                        weight=rel.weight,
                        created_by=rel.created_by,
                    )
                    if new_rel:
                        pasted_rels.append(new_rel)

        return pasted_rels

    def clear(self):
        """Clear all domain relationships and scene connectors."""
        for item in list(self._connectors.values()):
            if self._canvas and hasattr(self._canvas, "_scene") and self._canvas._scene:
                scene = self._canvas._scene
                if item in scene.items():
                    scene.removeItem(item)
        self._relationships.clear()
        self._connectors.clear()
        self._node_relationships.clear()
