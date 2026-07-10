"""Background task infrastructure built on QThreadPool/QRunnable.

Keeps the GUI thread responsive during API downloads and analysis. Worker
functions take the form ``fn(progress_callback, cancel_token, *args, **kwargs)``
and should periodically check ``cancel_token.is_cancelled`` so cancellation
does not corrupt local data (each unit of work - e.g. one fight - should be
fully committed or not started at all).
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class CancellationToken:
    def __init__(self):
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled


class WorkerSignals(QObject):
    started = Signal()
    progress = Signal(int, str)  # percent 0-100, status message
    finished = Signal(object)  # result value returned by the worker function
    error = Signal(str)
    cancelled = Signal()


class BackgroundTask(QRunnable):
    def __init__(self, fn: Callable, *args: Any, **kwargs: Any):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.cancel_token = CancellationToken()
        self.setAutoDelete(True)

    def cancel(self) -> None:
        self.cancel_token.cancel()

    @Slot()
    def run(self) -> None:
        self.signals.started.emit()

        def report_progress(percent: int, message: str = "") -> None:
            self.signals.progress.emit(percent, message)

        try:
            result = self.fn(report_progress, self.cancel_token, *self.args, **self.kwargs)
        except Exception as exc:  # noqa: BLE001 - surface any worker failure to the GUI
            self.signals.error.emit(f"{type(exc).__name__}: {exc}")
            return

        if self.cancel_token.is_cancelled:
            self.signals.cancelled.emit()
            return

        self.signals.finished.emit(result)


class BackgroundTaskManager:
    """Owns a dedicated thread pool (not Qt's process-wide global one, which Qt
    itself may also use internally and which would make multiple managers -
    or multiple tests in the same process - contend with each other)."""

    def __init__(self, max_thread_count: int = 4):
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(max_thread_count)
        self._active_tasks: list[BackgroundTask] = []

    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> BackgroundTask:
        task = BackgroundTask(fn, *args, **kwargs)
        self._active_tasks.append(task)

        def _cleanup(*_unused: Any) -> None:
            if task in self._active_tasks:
                self._active_tasks.remove(task)

        task.signals.finished.connect(_cleanup)
        task.signals.error.connect(_cleanup)
        task.signals.cancelled.connect(_cleanup)
        self.pool.start(task)
        return task

    def cancel_all(self) -> None:
        for task in list(self._active_tasks):
            task.cancel()

    def active_count(self) -> int:
        return len(self._active_tasks)

    def wait_for_done(self, timeout_ms: int = -1) -> bool:
        return self.pool.waitForDone(timeout_ms)
