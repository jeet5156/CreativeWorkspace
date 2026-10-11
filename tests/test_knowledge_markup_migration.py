"""Unit tests for Knowledge and Visual Markups path portability and migration safeguards."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from core.paths import (
    get_app_root,
    get_shared_data_dir,
    get_shared_knowledge_dir,
    get_shared_markups_dir,
    get_local_config_dir,
)
from services.knowledge_service import KnowledgeService
from services.markup_service import MarkupService
from services.activity_service import ActivityService
from services.knowledge_migration import KnowledgeMigrationService
from services.markup_migration import MarkupMigrationService


class TestKnowledgeMarkupMigration(unittest.TestCase):
    """Test suite for Milestone 3: Knowledge, Markups, and ActivityService portability."""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="cw_test_m3_"))
        self.source_dir = self.test_dir / "source"
        self.target_dir = self.test_dir / "target"
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.target_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Path Resolution Tests
    # -------------------------------------------------------------------------

    def test_path_resolution_knowledge_and_markups(self):
        """Verify dynamic resolution of shared knowledge and markup directories."""
        shared_data = get_shared_data_dir()
        self.assertEqual(get_shared_knowledge_dir(), shared_data / "knowledge")
        self.assertEqual(get_shared_markups_dir(), shared_data / "markups")

    def test_activity_service_local_config_resolution(self):
        """Verify ActivityService defaults to local config directory and supports custom path."""
        act_file = self.test_dir / "custom_activity" / "activity.json"
        act_svc = ActivityService(storage_file=act_file)
        self.assertEqual(act_svc._file, act_file)
        act_svc.record(action="test_action", description="Testing activity")
        self.assertTrue(act_file.exists())
        self.assertEqual(len(act_svc.recent(10)), 1)

    # -------------------------------------------------------------------------
    # 2. Knowledge Migration Tests
    # -------------------------------------------------------------------------

    def test_knowledge_dry_run_is_strictly_read_only(self):
        """Verify dry-run does not create target directories, files, or backups."""
        src_k = self.source_dir / "knowledge"
        src_docs = src_k / "documents"
        src_docs.mkdir(parents=True, exist_ok=True)
        (src_docs / "doc_1.json").write_text(json.dumps({"id": "doc_1", "title": "Note 1"}), encoding="utf-8")
        (src_k / "folders.json").write_text(json.dumps([{"id": "fld_1", "name": "Folder 1"}]), encoding="utf-8")

        tgt_k = self.target_dir / "knowledge"  # Does not exist yet

        migrator = KnowledgeMigrationService(source_dir=src_k, target_dir=tgt_k)
        report = migrator.analyze()

        self.assertEqual(report.source_documents_count, 1)
        self.assertEqual(report.source_folders_count, 1)
        self.assertEqual(len(report.new_documents), 1)
        self.assertEqual(len(report.new_folders), 1)
        self.assertFalse(tgt_k.exists())
        self.assertIsNone(report.backup_dir)

    def test_knowledge_migration_execution_and_idempotency(self):
        """Verify execution copies documents/folders and repeated execution is idempotent."""
        src_k = self.source_dir / "knowledge"
        src_docs = src_k / "documents"
        src_docs.mkdir(parents=True, exist_ok=True)
        (src_docs / "doc_1.json").write_text(json.dumps({"id": "doc_1", "title": "Note 1"}), encoding="utf-8")
        (src_k / "folders.json").write_text(json.dumps([{"id": "fld_1", "name": "Folder 1"}]), encoding="utf-8")

        tgt_k = self.target_dir / "knowledge"

        migrator = KnowledgeMigrationService(source_dir=src_k, target_dir=tgt_k)
        report1 = migrator.execute()

        self.assertEqual(len(report1.new_documents), 1)
        self.assertEqual(len(report1.new_folders), 1)
        self.assertTrue((tgt_k / "documents" / "doc_1.json").exists())
        self.assertTrue((tgt_k / "folders.json").exists())

        # Repeated migration
        migrator2 = KnowledgeMigrationService(source_dir=src_k, target_dir=tgt_k)
        report2 = migrator2.analyze()
        self.assertEqual(len(report2.new_documents), 0)
        self.assertEqual(len(report2.identical_documents), 1)
        self.assertEqual(len(report2.new_folders), 0)
        self.assertEqual(len(report2.identical_folders), 1)
        self.assertEqual(len(report2.conflicting_documents), 0)

    def test_knowledge_conflict_detection_and_bundle_isolation(self):
        """Verify differing documents/folders trigger conflict bundles without overwriting target."""
        src_k = self.source_dir / "knowledge"
        src_docs = src_k / "documents"
        src_docs.mkdir(parents=True, exist_ok=True)
        (src_docs / "doc_1.json").write_text(json.dumps({"id": "doc_1", "title": "Source Version"}), encoding="utf-8")
        (src_k / "folders.json").write_text(json.dumps([{"id": "fld_1", "name": "Source Folder"}]), encoding="utf-8")

        tgt_k = self.target_dir / "knowledge"
        tgt_docs = tgt_k / "documents"
        tgt_docs.mkdir(parents=True, exist_ok=True)
        (tgt_docs / "doc_1.json").write_text(json.dumps({"id": "doc_1", "title": "Target Version"}), encoding="utf-8")
        (tgt_k / "folders.json").write_text(json.dumps([{"id": "fld_1", "name": "Target Folder"}]), encoding="utf-8")

        migrator = KnowledgeMigrationService(source_dir=src_k, target_dir=tgt_k)
        report = migrator.execute()

        self.assertEqual(len(report.conflicting_documents), 1)
        self.assertEqual(len(report.conflicting_folders), 1)

        # Ensure target document was NOT overwritten
        tgt_content = json.loads((tgt_docs / "doc_1.json").read_text(encoding="utf-8"))
        self.assertEqual(tgt_content["title"], "Target Version")

        # Ensure conflict bundle exists
        conflicts_dir = tgt_k / "conflicts"
        self.assertTrue(conflicts_dir.exists())
        bundles = list(conflicts_dir.glob("conflict_*"))
        self.assertEqual(len(bundles), 1)
        self.assertTrue((bundles[0] / "conflict_manifest.json").exists())
        self.assertTrue((bundles[0] / "source_documents" / "doc_1.json").exists())
        self.assertTrue((bundles[0] / "target_documents" / "doc_1.json").exists())

    # -------------------------------------------------------------------------
    # 3. Markup Migration Tests
    # -------------------------------------------------------------------------

    def test_markup_dry_run_is_strictly_read_only(self):
        """Verify markup dry run does not write anything to target."""
        src_m = self.source_dir / "markups"
        src_docs = src_m / "documents"
        src_docs.mkdir(parents=True, exist_ok=True)
        (src_docs / "mkp_1.json").write_text(json.dumps({"id": "mkp_1", "name": "Markup 1", "annotations": []}), encoding="utf-8")

        tgt_m = self.target_dir / "markups"

        migrator = MarkupMigrationService(source_dir=src_m, target_dir=tgt_m)
        report = migrator.analyze()

        self.assertEqual(report.source_documents_count, 1)
        self.assertEqual(len(report.new_documents), 1)
        self.assertFalse(tgt_m.exists())

    def test_markup_migration_execution_and_conflict_handling(self):
        """Verify markup migration copies new documents and isolates conflicting ones."""
        src_m = self.source_dir / "markups"
        src_docs = src_m / "documents"
        src_docs.mkdir(parents=True, exist_ok=True)
        (src_docs / "mkp_1.json").write_text(json.dumps({"id": "mkp_1", "name": "Source MKP 1", "annotations": []}), encoding="utf-8")
        (src_docs / "mkp_2.json").write_text(json.dumps({"id": "mkp_2", "name": "New MKP 2", "annotations": []}), encoding="utf-8")

        tgt_m = self.target_dir / "markups"
        tgt_docs = tgt_m / "documents"
        tgt_docs.mkdir(parents=True, exist_ok=True)
        (tgt_docs / "mkp_1.json").write_text(json.dumps({"id": "mkp_1", "name": "Target MKP 1", "annotations": [{"type": "rect"}]}), encoding="utf-8")

        migrator = MarkupMigrationService(source_dir=src_m, target_dir=tgt_m)
        report = migrator.execute()

        self.assertEqual(len(report.new_documents), 1)
        self.assertEqual(len(report.conflicting_documents), 1)
        self.assertTrue((tgt_docs / "mkp_2.json").exists())

        # Ensure target mkp_1 was preserved
        tgt_data = json.loads((tgt_docs / "mkp_1.json").read_text(encoding="utf-8"))
        self.assertEqual(tgt_data["name"], "Target MKP 1")

        # Conflict bundle
        conflicts = list((tgt_m / "conflicts").glob("conflict_*"))
        self.assertEqual(len(conflicts), 1)
        self.assertTrue((conflicts[0] / "source_documents" / "mkp_1.json").exists())
        self.assertTrue((conflicts[0] / "target_documents" / "mkp_1.json").exists())

    # -------------------------------------------------------------------------
    # 4. Service Live Initialization Tests
    # -------------------------------------------------------------------------

    def test_knowledge_service_custom_storage(self):
        """Verify KnowledgeService reads and writes to assigned directory."""
        k_dir = self.test_dir / "k_live"
        svc = KnowledgeService(storage_dir=k_dir)
        folder = svc.create_folder(name="Design")
        doc = svc.create_document(title="Doc A", folder_id=folder.id, content="Sample content")

        self.assertTrue((k_dir / "folders.json").exists())
        self.assertTrue((k_dir / "documents" / f"{doc.id}.json").exists())

        # Reloading in new instance
        svc2 = KnowledgeService(storage_dir=k_dir)
        self.assertIsNotNone(svc2.get_folder(folder.id))
        self.assertIsNotNone(svc2.get_document(doc.id))

    def test_markup_service_custom_storage(self):
        """Verify MarkupService reads and writes to assigned directory."""
        m_dir = self.test_dir / "m_live"
        svc = MarkupService(storage_dir=m_dir)
        doc = svc.create_markup(source_reference={"relative_path": "test.png"}, name="Test Markup")

        self.assertTrue((m_dir / "documents" / f"{doc.id}.json").exists())

        svc2 = MarkupService(storage_dir=m_dir)
        self.assertIsNotNone(svc2.get_markup(doc.id))


if __name__ == "__main__":
    unittest.main()
