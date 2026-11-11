"""Shared command timeline for source edits and diagram edits."""
from dataclasses import dataclass
from diagram_editor.core.domain.models import Snapshot
import time


@dataclass
class HistoryEntry:
    before: Snapshot
    after: Snapshot
    origin: str
    created_at: float


class CommandManager:
    def __init__(self, limit: int = 100, merge_ms: int = 700):
        self.limit = limit
        self.merge_ms = merge_ms
        self._entries: list[HistoryEntry] = []
        self._cursor = 0

    def record(self, before: Snapshot, after: Snapshot, origin: str, now: float | None = None):
        now = time.monotonic() if now is None else now
        if before.source == after.source and before.document == after.document:
            return
        self._entries = self._entries[:self._cursor]
        if (origin == "source" and self._entries and self._cursor == len(self._entries)
            and self._entries[-1].origin == "source"
            and (now - self._entries[-1].created_at) * 1000 <= self.merge_ms):
            self._entries[-1].after = after.clone()
            self._entries[-1].created_at = now
        else:
            self._entries.append(HistoryEntry(before.clone(), after.clone(), origin, now))
            if len(self._entries) > self.limit:
                self._entries.pop(0)
        self._cursor = len(self._entries)

    def undo(self, state: str) -> Snapshot | None:
        if not self._cursor:
            return None
        entry = self._entries[self._cursor - 1]
        if state != "VALID" and entry.origin != "source":
            return None
        self._cursor -= 1
        return entry.before.clone()

    def redo(self, state: str) -> Snapshot | None:
        if self._cursor >= len(self._entries):
            return None
        entry = self._entries[self._cursor]
        if state != "VALID" and entry.origin != "source":
            return None
        self._cursor += 1
        return entry.after.clone()

    @property
    def can_undo(self) -> bool: return self._cursor > 0

    @property
    def can_redo(self) -> bool: return self._cursor < len(self._entries)
