import os

from password_manager.models.domain import (
    CipherDecryptionError,
    Credential,
    InvalidMasterPassword,
    VaultCorruptionError,
    VaultState,
    VaultStateError,
)
from password_manager.services.interfaces import CipherFactory, VaultRepository


CHECK_TEXT = b"password-manager-unlocked"
USERNAME_SEPARATOR = " | Username: "
PASSWORD_SEPARATOR = " | Password: "
RECORD_PREFIX = "Website: "


class VaultService:
    """Application service that owns the unlocked cryptographic session."""

    def __init__(self, repository: VaultRepository, cipher_factory: CipherFactory):
        self.repository = repository
        self.cipher_factory = cipher_factory
        self._cipher_suite = None

    def is_initialized(self):
        state = self.repository.state()
        if state is VaultState.CORRUPT:
            raise VaultCorruptionError(
                "The vault setup is incomplete. Restore salt.bin and vault.check "
                "from the same backup, or reset the vault."
            )
        return state is VaultState.READY

    def create(self, master_password):
        if self.repository.state() is not VaultState.NEW:
            raise VaultStateError("A vault already exists or its setup is incomplete.")
        salt = os.urandom(16)
        cipher_suite = self.cipher_factory.create(master_password, salt)
        self.repository.initialize(salt, cipher_suite.encrypt(CHECK_TEXT))
        self._cipher_suite = cipher_suite

    def unlock(self, master_password):
        if not self.is_initialized():
            raise VaultStateError("Create the vault before trying to unlock it.")
        salt = self.repository.read_salt()
        if len(salt) != 16:
            raise VaultCorruptionError("salt.bin is malformed; expected exactly 16 bytes.")
        encrypted_check = self.repository.read_check()
        if not encrypted_check:
            raise VaultCorruptionError("vault.check is empty or damaged.")
        cipher_suite = self.cipher_factory.create(master_password, salt)
        try:
            valid_check = cipher_suite.decrypt(encrypted_check) == CHECK_TEXT
        except CipherDecryptionError as exc:
            raise InvalidMasterPassword("That master password is incorrect.") from exc
        if not valid_check:
            raise InvalidMasterPassword("That master password is incorrect.")
        self._cipher_suite = cipher_suite

    def lock(self):
        self._cipher_suite = None

    def add_credential(self, credential):
        cipher_suite = self._require_unlocked()
        self._validate_credential(credential)
        raw_record = (
            f"{RECORD_PREFIX}{credential.website}{USERNAME_SEPARATOR}{credential.username}"
            f"{PASSWORD_SEPARATOR}{credential.password}"
        )
        self.repository.append_token(cipher_suite.encrypt(raw_record.encode("utf-8")))

    def list_credentials(self):
        cipher_suite = self._require_unlocked()
        credentials = []
        for record_number, token in enumerate(self.repository.read_tokens(), 1):
            try:
                raw_record = cipher_suite.decrypt(token).decode("utf-8")
                credentials.append(self._parse_credential(raw_record))
            except (CipherDecryptionError, UnicodeDecodeError, ValueError) as exc:
                raise VaultCorruptionError(
                    f"Credential record {record_number} is damaged or has an unsupported format."
                ) from exc
        return credentials

    def reset(self):
        self.lock()
        self.repository.reset()

    def _require_unlocked(self):
        if self._cipher_suite is None:
            raise VaultStateError("Unlock the vault before accessing credentials.")
        return self._cipher_suite

    @staticmethod
    def _validate_credential(credential):
        if not credential.website or not credential.username or credential.password == "":
            raise ValueError("Website, username, and password are required.")
        for name, value in (("Website", credential.website), ("Username", credential.username)):
            if USERNAME_SEPARATOR in value or PASSWORD_SEPARATOR in value:
                raise ValueError(f"{name} contains a reserved field separator.")

    @staticmethod
    def _parse_credential(raw_record):
        if not raw_record.startswith(RECORD_PREFIX):
            raise ValueError("Missing credential prefix")
        website, remainder = raw_record[len(RECORD_PREFIX) :].split(USERNAME_SEPARATOR, 1)
        username, password = remainder.split(PASSWORD_SEPARATOR, 1)
        return Credential(website=website, username=username, password=password)
