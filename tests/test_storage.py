import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from password_manager.data.storage import StorageLayout, prepare_storage
from password_manager.models.domain import StorageMigrationError


class StorageMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.target = self.root / "d-drive" / "PyVault" / "Data"
        self.backups = self.root / "d-drive" / "PyVault" / "Backups"
        self.official = self.root / "c-drive" / "PyVault"
        self.project = self.root / "project"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def layout(self, projects=()):
        return StorageLayout(
            data_directory=self.target,
            backup_directory=self.backups,
            authoritative_legacy_directory=self.official,
            project_legacy_directories=tuple(projects),
        )

    @staticmethod
    def make_vault(directory, marker=b"same", include_vault=True):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "salt.bin").write_bytes((marker * 16)[:16])
        (directory / "vault.check").write_bytes(b"check-" + marker)
        if include_vault:
            (directory / "vault.txt").write_bytes(b"token-" + marker + b"\n")

    def test_migrates_authoritative_source_backs_up_and_removes_duplicates(self):
        self.make_vault(self.official)
        self.make_vault(self.project)

        outcome = prepare_storage(self.layout((self.project,)))

        self.assertEqual(outcome.migrated_from, self.official.resolve())
        self.assertTrue(outcome.backup_directory.is_dir())
        for filename in ("salt.bin", "vault.check", "vault.txt"):
            expected = (outcome.paths.directory / filename).read_bytes()
            self.assertEqual((outcome.backup_directory / filename).read_bytes(), expected)
            self.assertFalse((self.official / filename).exists())
            self.assertFalse((self.project / filename).exists())

    def test_target_plus_source_recovers_interrupted_cleanup(self):
        self.make_vault(self.target)
        self.make_vault(self.official)

        outcome = prepare_storage(self.layout())

        self.assertIsNotNone(outcome.backup_directory)
        self.assertFalse((self.official / "salt.bin").exists())
        second = prepare_storage(self.layout())
        self.assertIsNone(second.backup_directory)
        self.assertEqual(second.paths.directory, self.target.resolve())

    def test_different_legacy_sources_abort_without_deletion(self):
        self.make_vault(self.official, b"official")
        self.make_vault(self.project, b"project")

        with self.assertRaisesRegex(StorageMigrationError, "Legacy vaults differ"):
            prepare_storage(self.layout((self.project,)))
        self.assertTrue((self.official / "salt.bin").exists())
        self.assertTrue((self.project / "salt.bin").exists())
        self.assertFalse(self.target.exists())

    def test_target_conflict_aborts_without_deletion(self):
        self.make_vault(self.target, b"target")
        self.make_vault(self.official, b"official")

        with self.assertRaisesRegex(StorageMigrationError, "D-drive vault differs"):
            prepare_storage(self.layout())
        self.assertTrue((self.official / "salt.bin").exists())

    def test_incomplete_source_aborts(self):
        self.official.mkdir(parents=True)
        (self.official / "salt.bin").write_bytes(b"s" * 16)
        with self.assertRaisesRegex(StorageMigrationError, "incomplete legacy vault"):
            prepare_storage(self.layout())

    def test_copy_verification_failure_retains_source_and_removes_staging(self):
        self.make_vault(self.official)

        def corrupt_copy(_source, destination):
            Path(destination).write_bytes(b"corrupt")

        with patch.object(shutil, "copyfile", side_effect=corrupt_copy):
            with self.assertRaisesRegex(StorageMigrationError, "Verification failed"):
                prepare_storage(self.layout())
        self.assertTrue((self.official / "salt.bin").exists())
        self.assertFalse(self.target.exists())
        self.assertFalse(list(self.target.parent.glob(".*-staging-*")))

    def test_missing_required_drive_does_not_fall_back(self):
        layout = StorageLayout(
            data_directory=Path("Z:/PyVault/Data"),
            backup_directory=Path("Z:/PyVault/Backups"),
            require_existing_drive=True,
        )
        with patch.object(Path, "exists", return_value=False):
            with self.assertRaisesRegex(StorageMigrationError, "required drive is unavailable"):
                prepare_storage(layout)


if __name__ == "__main__":
    unittest.main()
