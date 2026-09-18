import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from password_manager.data.file_repository import FileVaultRepository
from password_manager.data.storage import (
    FernetCipherFactory,
    VaultStorage,
    default_storage_layout,
    prepare_storage,
)
from password_manager.models.domain import StorageMigrationError
from password_manager.services.vault_service import VaultService
from password_manager.views.adapters import TkClipboardManager, TkScheduler, TkTaskRunner
from password_manager.views.presenter import PyVaultPresenter
from password_manager.views.tk_view import TkPyVaultView


def build_application():
    project_directory = Path(__file__).resolve().parent.parent
    layout = default_storage_layout(project_directory, Path.cwd())
    migration = prepare_storage(layout)

    storage = VaultStorage(migration.paths)
    repository = FileVaultRepository(storage)
    cipher_factory = FernetCipherFactory()
    service = VaultService(repository, cipher_factory)

    view = TkPyVaultView()
    scheduler = TkScheduler(view)
    task_runner = TkTaskRunner(view)
    clipboard = TkClipboardManager(view, scheduler)
    presenter = PyVaultPresenter(view, service, task_runner, clipboard, scheduler)
    view.bind_presenter(presenter)
    presenter.start()

    if migration.backup_directory is not None:
        removed = "\n".join(str(path) for path in migration.removed_sources)
        view.after(
            100,
            lambda: view.show_info(
                "Vault moved to D",
                f"Active vault:\n{migration.paths.directory}\n\n"
                f"Verified backup:\n{migration.backup_directory}\n\n"
                f"Removed verified legacy copies from:\n{removed}",
            ),
        )
    return view


def main():
    try:
        app = build_application()
    except StorageMigrationError as exc:
        error_window = tk.Tk()
        error_window.withdraw()
        messagebox.showerror("PyVault storage error", str(exc), parent=error_window)
        error_window.destroy()
        return
    app.mainloop()


if __name__ == "__main__":
    main()
