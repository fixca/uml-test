"""Per-document daemon I/O queue; stopped without waiting on app shutdown."""
from __future__ import annotations
import logging
import threading
from collections import deque
from typing import Callable
from diagram_editor.core.domain.models import Snapshot
from diagram_editor.modules.persistence.repository import ProjectRepository, RecoveryRepository
from diagram_editor.modules.persistence.archive_codec import SaveCancelled


class SaveWorker:
    def __init__(self, project: ProjectRepository, recovery: RecoveryRepository,
                 on_result: Callable[[str, int, bool, str, str], None]):
        self._project = project
        self._recovery = recovery
        self._on_result = on_result
        self._condition = threading.Condition()
        self._items: deque[tuple[str, str, Snapshot]] = deque()
        self._cancel = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="diagram-save-worker")
        self._thread.start()

    def submit_recovery(self, snapshot: Snapshot):
        with self._condition:
            if self._cancel.is_set(): return
            # Only latest pending recovery matters. Manual saves are not coalesced.
            self._items = deque(item for item in self._items if item[0] != "recovery")
            self._items.append(("recovery", "", snapshot.clone()))
            self._condition.notify()

    def submit_project(self, path: str, snapshot: Snapshot):
        with self._condition:
            if self._cancel.is_set(): return
            self._items.append(("project", path, snapshot.clone()))
            self._condition.notify()

    def _run(self):
        while True:
            with self._condition:
                while not self._items and not self._cancel.is_set():
                    self._condition.wait()
                if self._cancel.is_set(): return
                kind, path, snapshot = self._items.popleft()
            try:
                if kind == "project":
                    self._project.save(path, snapshot, self._cancel)
                else:
                    self._recovery.save(snapshot, self._cancel)
                success, message = True, ""
            except SaveCancelled:
                return
            except Exception as exc:
                logging.exception("Save failed")
                success, message = False, str(exc)
            if not self._cancel.is_set():
                self._on_result(kind, snapshot.edit_revision, success, message, path)

    def close(self):
        self._cancel.set()
        with self._condition:
            self._items.clear()
            self._condition.notify_all()
        # Explicitly do not join. The active writer checks cancellation before commit.
