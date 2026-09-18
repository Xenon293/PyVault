import inspect
import unittest

from password_manager.models.domain import Credential, InvalidMasterPassword
from password_manager.views.presenter import PyVaultPresenter


class FakeView:
    def __init__(self):
        self.master = ""
        self.confirmation = ""
        self.credential_input = ("", "", "")
        self.selected = None
        self.screen = None
        self.busy_states = []
        self.status = ""
        self.credentials = []
        self.messages = []
        self.visible = {}
        self.confirm_reset_result = True
        self.closed = False

    def show_unlock(self, creating): self.screen = ("unlock", creating)
    def show_vault(self): self.screen = ("vault", None)
    def get_master_password(self): return self.master
    def get_master_password_confirmation(self): return self.confirmation
    def get_credential_input(self): return self.credential_input
    def get_selected_index(self): return self.selected
    def clear_unlock_fields(self): self.master = self.confirmation = ""
    def clear_credential_fields(self): self.credential_input = ("", "", "")
    def set_busy(self, busy): self.busy_states.append(busy)
    def set_status(self, message): self.status = message
    def set_credentials(self, credentials): self.credentials = credentials
    def set_password_visible(self, index, password): self.visible[index] = password
    def set_password_masked(self, index): self.visible.pop(index, None)
    def confirm_reset(self): return self.confirm_reset_result
    def show_info(self, title, message): self.messages.append(("info", title, message))
    def show_warning(self, title, message): self.messages.append(("warning", title, message))
    def show_error(self, title, message): self.messages.append(("error", title, message))
    def close(self): self.closed = True


class FakeService:
    def __init__(self, initialized=False):
        self.initialized = initialized
        self.unlocked = False
        self.credentials = []
        self.created_password = None
        self.unlock_error = None

    def is_initialized(self): return self.initialized
    def create(self, password):
        self.created_password = password
        self.initialized = self.unlocked = True
    def unlock(self, _password):
        if self.unlock_error:
            raise self.unlock_error
        self.unlocked = True
    def lock(self): self.unlocked = False
    def add_credential(self, credential): self.credentials.append(credential)
    def list_credentials(self): return list(self.credentials)
    def reset(self):
        self.initialized = self.unlocked = False
        self.credentials.clear()


class SynchronousRunner:
    def __init__(self):
        self.accept = True
        self.submissions = 0
        self.closed = False

    def submit(self, operation, on_success, on_error):
        if not self.accept:
            return False
        self.submissions += 1
        try:
            result = operation()
        except Exception as exc:
            on_error(exc)
        else:
            on_success(result)
        return True

    def close(self): self.closed = True


class FakeClipboard:
    def __init__(self):
        self.copies = []
        self.clears = 0
    def copy(self, secret, lifetime_ms): self.copies.append((secret, lifetime_ms))
    def clear_if_owned(self): self.clears += 1


class FakeScheduler:
    def __init__(self):
        self.callbacks = {}
        self.next_handle = 0
    def call_later(self, milliseconds, callback):
        self.next_handle += 1
        self.callbacks[self.next_handle] = (milliseconds, callback)
        return self.next_handle
    def cancel(self, handle): self.callbacks.pop(handle, None)


class PresenterTests(unittest.TestCase):
    def make_presenter(self, initialized=False):
        view = FakeView()
        service = FakeService(initialized)
        runner = SynchronousRunner()
        clipboard = FakeClipboard()
        scheduler = FakeScheduler()
        presenter = PyVaultPresenter(view, service, runner, clipboard, scheduler)
        return presenter, view, service, runner, clipboard, scheduler

    def test_create_flow_and_master_password_confirmation(self):
        presenter, view, service, _, _, _ = self.make_presenter()
        presenter.start()
        self.assertEqual(view.screen, ("unlock", True))

        view.master = "one"
        view.confirmation = "two"
        presenter.unlock()
        self.assertIsNone(service.created_password)
        self.assertEqual(view.messages[-1][1], "Passwords do not match")

        view.confirmation = "one"
        presenter.unlock()
        self.assertEqual(service.created_password, "one")
        self.assertEqual(view.screen, ("vault", None))
        self.assertEqual(view.status, "No credentials saved yet.")

    def test_add_trims_labels_but_preserves_password(self):
        presenter, view, service, _, _, _ = self.make_presenter(initialized=True)
        presenter.start()
        view.master = "master"
        presenter.unlock()
        view.credential_input = (" example.com ", " alex ", "  secret  ")

        presenter.add_credential()

        self.assertEqual(service.credentials, [Credential("example.com", "alex", "  secret  ")])
        self.assertEqual(view.credentials, service.credentials)

    def test_invalid_password_maps_to_safe_message(self):
        presenter, view, service, _, _, _ = self.make_presenter(initialized=True)
        service.unlock_error = InvalidMasterPassword("That master password is incorrect.")
        presenter.start()
        view.master = "wrong"
        presenter.unlock()
        self.assertEqual(view.messages[-1], (
            "error", "Wrong password", "That master password is incorrect."
        ))

    def test_busy_state_rejects_overlapping_action(self):
        presenter, view, _, runner, _, _ = self.make_presenter(initialized=True)
        presenter.start()
        presenter.busy = True
        view.master = "master"
        presenter.unlock()
        self.assertEqual(runner.submissions, 0)

    def test_reveal_rehides_and_copy_uses_timed_clipboard(self):
        presenter, view, _, _, clipboard, scheduler = self.make_presenter(True)
        presenter.credentials = [Credential("example.com", "alex", "secret")]
        view.selected = 0

        presenter.toggle_reveal()
        self.assertEqual(view.visible[0], "secret")
        handle = presenter.reveal_handle
        self.assertEqual(scheduler.callbacks[handle][0], 15_000)
        scheduler.callbacks[handle][1]()
        self.assertNotIn(0, view.visible)

        presenter.copy_password()
        self.assertEqual(clipboard.copies, [("secret", 30_000)])

    def test_reset_and_close_clean_session_resources(self):
        presenter, view, service, runner, clipboard, _ = self.make_presenter(True)
        presenter.start()
        presenter.reset()
        self.assertEqual(view.screen, ("unlock", True))
        presenter.close()
        self.assertTrue(runner.closed)
        self.assertTrue(view.closed)
        self.assertGreaterEqual(clipboard.clears, 1)
        self.assertFalse(service.unlocked)

    def test_presenter_has_no_tkinter_or_fernet_dependency(self):
        source = inspect.getsource(PyVaultPresenter)
        self.assertNotIn("tkinter", source)
        self.assertNotIn("Fernet", source)


if __name__ == "__main__":
    unittest.main()
