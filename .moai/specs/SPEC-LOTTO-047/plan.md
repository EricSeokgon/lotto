---
id: SPEC-LOTTO-047
version: 0.1.0
status: Planned
created: 2026-06-02
updated: 2026-06-02
author: ircp
priority: medium
---

# SPEC-LOTTO-047 구현 계획 (Plan)

## 아키텍처

기존 통계 함수(`number_trend`, `weekly_report`, `yearly_prize_comparison`)와
동일한 3계층 패턴을 따른다.

1. **데이터 레이어** (`lotto/web/data.py`)
   - `cycle_analysis(draws=_UNSET) -> dict` 신규 함수 (단일 O(N) 패스)
   - `_cycle_status(appearances, current_gap, avg_cycle) -> str` 헬퍼
   - `_UNSET` 센티넬로 "인자 생략(자동 get_draws)" vs "명시적 None(데이터 없음)" 구분
   - 상수: `_CYCLE_OVERDUE_TOP_N=5`, `_CYCLE_NORMAL_TOLERANCE=0.5`

2. **API 레이어** (`lotto/web/routes/api.py`)
   - `GET /api/numbers/cycle` — 쿼리 파라미터 없음, 항상 200
   - `wd.cycle_analysis(wd.get_draws())` 동적 호출(테스트 patch 호환)
   - 정적 경로이므로 `/numbers/{number}/stats` 동적 라우트와 충돌 없음

3. **페이지 레이어** (`lotto/web/routes/pages.py` + 템플릿)
   - `GET /numbers/cycle` — `/numbers/{number}` 동적 라우트보다 **먼저** 등록
   - `cycle_analysis.html` (base.html 확장), `active_tab="cycle"`
   - 요약 카드 4종 + most_overdue 하이라이트 + 번호별 테이블(색상 코딩 배지)

4. **네비게이션** (`base.html`)
   - 데스크톱 탭 / 모바일 active 라벨 / 모바일 드롭다운 3곳에 "당첨 주기" 추가

## 핵심 알고리즘

- 회차를 `drwNo` 오름차순 정렬 → 시간순 인덱스 부여 (latest = idx N-1)
- 단일 패스로 번호별 출현 횟수 / 마지막 출현 인덱스 / 마지막 회차 번호 집계
- `avg_cycle = round(total_draws / appearances, 2)`
- `current_gap = (N-1) - last_idx_by_num[n]` (미출현은 total_draws)
- 상태 분류: never > normal(±0.5) > overdue(gap>cycle) > frequent
- most_overdue: overdue만 필터 → `(gap - cycle)` 내림차순 정렬 후 상위 5

## TDD 순서 (RED → GREEN → REFACTOR)

1. `tests/test_cycle_analysis.py` (13 tests) RED → `cycle_analysis()` 구현 GREEN
2. `tests/test_api_cycle.py` (4 tests) RED → API 라우트 추가 GREEN
3. `tests/test_cycle_page.py` (4 tests) RED → 페이지+템플릿+네비 추가 GREEN
4. mypy.ini 테스트 오버라이드에 3개 모듈명 추가
5. 전체 스위트 + mypy + ruff 확인

## 품질 게이트

- Python 3.9 호환 (런타임 위치의 typing 사용, zip(strict=) 금지)
- mypy strict = Success (테스트 모듈 mypy.ini 등록)
- ruff clean, 신규 외부 의존성 없음
- 커버리지 85%+ 유지
