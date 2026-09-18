from __future__ import annotations

from password_manager.models.domain import (
    Credential,
    InvalidMasterPassword,
    VaultCorruptionError,
    VaultError,
)
from password_manager.services.interfaces import (
    ClipboardManager,
    PyVaultView,
    Scheduler,
    TaskRunner,
    VaultServicePort,
)


REVEAL_MILLISECONDS = 15_000
CLIPBOARD_MILLISECONDS = 30_000


class PyVaultPresenter:
    """Tk-independent application orchestration for PyVault."""

    def __init__(
        self,
        view: PyVaultView,
        vault_service: VaultServicePort,
        task_runner: TaskRunner,
        clipboard: ClipboardManager,
        scheduler: Scheduler,
    ):
        self.view = view
        self.vault_service = vault_service
        self.task_runner = task_runner
        self.clipboard = clipboard
        self.scheduler = scheduler
        self.credentials = []
        self.busy = False
        self.creating = True
        self.revealed_index = None
        self.reveal_handle = None

    def start(self):
        try:
            self.creating = not self.vault_service.is_initialized()
        except VaultCorruptionError as exc:
            self.creating = False
            self.view.show_error("Vault error", str(exc))
        self.view.show_unlock(self.creating)

    def unlock(self):
        if self.busy:
            return
        master_password = self.view.get_master_password()
        if not master_password:
            self.view.show_warning("Missing password", "Please enter a master password.")
            return
        if self.creating and master_password != self.view.get_master_password_confirmation():
            self.view.show_warning("Passwords do not match", "Enter the same master password twice.")
            return

        action = "create" if self.creating else "unlock"
        self.view.set_status("Creating vault..." if self.creating else "Unlocking...")

        def operation():
            if action == "create":
                self.vault_service.create(master_password)
            else:
                self.vault_service.unlock(master_password)

        self._submit(operation, lambda _result: self._unlock_succeeded(action), self._unlock_failed)

    def lock(self):
        if self.busy:
            return
        self._cancel_reveal()
        self.clipboard.clear_if_owned()
        self.vault_service.lock()
        self.credentials = []
        self.view.clear_unlock_fields()
        self.view.clear_credential_fields()
        self.view.set_status("")
        self.creating = False
        self.view.show_unlock(False)

    def add_credential(self):
        if self.busy:
            return
        website, username, password = self.view.get_credential_input()
        credential = Credential(website.strip(), username.strip(), password)
        if not credential.website or not credential.username or credential.password == "":
            self.view.show_warning(
                "Missing details", "Please fill in website, username, and password."
            )
            return
        self.view.set_status("Saving credential...")
        self._submit(
            lambda: self.vault_service.add_credential(credential),
            self._add_succeeded,
            self._operation_failed,
        )

    def refresh_credentials(self):
        if self.busy:
            return
        self.view.set_status("Loading credentials...")
        self._submit(
            self.vault_service.list_credentials,
            self._list_succeeded,
            self._list_failed,
        )

    def reset(self):
        if self.busy or not self.view.confirm_reset():
            return
        self._submit(self.vault_service.reset, self._reset_succeeded, self._operation_failed)

    def selection_changed(self):
        self._cancel_reveal()

    def toggle_reveal(self):
        if self.busy:
            return
        index = self.view.get_selected_index()
        if index is None or not 0 <= index < len(self.credentials):
            self.view.show_info("Select a credential", "Select a credential to reveal its password.")
            return
        if self.revealed_index == index:
            self._cancel_reveal()
            return
        self._cancel_reveal()
        self.revealed_index = index
        self.view.set_password_visible(index, self.credentials[index].password)
        self.reveal_handle = self.scheduler.call_later(
            REVEAL_MILLISECONDS, self._scheduled_hide
        )

    def copy_password(self):
        if self.busy:
            return
        index = self.view.get_selected_index()
        if index is None or not 0 <= index < len(self.credentials):
            self.view.show_info("Select a credential", "Select a credential to copy its password.")
            return
        self.clipboard.copy(self.credentials[index].password, CLIPBOARD_MILLISECONDS)
        self.view.set_status("Password copied. Clipboard will clear in 30 seconds.")

    def close(self):
        self._cancel_reveal()
        self.clipboard.clear_if_owned()
        self.vault_service.lock()
        self.task_runner.close()
        self.view.close()

    def _submit(self, operation, on_success, on_error):
        self.busy = True
        self.view.set_busy(True)

        def success(result):
            self._finish_operation()
            on_success(result)

        def failure(exc):
            self._finish_operation()
            on_error(exc)

        if not self.task_runner.submit(operation, success, failure):
            self._finish_operation()

    def _finish_operation(self):
        self.busy = False
        self.view.set_busy(False)

    def _unlock_succeeded(self, action):
        self.view.clear_unlock_fields()
        if action == "create":
            self.view.show_info("Vault created", "New master password created.")
        self.creating = False
        self.view.show_vault()
        self.refresh_credentials()

    def _unlock_failed(self, exc):
        self.view.clear_unlock_fields()
        self.view.set_status("")
        if isinstance(exc, InvalidMasterPassword):
            self.view.show_error("Wrong password", str(exc))
        else:
            self._show_operation_error(exc)

    def _add_succeeded(self, _result):
        self.view.clear_credential_fields()
        self.refresh_credentials()

    def _list_succeeded(self, credentials):
        self.credentials = credentials
        self.view.set_credentials(credentials)
        self.view.set_status(
            f"{len(credentials)} credential(s) loaded."
            if credentials
            else "No credentials saved yet."
        )

    def _list_failed(self, exc):
        self.view.set_status("Credentials could not be loaded.")
        self._show_operation_error(exc)
        if isinstance(exc, VaultCorruptionError):
            self.lock()

    def _reset_succeeded(self, _result):
        self.credentials = []
        self.creating = True
        self.view.clear_unlock_fields()
        self.view.clear_credential_fields()
        self.view.show_info("Vault reset", "Vault reset complete. Create a new master password.")
        self.view.show_unlock(True)

    def _operation_failed(self, exc):
        self.view.set_status("Operation failed.")
        self._show_operation_error(exc)

    def _show_operation_error(self, exc):
        message = str(exc) if isinstance(exc, (VaultError, ValueError)) else "Unexpected vault error."
        self.view.show_error("Vault error", message)

    def _cancel_reveal(self):
        if self.reveal_handle is not None:
            self.scheduler.cancel(self.reveal_handle)
            self.reveal_handle = None
        if self.revealed_index is not None:
            self.view.set_password_masked(self.revealed_index)
        self.revealed_index = None

    def _scheduled_hide(self):
        self.reveal_handle = None
        self._cancel_reveal()
