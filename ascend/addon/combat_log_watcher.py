"""Combat log watcher interface.

The CombatLogWatcher monitors the WoW SavedVariables directory for changes
written by the in-game addon and converts them to RaidSession objects that
Ascend can display and analyse.

This module defines the abstract interface. A concrete Windows implementation
(using ReadDirectoryChangesW or a polling fallback) will be added once the
addon is shipped. The interface is intentionally minimal so alternative
implementations (e.g. reading from a local named pipe) can be dropped in
without changing the rest of Ascend.
"""
from __future__ import annotations

import abc
from typing import Callable

from ascend.addon.session_model import RaidSession


class CombatLogWatcher(abc.ABC):
    """Watch for new or updated raid session data and call a callback.

    Usage::

        watcher = ConcreteWatcher(saved_vars_path)
        watcher.on_session_updated(my_callback)
        watcher.start()
        # ... Ascend runs ...
        watcher.stop()
    """

    def __init__(self) -> None:
        self._callbacks: list[Callable[[RaidSession], None]] = []

    def on_session_updated(self, callback: Callable[[RaidSession], None]) -> None:
        """Register a callback to be called whenever a complete RaidSession is parsed."""
        self._callbacks.append(callback)

    def _emit(self, session: RaidSession) -> None:
        for cb in self._callbacks:
            cb(session)

    @abc.abstractmethod
    def start(self) -> None:
        """Begin watching. Must not block the caller's thread."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop watching and release resources."""

    @property
    @abc.abstractmethod
    def is_running(self) -> bool:
        """True if the watcher is currently active."""


class NullCombatLogWatcher(CombatLogWatcher):
    """No-op watcher used when the addon is not installed or the path is not configured.

    Allows Ascend to start normally without the addon; the rest of the app
    can check ``watcher.is_running`` to decide whether to show the live-log
    panel.
    """

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    @property
    def is_running(self) -> bool:
        return False
