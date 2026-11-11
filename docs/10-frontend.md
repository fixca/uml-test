# 1주차 프론트엔드팀 업무 (11/11 ~ 11/17)

> 상위 문서: [00-common.md](00-common.md) (인터페이스·일정·규칙). 설계 근거: [gui-design.md](../frontend/gui-design.md)
> 담당: 이도훈 (그림 요소·팩토리), 강승현 (화면 구성·컨트롤러·이벤트)

## 이도훈 — 다이어그램 그림 요소와 팩토리
| # | 업무 | 기한 | 우선 | 완료 기준 |
|---|---|---|---|---|
| F1 | 클래스 박스 `items/class_item.py` | 11/13 | High | 이름 칸 / 속성 칸 / 메서드 칸 3단. 가시성 기호, `<<interface>>` 등 스테레오타입, static 밑줄, abstract 기울임. enum은 값 목록 |
| F2 | 관계선 `items/relation_item.py` | 11/13 | High | 6종 UML 표기: 상속(빈 삼각형 실선), 구현(빈 삼각형 점선), 연관(실선, directed면 열린 화살표), 집합(빈 마름모), 합성(채운 마름모), 의존(점선 열린 화살표). 양 끝 다중성, 가운데 label. 직선/직각 꺾은 선 두 모드 |
| F3 | 팩토리 `factory.py` + 자동 배치 `auto_layout.py` | 11/14 | High | `build(scene, diagram, layout)`로 장면 재구성. layout에 없는 클래스는 상속 관계 기준 층으로 나눠 격자 배치(외부 라이브러리 없이). 30개에서 끊김 없음 |
| F4 | 상호작용 | 11/15 | High | 클릭 선택 테두리, 드래그 이동 시 연결선 따라감, 놓을 때 `moved` 시그널. 관계선 클릭 → `edge_toggled`. 더블 클릭 → `double_clicked` |
| F5 | 오류 상태 표시 | 11/16 | Medium | 파싱 오류가 있을 때도 마지막 정상 그림 위에 그려지도록 factory가 빈 모델·부분 모델을 안전하게 처리 |

시작 방법: 백엔드 파서가 나오기 전까지 [class-example.json](../backend/class-example.json)을 `ClassDiagram.from_dict()`(stub이면 직접 dict)로 읽어 그린다.

## 강승현 — 화면 구성, 컨트롤러, 이벤트
| # | 업무 | 기한 | 우선 | 완료 기준 |
|---|---|---|---|---|
| F6 | 메인 창 `main_window.py`, `main.py` | 11/12 | High | 왼쪽 코드 / 오른쪽 캔버스(QGraphicsView) 분할, 경계 드래그 조절. 메뉴: 새로 만들기·열기·저장·다른 이름으로 저장·내보내기. 상태줄. 제목에 파일 이름과 미저장 표시(●) |
| F7 | 코드 편집기 `code_editor.py` | 11/13 | High | 줄 번호, 오류 줄 빨간 표시, `goto_line(n)` |
| F8 | 컨트롤러 `controller.py` | 11/14 | High | 입력 200ms 디바운스 → `parse()` → `factory.build()`. 오류는 상태줄 "N번째 줄: 메시지". `moved`/`edge_toggled` 받으면 layout 갱신 후 다시 그림. `double_clicked` → 편집기 해당 줄로 |
| F9 | 파일 흐름 (U1~U7) | 11/16 | High | 시작 시 `last_path()` 열기, 없으면 `new_project()`. Ctrl+S: 경로 있으면 덮어쓰기, 없으면 저장 대화상자. 미저장 상태로 종료·열기·새로 만들기 → "저장 / 저장 안 함 / 취소" |
| F10 | 내보내기 대화상자 (U8) | 11/16 | High | 형식 선택(SVG 기본, PNG, JPEG) + 배율(1x/2x/4x, 비트맵만) → 경로 선택 → `export_scene()`. 선택 테두리는 숨기고 내보냄 |
| F11 | undo/redo | 11/17 | Medium (Should) | `{code, layout}` 스냅샷 이력 하나. Ctrl+Z / Ctrl+Y(Ctrl+Shift+Z). 타이핑과 드래그가 같은 이력 |
| F12 | 캔버스 복사/붙여넣기 | 11/17 | Low (Should) | 선택 클래스 Ctrl+C → `class_block()`, Ctrl+V → `append_class()`로 `User2`처럼 추가, 원래 위치 옆에 배치 |

## 두 사람이 맞출 것
- 시그널 이름·인자는 [00-common.md](00-common.md) 5.3 그대로. 바꾸면 두 사람 모두 확인
- 11/14 1차 통합 때 강승현 컨트롤러 + 이도훈 팩토리를 합쳐 시연 1·2번 확인
