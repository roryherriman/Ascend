import threading
import time

from ascend.services.background_worker import BackgroundTaskManager


def _add(progress_cb, _cancel_token, a, b):
    progress_cb(50, "adding")
    return a + b


def _gated(fn):
    """Hold the worker until the test has connected to its signals.

    submit() starts the task immediately, and a signal emitted before
    qtbot.waitSignal connects is lost, so an instant task races the test.
    """
    gate = threading.Event()

    def run(progress_cb, cancel_token, *args):
        gate.wait(5)
        return fn(progress_cb, cancel_token, *args)

    return run, gate


def _wait_for_cancellation(progress_cb, cancel_token):
    for _ in range(200):  # up to ~2 seconds
        if cancel_token.is_cancelled:
            return "stopped-early"
        time.sleep(0.01)
    return "never-cancelled"


def test_background_task_completes_successfully(qtbot):
    manager = BackgroundTaskManager()
    fn, gate = _gated(_add)
    task = manager.submit(fn, 2, 3)

    with qtbot.waitSignal(task.signals.finished, timeout=5000) as blocker:
        gate.set()

    assert blocker.args[0] == 5
    assert manager.active_count() == 0


def test_background_task_reports_progress(qtbot):
    manager = BackgroundTaskManager()
    fn, gate = _gated(_add)
    task = manager.submit(fn, 10, 20)

    with qtbot.waitSignal(task.signals.progress, timeout=5000) as blocker:
        gate.set()

    percent, message = blocker.args
    assert percent == 50
    assert "adding" in message


def test_background_task_cancellation_stops_work_without_error(qtbot):
    manager = BackgroundTaskManager()
    task = manager.submit(_wait_for_cancellation)

    task.cancel()

    with qtbot.waitSignal(task.signals.cancelled, timeout=5000):
        pass

    assert manager.active_count() == 0


def test_background_task_error_is_surfaced(qtbot):
    def _raises(progress_cb, _cancel_token):
        raise ValueError("boom")

    manager = BackgroundTaskManager()
    fn, gate = _gated(_raises)
    task = manager.submit(fn)

    with qtbot.waitSignal(task.signals.error, timeout=5000) as blocker:
        gate.set()

    assert "boom" in blocker.args[0]
