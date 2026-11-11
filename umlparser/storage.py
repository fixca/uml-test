""".umlproj 저장/불러오기와 최근 파일. 담당: 이찬혁 (B7, B8).

.umlproj 파일은 UTF-8 JSON 이다.

    {
      "version": 1,
      "code": "<다이어그램 코드>",
      "layout": {
        "nodes": {"User": [120, 80]},
        "edges": {"User->Order": "orthogonal"}
      },
      "model": { ...parse(code).to_dict()... }
    }

- 불러올 때는 code 가 원본이다. model 은 사람이 보거나 다른 모듈이 읽기 쉽게
  같이 저장하는 사본이라 읽지 않는다 (화면은 code 를 다시 파싱해서 그린다).
- 없는 키는 기본값으로 채운다.
- 깨진 JSON, 형식이 맞지 않는 값, 버전 불일치는 StorageError.
- 최근 파일 경로는 사용자 설정 폴더의 settings.json 에 저장한다.
  (Windows: %APPDATA%/uml-tool, 그 외: ~/.config/uml-tool)
"""

import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from umlparser.class_parser import parse

FORMAT_VERSION = 1
FILE_SUFFIX = ".umlproj"
EDGE_STYLES = ("straight", "orthogonal")
DEFAULT_EDGE_STYLE = "straight"

APP_DIR_NAME = "uml-tool"
SETTINGS_FILE_NAME = "settings.json"
EXAMPLE_PATH = Path(__file__).resolve().parent.parent / "examples" / "class-example.mmd"
FALLBACK_CODE = "classDiagram\n"


class StorageError(Exception):
    pass


@dataclass
class Layout:
    nodes: dict[str, tuple[float, float]] = field(default_factory=dict)
    edges: dict[str, str] = field(default_factory=dict)


@dataclass
class Project:
    code: str
    layout: Layout
    path: str | None


# ---------------------------------------------------------------- 새 프로젝트


def new_project() -> Project:
    """예시 코드(examples/class-example.mmd)가 든 새 프로젝트.

    예시 파일이 없으면 빈 다이어그램으로 시작한다.
    """
    try:
        code = EXAMPLE_PATH.read_text(encoding="utf-8-sig")
    except OSError:
        code = FALLBACK_CODE
    return Project(code=code, layout=Layout(), path=None)


# ---------------------------------------------------------------- 저장


def save(project: Project, path: str) -> None:
    """project 를 path 에 .umlproj JSON 으로 저장하고 project.path 를 path 로 바꾼다.

    임시 파일에 다 쓴 뒤 바꿔치기하므로, 저장 중 실패해도 기존 파일은 깨지지 않는다.
    """
    target = Path(path)
    data = {
        "version": FORMAT_VERSION,
        "code": project.code,
        "layout": _layout_to_dict(project.layout),
        "model": _model_dict(project.code),
    }
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"

    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_name = tmp.name
            tmp.write(text)
        os.replace(tmp_name, target)
    except OSError as exc:
        if tmp_name is not None:
            Path(tmp_name).unlink(missing_ok=True)
        raise StorageError(
            f"파일을 저장할 수 없습니다: {target} ({exc.strerror or exc})"
        ) from exc

    project.path = str(target)


def _layout_to_dict(layout: Layout) -> dict[str, Any]:
    return {
        "nodes": {class_id: [x, y] for class_id, (x, y) in layout.nodes.items()},
        "edges": dict(layout.edges),
    }


def _model_dict(code: str) -> dict[str, Any] | None:
    """parse(code).to_dict().

    파서가 아직 stub(NotImplementedError)이면 None 을 저장한다.
    """
    try:
        return parse(code).to_dict()
    except NotImplementedError:
        return None


# ---------------------------------------------------------------- 불러오기


def load(path: str) -> Project:
    """path 의 .umlproj 를 읽는다. 열 수 없거나 깨진 파일이면 StorageError."""
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise StorageError(
            f"파일을 열 수 없습니다: {source} ({exc.strerror or exc})"
        ) from exc
    except UnicodeDecodeError as exc:
        raise StorageError(f"UTF-8 파일이 아닙니다: {source}") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StorageError(
            f"프로젝트 파일이 깨졌습니다: {source} "
            f"({exc.lineno}번째 줄, {exc.colno}번째 칸)"
        ) from exc
    if not isinstance(data, dict):
        raise StorageError(f"프로젝트 파일 형식이 아닙니다: {source}")

    version = data.get("version", FORMAT_VERSION)
    if version != FORMAT_VERSION:
        raise StorageError(
            f"지원하지 않는 파일 버전입니다: {version!r} (지원: {FORMAT_VERSION})"
        )

    code = data.get("code", "")
    if not isinstance(code, str):
        raise StorageError("code 는 문자열이어야 합니다")

    return Project(
        code=code, layout=_layout_from_dict(data.get("layout")), path=str(source)
    )


def _layout_from_dict(data: Any) -> Layout:
    if data is None:
        return Layout()
    if not isinstance(data, dict):
        raise StorageError("layout 은 객체여야 합니다")

    nodes_data = data.get("nodes", {})
    edges_data = data.get("edges", {})
    if not isinstance(nodes_data, dict):
        raise StorageError("layout.nodes 는 객체여야 합니다")
    if not isinstance(edges_data, dict):
        raise StorageError("layout.edges 는 객체여야 합니다")

    nodes: dict[str, tuple[float, float]] = {}
    for class_id, point in nodes_data.items():
        if (
            not isinstance(point, list | tuple)
            or len(point) != 2
            or not all(_is_number(v) for v in point)
        ):
            raise StorageError(
                f"layout.nodes[{class_id!r}] 는 [x, y] 숫자 쌍이어야 합니다"
            )
        nodes[class_id] = (float(point[0]), float(point[1]))

    edges: dict[str, str] = {}
    for key, style in edges_data.items():
        if style not in EDGE_STYLES:
            raise StorageError(
                f"layout.edges[{key!r}] 값은 "
                f"{' / '.join(EDGE_STYLES)} 중 하나여야 합니다"
            )
        edges[key] = style

    return Layout(nodes=nodes, edges=edges)


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


# ---------------------------------------------------------------- 최근 파일


def last_path() -> str | None:
    """마지막으로 열거나 저장한 파일 경로.

    기록이 없거나, 설정이 깨졌거나, 파일이 사라졌으면 None.
    """
    try:
        data = json.loads(_settings_path().read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    path = data.get("lastPath") if isinstance(data, dict) else None
    if not isinstance(path, str) or not Path(path).is_file():
        return None
    return path


def set_last_path(path: str) -> None:
    """최근 파일 경로를 설정 파일에 기록한다. 쓸 수 없으면 StorageError."""
    settings = _settings_path()
    try:
        settings.parent.mkdir(parents=True, exist_ok=True)
        data = _read_settings(settings)
        data["lastPath"] = str(Path(path).resolve())
        settings.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        raise StorageError(
            f"설정을 저장할 수 없습니다: {settings} ({exc.strerror or exc})"
        ) from exc


def _read_settings(settings: Path) -> dict[str, Any]:
    """기존 설정을 읽는다. 없거나 깨졌으면 빈 설정으로 시작한다."""
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _settings_path() -> Path:
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    else:
        base = Path.home() / ".config"
    return base / APP_DIR_NAME / SETTINGS_FILE_NAME
