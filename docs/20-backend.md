# 1주차 백엔드팀 업무 (11/11 ~ 11/17)

> 상위 문서: [00-common.md](00-common.md) (인터페이스·일정·규칙). 설계 근거: [parser-design.md](../backend/parser-design.md), [class-model.md](../backend/class-model.md)
> 담당: 심현보 (파서·모델), 이찬혁 (저장·내보내기)
> `umlparser`는 표준 라이브러리만 쓰고 PyQt를 import하지 않는다 (`export.py`만 예외). 모든 공개 함수는 pytest 테스트를 함께 올린다.

## 심현보 — 코드 파싱 → 공통 모델
| # | 업무 | 기한 | 우선 | 완료 기준 |
|---|---|---|---|---|
| B1 | 모델 `model.py` | 11/11 | High | class-model.md의 모든 필드를 dataclass로. `to_dict()` 결과가 [class-example.json](../backend/class-example.json)과 같음. `from_dict()` 왕복 테스트. 오늘 중 커밋(프론트가 바로 씀) |
| B2 | 클래스 선언 파싱 `class_parser.py` | 11/13 | High | `class X { ... }`, 제네릭 `~T~`, `<<interface>>`/`<<abstract>>`/`<<enumeration>>`, 속성·메서드(가시성, 타입, 파라미터, `$` static, `*` abstract), enum 값, `%%` 주석. 모든 요소에 `source {line, endLine}` |
| B3 | 관계 파싱 | 11/13 | High | 6종 화살표 양방향 표기, 상속/구현은 from=자식으로 정규화, 다중성 `"1"`, label `: places`, `directed`, `layout_key`(`from->to`, 중복은 `#2`), 선언 없는 클래스는 `implicit=True`로 자동 생성 |
| B4 | 오류 처리 | 11/14 | High | 잘못된 줄은 건너뛰고 `errors`에 `{line, column, message}` 추가, 나머지는 정상 파싱. 예외를 밖으로 던지지 않음. 메시지는 한국어 |
| B5 | 성능 확인 | 11/14 | Medium | 클래스 30개·관계 40개 코드 파싱 10ms 이하 (테스트로 측정) |
| B6 | 편집 헬퍼 `edit.py` | 11/16 | Low (Should) | `class_block()`, `append_class()` (이름 충돌 시 `User2`, `User3`) |

## 이찬혁 — 저장/불러오기, 내보내기
| # | 업무 | 기한 | 우선 | 완료 기준 |
|---|---|---|---|---|
| B7 | `Layout`, `Project`, 저장/불러오기 `storage.py` | 11/13 | High | `.umlproj` = JSON `{version: 1, code, layout: {nodes, edges}, model}`. 불러올 때는 `code`가 원본(모델은 다시 파싱). 없는 키는 기본값, 깨진 JSON·버전 불일치는 `StorageError`. UTF-8 |
| B8 | 새 프로젝트·최근 파일 | 11/13 | High | `new_project()`는 예시 코드(examples/class-example.mmd) 포함. `last_path()/set_last_path()`는 사용자 설정 폴더의 작은 JSON에 저장 (Windows `%APPDATA%`, 그 외 `~/.config`). 파일이 사라졌으면 None |
| B9 | SVG 내보내기 `export.py` | 11/15 | High | `QSvgGenerator` + `scene.render()`. 그림 영역 + 여백 20px만, 흰 배경. 논문용이라 글자가 벡터로 남는지 확인 |
| B10 | PNG/JPEG 내보내기 | 11/16 | Medium | `QImage`에 배율(1x/2x/4x) 적용해 렌더. JPEG는 흰 배경, 품질 95 |
| B11 | 저장 왕복 테스트 | 11/16 | Medium | 저장 → 불러오기 → 같은 code·layout. 한글 클래스 이름 포함 |

## 두 사람이 맞출 것
- `storage.save()`가 함께 저장하는 `model`은 `parse(code).to_dict()` 결과 (심현보 함수 사용)
- 11/14 1차 통합 전까지 `parse()`가 예시 코드를 정상 처리해야 프론트가 붙일 수 있음
