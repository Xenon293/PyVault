from tkinter import ttk


class UnlockView(ttk.Frame):
    def __init__(self, parent, host, creating):
        super().__init__(parent, padding=32)
        self.host = host
        self.creating = creating
        self.controls = []
        self._build_layout()

    def _build_layout(self):
        self.pack(expand=True)
        ttk.Label(self, text="PyVault", font=("Segoe UI", 22, "bold")).pack(pady=(0, 8))
        ttk.Label(
            self,
            text="Create your master password" if self.creating else "Enter your master password",
            font=("Segoe UI", 11),
        ).pack(pady=(0, 18))

        password_entry = ttk.Entry(
            self,
            textvariable=self.host.master_password,
            show="*",
            width=34,
            font=("Segoe UI", 11),
        )
        password_entry.pack(pady=(0, 10), ipady=4)
        password_entry.focus_set()
        password_entry.bind("<Return>", lambda _event: self.host.presenter.unlock())
        self.controls.append(password_entry)

        if self.creating:
            confirm_entry = ttk.Entry(
                self,
                textvariable=self.host.confirm_master_password,
                show="*",
                width=34,
                font=("Segoe UI", 11),
            )
            confirm_entry.pack(pady=(0, 10), ipady=4)
            confirm_entry.bind("<Return>", lambda _event: self.host.presenter.unlock())
            self.controls.append(confirm_entry)

        unlock_button = ttk.Button(
            self,
            text="Create vault" if self.creating else "Unlock",
            command=self.host.presenter.unlock,
        )
        unlock_button.pack(fill="x", pady=(0, 8))
        self.controls.append(unlock_button)

        if not self.creating:
            reset_button = ttk.Button(
                self,
                text="Forgot password?",
                command=self.host.presenter.reset,
            )
            reset_button.pack(fill="x")
            self.controls.append(reset_button)
            ttk.Label(
                self,
                text="Resetting creates a new empty vault.",
                foreground="#667085",
            ).pack(pady=(14, 0))

        ttk.Label(
            self,
            textvariable=self.host.status,
            foreground="#667085",
        ).pack(pady=(14, 0))

    def set_busy(self, busy):
        for control in self.controls:
            control.state(["disabled"] if busy else ["!disabled"])
