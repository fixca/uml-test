""".umlproj 저장/불러오기와 최근 파일. 담당: 이찬혁 (B7, B8)."""

from dataclasses import dataclass, field


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


def new_project() -> Project:
    raise NotImplementedError


def save(project: Project, path: str) -> None:
    raise NotImplementedError


def load(path: str) -> Project:
    raise NotImplementedError


def last_path() -> str | None:
    raise NotImplementedError


def set_last_path(path: str) -> None:
    raise NotImplementedError
