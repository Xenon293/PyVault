import base64
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


CHECK_TEXT = b"password-manager-unlocked"
PBKDF2_ITERATIONS = 600_000


class VaultModel:
    """Crypto and file storage for the password vault."""

    def __init__(self, vault_path, check_path, salt_path):
        self.vault_path = Path(vault_path)
        self.check_path = Path(check_path)
        self.salt_path = Path(salt_path)

    def is_initialized(self):
        return self.check_path.exists()

    def create(self, master_password):
        salt = self._load_or_create_salt()
        cipher_suite = Fernet(self._derive_key(master_password, salt))

        with self.check_path.open("wb") as check_file:
            self._chmod_private(self.check_path)
            check_file.write(cipher_suite.encrypt(CHECK_TEXT))

        return cipher_suite

    def unlock(self, master_password):
        salt = self._load_or_create_salt()
        cipher_suite = Fernet(self._derive_key(master_password, salt))

        with self.check_path.open("rb") as check_file:
            encrypted_check = check_file.read()

        try:
            if cipher_suite.decrypt(encrypted_check) != CHECK_TEXT:
                raise InvalidToken
        except InvalidToken:
            raise

        return cipher_suite

    def add_credential(self, cipher_suite, website, username, password):
        raw_string = f"Website: {website} | Username: {username} | Password: {password}"
        cipher_text = cipher_suite.encrypt(raw_string.encode("utf-8"))
        vault_existed = self.vault_path.exists()

        with self.vault_path.open("ab") as vault_file:
            if not vault_existed:
                self._chmod_private(self.vault_path)
            vault_file.write(cipher_text + b"\n")

    def list_credentials(self, cipher_suite):
        credentials = []

        if not self.vault_path.exists() or self.vault_path.stat().st_size == 0:
            return credentials

        with self.vault_path.open("rb") as vault_file:
            for line in vault_file:
                clean_line = line.strip()
                if not clean_line:
                    continue

                decrypted_bytes = cipher_suite.decrypt(clean_line)
                credentials.append(decrypted_bytes.decode("utf-8"))

        return credentials

    def reset(self):
        for file_path in (self.vault_path, self.check_path, self.salt_path):
            if file_path.exists():
                file_path.unlink()

    def _load_or_create_salt(self):
        if self.salt_path.exists():
            with self.salt_path.open("rb") as salt_file:
                return salt_file.read()

        salt = os.urandom(16)
        with self.salt_path.open("wb") as salt_file:
            self._chmod_private(self.salt_path)
            salt_file.write(salt)
        return salt

    def _derive_key(self, master_password, salt):
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
        )
        key = kdf.derive(master_password.encode("utf-8"))
        return base64.urlsafe_b64encode(key)

    def _chmod_private(self, path):
        if os.name == "posix":
            os.chmod(path, 0o600)
