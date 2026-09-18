from tkinter import ttk


MASKED_PASSWORD = "••••••••••••"


class VaultView(ttk.Frame):
    def __init__(self, parent, host):
        super().__init__(parent, padding=18)
        self.host = host
        self.controls = []
        self.credential_tree = None
        self.reveal_button = None
        self._build_layout()

    def _build_layout(self):
        self.pack(fill="both", expand=True)

        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Your Vault", font=("Segoe UI", 18, "bold")).pack(side="left")
        lock_button = ttk.Button(header, text="Lock", command=self.host.presenter.lock)
        lock_button.pack(side="right")
        self.controls.append(lock_button)

        form = ttk.LabelFrame(self, text="Add Credential", padding=14)
        form.pack(fill="x", pady=(0, 14))
        ttk.Label(form, text="Website").grid(row=0, column=0, sticky="w", padx=(0, 10))
        website_entry = ttk.Entry(form, textvariable=self.host.website)
        website_entry.grid(row=0, column=1, sticky="ew", padx=(0, 12))
        ttk.Label(form, text="Username").grid(row=0, column=2, sticky="w", padx=(0, 10))
        username_entry = ttk.Entry(form, textvariable=self.host.username)
        username_entry.grid(row=0, column=3, sticky="ew")
        ttk.Label(form, text="Password").grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=(10, 0)
        )
        password_entry = ttk.Entry(form, textvariable=self.host.password, show="*")
        password_entry.grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=(0, 12), pady=(10, 0)
        )
        add_button = ttk.Button(form, text="Add", command=self.host.presenter.add_credential)
        add_button.grid(row=1, column=3, sticky="ew", pady=(10, 0))
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)
        self.controls.extend((website_entry, username_entry, password_entry, add_button))

        list_frame = ttk.LabelFrame(self, text="Saved Credentials", padding=12)
        list_frame.pack(fill="both", expand=True)
        columns = ("website", "username", "password")
        self.credential_tree = ttk.Treeview(
            list_frame, columns=columns, show="headings", selectmode="browse", height=10
        )
        self.credential_tree.heading("website", text="Website")
        self.credential_tree.heading("username", text="Username")
        self.credential_tree.heading("password", text="Password")
        self.credential_tree.column("website", width=190, anchor="w")
        self.credential_tree.column("username", width=190, anchor="w")
        self.credential_tree.column("password", width=170, anchor="w")
        self.credential_tree.grid(row=0, column=0, sticky="nsew")
        self.credential_tree.bind(
            "<<TreeviewSelect>>", lambda _event: self.host.presenter.selection_changed()
        )

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.credential_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.credential_tree.configure(yscrollcommand=scrollbar.set)
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        actions = ttk.Frame(list_frame)
        actions.grid(row=1, column=0, columnspan=2, sticky="e", pady=(10, 0))
        self.reveal_button = ttk.Button(
            actions, text="Reveal", command=self.host.presenter.toggle_reveal
        )
        self.reveal_button.pack(side="left", padx=(0, 8))
        copy_button = ttk.Button(
            actions, text="Copy password", command=self.host.presenter.copy_password
        )
        copy_button.pack(side="left")
        self.controls.extend((self.credential_tree, self.reveal_button, copy_button))

        ttk.Label(
            self, textvariable=self.host.status, foreground="#667085"
        ).pack(fill="x", pady=(10, 0))

    def set_credentials(self, credentials):
        for item in self.credential_tree.get_children():
            self.credential_tree.delete(item)
        for index, credential in enumerate(credentials):
            self.credential_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(credential.website, credential.username, MASKED_PASSWORD),
            )

    def get_selected_index(self):
        selection = self.credential_tree.selection()
        return int(selection[0]) if selection else None

    def set_password_visible(self, index, password):
        if self.credential_tree.exists(str(index)):
            values = list(self.credential_tree.item(str(index), "values"))
            values[2] = password
            self.credential_tree.item(str(index), values=values)
            self.reveal_button.configure(text="Hide")

    def set_password_masked(self, index):
        if self.credential_tree.exists(str(index)):
            values = list(self.credential_tree.item(str(index), "values"))
            values[2] = MASKED_PASSWORD
            self.credential_tree.item(str(index), values=values)
        self.reveal_button.configure(text="Reveal")

    def set_busy(self, busy):
        for control in self.controls:
            control.state(["disabled"] if busy else ["!disabled"])
