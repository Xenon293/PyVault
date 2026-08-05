from tkinter import ttk


class UnlockView(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=32)
        self.controller = controller
        self._build_layout()

    def _build_layout(self):
        self.pack(expand=True)

        title = ttk.Label(
            self,
            text="Password Manager",
            font=("Segoe UI", 22, "bold"),
        )
        title.pack(pady=(0, 8))

        subtitle = ttk.Label(
            self,
            text=self.controller.get_unlock_subtitle(),
            font=("Segoe UI", 11),
        )
        subtitle.pack(pady=(0, 18))

        password_entry = ttk.Entry(
            self,
            textvariable=self.controller.master_password,
            show="*",
            width=34,
            font=("Segoe UI", 11),
        )
        password_entry.pack(pady=(0, 10), ipady=4)
        password_entry.focus_set()
        password_entry.bind("<Return>", lambda event: self.controller.unlock_vault())

        unlock_button = ttk.Button(
            self,
            text="Unlock",
            command=self.controller.unlock_vault,
        )
        unlock_button.pack(fill="x", pady=(0, 8))

        reset_button = ttk.Button(
            self,
            text="Forgot password?",
            command=self.controller.confirm_reset_from_unlock,
        )
        reset_button.pack(fill="x")

        helper = ttk.Label(
            self,
            text="Resetting creates a new empty vault.",
            foreground="#667085",
        )
        helper.pack(pady=(14, 0))
