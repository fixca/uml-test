"""storage.py 테스트 (B7, B8, B11)."""

import json
from pathlib import Path

import pytest

from umlparser import storage
from umlparser.storage import Layout, Project, StorageError

KOREAN_CODE = (
    "classDiagram\n"
    "class 사용자 {\n"
    "  +이름: string\n"
    "}\n"
    '사용자 "1" --> "*" 주문 : 주문한다\n'
)


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """최근 파일 설정이 실제 사용자 폴더에 쓰이지 않게 한다.

    홈/APPDATA 를 임시 폴더로 바꾼다.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("APPDATA", str(home / "AppData" / "Roaming"))
    return home


def sample_project() -> Project:
    return Project(
        code=KOREAN_CODE,
        layout=Layout(
            nodes={"사용자": (120.0, 80.0), "주문": (360.5, -40.0)},
            edges={"사용자->주문": "orthogonal"},
        ),
        path=None,
    )


def write_json(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------- B11 저장 왕복


def test_round_trip_keeps_code_and_layout(tmp_path: Path) -> None:
    project = sample_project()
    path = tmp_path / "한글 프로젝트.umlproj"

    storage.save(project, str(path))
    loaded = storage.load(str(path))

    assert loaded.code == project.code
    assert loaded.layout == project.layout
    assert loaded.path == str(path)


def test_round_trip_twice_is_stable(tmp_path: Path) -> None:
    first = tmp_path / "a.umlproj"
    second = tmp_path / "b.umlproj"
    storage.save(sample_project(), str(first))
    storage.save(storage.load(str(first)), str(second))
    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")


# ---------------------------------------------------------------- B7 저장 형식


def test_saved_file_format(tmp_path: Path) -> None:
    path = tmp_path / "p.umlproj"
    storage.save(sample_project(), str(path))

    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert list(data) == ["version", "code", "layout", "model"]
    assert data["version"] == 1
    assert data["layout"] == {
        "nodes": {"사용자": [120.0, 80.0], "주문": [360.5, -40.0]},
        "edges": {"사용자->주문": "orthogonal"},
    }
    assert "사용자" in raw  # UTF-8 그대로 저장 (\uXXXX 이스케이프 없음)
    assert data["model"] is None or data["model"]["type"] == "class"


def test_save_stores_parsed_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeDiagram:
        def to_dict(self) -> dict[str, object]:
            return {
                "version": 1,
                "type": "class",
                "classes": [],
                "relations": [],
                "errors": [],
            }

    monkeypatch.setattr(storage, "parse", lambda code: FakeDiagram())
    path = tmp_path / "p.umlproj"
    storage.save(sample_project(), str(path))

    assert json.loads(path.read_text(encoding="utf-8"))["model"]["type"] == "class"


def test_save_updates_project_path(tmp_path: Path) -> None:
    project = sample_project()
    path = tmp_path / "p.umlproj"
    storage.save(project, str(path))
    assert project.path == str(path)


def test_save_overwrites_without_leftover_temp_files(tmp_path: Path) -> None:
    folder = tmp_path / "out"
    folder.mkdir()
    path = folder / "p.umlproj"
    storage.save(sample_project(), str(path))
    project = sample_project()
    project.code = "classDiagram\nA --> B\n"
    storage.save(project, str(path))

    assert storage.load(str(path)).code == "classDiagram\nA --> B\n"
    assert [p.name for p in folder.iterdir()] == ["p.umlproj"]


def test_save_to_missing_folder_raises(tmp_path: Path) -> None:
    with pytest.raises(StorageError):
        storage.save(sample_project(), str(tmp_path / "없는 폴더" / "p.umlproj"))


# ---------------------------------------------------------------- B7 불러오기


def test_missing_keys_use_defaults(tmp_path: Path) -> None:
    loaded = storage.load(str(write_json(tmp_path / "p.umlproj", {})))
    assert loaded.code == ""
    assert loaded.layout == Layout()

    loaded = storage.load(
        str(write_json(tmp_path / "q.umlproj", {"code": "classDiagram", "layout": {}}))
    )
    assert loaded.code == "classDiagram"
    assert loaded.layout == Layout()


def test_model_is_ignored_on_load(tmp_path: Path) -> None:
    data = {"version": 1, "code": "classDiagram\n", "model": {"broken": True}}
    assert (
        storage.load(str(write_json(tmp_path / "p.umlproj", data))).code
        == "classDiagram\n"
    )


def test_utf8_bom_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "p.umlproj"
    path.write_text('{"version": 1, "code": "classDiagram"}', encoding="utf-8-sig")
    assert storage.load(str(path)).code == "classDiagram"


@pytest.mark.parametrize(
    "content",
    [
        "{ 깨진 json",
        "[1, 2, 3]",
        '{"version": 2, "code": ""}',
        '{"version": "1"}',
        '{"code": 123}',
        '{"layout": []}',
        '{"layout": {"nodes": {"A": [1]}}}',
        '{"layout": {"nodes": {"A": ["x", 2]}}}',
        '{"layout": {"nodes": {"A": [true, 2]}}}',
        '{"layout": {"nodes": []}}',
        '{"layout": {"edges": {"A->B": "curved"}}}',
    ],
)
def test_broken_files_raise_storage_error(tmp_path: Path, content: str) -> None:
    path = tmp_path / "p.umlproj"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(StorageError):
        storage.load(str(path))


def test_missing_file_raises_storage_error(tmp_path: Path) -> None:
    with pytest.raises(StorageError):
        storage.load(str(tmp_path / "없음.umlproj"))


def test_non_utf8_file_raises_storage_error(tmp_path: Path) -> None:
    path = tmp_path / "p.umlproj"
    path.write_bytes('{"code": "사용자"}'.encode("cp949"))
    with pytest.raises(StorageError):
        storage.load(str(path))


# -------------------------------------------- B8 새 프로젝트·최근 파일


def test_new_project_contains_example_code() -> None:
    project = storage.new_project()
    example = storage.EXAMPLE_PATH.read_text(encoding="utf-8")
    assert project.code == example
    assert project.code.startswith("classDiagram")
    assert project.layout == Layout()
    assert project.path is None


def test_last_path_is_none_without_settings() -> None:
    assert storage.last_path() is None


def test_set_and_get_last_path(tmp_path: Path) -> None:
    path = tmp_path / "최근.umlproj"
    storage.save(sample_project(), str(path))
    storage.set_last_path(str(path))
    assert storage.last_path() == str(path.resolve())


def test_last_path_is_none_when_file_removed(tmp_path: Path) -> None:
    path = tmp_path / "p.umlproj"
    storage.save(sample_project(), str(path))
    storage.set_last_path(str(path))
    path.unlink()
    assert storage.last_path() is None


def test_last_path_is_none_when_settings_broken(isolated_settings: Path) -> None:
    storage.set_last_path(str(isolated_settings))
    settings = next(isolated_settings.rglob("settings.json"))
    settings.write_text("{ 깨짐", encoding="utf-8")
    assert storage.last_path() is None

    storage.set_last_path(str(isolated_settings / "x"))  # 깨진 설정 위에 다시 써도 동작
    assert json.loads(settings.read_text(encoding="utf-8"))["lastPath"].endswith("x")


def test_settings_live_in_user_config_folder(
    isolated_settings: Path, tmp_path: Path
) -> None:
    storage.set_last_path(str(tmp_path / "p.umlproj"))
    settings = list(isolated_settings.rglob("settings.json"))
    assert len(settings) == 1
    assert settings[0].parent.name == "uml-tool"
