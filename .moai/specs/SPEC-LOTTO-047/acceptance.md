---
id: SPEC-LOTTO-047
version: 0.1.0
status: Planned
created: 2026-06-02
updated: 2026-06-02
author: ircp
priority: medium
---

# SPEC-LOTTO-047 인수 기준 (Acceptance Criteria)

## 데이터 레이어 — `cycle_analysis()` (tests/test_cycle_analysis.py)

- **AC-1**: `numbers`는 정확히 45개이며 번호 1~45 오름차순. 각 항목은
  `{number, appearances, avg_cycle, last_appeared_drwNo, current_gap, status}`.
  (REQ-CYCLE-001, REQ-CYCLE-002)
- **AC-2**: `appearances`와 `avg_cycle = round(total_draws/appearances, 2)`가
  알려진 픽스처에서 정확하다. (REQ-CYCLE-003)
- **AC-3**: `current_gap`이 마지막 출현 이후 경과 회차와 일치하며, 최신 회차
  출현 시 0이다. (REQ-CYCLE-004)
- **AC-4**: status 분류 — overdue/frequent/normal이 알려진 케이스에서 정확하다.
  current_gap == avg_cycle인 번호는 normal이다. (REQ-CYCLE-005)
- **AC-5**: 미출현 번호는 status `never`, appearances 0, last None,
  current_gap == total_draws. (REQ-CYCLE-005, REQ-CYCLE-004)
- **AC-6**: `most_overdue`는 overdue 번호만, `(current_gap - avg_cycle)`
  내림차순 상위 5개. (REQ-CYCLE-006)
- **AC-7**: `summary` 4개 상태 카운트 합계 == 45이며 numbers의 status 분포와
  일치한다. (REQ-CYCLE-007)
- **AC-8**: 빈 리스트 → total_draws 0, 45개 모두 never, most_overdue=[],
  summary never=45, 예외 없음. (REQ-CYCLE-008)
- **AC-9**: 명시적 None → 빈 구조. (REQ-CYCLE-008)
- **AC-10**: 동일 입력 2회 호출 시 결과 동일. 인자 생략 시 get_draws() 호출.
  (REQ-CYCLE-009)

## API 레이어 — `GET /api/numbers/cycle` (tests/test_api_cycle.py)

- **AC-11**: 데이터 있으면 200 + 최상위 키 4종. (REQ-CYCLE-010)
- **AC-12**: `numbers` 45개, 번호 오름차순. (REQ-CYCLE-002)
- **AC-13**: get_draws None → 200 + 전부 never 구조. (REQ-CYCLE-008, 010)
- **AC-14**: 응답 Content-Type이 application/json. (REQ-CYCLE-010)

## 페이지 레이어 — `GET /numbers/cycle` (tests/test_cycle_page.py)

- **AC-15**: 200 HTML, "당첨 주기" 제목 + "평균 주기"/"현재 간격" 헤더 노출.
  (REQ-CYCLE-011, REQ-CYCLE-012)
- **AC-16**: 상태 마커("미출현" 등) 노출. (REQ-CYCLE-011)
- **AC-17**: get_draws None → 200 + "데이터가 없습니다" 빈 상태. (REQ-CYCLE-011)
- **AC-18**: 인덱스 페이지에 `href="/numbers/cycle"` 네비 링크 노출.
  (REQ-CYCLE-013)

## 품질 게이트

- 전체 테스트 1126 passed (1105 → 1126, +21)
- mypy strict = Success (0 errors)
- ruff clean, 신규 외부 의존성 없음
- 커버리지 96%+ 유지

## 검증 결과 (2026-06-02)

- [x] test_cycle_analysis.py — 13 passed
- [x] test_api_cycle.py — 4 passed
- [x] test_cycle_page.py — 4 passed
- [x] 전체 스위트 — 1126 passed, coverage 96.37%
- [x] mypy . — Success: no issues found in 115 source files
- [x] ruff — All checks passed
