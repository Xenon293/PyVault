import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from password_manager.data.file_repository import FileVaultRepository
from password_manager.data.storage import VaultPaths, VaultStorage
from password_manager.models.domain import VaultCorruptionError, VaultState


class FileVaultRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.paths = VaultPaths.from_directory(self.directory)
        self.storage = VaultStorage(self.paths)
        self.repository = FileVaultRepository(self.storage)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_state_and_atomic_token_persistence(self):
        self.assertEqual(self.repository.state(), VaultState.NEW)
        self.repository.initialize(b"s" * 16, b"encrypted-check")
        self.assertEqual(self.repository.state(), VaultState.READY)
        self.repository.append_token(b"first")
        self.repository.append_token(b"second")
        self.assertEqual(self.repository.read_tokens(), [b"first", b"second"])

    def test_incomplete_setup_is_corrupt_and_unchanged(self):
        self.paths.salt.write_bytes(b"s" * 16)
        self.assertEqual(self.repository.state(), VaultState.CORRUPT)
        with self.assertRaises(VaultCorruptionError):
            self.repository.read_salt()
        self.assertEqual(self.paths.salt.read_bytes(), b"s" * 16)

    def test_initialize_rolls_back_salt_if_check_write_fails(self):
        original_write = self.storage.write_atomic
        calls = 0

        def failing_write(path, data):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated check failure")
            original_write(path, data)

        with patch.object(self.storage, "write_atomic", side_effect=failing_write):
            with self.assertRaisesRegex(OSError, "simulated check failure"):
                self.repository.initialize(b"s" * 16, b"check")
        self.assertFalse(self.paths.salt.exists())
        self.assertFalse(self.paths.check.exists())


if __name__ == "__main__":
    unittest.main()
