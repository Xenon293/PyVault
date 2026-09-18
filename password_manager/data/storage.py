import base64
import hashlib
import os
import shutil
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from password_manager.models.domain import CipherDecryptionError, StorageMigrationError


SALT_FILE = "salt.bin"
CHECK_FILE = "vault.check"
VAULT_FILE = "vault.txt"
VAULT_FILES = (SALT_FILE, CHECK_FILE, VAULT_FILE)
PBKDF2_ITERATIONS = 600_000


class FernetVaultCipher:
    """Authenticated-encryption adapter that hides Fernet from the use-case layer."""

    def __init__(self, key: bytes):
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: bytes) -> bytes:
        return self._fernet.encrypt(plaintext)

    def decrypt(self, token: bytes) -> bytes:
        try:
            return self._fernet.decrypt(token)
        except InvalidToken as exc:
            raise CipherDecryptionError("Authenticated decryption failed.") from exc


class FernetCipherFactory:
    """Builds compatible Fernet sessions from a master password and vault salt."""

    def create(self, master_password: str, salt: bytes) -> FernetVaultCipher:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_password.encode("utf-8")))
        return FernetVaultCipher(key)


@dataclass(frozen=True)
class VaultPaths:
    directory: Path
    salt: Path
    check: Path
    vault: Path

    @classmethod
    def from_directory(cls, directory):
        directory = Path(directory)
        return cls(
            directory=directory,
            salt=directory / SALT_FILE,
            check=directory / CHECK_FILE,
            vault=directory / VAULT_FILE,
        )


class VaultStorage:
    """Low-level, atomic byte storage for one vault directory."""

    def __init__(self, paths: VaultPaths):
        self.paths = paths

    def exists(self, path: Path) -> bool:
        return path.is_file()

    def read(self, path: Path) -> bytes:
        return path.read_bytes()

    def read_lines(self, path: Path) -> list[bytes]:
        return [line.strip() for line in self.read(path).splitlines() if line.strip()]

    def write_atomic(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as temporary_file:
                temporary_file.write(data)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            _chmod_private_file(temporary_path)
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)

    def remove(self, path: Path) -> None:
        path.unlink(missing_ok=True)


@dataclass(frozen=True)
class StorageLayout:
    data_directory: Path
    backup_directory: Path
    authoritative_legacy_directory: Path | None = None
    project_legacy_directories: tuple[Path, ...] = ()
    require_existing_drive: bool = False

    @property
    def paths(self):
        return VaultPaths.from_directory(self.data_directory)


@dataclass(frozen=True)
class MigrationOutcome:
    paths: VaultPaths
    migrated_from: Path | None = None
    backup_directory: Path | None = None
    removed_sources: tuple[Path, ...] = ()


def default_storage_layout(project_directory, launch_directory=None):
    project_directory = Path(project_directory).resolve()
    launch_directory = Path(launch_directory or Path.cwd()).resolve()
    legacy_directories = _unique_directories((project_directory, launch_directory))

    if sys.platform == "win32":
        local_app_data = Path(
            os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        )
        return StorageLayout(
            data_directory=Path("D:/PyVault/Data"),
            backup_directory=Path("D:/PyVault/Backups"),
            authoritative_legacy_directory=local_app_data / "PyVault",
            project_legacy_directories=tuple(legacy_directories),
            require_existing_drive=True,
        )

    if sys.platform == "darwin":
        data_directory = Path.home() / "Library" / "Application Support" / "PyVault"
    else:
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg_data_home) if xdg_data_home else Path.home() / ".local" / "share"
        data_directory = base / "pyvault"
    return StorageLayout(
        data_directory=data_directory,
        backup_directory=data_directory.parent / "PyVault Backups",
        project_legacy_directories=tuple(legacy_directories),
    )


def prepare_storage(layout):
    """Prepare active storage and safely retire verified legacy copies."""
    data_directory = Path(layout.data_directory).resolve()
    backup_root = Path(layout.backup_directory).resolve()
    _validate_layout(data_directory, backup_root, layout.require_existing_drive)

    sources = _legacy_sources(layout, excluding=(data_directory, backup_root))
    source_fingerprints = {}
    for source in sources:
        present = _present_files(source)
        if not present:
            continue
        if not _is_complete_vault(source):
            raise StorageMigrationError(
                f"An incomplete legacy vault was found at {source}. No files were changed."
            )
        source_fingerprints[source] = _fingerprint(source)

    if len(set(source_fingerprints.values())) > 1:
        locations = "\n".join(f"- {path}" for path in source_fingerprints)
        raise StorageMigrationError(
            "Legacy vaults differ, so PyVault will not choose between them:\n"
            f"{locations}\n\nNo files were changed."
        )

    target_present = _present_files(data_directory)
    if target_present and not _is_complete_vault(data_directory):
        raise StorageMigrationError(
            f"The D-drive vault is incomplete: {data_directory}. No files were changed."
        )

    authoritative_source = _choose_authoritative_source(layout, source_fingerprints)
    source_fingerprint = (
        source_fingerprints[authoritative_source] if authoritative_source is not None else None
    )

    if target_present:
        target_fingerprint = _fingerprint(data_directory)
        if source_fingerprint is not None and target_fingerprint != source_fingerprint:
            raise StorageMigrationError(
                "The D-drive vault differs from the legacy vault. No files were changed."
            )
    elif authoritative_source is not None:
        _copy_snapshot(authoritative_source, data_directory)
        target_fingerprint = _fingerprint(data_directory)
        if target_fingerprint != source_fingerprint:
            raise StorageMigrationError("The D-drive vault failed post-copy verification.")
    else:
        data_directory.mkdir(parents=True, exist_ok=True)
        _chmod_private_directory(data_directory)
        return MigrationOutcome(paths=VaultPaths.from_directory(data_directory))

    if not source_fingerprints:
        return MigrationOutcome(paths=VaultPaths.from_directory(data_directory))

    backup_path = _matching_backup(backup_root, target_fingerprint)
    if backup_path is None:
        backup_path = _next_backup_path(backup_root)
        _copy_snapshot(data_directory, backup_path)
    if _fingerprint(backup_path) != target_fingerprint:
        raise StorageMigrationError("The D-drive backup failed verification; sources were retained.")

    removed = []
    for source, fingerprint in source_fingerprints.items():
        if fingerprint != target_fingerprint:
            raise StorageMigrationError("A legacy source changed during migration; sources were retained.")
    for source, expected_fingerprint in source_fingerprints.items():
        _remove_verified_vault_files(source, expected_fingerprint)
        removed.append(source)
        if layout.authoritative_legacy_directory is not None:
            authoritative = Path(layout.authoritative_legacy_directory).resolve()
            if source == authoritative:
                try:
                    source.rmdir()
                except OSError:
                    pass

    return MigrationOutcome(
        paths=VaultPaths.from_directory(data_directory),
        migrated_from=authoritative_source,
        backup_directory=backup_path,
        removed_sources=tuple(removed),
    )


def _validate_layout(data_directory, backup_root, require_existing_drive):
    if data_directory == backup_root or data_directory in backup_root.parents:
        raise StorageMigrationError("The backup directory must be outside the active data directory.")
    if require_existing_drive and not Path(data_directory.anchor).exists():
        raise StorageMigrationError(
            f"The required drive is unavailable: {data_directory.anchor}. PyVault will not use C instead."
        )
    try:
        data_directory.parent.mkdir(parents=True, exist_ok=True)
        backup_root.mkdir(parents=True, exist_ok=True)
        _chmod_private_directory(data_directory.parent)
        _chmod_private_directory(backup_root)
        descriptor, probe_name = tempfile.mkstemp(prefix=".write-test-", dir=data_directory.parent)
        os.close(descriptor)
        Path(probe_name).unlink()
    except OSError as exc:
        raise StorageMigrationError(f"D-drive storage is not writable: {exc}") from exc


def _legacy_sources(layout, excluding):
    ordered = []
    if layout.authoritative_legacy_directory is not None:
        ordered.append(layout.authoritative_legacy_directory)
    ordered.extend(layout.project_legacy_directories)
    excluded = {Path(path).resolve() for path in excluding}
    return [path for path in _unique_directories(ordered) if path not in excluded]


def _choose_authoritative_source(layout, fingerprints):
    if layout.authoritative_legacy_directory is not None:
        authoritative = Path(layout.authoritative_legacy_directory).resolve()
        if authoritative in fingerprints:
            return authoritative
    return next(iter(fingerprints), None)


def _copy_snapshot(source, destination):
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    if destination.exists():
        if any(destination.iterdir()):
            raise StorageMigrationError(f"Migration target is not empty: {destination}")
        destination.rmdir()

    staging = destination.parent / f".{destination.name}-staging-{uuid.uuid4().hex}"
    try:
        staging.mkdir(parents=False)
        _chmod_private_directory(staging)
        for filename in VAULT_FILES:
            source_file = source / filename
            if not source_file.exists():
                continue
            destination_file = staging / filename
            shutil.copyfile(source_file, destination_file)
            _chmod_private_file(destination_file)
            with destination_file.open("r+b") as copied_file:
                copied_file.flush()
                os.fsync(copied_file.fileno())
        if _fingerprint(staging) != _fingerprint(source):
            raise StorageMigrationError(f"Verification failed while copying {source}.")
        os.replace(staging, destination)
    except StorageMigrationError:
        raise
    except OSError as exc:
        raise StorageMigrationError(f"Could not copy the vault to {destination}: {exc}") from exc
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _matching_backup(backup_root, expected_fingerprint):
    if not backup_root.exists():
        return None
    for candidate in sorted(backup_root.glob("migration-*"), reverse=True):
        if candidate.is_dir() and _is_complete_vault(candidate):
            if _fingerprint(candidate) == expected_fingerprint:
                return candidate
    return None


def _next_backup_path(backup_root):
    stem = datetime.now().strftime("migration-%Y%m%d-%H%M%S")
    candidate = backup_root / stem
    counter = 2
    while candidate.exists():
        candidate = backup_root / f"{stem}-{counter}"
        counter += 1
    return candidate


def _fingerprint(directory):
    directory = Path(directory)
    entries = []
    for filename in VAULT_FILES:
        path = directory / filename
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            entries.append((filename, path.stat().st_size, digest))
    return tuple(entries)


def _present_files(directory):
    directory = Path(directory)
    return tuple(filename for filename in VAULT_FILES if (directory / filename).exists())


def _is_complete_vault(directory):
    directory = Path(directory)
    return (directory / SALT_FILE).is_file() and (directory / CHECK_FILE).is_file()


def _remove_verified_vault_files(directory, expected_fingerprint):
    directory = Path(directory)
    if _fingerprint(directory) != expected_fingerprint:
        raise StorageMigrationError(
            f"Legacy vault changed before cleanup and was retained: {directory}"
        )
    for filename in VAULT_FILES:
        path = directory / filename
        if path.is_file():
            try:
                path.unlink()
            except OSError as exc:
                raise StorageMigrationError(
                    f"Verified backups are safe, but cleanup failed for {path}: {exc}"
                ) from exc


def _unique_directories(directories):
    result = []
    seen = set()
    for directory in directories:
        resolved = Path(directory).resolve()
        if resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return result


def _chmod_private_directory(path):
    if os.name == "posix":
        os.chmod(path, 0o700)


def _chmod_private_file(path):
    if os.name == "posix":
        os.chmod(path, 0o600)
