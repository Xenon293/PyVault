import unittest

from password_manager.views.adapters import TkClipboardManager


class FakeRoot:
    def __init__(self):
        self.clipboard = ""
        self.clear_count = 0
    def clipboard_clear(self):
        self.clipboard = ""
        self.clear_count += 1
    def clipboard_append(self, value): self.clipboard = value
    def clipboard_get(self): return self.clipboard
    def update_idletasks(self): pass


class FakeScheduler:
    def __init__(self):
        self.callback = None
        self.cancelled = []
    def call_later(self, _milliseconds, callback):
        self.callback = callback
        return "timer"
    def cancel(self, handle): self.cancelled.append(handle)


class ClipboardAdapterTests(unittest.TestCase):
    def test_clears_password_only_when_clipboard_is_unchanged(self):
        root = FakeRoot()
        scheduler = FakeScheduler()
        clipboard = TkClipboardManager(root, scheduler)
        clipboard.copy("secret", 30_000)
        initial_clears = root.clear_count
        clipboard.clear_if_owned()
        self.assertEqual(root.clear_count, initial_clears + 1)

        clipboard.copy("secret", 30_000)
        initial_clears = root.clear_count
        root.clipboard = "new user text"
        clipboard.clear_if_owned()
        self.assertEqual(root.clear_count, initial_clears)


if __name__ == "__main__":
    unittest.main()
