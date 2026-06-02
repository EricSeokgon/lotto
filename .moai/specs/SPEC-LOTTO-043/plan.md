# SPEC-LOTTO-043 구현 계획

## 개발 방법론

TDD (RED → GREEN → REFACTOR). 기존 SPEC-LOTTO-042 패턴을 그대로 따른다.

## 마일스톤 (우선순위 순)

### M1 (Priority High) — 데이터 함수

- `lotto/web/data.py`에 `consecutive_pattern(draws=_UNSET, recent_n=None)` 추가.
- 정렬된 본번호 6개에서 연속 런을 탐지하고 런 길이 분포·연속 쌍 빈도·최장 런·
  연속 포함/미포함 회차 수·연속 비율을 단일 패스로 집계.
- `_UNSET` 센티넬 패턴으로 draws 자동 로드, recent_n 윈도 클램핑.
- 테스트: `tests/test_consecutive_pattern.py` (8개) — RED 먼저.

### M2 (Priority High) — API 라우트

- `lotto/web/routes/api.py`에 `GET /api/patterns/consecutive` 추가.
- `recent_n: Optional[int] = Query(default=None, ge=1, le=2000)`.
- `wd.` 동적 디스패치로 데이터 함수 호출, 항상 200.
- 테스트: `tests/test_api_consecutive.py` (4개) — RED 먼저.

### M3 (Priority Medium) — 페이지 + 템플릿 + 네비게이션

- `lotto/web/routes/pages.py`에 `GET /patterns/consecutive` 추가.
- `lotto/web/templates/patterns_consecutive.html` 신규 (base.html 상속).
- `lotto/web/templates/base.html` 네비게이션 3곳 추가
  (desktop_nav_items, active 라벨 블록, mobile nav_items).
- 테스트: `tests/test_consecutive_page.py` (4개) — RED 먼저.

### M4 (Priority Low) — 검증 및 정리

- 전체 테스트 스위트 통과 확인 (1047 → 1063+).
- ruff clean, 신규 코드 mypy clean.
- REFACTOR (필요 시 헬퍼 추출).

## 품질 게이트

- Python 3.9.25 런타임 호환 (Optional[int] from typing, X|Y 런타임 위치 금지).
- 신규 외부 의존성 없음.
- @MX 태그: data 함수에 NOTE + SPEC, API/페이지에 NOTE + SPEC.
