"""Versioned, checksum-verified ZIP codec with atomic replacement and size controls."""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import zipfile
from datetime import datetime, timezone
from diagram_editor.core.domain.models import Snapshot

ARCHIVE_VERSION = 1
FILES = ("manifest.json", "source.mmd", "document.json")
MAX_ENTRY_SIZE = 50 * 1024 * 1024  # Safety constraint, not an object count limit.
MAX_TOTAL_SIZE = 100 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1000


class ArchiveError(ValueError):
    pass


class SaveCancelled(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_json(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def encode(snapshot: Snapshot) -> bytes:
    source = snapshot.source.encode("utf-8")
    # Document is kept separately from source so an invalid draft cannot erase
    # the last correctly parsed structure.
    doc_data = _safe_json(snapshot.to_dict()["document"])
    manifest = {
        "format": "diagram-editor-project",
        "schema_version": ARCHIVE_VERSION,
        "document_id": snapshot.document_id,
        "source_revision": snapshot.source_revision,
        "edit_revision": snapshot.edit_revision,
        "valid_revision": snapshot.valid_revision,
        "saved_revision": snapshot.saved_revision,
        "project_path": snapshot.project_path,
        "status": snapshot.status,
        "diagnostics": snapshot.diagnostics,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "checksums": {"source.mmd": _sha(source), "document.json": _sha(doc_data)},
    }
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr("manifest.json", _safe_json(manifest))
        z.writestr("source.mmd", source)
        z.writestr("document.json", doc_data)
    return payload.getvalue()


def decode(raw: bytes) -> Snapshot:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos = z.infolist()
            names = [x.filename for x in infos]
            if len(names) != len(FILES) or set(names) != set(FILES) or len(set(names)) != len(names):
                raise ArchiveError("ZIP 내부 파일 목록이 유효하지 않습니다")
            if any(("/" in n or "\\" in n or n.startswith(".") or ".." in n) for n in names):
                raise ArchiveError("ZIP 경로가 안전하지 않습니다")
            if any((info.external_attr >> 16) & 0o170000 == stat.S_IFLNK for info in infos):
                raise ArchiveError("ZIP 심볼릭 링크를 허용하지 않습니다")
            if any(info.file_size > MAX_ENTRY_SIZE or
                   (info.compress_size == 0 and info.file_size != 0) or
                   info.file_size > max(1, info.compress_size) * MAX_COMPRESSION_RATIO
                   for info in infos):
                raise ArchiveError("ZIP 항목의 크기 또는 압축 비율 제한을 초과했습니다")
            if sum(info.file_size for info in infos) > MAX_TOTAL_SIZE:
                raise ArchiveError("ZIP 총 압축 해제 크기 제한 초과")
            manifest = json.loads(z.read("manifest.json").decode("utf-8"))
            if manifest.get("format") != "diagram-editor-project":
                raise ArchiveError("지원하지 않는 프로젝트 형식")
            if manifest.get("schema_version") != ARCHIVE_VERSION:
                raise ArchiveError("지원하지 않는 프로젝트 스키마 버전")
            source_raw = z.read("source.mmd")
            doc_raw = z.read("document.json")
            if manifest.get("checksums", {}).get("source.mmd") != _sha(source_raw) or \
                    manifest.get("checksums", {}).get("document.json") != _sha(doc_raw):
                raise ArchiveError("프로젝트 데이터 체크섬 불일치")
            document = json.loads(doc_raw.decode("utf-8"))
            return Snapshot.from_dict({
                "document_id": manifest["document_id"],
                "source": source_raw.decode("utf-8"),
                "document": document,
                "source_revision": manifest["source_revision"],
                "edit_revision": manifest.get("edit_revision", manifest["source_revision"]),
                "valid_revision": manifest["valid_revision"],
                "saved_revision": manifest.get("saved_revision", -1),
                "project_path": manifest.get("project_path"),
                "status": manifest.get("status", "VALID"),
                "diagnostics": manifest.get("diagnostics", ""),
            })
    except ArchiveError:
        raise
    except (zipfile.BadZipFile, OSError, KeyError, TypeError, UnicodeError,
            ValueError, OverflowError) as exc:
        raise ArchiveError("프로젝트 ZIP이 손상되었거나 메타데이터가 잘못되었습니다") from exc


def read_archive(path: str | Path) -> Snapshot:
    try:
        path = Path(path)
        if path.stat().st_size > MAX_TOTAL_SIZE:
            raise ArchiveError("ZIP 파일이 너무 큽니다")
        return decode(path.read_bytes())
    except OSError as exc:
        raise ArchiveError(f"파일 읽기 실패: {exc}") from exc


def write_atomic(path: str | Path, snapshot: Snapshot,
                 cancel: threading.Event | None = None) -> None:
    """Write temp and verify before os.replace; abort before commit if canceled."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if cancel and cancel.is_set():
        raise SaveCancelled("저장 취소")
    data = encode(snapshot)
    # Check the actual serialized bytes before they can reach a destination.
    checked = decode(data)
    if checked.edit_revision != snapshot.edit_revision or checked.source_revision != snapshot.source_revision:
        raise ArchiveError("기록할 Revision 검증 실패")
    fd, tmp = tempfile.mkstemp(prefix=".diagram-tmp-", suffix=".zip", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        if cancel and cancel.is_set():
            raise SaveCancelled("저장 취소")
        read_archive(tmp)
        if cancel and cancel.is_set():
            raise SaveCancelled("저장 취소")
        os.replace(tmp, path)
        # Directory fsync makes the replacement more durable on POSIX.
        if os.name == "posix":
            try:
                dir_fd = os.open(str(path.parent), os.O_DIRECTORY)
                try: os.fsync(dir_fd)
                finally: os.close(dir_fd)
            except OSError:
                pass
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass
