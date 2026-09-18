import os
import tempfile
import unittest
from pathlib import Path

from password_manager.data.file_repository import FileVaultRepository
from password_manager.data.storage import FernetCipherFactory, VaultPaths, VaultStorage
from password_manager.models.domain import (
    Credential,
    InvalidMasterPassword,
    VaultCorruptionError,
    VaultStateError,
)
from password_manager.services.vault_service import (
    PASSWORD_SEPARATOR,
    USERNAME_SEPARATOR,
    VaultService,
)


class VaultServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.paths = VaultPaths.from_directory(self.directory)
        self.storage = VaultStorage(self.paths)
        self.repository = FileVaultRepository(self.storage)
        self.service = VaultService(self.repository, FernetCipherFactory())

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_create_unlock_add_list_lock_and_reset(self):
        self.service.create("master password")
        self.service.add_credential(Credential("example.com", "alex", "  spaced secret  "))
        self.service.lock()
        with self.assertRaises(VaultStateError):
            self.service.list_credentials()

        self.service.unlock("master password")
        self.assertEqual(
            self.service.list_credentials(),
            [Credential("example.com", "alex", "  spaced secret  ")],
        )
        self.service.reset()
        self.assertFalse(self.service.is_initialized())

    def test_wrong_master_password_is_typed_domain_error(self):
        self.service.create("correct password")
        self.service.lock()
        with self.assertRaises(InvalidMasterPassword):
            self.service.unlock("wrong password")

    def test_reads_existing_legacy_record_format(self):
        self.service.create("master password")
        cipher = self.service._require_unlocked()
        legacy = b"Website: legacy.example | Username: user | Password: old secret"
        self.repository.append_token(cipher.encrypt(legacy))

        self.assertEqual(
            self.service.list_credentials(),
            [Credential("legacy.example", "user", "old secret")],
        )

    def test_rejects_reserved_separators(self):
        self.service.create("master password")
        for separator in (USERNAME_SEPARATOR, PASSWORD_SEPARATOR):
            with self.subTest(separator=separator):
                with self.assertRaisesRegex(ValueError, "reserved field separator"):
                    self.service.add_credential(
                        Credential(f"bad{separator}site", "user", "secret")
                    )

    def test_malformed_salt_is_reported(self):
        self.service.create("master password")
        self.paths.salt.write_bytes(b"too short")
        self.service.lock()
        with self.assertRaisesRegex(VaultCorruptionError, "16 bytes"):
            self.service.unlock("master password")

    def test_damaged_credential_reports_record_number(self):
        self.service.create("master password")
        self.repository.append_token(b"not-a-fernet-token")
        with self.assertRaisesRegex(VaultCorruptionError, "record 1"):
            self.service.list_credentials()

    @unittest.skipUnless(os.name == "posix", "POSIX permissions only")
    def test_new_files_are_private_on_posix(self):
        self.service.create("master password")
        self.service.add_credential(Credential("example.com", "alex", "secret"))
        for filename in ("salt.bin", "vault.check", "vault.txt"):
            self.assertEqual((self.directory / filename).stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
