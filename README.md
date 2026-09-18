# PyVault

PyVault is a local desktop password manager built with Python and Tkinter. Credentials are stored in an encrypted vault protected by one master password.

> [!IMPORTANT]
> PyVault is a learning project and has not received an independent security audit. Keep separate backups of important credentials and do not treat it as a replacement for a professionally audited password manager.

## Features

- Fernet authenticated encryption for every credential
- PBKDF2-HMAC-SHA256 master-key derivation with 600,000 iterations
- Passwords masked by default with deliberate reveal and copy actions
- Automatic re-masking and conditional clipboard clearing
- Atomic encrypted-file writes and explicit corruption detection
- Background cryptographic and file operations that do not freeze the interface
- Verified migration and backup of legacy vault files

## Installation

PyVault requires Python 3.10 or later. Tkinter is normally included with installers from [python.org](https://www.python.org/downloads/).

```bash
git clone https://github.com/Xenon293/PyVault.git
cd PyVault
python -m venv .venv
```

Activate the environment and install the dependency:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

```bash
# macOS or Linux
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Run the application:

```bash
python -m password_manager
```

The legacy `python "Password Manager.py"` command remains available.

## Using PyVault

On first launch, enter the new master password twice. Later launches require the same master password to decrypt the vault.

After unlocking, add a website, username, and password. Select a saved credential to reveal its password for 15 seconds or copy it for 30 seconds. Clipboard cleanup occurs only when the clipboard still contains the value copied by PyVault.

The **Forgot password?** action permanently resets the active vault after two confirmations. A forgotten master password cannot be recovered.

## Data, migration, and backups

On Windows, PyVault requires the D drive and stores its active encrypted data in:

```text
D:\PyVault\Data
```

Migration backups are stored under:

```text
D:\PyVault\Backups\migration-YYYYMMDD-HHMMSS
```

When upgrading from an earlier version, PyVault treats `%LOCALAPPDATA%\PyVault` as authoritative. It copies the vault to the D-drive data and backup directories, verifies file sizes and SHA-256 hashes, and only then removes matching legacy vault files. A differing, incomplete, unavailable, or unwritable source causes migration to stop without selecting another vault or falling back to C.

On macOS and Linux, PyVault retains their platform-native user-data directories. All platforms use the same encrypted filenames:

- `salt.bin`
- `vault.check`
- `vault.txt`, created after the first credential is saved

Back up these files together. Mixing files from different vaults makes the encrypted credentials inaccessible.

## Architecture

PyVault follows Clean Architecture and Model-View-Presenter boundaries:

```text
password_manager/
|-- app.py                       # dependency injection and startup only
|-- __main__.py                  # python -m password_manager entry point
|-- models/
|   `-- domain.py                # pure entities, vault state, and typed errors
|-- services/
|   |-- interfaces.py            # repository, service, view, and adapter ports
|   `-- vault_service.py         # encryption session and business use cases
|-- data/
|   |-- storage.py               # low-level atomic I/O, paths, and migration
|   `-- file_repository.py       # filesystem implementation of VaultRepository
`-- views/
    |-- adapters.py              # Tk task runner, scheduler, and clipboard adapters
    |-- presenter.py             # Tk-independent MVP presenter
    |-- tk_view.py               # presenter-facing Tk application shell
    |-- unlock_view.py           # unlock/setup widgets
    `-- vault_view.py            # credential-management widgets
```

The composition root builds dependencies in this direction:

```text
VaultStorage -> FileVaultRepository -> VaultService -> PyVaultPresenter <- TkPyVaultView
```

Views dispatch events only to the presenter and never import the data layer. The presenter depends on protocols and pure domain types, not Tkinter, filesystem APIs, or Fernet. Encryption keys remain inside `VaultService`; only encrypted bytes cross the repository boundary.

## Tests

```bash
python -m compileall -q "Password Manager.py" password_manager tests
python -m unittest discover -v
```

Tests cover encryption compatibility, service locking, atomic persistence, migration precedence and rollback, verified cleanup, presenter behavior, clipboard ownership, and corruption handling. GitHub Actions runs the same checks on Python 3.10 and 3.14.

## License

No license has been granted for redistribution or reuse.
