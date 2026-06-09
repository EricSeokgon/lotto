---
id: SPEC-LOTTO-054
version: 0.1.0
status: Planned
created: 2026-06-09
updated: 2026-06-09
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-054: 롤링 윈도우 빈도 분석 (Rolling Window Frequency Analysis)

## HISTORY

- 2026-06-09 (v0.1.0): 최초 작성 (Planned). 최근 N회차(롤링 윈도우)별 번호 빈도를
  여러 윈도우에 대해 동시에 비교하고, 전체 이력 대비 추세 변화(trend delta)를
  산출하는 읽기 전용 분석 기능으로 정의. SPEC-LOTTO-042(번호 추세 추적기)가
  장기 추세를 다루는 반면, 본 SPEC은 서로 다른 최근 윈도우(예: 최근 10/20/50/100
  회차) 간의 빈도 비교에 초점을 둔다.

## 개요

여러 윈도우 크기 W ∈ {10, 20, 50, 100}에 대해, 최근 W회차 내에서 각 번호(1~45)의
출현 빈도를 계산하고, 이를 전체 이력 대비 정규화한 추세 델타(trend delta)로 비교한다.
각 번호를 추세 델타에 따라 "상승"/"하락"/"보합"으로 분류하고, 윈도우별 "최고 상승"
상위 5개와 "최고 하락" 상위 5개를 산출한다. 이를 통해 사용자는 "특정 번호가 최근에
뜨고 있는가(상승), 식고 있는가(하락)"라는 윈도우별 추세를 한눈에 비교할 수 있다.

본 기능은 **읽기 전용 분석 기능**이다. 추천/분석 코어 로직을 변경하지 않고, 기존
데이터 접근 레이어(`lotto/web/data.py`)에 신규 함수를 추가하여 윈도우별 빈도/델타/
추세 분류/상승·하락 목록을 산출한다. 결과는 메모리에 캐시하며 DB나 파일에
영속화하지 않는다.

## 배경

- `lotto/analyzer.py`의 `Statistics`로 과거 추첨 데이터에 접근할 수 있고,
  `DrawResult.numbers()`로 회차별 정렬된 본번호 6개(보너스 제외)를 얻는다.
- `lotto/web/data.py`는 `_draws_cache`, `_backtest_cache`, `_cooccurrence_cache`
  등 모듈 레벨 캐시 패턴과 `invalidate_cache()` 무효화 규칙을 이미 갖추고 있다.
- SPEC-LOTTO-038(`/stats`)은 전체 통계 대시보드를 제공하지만 **전체 이력 기준**
  단일 빈도만 보여준다.
- SPEC-LOTTO-042(`/numbers/trend`)는 번호 추세를 추적하지만 장기 추세에 초점을
  두며, 여러 최근 윈도우를 나란히 비교하지 않는다.
- SPEC-LOTTO-052(`/backtest`)는 전략 적중 성능을 평가할 뿐, 번호 빈도 자체의
  윈도우별 변화를 다루지 않는다.
- 현재 모든 빈도/통계 페이지가 **전체 추첨 이력**을 사용한다. 서로 다른 최근
  윈도우(예: 최근 10회 vs 30회 vs 100회) 간 번호 빈도가 어떻게 달라지는지 비교할
  방법이 없다.

본 SPEC은 이 공백을 메워, 여러 롤링 윈도우의 번호 빈도와 추세 델타를 표로 동시에
비교 제공한다.

## 용어

- **윈도우(window) W**: 최근 W회차의 집합. 본 SPEC의 기본 윈도우는 {10, 20, 50, 100}.
- **윈도우 빈도(window frequency)**: 최근 W회차 내에서 어떤 번호가 출현한 회차 수.
- **전체 빈도(total frequency)**: 전체 추첨 이력에서 어떤 번호가 출현한 회차 수.
- **추세 델타(trend delta)**: 회차당 정규화된 빈도 차이 =
  `freq_in_window / W - freq_total / total_draws`. 양수면 최근에 더 자주, 음수면 덜
  자주 나왔음을 의미한다.
- **추세 분류(trend classification)**: 델타에 따른 분류.
  - 델타 > +0.02 → "상승" (trending up)
  - 델타 < -0.02 → "하락" (trending down)
  - 그 외 (-0.02 ≤ 델타 ≤ +0.02) → "보합" (neutral)
- **최고 상승(rising)**: 윈도우별 델타 내림차순 상위 5개 번호.
- **최고 하락(falling)**: 윈도우별 델타 오름차순 하위 5개 번호(가장 많이 하락한 5개).
- **RollingResult**: 한 윈도우에 대한 결과 구조
  `{"window": int, "freq": dict[int,int], "delta": dict[int,float],
  "trend": dict[int,str], "rising": list[int], "falling": list[int]}`.

## 요구사항 (EARS)

### Ubiquitous Requirements

- REQ-RW-001: The system SHALL provide
  `get_rolling_frequency(draws: list[DrawResult], windows: tuple[int, ...] = (10, 20, 50, 100)) -> dict[int, RollingResult]`
  in `lotto/web/data.py`, returning a mapping from each applicable window size `W`
  to its `RollingResult`.
- REQ-RW-002: For each window `W`, window frequency SHALL be computed over the most
  recent `W` draws only, counting, for each number 1~45, the number of those `W`
  draws whose 6 main winning numbers include that number.
- REQ-RW-003: Frequency counting SHALL use only the 6 main winning numbers of each
  draw (`DrawResult.numbers()`); the bonus number SHALL NOT contribute to any
  frequency, delta, or trend value.
- REQ-RW-004: The trend delta for number `n` in window `W` SHALL be computed as
  `freq_in_window[n] / W - freq_total[n] / total_draws`, where `freq_total` is the
  per-number frequency over the full draw history and `total_draws` is the total
  number of draws.
- REQ-RW-005: Each number SHALL be classified into a trend string per window:
  `"상승"` when delta > +0.02, `"하락"` when delta < -0.02, and `"보합"` otherwise.
  The thresholds +0.02 / -0.02 SHALL be hardcoded and SHALL NOT be configurable.
- REQ-RW-006: For each window, `rising` SHALL be the top 5 numbers by delta
  (descending) and `falling` SHALL be the bottom 5 numbers by delta (ascending,
  i.e. the 5 most-negative deltas); ties SHALL break by number ascending for
  deterministic ordering.
- REQ-RW-007: The `freq`, `delta`, and `trend` maps in each `RollingResult` SHALL
  cover all numbers 1~45 (a number absent from the window has `freq` 0 and a
  negative-or-zero delta), so consumers can render a complete 45-row table.

### Event-driven Requirements

- REQ-RW-008: WHEN `GET /stats/rolling` loads without a `w` query parameter, the
  system SHALL render a page showing all applicable default windows
  (10, 20, 50, 100) side by side (or stacked) in a table comparing per-number
  frequency, delta, and trend.
- REQ-RW-009: WHEN `GET /stats/rolling?w=W` is requested with a single window size
  `W` that is one of the supported windows, the system SHALL render a focused page
  for only that window.
- REQ-RW-010: WHEN `GET /api/stats/rolling?windows=10,20,50,100` is called, the
  system SHALL return a JSON object containing a `RollingResult` for each requested
  window that is applicable.
- REQ-RW-011: WHEN `GET /api/stats/rolling` is called without a `windows`
  parameter, the system SHALL use the default windows (10, 20, 50, 100).

### State-driven Requirements

- REQ-RW-012: WHILE the total number of available draws is fewer than a given window
  size `W`, that window SHALL be skipped (omitted from results) rather than raising
  an error.
- REQ-RW-013: WHILE draw data is unavailable (no draws or empty list), the system
  SHALL return an empty result mapping without error — all windows are skipped, and
  the page renders an explanatory empty state with HTTP 200.
- REQ-RW-014: WHILE a `w` query parameter selecting a single window is present, the
  page SHALL show only that window's view; otherwise it SHALL show all default
  windows.
- REQ-RW-015: WHILE rolling results are cached in memory, invalidating the cache
  (via the existing `invalidate_cache`) SHALL cause the next request to recompute.

### Unwanted Behavior Requirements

- REQ-RW-016: The system SHALL NOT include the bonus number in any frequency, delta,
  or trend computation. (See REQ-RW-003.)
- REQ-RW-017: The trend thresholds SHALL NOT be exposed as configuration; the
  +0.02 / -0.02 boundaries are fixed constants. (See REQ-RW-005.)
- REQ-RW-018: The system SHALL NOT persist rolling results to the database or any
  on-disk store; results live only in the in-memory cache and are recomputed on
  demand.
- REQ-RW-019: The system SHALL NOT add any new recommendation strategy; it provides
  only frequency/trend analysis data, not recommended number sets.
- REQ-RW-020: The system SHALL NOT introduce any new client-side JavaScript
  dependency; the page is rendered server-side as static tables.
- REQ-RW-021: The system SHALL NOT raise an error for a window larger than the
  available draw count; such windows are silently skipped. (See REQ-RW-012.)

### Optional Requirements

- REQ-RW-022: WHERE feasible, the system SHALL compute the full-history per-number
  frequency once and reuse it across all requested windows, rather than recomputing
  the total frequency per window.
- REQ-RW-023: WHERE the rolling results can be memoized, the system SHALL cache them
  at module level keyed by the requested windows tuple (like existing
  `lotto/web/data.py` caches) so repeated requests with the same windows reuse the
  computed results.

## 성능 요구사항

- REQ-RW-024: Computing rolling frequency for the default windows over the full draw
  history SHALL complete in under 5 seconds on the reference environment.

## 인수 기준

acceptance.md 참조.

## 범위 밖 (Out of Scope) / Exclusions

본 SPEC 범위에서 **명시적으로 제외**되는 항목 (구현 금지):

1. **보너스 번호 집계 금지** — 보너스 번호를 빈도/델타/추세 계산에 포함하지 않는다.
   본번호 6개(1~45)만 사용한다. (REQ-RW-003, REQ-RW-016)
2. **임계값 설정화 금지** — 추세 분류 임계값 +0.02 / -0.02는 하드코딩 상수이며,
   설정 파일이나 쿼리 파라미터로 노출하지 않는다. (REQ-RW-005, REQ-RW-017)
3. **DB/파일 영속화 금지** — 롤링 결과를 데이터베이스나 파일에 저장하지 않는다.
   메모리 캐시만 사용하며 요청 시 재계산한다. (REQ-RW-018)
4. **신규 추천 전략 추가 금지** — 새로운 추천 전략을 만들지 않는다. 본 SPEC은 빈도/
   추세 분석 데이터만 제공하며 추천 조합(recommended set)을 생성하지 않는다.
   (REQ-RW-019)
5. **JavaScript 의존성 추가 금지** — 클라이언트 스크립트 기반 인터랙티브 시각화를
   추가하지 않는다. 서버사이드 렌더링 표로 처리하며 신규 클라이언트 스크립트
   의존성을 추가하지 않는다. (REQ-RW-020)
6. **추천/분석 코어 로직 변경 금지** — `recommender.py`와 `analyzer.py`의 기존
   로직을 수정하지 않는다. `lotto/web/data.py`에 신규 함수만 추가한다.
7. **부족 윈도우 에러화 금지** — 가용 회차보다 큰 윈도우는 조용히 건너뛴다(에러를
   발생시키지 않는다). (REQ-RW-012, REQ-RW-021)
8. **예측 보장/투자 권유 금지** — 롤링 추세는 과거 통계일 뿐 미래 출현을 보장하지
   않는다. UI는 이 한계를 명시한다(예측 보장 문구 금지).
