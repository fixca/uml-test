"""Separate manual project repository and automatic recovery repository."""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import re
import sys
import threading
from diagram_editor.core.domain.models import Snapshot
from diagram_editor.modules.persistence.archive_codec import read_archive, write_atomic, ArchiveError


class ProjectRepository:
    def save(self, path: str, snapshot: Snapshot, cancel: threading.Event | None = None) -> None:
        write_atomic(path, snapshot, cancel)

    def load(self, path: str) -> Snapshot:
        return read_archive(path)


def app_recovery_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "OfflineDiagramEditor" / "recovery"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "OfflineDiagramEditor" / "recovery"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "offline-diagram-editor" / "recovery"


class RecoveryRepository:
    """Default retention: last 5 revisions per doc, <=7d old extras, <=250MB total.

    The newest valid revision for each doc is never deleted by cleanup.
    """
    def __init__(self, directory: Path | str | None = None, keep: int = 5,
                 retention_days: int = 7, max_total_bytes: int = 250 * 1024 * 1024):
        self.directory = Path(directory) if directory is not None else app_recovery_dir()
        self.keep = keep
        self.retention_days = retention_days
        self.max_total_bytes = max_total_bytes

    def path_for(self, snapshot: Snapshot) -> Path:
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", snapshot.document_id):
            raise ArchiveError("문서 ID가 유효하지 않습니다")
        utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        return self.directory / f"{snapshot.document_id}--{utc}--{snapshot.edit_revision:012d}.recovery.zip"

    def save(self, snapshot: Snapshot, cancel: threading.Event | None = None) -> Path:
        target = self.path_for(snapshot)
        write_atomic(target, snapshot, cancel)
        # No cleanup after cancellation; leave previously committed copies intact.
        if not (cancel and cancel.is_set()):
            self.cleanup()
        return target

    def candidates(self, document_id: str | None = None) -> list[tuple[Path, Snapshot]]:
        if not self.directory.exists():
            return []
        result: list[tuple[Path, Snapshot]] = []
        for p in self.directory.glob("*.recovery.zip"):
            if document_id is not None and not p.name.startswith(document_id + "--"):
                continue
            try:
                state = read_archive(p)
                result.append((p, state))
            except (ArchiveError, OSError):
                continue
        return sorted(result, key=lambda x: (x[1].edit_revision, x[0].name), reverse=True)

    def cleanup(self) -> None:
        if not self.directory.exists():
            return
        valid = self.candidates()
        grouped: dict[str, list[tuple[Path, Snapshot]]] = {}
        for entry in valid:
            grouped.setdefault(entry[1].document_id, []).append(entry)
        protected: set[Path] = set()
        now = datetime.now(timezone.utc).timestamp()
        deletion: list[Path] = []
        for group in grouped.values():
            group.sort(key=lambda x: (x[1].edit_revision, x[0].name), reverse=True)
            protected.add(group[0][0])
            for index, (p, snapshot) in enumerate(group):
                if index >= self.keep or (index > 0 and (now - p.stat().st_mtime) > self.retention_days * 86400):
                    deletion.append(p)
        for p in deletion:
            try: p.unlink(missing_ok=True)
            except OSError: pass
        existing = [(p, p.stat().st_size, p.stat().st_mtime) for p, _ in valid if p.exists()]
        total = sum(size for _, size, _ in existing)
        for p, size, mtime in sorted(existing, key=lambda x: x[2]):
            if total <= self.max_total_bytes:
                break
            if p in protected:
                continue
            try:
                p.unlink()
                total -= size
            except OSError:
                pass
