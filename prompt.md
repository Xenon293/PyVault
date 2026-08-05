# Password Manager Refactor Prompt (RICE-CO Framework)

## Role
You are a senior Python developer specializing in Tkinter desktop applications and clean software architecture (MVC/MVP patterns). You have deep experience refactoring monolithic GUI scripts into modular, maintainable codebases without introducing regressions.

## Instruction
Refactor the attached password manager application into a clean, modular architecture. Preserve all existing functionality exactly (encryption logic, file formats, unlock flow, vault reset flow, credential add/list flow) — this is a structural refactor, not a feature rewrite. Split the current single-file script into logically separated modules following MVC principles, apply Tkinter best practices, and improve performance where the GUI could freeze during I/O.

## Context
- **Current state:** A single-file Tkinter app (`password_manager.py`, ~250 lines) that mixes crypto logic, file I/O, and UI code in one `PasswordManagerApp(tk.Tk)` class with screen-switching via `clear_window()`.
- **Core logic that must not change:**
  - PBKDF2HMAC key derivation (600,000 iterations, SHA256) + Fernet encryption
  - `salt.bin`, `vault.check`, `vault.txt` file scheme
  - First-run "create master password" vs. returning-user "unlock" flow
  - Two-step confirmation before vault reset
  - Append-only encrypted credential storage, one Fernet token per line
- **Known weaknesses to fix:**
  - UI, business logic, and file I/O are all interleaved in one class
  - Global-style state stored directly as Tk widget variables
  - File reads/writes and key derivation run on the main thread (600k PBKDF2 iterations can visibly freeze the UI)
  - No separation that would let the crypto/storage layer be unit-tested without Tkinter running

## Examples
Apply these patterns consistently (don't just describe them — implement them):

**1. Views as `ttk.Frame` subclasses, not screen-clearing:**
```python
class UnlockView(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self._build_layout()

    def _build_layout(self):
        # widget creation and geometry management only — no business logic
        ...
```

**2. Separate creation from placement (never chain `.pack()`/`.grid()` onto assignment):**
```python
# Wrong (current pattern in some places):
# button = ttk.Button(...).pack()

# Right:
unlock_button = ttk.Button(container, text="Unlock", command=self.controller.unlock_vault)
unlock_button.pack(fill="x", pady=(0, 8))
```

**3. Model layer with zero Tkinter imports (testable in isolation):**
```python
# vault_model.py
class VaultModel:
    def __init__(self, vault_path, check_path, salt_path):
        ...
    def unlock(self, master_password: str) -> bool: ...
    def create(self, master_password: str) -> None: ...
    def add_credential(self, website, username, password) -> None: ...
    def list_credentials(self) -> list[str]: ...
```

**4. Threaded key derivation with safe UI updates via `queue.Queue` + `.after()`:**
```python
def unlock_vault(self):
    self.status.set("Unlocking...")
    threading.Thread(target=self._unlock_worker, daemon=True).start()
    self.after(50, self._poll_result_queue)
```

## Constraints
- **Single `tk.Tk()` instance** — the root app owns it; any secondary windows use `tk.Toplevel()`.
- **Do not mix `.pack()` and `.grid()` within the same parent container.**
- Use `ttk` widgets throughout (already mostly done — preserve this).
- Keep all state in `self.` instance attributes — no module-level globals.
- Business logic (crypto, file I/O, validation) must be fully separated from view code — the model layer must be importable and runnable without a Tk root existing.
- Any operation involving PBKDF2 key derivation or file I/O must run off the main thread, with results delivered back to the UI via `queue.Queue` and `.after()` polling — no direct widget mutation from a background thread.
- Do not change the on-disk file format, encryption parameters, or filenames — this must remain compatible with vaults created by the current version.
- Do not add third-party UI libraries (CustomTkinter/ttkbootstrap) unless I explicitly ask in a follow-up — treat that as optional/future scope, not part of this refactor.
- No behavior changes visible to the user: same screens, same confirmations, same error messages.

## Output Format
1. A short summary (5–10 lines) of the new file/folder structure and why each module exists.
2. Full contents of each new file, in this suggested structure (adjust names if there's a clearer convention, but keep the separation):
   ```
   password_manager/
     app.py              # entry point, root Tk, view controller
     models/
       vault_model.py     # crypto + file I/O, no tkinter imports
     views/
       unlock_view.py      # ttk.Frame subclass
       vault_view.py        # ttk.Frame subclass
   ```
3. No inline explanations mixed into the code blocks — keep prose commentary in the summary section only, plus brief docstrings/comments in the code itself.
4. End with a short "What changed vs. what stayed the same" checklist so I can verify no functional drift.
