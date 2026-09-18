import threading

from password_manager.data.storage import VaultStorage
from password_manager.models.domain import VaultCorruptionError, VaultState, VaultStateError
from password_manager.services.interfaces import VaultRepository


class FileVaultRepository(VaultRepository):
    """Atomic encrypted-file persistence with no cryptographic responsibilities."""

    def __init__(self, storage: VaultStorage):
        self.storage = storage
        self.paths = storage.paths
        self._lock = threading.RLock()

    def state(self):
        setup_files = (
            self.storage.exists(self.paths.check),
            self.storage.exists(self.paths.salt),
        )
        if setup_files == (False, False):
            return VaultState.CORRUPT if self.storage.exists(self.paths.vault) else VaultState.NEW
        if setup_files == (True, True):
            return VaultState.READY
        return VaultState.CORRUPT

    def read_salt(self):
        with self._lock:
            self._require_ready()
            return self.storage.read(self.paths.salt)

    def read_check(self):
        with self._lock:
            self._require_ready()
            return self.storage.read(self.paths.check)

    def read_tokens(self):
        with self._lock:
            self._require_ready()
            if not self.storage.exists(self.paths.vault):
                return []
            return self.storage.read_lines(self.paths.vault)

    def initialize(self, salt, encrypted_check):
        with self._lock:
            if self.state() is not VaultState.NEW:
                raise VaultStateError("A vault already exists or its setup is incomplete.")
            self.storage.write_atomic(self.paths.salt, salt)
            try:
                self.storage.write_atomic(self.paths.check, encrypted_check)
            except Exception:
                self.storage.remove(self.paths.salt)
                raise

    def append_token(self, token):
        with self._lock:
            self._require_ready()
            existing = (
                self.storage.read(self.paths.vault)
                if self.storage.exists(self.paths.vault)
                else b""
            )
            if existing and not existing.endswith(b"\n"):
                existing += b"\n"
            self.storage.write_atomic(self.paths.vault, existing + token + b"\n")

    def reset(self):
        with self._lock:
            for path in (self.paths.vault, self.paths.check, self.paths.salt):
                self.storage.remove(path)

    def _require_ready(self):
        if self.state() is not VaultState.READY:
            raise VaultCorruptionError(
                "The vault setup is incomplete. Restore salt.bin and vault.check "
                "from the same backup, or reset the vault."
            )
