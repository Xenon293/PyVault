import tkinter as tk
from tkinter import messagebox

from password_manager.views.unlock_view import UnlockView
from password_manager.views.vault_view import VaultView


class TkPyVaultView(tk.Tk):
    """Tkinter implementation of the presenter-facing view interface."""

    def __init__(self):
        super().__init__()
        self.title("PyVault")
        self.geometry("760x500")
        self.minsize(640, 440)
        self.configure(bg="#f4f6f8")
        self.presenter = None
        self.current_view = None

        self.master_password = tk.StringVar()
        self.confirm_master_password = tk.StringVar()
        self.website = tk.StringVar()
        self.username = tk.StringVar()
        self.password = tk.StringVar()
        self.status = tk.StringVar()

    def bind_presenter(self, presenter):
        self.presenter = presenter
        self.protocol("WM_DELETE_WINDOW", presenter.close)

    def show_unlock(self, creating):
        self._clear_view()
        self.current_view = UnlockView(self, self, creating)

    def show_vault(self):
        self._clear_view()
        self.current_view = VaultView(self, self)

    def get_master_password(self):
        return self.master_password.get()

    def get_master_password_confirmation(self):
        return self.confirm_master_password.get()

    def get_credential_input(self):
        return self.website.get(), self.username.get(), self.password.get()

    def get_selected_index(self):
        if isinstance(self.current_view, VaultView):
            return self.current_view.get_selected_index()
        return None

    def clear_unlock_fields(self):
        self.master_password.set("")
        self.confirm_master_password.set("")

    def clear_credential_fields(self):
        self.website.set("")
        self.username.set("")
        self.password.set("")

    def set_busy(self, busy):
        if self.current_view is not None:
            self.current_view.set_busy(busy)

    def set_status(self, message):
        self.status.set(message)

    def set_credentials(self, credentials):
        if isinstance(self.current_view, VaultView):
            self.current_view.set_credentials(credentials)

    def set_password_visible(self, index, password):
        if isinstance(self.current_view, VaultView):
            self.current_view.set_password_visible(index, password)

    def set_password_masked(self, index):
        if isinstance(self.current_view, VaultView):
            self.current_view.set_password_masked(index)

    def confirm_reset(self):
        first = messagebox.askyesno(
            "Reset vault?",
            "Resetting deletes your saved credentials and master password setup.\n\n"
            "Do you want to continue?",
            parent=self,
        )
        if not first:
            return False
        return messagebox.askyesno(
            "Delete everything?",
            "This cannot recover your old passwords later.\n\n"
            "Delete the vault and start over?",
            parent=self,
        )

    def show_info(self, title, message):
        messagebox.showinfo(title, message, parent=self)

    def show_warning(self, title, message):
        messagebox.showwarning(title, message, parent=self)

    def show_error(self, title, message):
        messagebox.showerror(title, message, parent=self)

    def close(self):
        self.destroy()

    def _clear_view(self):
        if self.current_view is not None:
            self.current_view.destroy()
            self.current_view = None
