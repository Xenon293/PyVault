import tkinter as tk
from tkinter import ttk


class VaultView(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=18)
        self.controller = controller
        self.credential_list = None
        self._build_layout()

    def _build_layout(self):
        self.pack(fill="both", expand=True)

        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 12))

        title = ttk.Label(header, text="Your Vault", font=("Segoe UI", 18, "bold"))
        title.pack(side="left")

        lock_button = ttk.Button(header, text="Lock", command=self.controller.show_unlock_screen)
        lock_button.pack(side="right")

        form = ttk.LabelFrame(self, text="Add Credential", padding=14)
        form.pack(fill="x", pady=(0, 14))

        website_label = ttk.Label(form, text="Website")
        website_label.grid(row=0, column=0, sticky="w", padx=(0, 10))

        website_entry = ttk.Entry(form, textvariable=self.controller.website)
        website_entry.grid(row=0, column=1, sticky="ew", padx=(0, 12))

        username_label = ttk.Label(form, text="Username")
        username_label.grid(row=0, column=2, sticky="w", padx=(0, 10))

        username_entry = ttk.Entry(form, textvariable=self.controller.username)
        username_entry.grid(row=0, column=3, sticky="ew")

        password_label = ttk.Label(form, text="Password")
        password_label.grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(10, 0))

        password_entry = ttk.Entry(form, textvariable=self.controller.password, show="*")
        password_entry.grid(
            row=1,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(0, 12),
            pady=(10, 0),
        )

        add_button = ttk.Button(form, text="Add", command=self.controller.add_credential)
        add_button.grid(row=1, column=3, sticky="ew", pady=(10, 0))

        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        list_frame = ttk.LabelFrame(self, text="Saved Credentials", padding=12)
        list_frame.pack(fill="both", expand=True)

        self.credential_list = tk.Listbox(
            list_frame,
            activestyle="none",
            font=("Consolas", 10),
            height=10,
        )
        self.credential_list.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.credential_list.yview,
        )
        scrollbar.pack(side="right", fill="y")
        self.credential_list.configure(yscrollcommand=scrollbar.set)

        status_label = ttk.Label(
            self,
            textvariable=self.controller.status,
            foreground="#667085",
        )
        status_label.pack(fill="x", pady=(10, 0))

    def set_credentials(self, credentials):
        self.credential_list.delete(0, tk.END)
        for index, credential in enumerate(credentials, 1):
            self.credential_list.insert(tk.END, f"{index}. {credential}")
