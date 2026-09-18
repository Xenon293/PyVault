from dataclasses import dataclass
from enum import Enum


class VaultState(Enum):
    NEW = "new"
    READY = "ready"
    CORRUPT = "corrupt"


class VaultError(Exception):
    """Base class for expected vault failures."""


class VaultStateError(VaultError):
    """Raised when an operation is invalid for the current vault state."""


class VaultCorruptionError(VaultStateError):
    """Raised when encrypted vault files are incomplete or malformed."""


class InvalidMasterPassword(VaultError):
    """Raised when the supplied master password cannot unlock the vault."""


class CipherDecryptionError(VaultError):
    """Internal boundary error raised when authenticated decryption fails."""


class StorageMigrationError(VaultError):
    """Raised when vault storage cannot be migrated safely."""


@dataclass(frozen=True)
class Credential:
    website: str
    username: str
    password: str
