"""Focused unit tests for Knowledge subsystem: Relationship Data + Service layer."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from models.knowledge import KnowledgeDocument
from services.knowledge_service import KnowledgeService


class TestKnowledgeRelationships(unittest.TestCase):
    """Test suite covering KnowledgeDocument relationship anchors, KnowledgeService APIs, persistence, and isolation."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.storage_dir = Path(self.test_dir) / "knowledge"
        self.storage_dir.mkdir(parents=True)
        self.service = KnowledgeService(storage_dir=self.storage_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Project Relationships
    # -------------------------------------------------------------------------

    def test_project_relationship_lifecycle_and_idempotency(self):
        """Verify adding, duplicate prevention, and removing project relationships."""
        doc = self.service.create_document(title="GDD Document")
        proj_id_1 = "ProjectAlpha"
        proj_id_2 = "CyclopsGame"

        # Add project 1
        self.service.add_project_relationship(doc.id, proj_id_1)
        self.assertEqual(self.service.get_related_projects(doc.id), [proj_id_1])

        # Duplicate add should be idempotent
        self.service.add_project_relationship(doc.id, proj_id_1)
        self.assertEqual(self.service.get_related_projects(doc.id), [proj_id_1])

        # Add project 2
        self.service.add_project_relationship(doc.id, proj_id_2)
        self.assertEqual(self.service.get_related_projects(doc.id), [proj_id_1, proj_id_2])

        # Safe removal
        self.service.remove_project_relationship(doc.id, "NonExistentProject")
        self.assertEqual(self.service.get_related_projects(doc.id), [proj_id_1, proj_id_2])

        self.service.remove_project_relationship(doc.id, proj_id_1)
        self.assertEqual(self.service.get_related_projects(doc.id), [proj_id_2])

    def test_project_reverse_lookup(self):
        """Verify finding documents by associated project ID."""
        doc1 = self.service.create_document(title="Doc 1", project_ids=["ProjectAlpha", "OtherProject"])
        doc2 = self.service.create_document(title="Doc 2", project_ids=["ProjectAlpha"])
        doc3 = self.service.create_document(title="Doc 3", project_ids=["OtherProject"])

        res = self.service.find_documents_for_project("ProjectAlpha")
        self.assertEqual(len(res), 2)
        self.assertEqual({d.id for d in res}, {doc1.id, doc2.id})

    def test_project_relationship_persistence_and_reload(self):
        """Verify project relationships survive service restarts and reloads."""
        doc = self.service.create_document(title="Persisted Project Note")
        self.service.add_project_relationship(doc.id, "Project_X")

        reloaded = KnowledgeService(storage_dir=self.storage_dir)
        r_doc = reloaded.get_document(doc.id)
        self.assertIsNotNone(r_doc)
        self.assertEqual(r_doc.project_ids, ["Project_X"])
        self.assertEqual(reloaded.get_related_projects(doc.id), ["Project_X"])

    # -------------------------------------------------------------------------
    # 2. Global Library Asset Relationships
    # -------------------------------------------------------------------------

    def test_library_asset_relationship_lifecycle_and_idempotency(self):
        """Verify library asset relationship adding, deduplication, and removal."""
        doc = self.service.create_document(title="Lighting Reference Note")
        lib_id_1 = "lib_3d_rock_001"
        lib_id_2 = "lib_hdri_sunset_002"

        self.service.add_library_asset_relationship(doc.id, lib_id_1)
        # Duplicate add
        self.service.add_library_asset_relationship(doc.id, lib_id_1)
        self.assertEqual(self.service.get_related_library_assets(doc.id), [lib_id_1])

        self.service.add_library_asset_relationship(doc.id, lib_id_2)
        self.assertEqual(len(self.service.get_related_library_assets(doc.id)), 2)

        # Removal
        self.service.remove_library_asset_relationship(doc.id, lib_id_1)
        self.assertEqual(self.service.get_related_library_assets(doc.id), [lib_id_2])

    def test_library_asset_reverse_lookup_and_offline_drive_resilience(self):
        """Verify reverse lookup works even when library drives/files are offline or missing."""
        doc = self.service.create_document(title="Rock Material Spec")
        lib_asset_id = "lib_portable_ssd_asset_999"
        self.service.add_library_asset_relationship(doc.id, lib_asset_id)

        # Simulate external drive offline (LibraryService / filesystem not loaded)
        matching = self.service.find_documents_for_library_asset(lib_asset_id)
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].id, doc.id)

    # -------------------------------------------------------------------------
    # 3. Project-Local Asset Relationships
    # -------------------------------------------------------------------------

    def test_project_local_asset_relationships(self):
        """Verify project-local asset relationship (project_id + asset_id + relative_path)."""
        doc = self.service.create_document(title="Hero Character Breakdown")
        proj_id = "ProjectAlpha"
        asset_id = "asset_hash_hero_fbx"
        rel_path = "Assets/Characters/Hero_Base.fbx"

        self.service.add_project_asset_relationship(doc.id, proj_id, asset_id, rel_path)
        related = self.service.get_related_project_assets(doc.id)
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0]["project_id"], proj_id)
        self.assertEqual(related[0]["asset_id"], asset_id)
        self.assertEqual(related[0]["relative_path"], rel_path)

        # Duplicate add should not add a second entry
        self.service.add_project_asset_relationship(doc.id, proj_id, asset_id, rel_path)
        self.assertEqual(len(self.service.get_related_project_assets(doc.id)), 1)

        # Reverse lookup
        docs = self.service.find_documents_for_project_asset(proj_id, asset_id)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].id, doc.id)

        # Removal
        self.service.remove_project_asset_relationship(doc.id, proj_id, asset_id)
        self.assertEqual(len(self.service.get_related_project_assets(doc.id)), 0)
        self.assertEqual(len(self.service.find_documents_for_project_asset(proj_id, asset_id)), 0)

    # -------------------------------------------------------------------------
    # 4. Creative Lab Node Relationships
    # -------------------------------------------------------------------------

    def test_lab_node_relationships(self):
        """Verify Lab node relationship adding, removal, reverse lookup, and reload."""
        doc = self.service.create_document(title="Board Notes Integration")
        node_id_1 = "node_uuid_boss_fight_concept"
        node_id_2 = "node_uuid_dialog_tree"

        self.service.add_lab_node_relationship(doc.id, node_id_1, board_id="board_main", project_id="ProjectAlpha")
        # Duplicate add
        self.service.add_lab_node_relationship(doc.id, node_id_1)
        self.assertEqual(self.service.get_related_lab_nodes(doc.id), [node_id_1])

        self.service.add_lab_node_relationship(doc.id, node_id_2)
        self.assertEqual(self.service.get_related_lab_nodes(doc.id), [node_id_1, node_id_2])

        # Reverse lookup
        found = self.service.find_documents_for_lab_node(node_id_1)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].id, doc.id)

        # Persistence across reload
        reloaded = KnowledgeService(storage_dir=self.storage_dir)
        self.assertEqual(reloaded.get_related_lab_nodes(doc.id), [node_id_1, node_id_2])

        # Removal
        reloaded.remove_lab_node_relationship(doc.id, node_id_1)
        self.assertEqual(reloaded.get_related_lab_nodes(doc.id), [node_id_2])

    # -------------------------------------------------------------------------
    # 5. Missing / Offline References & Multiple Relationships
    # -------------------------------------------------------------------------

    def test_multi_target_relationships_on_single_document(self):
        """Verify a single document can simultaneously reference projects, library assets, project assets, and lab nodes."""
        doc = self.service.create_document(
            title="Complete Creative Bible",
            project_ids=["Proj_A", "Proj_B"],
            library_asset_ids=["lib_tree_01", "lib_tree_02"],
            project_asset_refs=[{"project_id": "Proj_A", "asset_id": "asset_1", "relative_path": "Assets/Tree.fbx"}],
            lab_node_ids=["node_x", "node_y"],
        )

        reloaded = KnowledgeService(storage_dir=self.storage_dir)
        r_doc = reloaded.get_document(doc.id)

        self.assertEqual(len(r_doc.project_ids), 2)
        self.assertEqual(len(r_doc.library_asset_ids), 2)
        self.assertEqual(len(r_doc.project_asset_refs), 1)
        self.assertEqual(len(r_doc.lab_node_ids), 2)

    def test_missing_referenced_object_does_not_corrupt_knowledge(self):
        """Verify Knowledge documents remain completely intact when external referenced objects are deleted or missing."""
        doc = self.service.create_document(title="Resilient Note")
        missing_proj = "Deleted_Project_99"
        missing_lib_asset = "lib_deleted_asset_88"
        missing_lab_node = "node_deleted_77"

        self.service.add_project_relationship(doc.id, missing_proj)
        self.service.add_library_asset_relationship(doc.id, missing_lib_asset)
        self.service.add_lab_node_relationship(doc.id, missing_lab_node)

        # Service reloads without any external object existing
        reloaded = KnowledgeService(storage_dir=self.storage_dir)
        r_doc = reloaded.get_document(doc.id)

        self.assertIsNotNone(r_doc)
        self.assertIn(missing_proj, r_doc.project_ids)
        self.assertIn(missing_lib_asset, r_doc.library_asset_ids)
        self.assertIn(missing_lab_node, r_doc.lab_node_ids)

    # -------------------------------------------------------------------------
    # 6. Isolation
    # -------------------------------------------------------------------------

    def test_document_deletion_does_not_delete_referenced_objects(self):
        """Verify deleting a knowledge document only deletes the knowledge document file."""
        doc = self.service.create_document(
            title="Temporary Note",
            project_ids=["ProjectAlpha"],
            library_asset_ids=["lib_asset_1"],
            project_asset_refs=[{"project_id": "ProjectAlpha", "asset_id": "asset_1", "relative_path": "Assets/test.png"}],
            lab_node_ids=["node_1"],
        )

        doc_file = self.storage_dir / "documents" / f"{doc.id}.json"
        self.assertTrue(doc_file.exists())

        res = self.service.delete_document(doc.id)
        self.assertTrue(res)
        self.assertFalse(doc_file.exists())

        # Reverse lookups should now return empty
        self.assertEqual(len(self.service.find_documents_for_project("ProjectAlpha")), 0)
        self.assertEqual(len(self.service.find_documents_for_library_asset("lib_asset_1")), 0)
        self.assertEqual(len(self.service.find_documents_for_project_asset("ProjectAlpha", "asset_1")), 0)
        self.assertEqual(len(self.service.find_documents_for_lab_node("node_1")), 0)


if __name__ == "__main__":
    unittest.main()
