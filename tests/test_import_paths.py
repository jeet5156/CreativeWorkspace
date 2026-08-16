import os
import shutil
import tempfile
import unittest
from pathlib import Path
from models.project import Project
from services.project_service import ProjectService
from services.asset_service import AssetService


class TestImportPaths(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.project_dir = os.path.join(self.test_dir, "TestProject")
        os.makedirs(self.project_dir, exist_ok=True)
        self.project = Project(
            name="TestProject",
            project_type="game",
            location=self.project_dir,
            description="Test Project"
        )
        self.project_service = ProjectService()
        self.asset_service = AssetService(self.project_service)

        # Create temporary external files for testing imports
        self.source_dir = os.path.join(self.test_dir, "SourceFiles")
        os.makedirs(self.source_dir, exist_ok=True)

        self.sample_image = os.path.join(self.source_dir, "hero_banner.png")
        with open(self.sample_image, "w") as f:
            f.write("dummy image content")

        self.sample_audio = os.path.join(self.source_dir, "theme.wav")
        with open(self.sample_audio, "w") as f:
            f.write("dummy audio content")

        self.sample_doc = os.path.join(self.source_dir, "reference.pdf")
        with open(self.sample_doc, "w") as f:
            f.write("dummy document content")

        # Create temporary external folder containing files
        self.sample_folder = os.path.join(self.source_dir, "HeroAssets")
        os.makedirs(self.sample_folder, exist_ok=True)
        self.folder_file1 = os.path.join(self.sample_folder, "model_mesh.obj")
        with open(self.folder_file1, "w") as f:
            f.write("dummy model content")
        self.folder_file2 = os.path.join(self.sample_folder, "texture_skin.png")
        with open(self.folder_file2, "w") as f:
            f.write("dummy texture content")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_import_into_category_root_legacy_behavior(self):
        """Test legacy behavior (target_rel_path omitted): files routed by extension into Assets/Images etc."""
        report = self.asset_service.import_paths(self.project, "assets", [self.sample_image, self.sample_audio])
        self.assertEqual(len(report["imported"]), 2)
        self.assertEqual(len(report["errors"]), 0)

        # Physical destination verification
        expected_img_path = Path(self.project_dir) / "Assets" / "Images" / "hero_banner.png"
        expected_audio_path = Path(self.project_dir) / "Assets" / "Audio" / "theme.wav"
        self.assertTrue(expected_img_path.exists())
        self.assertTrue(expected_audio_path.exists())

        # Asset index & category verification
        assets = self.asset_service.get_assets(self.project)
        self.assertEqual(len(assets), 2)

        img_asset = next(a for a in assets if a["filename"] == "hero_banner.png")
        audio_asset = next(a for a in assets if a["filename"] == "theme.wav")

        self.assertEqual(img_asset["category"], "Assets")
        self.assertEqual(img_asset["relative_path"], "Assets/Images/hero_banner.png")

        self.assertEqual(audio_asset["category"], "Assets")
        self.assertEqual(audio_asset["relative_path"], "Assets/Audio/theme.wav")

    def test_import_file_into_subfolder(self):
        """Test importing single file directly into a physical subfolder (Assets/Hero)."""
        target_rel = "Assets/Hero"
        report = self.asset_service.import_paths(
            self.project, "assets", [self.sample_image], target_rel_path=target_rel
        )
        self.assertEqual(len(report["imported"]), 1)
        self.assertEqual(len(report["errors"]), 0)

        # 1. Physical destination verification
        expected_path = Path(self.project_dir) / "Assets" / "Hero" / "hero_banner.png"
        self.assertTrue(expected_path.exists())

        # 2. Verify no fallback to extension folder (Assets/Images)
        fallback_path = Path(self.project_dir) / "Assets" / "Images" / "hero_banner.png"
        self.assertFalse(fallback_path.exists())

        # 3. Index & category & relative_path verification
        assets = self.asset_service.get_assets(self.project)
        self.assertEqual(len(assets), 1)
        asset = assets[0]

        self.assertEqual(asset["filename"], "hero_banner.png")
        self.assertEqual(asset["category"], "Assets")
        self.assertEqual(asset["relative_path"], "Assets/Hero/hero_banner.png")

        # 4. Immediate UI visibility (querying assets in subfolder)
        visible_assets = self.asset_service.get_assets(self.project, relative_path="Assets/Hero")
        self.assertEqual(len(visible_assets), 1)
        self.assertEqual(visible_assets[0]["filename"], "hero_banner.png")

    def test_import_folder_into_subfolder(self):
        """Test importing a directory into a physical subfolder (Assets/Hero)."""
        target_rel = "Assets/Hero"
        report = self.asset_service.import_paths(
            self.project, "assets", [self.sample_folder], target_rel_path=target_rel
        )
        self.assertEqual(len(report["imported"]), 2)
        self.assertEqual(len(report["errors"]), 0)

        # Physical destination verification
        file1_path = Path(self.project_dir) / "Assets" / "Hero" / "HeroAssets" / "model_mesh.obj"
        file2_path = Path(self.project_dir) / "Assets" / "Hero" / "HeroAssets" / "texture_skin.png"
        self.assertTrue(file1_path.exists())
        self.assertTrue(file2_path.exists())

        # Index & category verification
        assets = self.asset_service.get_assets(self.project)
        self.assertEqual(len(assets), 2)
        for a in assets:
            self.assertEqual(a["category"], "Assets")
            self.assertTrue(a["relative_path"].startswith("Assets/Hero/"))

    def test_import_references_subfolder(self):
        """Test importing file into References subfolder (References/Docs)."""
        target_rel = "References/Docs"
        report = self.asset_service.import_paths(
            self.project, "references", [self.sample_doc], target_rel_path=target_rel
        )
        self.assertEqual(len(report["imported"]), 1)

        expected_path = Path(self.project_dir) / "References" / "Docs" / "reference.pdf"
        self.assertTrue(expected_path.exists())

        assets = self.asset_service.get_assets(self.project)
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["category"], "References")
        self.assertEqual(assets[0]["relative_path"], "References/Docs/reference.pdf")


if __name__ == "__main__":
    unittest.main()
