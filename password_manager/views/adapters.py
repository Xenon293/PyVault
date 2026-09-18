import tkinter as tk
from concurrent.futures import ThreadPoolExecutor


class TkScheduler:
    def __init__(self, root):
        self.root = root

    def call_later(self, milliseconds, callback):
        return self.root.after(milliseconds, callback)

    def cancel(self, handle):
        if handle is None:
            return
        try:
            self.root.after_cancel(handle)
        except tk.TclError:
            pass


class TkTaskRunner:
    """Single-worker executor that returns every result on Tk's event loop."""

    def __init__(self, root, poll_interval_ms=50):
        self.root = root
        self.poll_interval_ms = poll_interval_ms
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pyvault")
        self.future = None
        self.callbacks = None
        self.closed = False

    def submit(self, operation, on_success, on_error):
        if self.closed or self.future is not None:
            return False
        self.future = self.executor.submit(operation)
        self.callbacks = (on_success, on_error)
        self.root.after(self.poll_interval_ms, self._poll)
        return True

    def close(self):
        self.closed = True
        if self.future is not None:
            self.future.cancel()
        self.executor.shutdown(wait=False, cancel_futures=True)

    def _poll(self):
        if self.closed or self.future is None:
            return
        if not self.future.done():
            self.root.after(self.poll_interval_ms, self._poll)
            return

        future = self.future
        on_success, on_error = self.callbacks
        self.future = None
        self.callbacks = None
        try:
            result = future.result()
        except Exception as exc:
            on_error(exc)
        else:
            on_success(result)


class TkClipboardManager:
    """Owns clipboard cleanup without deleting newer user clipboard contents."""

    def __init__(self, root, scheduler):
        self.root = root
        self.scheduler = scheduler
        self.secret = None
        self.clear_handle = None

    def copy(self, secret, lifetime_ms):
        self.clear_if_owned()
        self.root.clipboard_clear()
        self.root.clipboard_append(secret)
        self.root.update_idletasks()
        self.secret = secret
        self.clear_handle = self.scheduler.call_later(lifetime_ms, self._scheduled_clear)

    def clear_if_owned(self):
        if self.clear_handle is not None:
            self.scheduler.cancel(self.clear_handle)
            self.clear_handle = None
        if self.secret is not None:
            try:
                if self.root.clipboard_get() == self.secret:
                    self.root.clipboard_clear()
            except tk.TclError:
                pass
        self.secret = None

    def _scheduled_clear(self):
        self.clear_handle = None
        self.clear_if_owned()
