# 1주차 개발 공통사항 (11/11 ~ 11/17)

> 상위 문서. 프론트엔드·백엔드 팀 문서([10-frontend.md](10-frontend.md), [20-backend.md](20-backend.md))는 이 문서의 약속을 따른다.
> 근거: [requirements.md](../planning/requirements.md), [class-model.md](../backend/class-model.md), [gui-design.md](../frontend/gui-design.md), 노션 회의록 9/30·10/14·11/11.

## 1. 목표
**11/17(화)까지 클래스 다이어그램 프로토타입이 실제로 동작**하고, 다음 회의에서 시연한다 (11/11 회의: "구현 → 프로토타입 제작", 발표 20분).

시연 시나리오 (이것이 완료 기준):
1. 앱 실행 → 예시 코드와 다이어그램이 보인다
2. 왼쪽 코드에 클래스·관계를 추가하면 오른쪽 그림이 바로 바뀐다. 문법 오류는 줄 번호와 함께 표시된다
3. 오른쪽에서 클래스를 드래그해 옮기고, 관계선을 클릭해 꺾은 선으로 바꾼다
4. 클래스를 더블 클릭하면 왼쪽 코드의 해당 줄로 이동한다
5. Ctrl+S로 `.umlproj` 저장 → 앱 재시작 → 위치까지 그대로 복원된다
6. SVG로 내보내고(우선), PNG/JPEG도 내보낸다

### 범위
| 이번 주 (Must) | 시간 남으면 (Should) | 이번 주 제외 |
|---|---|---|
| 클래스 다이어그램 코드 → 그림, 오류 표시 | undo/redo (Ctrl+Z/Y) | 시퀀스 다이어그램 |
| 드래그 이동, 꺾은 선 전환, 더블 클릭 이동 | 캔버스 복사/붙여넣기 (Ctrl+C/V) | 인스턴스 박스, 패키지 |
| 저장/불러오기, 마지막 파일 복원, 종료 경고 | 확대/축소 | PDF 내보내기 |
| SVG 내보내기 (+ PNG/JPEG) | | |

## 2. 역할 (9/30, 10/14 회의 기준)
| 팀 | 담당 | 맡은 영역 |
|---|---|---|
| 총괄 | 김재훈 | 일정·구조 관리, 인터페이스 변경 승인, PR 최종 확인 |
| 프론트엔드 | 이도훈 | 다이어그램 그림 요소와 생성 팩토리 (클래스 박스, 관계선, 자동 배치) |
| 프론트엔드 | 강승현 | 전체 화면 구성, 코드 편집기, 모델 → 그림 연결(컨트롤러), 이벤트 바인딩 |
| 백엔드 | 심현보 | 코드 파싱 → 공통 모델, 코드 편집 헬퍼 |
| 백엔드 | 이찬혁 | `.umlproj` 저장/불러오기, 최근 파일, SVG/PNG/JPEG 내보내기 |

## 3. 구조 (MVC, 10/14 회의)
```
코드 편집기 ──(텍스트)──▶ 컨트롤러 ──parse()──▶ 모델(ClassDiagram)
                            │                         │
                            └──factory.build(모델, layout)──▶ 캔버스 그림
캔버스 조작(이동·꺾은 선) ──시그널──▶ 컨트롤러 ──▶ layout 수정 → 다시 그림
```
- **Model** = `umlparser` 패키지 (백엔드). PyQt를 import하지 않는다. 단, `export.py`만 예외로 Qt 장면을 받는다.
- **View** = `gui/items`, `gui/factory.py` (이도훈)
- **Controller** = `gui/controller.py`, `gui/main_window.py` (강승현)
- 코드가 원본. 위치·선 모양은 `layout`에만 저장. 화면은 항상 `코드 → parse → 모델 → factory` 한 방향으로 다시 그린다.

## 4. 저장소 구조와 파일 담당
```
uml-tool/
  main.py                      # 진입점 (강승현)
  umlparser/                   # 백엔드
    __init__.py                # parse() 공개
    model.py                   # dataclass + to_dict/from_dict (심현보)
    class_parser.py            # 클래스 다이어그램 파서 (심현보)
    edit.py                    # 코드 편집 헬퍼 (심현보)
    storage.py                 # .umlproj 저장/불러오기, 최근 파일 (이찬혁)
    export.py                  # SVG/PNG/JPEG (이찬혁)
  gui/                         # 프론트엔드
    main_window.py             # 메뉴, 단축키, 분할 화면, 상태줄 (강승현)
    code_editor.py             # 줄 번호, 오류 표시, 줄 이동 (강승현)
    controller.py              # 파싱 디바운스, 다시 그리기, layout 갱신 (강승현)
    factory.py                 # 모델 → 그림 요소 생성 (이도훈)
    auto_layout.py             # 위치 없는 클래스 자동 배치 (이도훈)
    items/class_item.py        # 클래스 박스 (이도훈)
    items/relation_item.py     # 관계선, 화살표 머리, 다중성 라벨 (이도훈)
  tests/                       # pytest (백엔드 필수, 프론트는 선택)
  examples/class-example.mmd
```
- Python 3.11 이상, 외부 패키지는 **PyQt6만** 사용 (Graphviz 등 추가 금지. 필요하면 총괄 승인)
- 파서는 표준 라이브러리만 사용

## 5. 팀 사이 약속 (인터페이스) — 11/11 확정, 바꾸려면 총괄 승인
### 5.1 모델
[class-model.md](../backend/class-model.md)의 JSON과 같은 모양의 dataclass. 프론트는 이것만 보고 그린다.
```python
@dataclass
class ClassDiagram:
    version: int; type: str            # "class"
    classes: list[ClassNode]           # id, name, kind, generics, attributes, methods, values, implicit, source
    relations: list[Relation]          # id, from_, to, kind, directed, from_multiplicity, to_multiplicity, label, layout_key, source
    errors: list[ParseError]           # line, column, message
```
Python 이름은 snake_case(`from_`, `layout_key`), JSON은 class-model.md 이름(`from`, `layoutKey`). 변환은 `to_dict()/from_dict()`.

### 5.2 백엔드가 제공하는 함수
```python
umlparser.parse(code: str) -> ClassDiagram           # 오류가 있어도 예외 없이 부분 모델 + errors
umlparser.edit.class_block(code, class_id) -> str     # 클래스 정의 코드 블록 (복사용, Should)
umlparser.edit.append_class(code, block, new_id) -> str  # 이름 바꿔 코드 끝에 추가 (붙여넣기용, Should)

@dataclass
class Layout:
    nodes: dict[str, tuple[float, float]]             # class_id -> 박스 왼쪽 위 좌표
    edges: dict[str, str]                             # layout_key -> "straight" | "orthogonal"
@dataclass
class Project:
    code: str; layout: Layout; path: str | None
umlparser.storage.new_project() -> Project            # 예시 코드가 든 새 프로젝트
umlparser.storage.save(project, path) -> None         # .umlproj JSON {version, code, layout, model}
umlparser.storage.load(path) -> Project               # 깨진 파일이면 StorageError
umlparser.storage.last_path() -> str | None           # 마지막으로 열거나 저장한 파일
umlparser.storage.set_last_path(path) -> None
umlparser.export.export_scene(scene, path, fmt, scale=1.0) -> None   # fmt: "svg" | "png" | "jpeg"
```

### 5.3 프론트엔드 내부 약속 (이도훈 ↔ 강승현)
```python
factory.build(scene, diagram: ClassDiagram, layout: Layout) -> None   # 장면을 비우고 다시 그림. 위치 없는 클래스는 auto_layout
# 그림 요소가 보내는 시그널 (factory가 하나의 DiagramSignals 객체로 모아 줌)
moved(class_id: str, x: float, y: float)       # 드래그를 놓았을 때
double_clicked(class_id: str)
edge_toggled(layout_key: str)                  # 관계선 클릭
```

## 6. 일정
| 날짜 | 공통 | 마감 산출물 |
|---|---|---|
| 11/11 (수) | 저장소 뼈대, 인터페이스 확정, 빈 함수(stub) 커밋 | 각자 파일이 import 되는 상태 |
| 11/12 (목) ~ 11/13 (금) | 팀별 단독 개발. 프론트는 `class-example.json`으로, 백엔드는 테스트로 확인 | 파서·그림 요소 1차 |
| 11/14 (토) | **1차 통합**: 코드 → 파싱 → 그림이 한 화면에서 동작 | 시연 1·2번 |
| 11/15 (일) ~ 11/16 (월) | 상호작용·저장·내보내기 | 시연 3~6번 |
| 11/17 (화) | 버그 수정, 시연 리허설, 문서 정리 | 시연 시나리오 전부 통과, 발표 자료 |

## 7. 작업 규칙
- 코드 작성·빌드·커밋·변경 기록 규칙은 저장소 루트의 [AGENTS.md](../AGENTS.md)를 따른다 (사람과 에이전트 공통)
- GitHub: `main`은 항상 실행되는 상태. 작업은 `fe/<이름>-<기능>`, `be/<이름>-<기능>` 브랜치(영문, 예: `fe/dohoon-class-item`) → PR → 다른 팀원 1명 확인 후 병합
- 인터페이스(5장)를 바꾸는 PR은 총괄 확인 필수, 이 문서도 같이 고친다
- 매일 밤 노션 팀 보드의 내 업무 상태(Not started / In progress / Done) 갱신, 막힌 점은 해당 업무 페이지 댓글로
- 문법은 Mermaid classDiagram을 따른다 ([parser-design.md](../backend/parser-design.md) 2장)
- 완료 기준: 해당 기능이 `main`에서 시연 시나리오대로 동작 + (백엔드) 테스트 통과
