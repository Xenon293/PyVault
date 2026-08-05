import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from cryptography.fernet import InvalidToken

from password_manager.models.vault_model import VaultModel
from password_manager.views.unlock_view import UnlockView
from password_manager.views.vault_view import VaultView


SALT_FILE = "salt.bin"
CHECK_FILE = "vault.check"
VAULT_FILE = "vault.txt"


class PasswordManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Password Manager")
        self.geometry("680x460")
        self.minsize(560, 420)
        self.configure(bg="#f4f6f8")

        base_path = Path.cwd()
        self.vault_model = VaultModel(
            vault_path=base_path / VAULT_FILE,
            check_path=base_path / CHECK_FILE,
            salt_path=base_path / SALT_FILE,
        )

        self.cipher_suite = None
        self.current_view = None
        self.result_queue = queue.Queue()
        self.polling_queue = False
        self.active_workers = 0
        self.worker_lock = threading.Lock()

        self.master_password = tk.StringVar()
        self.website = tk.StringVar()
        self.username = tk.StringVar()
        self.password = tk.StringVar()
        self.status = tk.StringVar()

        self.show_unlock_screen()

    def get_unlock_subtitle(self):
        if self.vault_model.is_initialized():
            return "Enter your master password"
        return "Create your master password"

    def show_unlock_screen(self):
        self._clear_view()
        self.cipher_suite = None
        self.master_password.set("")
        self.current_view = UnlockView(self, self)

    def show_vault_screen(self):
        self._clear_view()
        self.current_view = VaultView(self, self)
        self.refresh_credentials()

    def unlock_vault(self):
        master_password = self.master_password.get()
        if not master_password:
            messagebox.showwarning("Missing password", "Please enter a master password.")
            return

        self.status.set("Unlocking...")
        action = "unlock"
        if not self.vault_model.is_initialized():
            action = "create"

        self._run_worker(action, self._unlock_worker, action, master_password)

    def confirm_reset_from_unlock(self):
        confirmed = messagebox.askyesno(
            "Reset vault?",
            "Resetting deletes your saved credentials and master password setup.\n\n"
            "Do you want to continue?",
        )
        if not confirmed:
            return

        second_confirm = messagebox.askyesno(
            "Delete everything?",
            "This cannot recover your old passwords later.\n\n"
            "Delete the vault and start over?",
        )
        if not second_confirm:
            return

        self._run_worker("reset", self._reset_worker)

    def add_credential(self):
        website = self.website.get().strip()
        username = self.username.get().strip()
        password = self.password.get().strip()

        if not website or not username or not password:
            messagebox.showwarning(
                "Missing details",
                "Please fill in website, username, and password.",
            )
            return

        self._run_worker("add", self._add_worker, website, username, password)

    def refresh_credentials(self):
        if self.cipher_suite is None:
            return
        self._run_worker("list", self._list_worker)

    def _clear_view(self):
        if self.current_view is not None:
            self.current_view.destroy()
            self.current_view = None

    def _run_worker(self, action, target, *args):
        with self.worker_lock:
            self.active_workers += 1

        worker = threading.Thread(
            target=self._worker_wrapper,
            args=(target, args),
            daemon=True,
        )
        worker.start()
        if not self.polling_queue:
            self.polling_queue = True
            self.after(50, self._poll_result_queue)

    def _worker_wrapper(self, target, args):
        try:
            target(*args)
        finally:
            with self.worker_lock:
                self.active_workers -= 1

    def _unlock_worker(self, action, master_password):
        try:
            if action == "create":
                cipher_suite = self.vault_model.create(master_password)
            else:
                cipher_suite = self.vault_model.unlock(master_password)
        except InvalidToken:
            self.result_queue.put((action, "invalid", None))
        except Exception as exc:
            self.result_queue.put((action, "error", exc))
        else:
            self.result_queue.put((action, "success", cipher_suite))
        finally:
            master_password = None

    def _add_worker(self, website, username, password):
        try:
            self.vault_model.add_credential(
                self.cipher_suite,
                website,
                username,
                password,
            )
        except InvalidToken:
            self.result_queue.put(("add", "invalid", None))
        except Exception as exc:
            self.result_queue.put(("add", "error", exc))
        else:
            self.result_queue.put(("add", "success", None))
        finally:
            website = None
            username = None
            password = None

    def _list_worker(self):
        try:
            credentials = self.vault_model.list_credentials(self.cipher_suite)
        except InvalidToken:
            self.result_queue.put(("list", "invalid", None))
        except Exception as exc:
            self.result_queue.put(("list", "error", exc))
        else:
            self.result_queue.put(("list", "success", credentials))

    def _reset_worker(self):
        try:
            self.vault_model.reset()
        except Exception as exc:
            self.result_queue.put(("reset", "error", exc))
        else:
            self.result_queue.put(("reset", "success", None))

    def _poll_result_queue(self):
        try:
            while True:
                action, status, payload = self.result_queue.get_nowait()
                self._handle_worker_result(action, status, payload)
        except queue.Empty:
            pass

        if self.result_queue.empty() and not self._has_active_workers():
            self.polling_queue = False
            return

        self.after(50, self._poll_result_queue)

    def _has_active_workers(self):
        with self.worker_lock:
            return self.active_workers > 0

    def _handle_worker_result(self, action, status, payload):
        if action in ("create", "unlock"):
            self._handle_unlock_result(action, status, payload)
        elif action == "add":
            self._handle_add_result(status, payload)
        elif action == "list":
            self._handle_list_result(status, payload)
        elif action == "reset":
            self._handle_reset_result(status, payload)

    def _handle_unlock_result(self, action, status, payload):
        if status == "invalid":
            messagebox.showerror("Wrong password", "That master password is incorrect.")
            self.master_password.set("")
            return

        if status == "error":
            messagebox.showerror("Vault error", str(payload))
            self.master_password.set("")
            return

        self.cipher_suite = payload
        self.master_password.set("")

        if action == "create":
            messagebox.showinfo("Vault created", "New master password created.")

        self.show_vault_screen()

    def _handle_add_result(self, status, payload):
        if status == "invalid":
            messagebox.showerror("Vault error", "Could not decrypt the vault.")
            self.show_unlock_screen()
            return

        if status == "error":
            messagebox.showerror("Vault error", str(payload))
            return

        self.website.set("")
        self.username.set("")
        self.password.set("")
        self.status.set("Credential saved.")
        self.refresh_credentials()

    def _handle_list_result(self, status, payload):
        if status == "invalid":
            messagebox.showerror("Vault error", "Could not decrypt the vault.")
            self.show_unlock_screen()
            return

        if status == "error":
            messagebox.showerror("Vault error", str(payload))
            return

        credentials = payload
        if isinstance(self.current_view, VaultView):
            self.current_view.set_credentials(credentials)

        if not credentials:
            self.status.set("No credentials saved yet.")
            return

        self.status.set(f"{len(credentials)} credential(s) loaded.")

    def _handle_reset_result(self, status, payload):
        if status == "error":
            messagebox.showerror("Vault error", str(payload))
            return

        self.master_password.set("")
        messagebox.showinfo(
            "Vault reset",
            "Vault reset complete. Create a new master password.",
        )
        self.show_unlock_screen()


def main():
    app = PasswordManagerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
