"""Focused unit tests for Knowledge subsystem: Models, KnowledgeService, and Local Atomic Persistence."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from models.knowledge import KnowledgeDocument, KnowledgeFolder
from services.knowledge_service import KnowledgeService


class TestKnowledgeModels(unittest.TestCase):
    """Test pure domain models and serialization/deserialization."""

    def test_folder_model_defaults_and_serialization(self):
        folder = KnowledgeFolder(name="Concept Art")
        self.assertTrue(folder.id.startswith("fld_"))
        self.assertEqual(folder.name, "Concept Art")
        self.assertIsNone(folder.parent_id)

        d = folder.to_dict()
        self.assertEqual(d["name"], "Concept Art")
        self.assertEqual(d["id"], folder.id)

        restored = KnowledgeFolder.from_dict(d)
        self.assertEqual(restored.id, folder.id)
        self.assertEqual(restored.name, "Concept Art")
        self.assertEqual(restored.created, folder.created)

    def test_document_model_defaults_and_future_relationships(self):
        doc = KnowledgeDocument(
            title="World Building Lore",
            content="# Ancient Ruins\nDeep lore about the realm.",
            tags=["lore", "world"],
            favorite=True,
            project_ids=["proj_1", "proj_2"],
            library_asset_ids=["lib_asset_10"],
            project_asset_refs=[{"project_id": "proj_1", "asset_id": "asset_x", "relative_path": "Assets/ruins.fbx"}],
            lab_node_ids=["node_x"],
            attachment_ids=["att_1"],
        )

        self.assertTrue(doc.id.startswith("doc_"))
        self.assertEqual(doc.title, "World Building Lore")
        self.assertEqual(len(doc.tags), 2)
        self.assertTrue(doc.favorite)
        self.assertEqual(doc.project_ids, ["proj_1", "proj_2"])
        self.assertEqual(doc.library_asset_ids, ["lib_asset_10"])
        self.assertEqual(len(doc.project_asset_refs), 1)
        self.assertEqual(doc.lab_node_ids, ["node_x"])
        self.assertEqual(doc.attachment_ids, ["att_1"])

        d = doc.to_dict()
        restored = KnowledgeDocument.from_dict(d)
        self.assertEqual(restored.id, doc.id)
        self.assertEqual(restored.title, "World Building Lore")
        self.assertEqual(restored.tags, ["lore", "world"])
        self.assertTrue(restored.favorite)
        self.assertEqual(restored.project_ids, ["proj_1", "proj_2"])
        self.assertEqual(restored.library_asset_ids, ["lib_asset_10"])
        self.assertEqual(restored.project_asset_refs, [{"project_id": "proj_1", "asset_id": "asset_x", "relative_path": "Assets/ruins.fbx"}])
        self.assertEqual(restored.lab_node_ids, ["node_x"])
        self.assertEqual(restored.attachment_ids, ["att_1"])


class TestKnowledgeService(unittest.TestCase):
    """Test KnowledgeService operations with local atomic persistence."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.storage_dir = Path(self.test_dir) / "knowledge"
        self.service = KnowledgeService(storage_dir=self.storage_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_document_creation_and_persistence(self):
        """Verify creating a document creates memory and disk representation."""
        doc = self.service.create_document(
            title="Character Design Brief",
            content="Guidelines for protagonist silhouette and palette.",
            tags=["character", "design"],
            favorite=False,
        )

        self.assertIsNotNone(doc.id)
        self.assertEqual(doc.title, "Character Design Brief")
        self.assertEqual(doc.tags, ["character", "design"])
        self.assertFalse(doc.favorite)

        # Verify disk persistence
        doc_file = self.storage_dir / "documents" / f"{doc.id}.json"
        self.assertTrue(doc_file.exists())

        disk_data = json.loads(doc_file.read_text(encoding="utf-8"))
        self.assertEqual(disk_data["title"], "Character Design Brief")
        self.assertEqual(disk_data["tags"], ["character", "design"])

    def test_document_reload_from_disk(self):
        """Verify documents persist and reload cleanly in a fresh service instance."""
        doc1 = self.service.create_document(title="Doc 1", content="Content 1", tags=["t1"])
        doc2 = self.service.create_document(title="Doc 2", content="Content 2", favorite=True)

        # Create new service pointing to same directory
        reloaded_service = KnowledgeService(storage_dir=self.storage_dir)

        r_doc1 = reloaded_service.get_document(doc1.id)
        r_doc2 = reloaded_service.get_document(doc2.id)

        self.assertIsNotNone(r_doc1)
        self.assertIsNotNone(r_doc2)
        self.assertEqual(r_doc1.title, "Doc 1")
        self.assertEqual(r_doc1.tags, ["t1"])
        self.assertEqual(r_doc2.title, "Doc 2")
        self.assertTrue(r_doc2.favorite)

    def test_document_editing_and_timestamp(self):
        """Verify updating document modifies fields and modified timestamp."""
        doc = self.service.create_document(title="Original Title", content="Original Content")
        old_modified = doc.modified

        updated = self.service.update_document(
            doc.id,
            title="Updated Title",
            content="Updated Content",
            tags=["new_tag"],
            favorite=True,
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.title, "Updated Title")
        self.assertEqual(updated.content, "Updated Content")
        self.assertEqual(updated.tags, ["new_tag"])
        self.assertTrue(updated.favorite)
        self.assertGreaterEqual(updated.modified, old_modified)

        # Verify persisted to disk
        reloaded_service = KnowledgeService(storage_dir=self.storage_dir)
        disk_doc = reloaded_service.get_document(doc.id)
        self.assertEqual(disk_doc.title, "Updated Title")
        self.assertEqual(disk_doc.content, "Updated Content")

    def test_document_deletion_is_isolated(self):
        """Verify document deletion removes only document file and leaves others intact."""
        doc1 = self.service.create_document(title="Doc 1")
        doc2 = self.service.create_document(title="Doc 2")

        doc1_path = self.storage_dir / "documents" / f"{doc1.id}.json"
        doc2_path = self.storage_dir / "documents" / f"{doc2.id}.json"

        self.assertTrue(doc1_path.exists())
        self.assertTrue(doc2_path.exists())

        res = self.service.delete_document(doc1.id)
        self.assertTrue(res)
        self.assertIsNone(self.service.get_document(doc1.id))
        self.assertFalse(doc1_path.exists())
        self.assertTrue(doc2_path.exists())
        self.assertIsNotNone(self.service.get_document(doc2.id))

    def test_folder_creation_and_nesting(self):
        """Verify folder hierarchy creation, listing, and breadcrumbs."""
        root_folder = self.service.create_folder(name="Game Design")
        sub_folder_1 = self.service.create_folder(name="Mechanics", parent_id=root_folder.id)
        sub_folder_2 = self.service.create_folder(name="Combat", parent_id=sub_folder_1.id)

        self.assertEqual(sub_folder_1.parent_id, root_folder.id)
        self.assertEqual(sub_folder_2.parent_id, sub_folder_1.id)

        # Test listing by parent
        root_folders = self.service.list_folders(parent_id=None)
        self.assertEqual(len(root_folders), 1)
        self.assertEqual(root_folders[0].id, root_folder.id)

        sub_folders = self.service.list_folders(parent_id=root_folder.id)
        self.assertEqual(len(sub_folders), 1)
        self.assertEqual(sub_folders[0].id, sub_folder_1.id)

        # Test descendants
        descendants = self.service.get_descendant_folder_ids(root_folder.id)
        self.assertEqual(set(descendants), {sub_folder_1.id, sub_folder_2.id})

        # Test breadcrumb path
        path = self.service.get_folder_path(sub_folder_2.id)
        self.assertEqual([f.name for f in path], ["Game Design", "Mechanics", "Combat"])

    def test_folder_persistence_and_reload(self):
        """Verify folders persist across service reloads."""
        f1 = self.service.create_folder(name="Audio Design")
        f2 = self.service.create_folder(name="Foley", parent_id=f1.id)

        reloaded = KnowledgeService(storage_dir=self.storage_dir)
        self.assertEqual(len(reloaded.list_folders()), 2)
        rf2 = reloaded.get_folder(f2.id)
        self.assertIsNotNone(rf2)
        self.assertEqual(rf2.parent_id, f1.id)

    def test_moving_documents_between_folders(self):
        """Verify moving documents between folders updates parent folder and queries."""
        fld_a = self.service.create_folder(name="Folder A")
        fld_b = self.service.create_folder(name="Folder B")

        doc = self.service.create_document(title="Asset Spec", folder_id=fld_a.id)
        self.assertEqual(doc.folder_id, fld_a.id)

        # Check list by folder
        self.assertEqual(len(self.service.list_documents(folder_id=fld_a.id)), 1)
        self.assertEqual(len(self.service.list_documents(folder_id=fld_b.id)), 0)

        # Move to Folder B
        moved = self.service.move_document(doc.id, fld_b.id)
        self.assertEqual(moved.folder_id, fld_b.id)
        self.assertEqual(len(self.service.list_documents(folder_id=fld_a.id)), 0)
        self.assertEqual(len(self.service.list_documents(folder_id=fld_b.id)), 1)

        # Move to Root (None)
        self.service.move_document(doc.id, None)
        self.assertIsNone(self.service.get_document(doc.id).folder_id)
        self.assertEqual(len(self.service.list_documents(folder_id=None)), 1)

    def test_folder_moving_and_cycle_prevention(self):
        """Verify folder moving and cycle prevention (cannot move parent into child)."""
        f1 = self.service.create_folder(name="F1")
        f2 = self.service.create_folder(name="F2", parent_id=f1.id)
        f3 = self.service.create_folder(name="F3", parent_id=f2.id)

        # Moving f3 under f1 directly is allowed
        self.service.move_folder(f3.id, f1.id)
        self.assertEqual(self.service.get_folder(f3.id).parent_id, f1.id)

        # Moving f1 inside itself is invalid
        with self.assertRaises(ValueError):
            self.service.move_folder(f1.id, f1.id)

        # Moving f1 inside its descendant f2 is invalid
        with self.assertRaises(ValueError):
            self.service.move_folder(f1.id, f2.id)

    def test_favorites_management(self):
        """Verify favoriting, unfavoriting, toggling, and favorite filtering."""
        doc1 = self.service.create_document(title="Doc 1", favorite=False)
        doc2 = self.service.create_document(title="Doc 2", favorite=True)

        self.assertEqual(len(self.service.list_documents(favorite_only=True)), 1)

        # Toggle doc1
        self.service.toggle_favorite(doc1.id)
        self.assertTrue(self.service.get_document(doc1.id).favorite)
        self.assertEqual(len(self.service.list_documents(favorite_only=True)), 2)

        # Unfavorite doc2
        self.service.unfavorite(doc2.id)
        self.assertFalse(self.service.get_document(doc2.id).favorite)
        fav_docs = self.service.list_documents(favorite_only=True)
        self.assertEqual(len(fav_docs), 1)
        self.assertEqual(fav_docs[0].id, doc1.id)

    def test_tag_management_and_deduplication(self):
        """Verify tag addition, removal, deduplication, and all tags retrieval."""
        doc1 = self.service.create_document(title="Doc 1", tags=["UI", "Design", "ui"])
        self.assertEqual(doc1.tags, ["UI", "Design", "ui"])

        # Add existing tag (case-insensitive check)
        self.service.add_tag(doc1.id, "ui")
        self.assertEqual(len(self.service.get_document(doc1.id).tags), 3)

        # Add new tag
        self.service.add_tag(doc1.id, "Audio")
        self.assertIn("Audio", self.service.get_document(doc1.id).tags)

        # Remove tag
        self.service.remove_tag(doc1.id, "Design")
        self.assertNotIn("Design", self.service.get_document(doc1.id).tags)

        # List all tags across documents
        self.service.create_document(title="Doc 2", tags=["VFX", "Audio"])
        all_tags = self.service.get_all_tags()
        self.assertIn("Audio", all_tags)
        self.assertIn("VFX", all_tags)
        self.assertIn("UI", all_tags)

    def test_search_by_title_content_and_tag(self):
        """Verify basic search over title, content, and tags."""
        doc1 = self.service.create_document(
            title="Lighting Blueprint Guide",
            content="How to calibrate Lumen and exposure.",
            tags=["lighting", "unreal"],
        )
        doc2 = self.service.create_document(
            title="Animation Pipeline",
            content="Rigging in Blender with Rigify.",
            tags=["animation", "pipeline"],
        )
        doc3 = self.service.create_document(
            title="Shader Notes",
            content="Custom HLSL nodes in Unreal Engine.",
            tags=["materials", "unreal"],
        )

        # Search by title
        res_title = self.service.search("blueprint")
        self.assertEqual(len(res_title), 1)
        self.assertEqual(res_title[0].id, doc1.id)

        # Search by content
        res_content = self.service.search("rigify")
        self.assertEqual(len(res_content), 1)
        self.assertEqual(res_content[0].id, doc2.id)

        # Search by tag
        res_tag = self.service.search("materials")
        self.assertEqual(len(res_tag), 1)
        self.assertEqual(res_tag[0].id, doc3.id)

        # Search matching multiple via tag/content
        res_unreal = self.service.search("unreal")
        self.assertEqual(len(res_unreal), 2)
        self.assertEqual({r.id for r in res_unreal}, {doc1.id, doc3.id})

    def test_safe_folder_deletion(self):
        """Verify safe folder deletion protects against accidental data loss."""
        folder = self.service.create_folder(name="Parent Folder")
        child_doc = self.service.create_document(title="Doc Inside", folder_id=folder.id)

        # Safe mode without reparenting should raise error
        with self.assertRaises(ValueError):
            self.service.delete_folder(folder.id, safe_mode=True, reparent_children=False)

        # With reparent_children=True, doc should be reparented to root
        res = self.service.delete_folder(folder.id, safe_mode=True, reparent_children=True)
        self.assertTrue(res)
        self.assertIsNone(self.service.get_folder(folder.id))

        # Check doc was reparented to None (root)
        reparented_doc = self.service.get_document(child_doc.id)
        self.assertIsNotNone(reparented_doc)
        self.assertIsNone(reparented_doc.folder_id)

    def test_atomic_persistence_guarantee(self):
        """Verify that files are written atomically and temporary files are cleaned up."""
        doc = self.service.create_document(title="Atomic Test", content="Content to write")
        doc_file = self.storage_dir / "documents" / f"{doc.id}.json"
        self.assertTrue(doc_file.exists())

        # Verify no stray tmp files left in directory
        tmp_files = list(self.storage_dir.glob("tmp_*")) + list((self.storage_dir / "documents").glob("tmp_*"))
        self.assertEqual(len(tmp_files), 0)


if __name__ == "__main__":
    unittest.main()
