---
id: SPEC-LOTTO-055
version: 0.1.0
status: Planned
created: 2026-06-09
updated: 2026-06-09
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-055: 끝자리 분포 분석 (Last Digit Distribution Analysis)

## HISTORY

- 2026-06-09 (v0.1.0): 최초 작성 (Planned). 당첨 번호의 끝자리(1의 자리, 0~9)별
  출현 분포를 분석하는 읽기 전용 기능으로 정의. 각 끝자리 d ∈ {0,…,9}에 대해
  해당 끝자리를 갖는 번호들의 총 출현 횟수, 비율, 균등 기대치 대비 편차(deviation)를
  산출한다. SPEC-LOTTO-049(합계 범위 분석)가 6개 본번호 합의 분포를 다루는 반면,
  본 SPEC은 개별 번호의 끝자리 분포에 초점을 둔다.

## 개요

각 끝자리(units digit) d ∈ {0, 1, …, 9}에 대해, 끝자리가 d인 번호들이 당첨
본번호로 얼마나 자주 출현했는지를 분석한다. 끝자리별 번호 그룹은 다음과 같다.

- 0: 10, 20, 30, 40 (4개)
- 1: 1, 11, 21, 31, 41 (5개)
- 2: 2, 12, 22, 32, 42 (5개)
- 3: 3, 13, 23, 33, 43 (5개)
- 4: 4, 14, 24, 34, 44 (5개)
- 5: 5, 15, 25, 35, 45 (5개)
- 6: 6, 16, 26, 36 (4개)
- 7: 7, 17, 27, 37 (4개)
- 8: 8, 18, 28, 38 (4개)
- 9: 9, 19, 29, 39 (4개)

각 끝자리에 대해 (1) 전체 추첨에서의 총 출현 횟수, (2) 전체 번호 슬롯 대비 비율,
(3) 균등 분포 가정 시 기대 출현 횟수, (4) 기대치 대비 편차(과대표/과소표 여부)를
산출한다. 이를 통해 사용자는 "끝자리가 3이나 7인 번호가 더 자주 나오는가"와 같은
끝자리 분포의 균등성/편향을 한눈에 확인할 수 있다.

본 기능은 **읽기 전용 분석 기능**이다. 추천/분석 코어 로직을 변경하지 않고, 기존
데이터 접근 레이어(`lotto/web/data.py`)에 신규 함수를 추가하여 끝자리별 통계를
산출한다. 결과는 메모리에 캐시하며 DB나 파일에 영속화하지 않는다.

## 배경

- `lotto/analyzer.py`의 `Statistics`로 과거 추첨 데이터에 접근할 수 있고,
  `DrawResult.numbers()`로 회차별 정렬된 본번호 6개(보너스 제외)를 얻는다.
- `lotto/web/data.py`는 `_draws_cache`, `_backtest_cache`, `_cooccurrence_cache`
  등 모듈 레벨 캐시 패턴과 `invalidate_cache()` 무효화 규칙을 이미 갖추고 있다.
- SPEC-LOTTO-038(`/stats`)은 전체 통계 대시보드를 제공하지만 끝자리별 분포를
  보여주지 않는다.
- SPEC-LOTTO-049(합계 범위 분석)는 6개 본번호의 **합계** 분포를 다루지만, 개별
  번호의 **끝자리** 분포는 다루지 않는다.
- 현재 빈도/통계 페이지(stats, rolling, cooccurrence)는 번호 단위 또는 쌍 단위
  빈도를 제공할 뿐, 끝자리(1의 자리) 단위로 묶어서 분포를 비교하는 기능이 없다.
- 많은 로또 분석가가 특정 끝자리(예: 3 또는 7로 끝나는 번호)가 더 자주 출현하는지
  추적한다. 사용자는 끝자리 분포가 균등한지 편향되었는지 확인할 방법이 없다.

본 SPEC은 이 공백을 메워, 끝자리별 출현 횟수/비율/편차를 표로 제공한다.

## 용어

- **끝자리(last digit / units digit) d**: 번호를 10으로 나눈 나머지. d ∈ {0,…,9}.
- **끝자리 그룹(digit group)**: 끝자리가 같은 번호들의 집합 (예: 끝자리 3 그룹은
  {3, 13, 23, 33, 43}).
- **출현 횟수(count)**: 전체 추첨 이력에서, 어떤 끝자리 그룹에 속한 번호들이 당첨
  본번호로 등장한 총 횟수(보너스 제외). 한 회차에 같은 끝자리 번호가 둘 이상 나오면
  각각 모두 카운트한다.
- **비율(pct)**: 전체 번호 슬롯 대비 백분율 =
  `count / (total_draws * 6) * 100`. 즉 전체 추첨의 모든 번호 슬롯 중 해당 끝자리가
  차지한 비율.
- **균등 기대치(avg_expected)**: 끝자리 분포가 완전히 균등하다고 가정할 때의 기대
  출현 횟수 = `(len(numbers) / 45) * 6 * total_draws`. 여기서 `len(numbers)`는 해당
  끝자리 그룹의 번호 개수(4 또는 5)이다.
- **편차(deviation)**: 실제 출현 횟수와 균등 기대치의 차이 = `count - avg_expected`.
  양수면 과대표(over-represented, 기대보다 자주 출현), 음수면 과소표
  (under-represented, 기대보다 덜 출현).
- **LastDigitStat**: 한 끝자리에 대한 결과 구조
  `{"digit": int, "count": int, "pct": float, "numbers": list[int],
  "avg_expected": float, "deviation": float}`.

## 요구사항 (EARS)

### Ubiquitous Requirements

- REQ-LD-001: The system SHALL provide
  `get_last_digit_stats(draws: list[DrawResult]) -> dict[int, dict]` in
  `lotto/web/data.py`, returning a mapping keyed by each units digit `d` ∈ {0,…,9}
  to its `LastDigitStat` structure.
- REQ-LD-002: Each `LastDigitStat` value SHALL contain the keys `digit` (int),
  `count` (int), `pct` (float), `numbers` (list[int], ascending), `avg_expected`
  (float), and `deviation` (float).
- REQ-LD-003: The `numbers` list for digit `d` SHALL contain exactly the numbers in
  1~45 whose units digit equals `d` (i.e. `n % 10 == d`), in ascending order; digit
  0 has {10,20,30,40}, digits 6~9 have 4 numbers each, and digits 1~5 have 5 numbers
  each.
- REQ-LD-004: The `count` for digit `d` SHALL be the total number of appearances,
  across all draws, of any number whose units digit is `d` among the 6 main winning
  numbers; multiple matching numbers in the same draw SHALL each be counted.
- REQ-LD-005: Counting SHALL use only the 6 main winning numbers of each draw
  (`DrawResult.numbers()`); the bonus number SHALL NOT contribute to any count, pct,
  expected, or deviation value.
- REQ-LD-006: The `pct` for digit `d` SHALL be computed as
  `count / (total_draws * 6) * 100`, where `total_draws` is the total number of
  draws; when `total_draws` is 0, `pct` SHALL be 0.0.
- REQ-LD-007: The `avg_expected` for digit `d` SHALL be computed as
  `(len(numbers) / 45) * 6 * total_draws`, representing the expected count under a
  uniform distribution over all 45 numbers.
- REQ-LD-008: The `deviation` for digit `d` SHALL be computed as
  `count - avg_expected`; a positive value indicates over-representation and a
  negative value indicates under-representation.
- REQ-LD-009: The result mapping SHALL always contain all 10 digits (0~9), even when
  a digit's `count` is 0, so consumers can render a complete 10-row table.

### Event-driven Requirements

- REQ-LD-010: WHEN `GET /stats/last-digit` is requested, the system SHALL render a
  page with a table listing, for each digit 0~9: the digit, its number group, count,
  pct%, and deviation (with explicit +/- sign).
- REQ-LD-011: WHEN the page renders, rows that are over-represented (deviation > 0)
  and under-represented (deviation < 0) SHALL be visually highlighted (distinct
  styling per direction) so the skew is immediately apparent.
- REQ-LD-012: WHEN `GET /api/stats/last-digit` is called, the system SHALL return a
  JSON list containing all 10 digits with their `LastDigitStat` fields, ordered by
  digit ascending (0 first).

### State-driven Requirements

- REQ-LD-013: WHILE draw data is unavailable (no draws or empty list), the system
  SHALL still return all 10 digits with `count` 0, `pct` 0.0, `avg_expected` 0.0, and
  `deviation` 0.0, without error; the page renders an explanatory empty state with
  HTTP 200.
- REQ-LD-014: WHILE last-digit stats are cached in memory, invalidating the cache
  (via the existing `invalidate_cache`) SHALL cause the next request to recompute.

### Unwanted Behavior Requirements

- REQ-LD-015: The system SHALL NOT include the bonus number in any count, pct,
  expected, or deviation computation. (See REQ-LD-005.)
- REQ-LD-016: The system SHALL NOT omit any digit from the result; all 10 digits
  (0~9) SHALL always be present even with count 0. (See REQ-LD-009.)
- REQ-LD-017: The system SHALL NOT persist last-digit results to the database or any
  on-disk store; results live only in the in-memory cache and are recomputed on
  demand.
- REQ-LD-018: The system SHALL NOT add any new recommendation strategy; it provides
  only distribution analysis data, not recommended number sets.
- REQ-LD-019: The system SHALL NOT introduce any new client-side JavaScript
  dependency; the page is rendered server-side as a static table.
- REQ-LD-020: The system SHALL NOT modify the existing recommendation/analysis core
  logic (`recommender.py`, `analyzer.py`); only a new function is added to
  `lotto/web/data.py`.

### Optional Requirements

- REQ-LD-021: WHERE feasible, the system SHALL compute the total per-number frequency
  once and aggregate it by last digit, rather than re-scanning all draws separately
  for each digit.
- REQ-LD-022: WHERE the last-digit results can be memoized, the system SHALL cache
  them at module level (like existing `lotto/web/data.py` caches, e.g. a module-level
  `_last_digit_cache`) so repeated requests reuse the computed results.

## 성능 요구사항

- REQ-LD-023: Computing last-digit stats over the full draw history SHALL complete in
  under 5 seconds on the reference environment.

## 인수 기준

acceptance.md 참조.

## 범위 밖 (Out of Scope) / Exclusions

본 SPEC 범위에서 **명시적으로 제외**되는 항목 (구현 금지):

1. **보너스 번호 집계 금지** — 보너스 번호를 출현 횟수/비율/기대치/편차 계산에
   포함하지 않는다. 본번호 6개(1~45)만 사용한다. (REQ-LD-005, REQ-LD-015)
2. **끝자리 누락 금지** — 결과에서 어떤 끝자리도 빠뜨리지 않는다. 10개 끝자리(0~9)는
   count=0이라도 항상 포함한다. (REQ-LD-009, REQ-LD-016)
3. **DB/파일 영속화 금지** — 끝자리 결과를 데이터베이스나 파일에 저장하지 않는다.
   메모리 캐시만 사용하며 요청 시 재계산한다. (REQ-LD-017)
4. **신규 추천 전략 추가 금지** — 새로운 추천 전략을 만들지 않는다. 본 SPEC은 끝자리
   분포 분석 데이터만 제공하며 추천 조합(recommended set)을 생성하지 않는다.
   (REQ-LD-018)
5. **JavaScript 의존성 추가 금지** — 클라이언트 스크립트 기반 인터랙티브 시각화를
   추가하지 않는다. 서버사이드 렌더링 표로 처리하며 신규 클라이언트 스크립트
   의존성을 추가하지 않는다. (REQ-LD-019)
6. **추천/분석 코어 로직 변경 금지** — `recommender.py`와 `analyzer.py`의 기존
   로직을 수정하지 않는다. `lotto/web/data.py`에 신규 함수만 추가한다. (REQ-LD-020)
7. **예측 보장/투자 권유 금지** — 끝자리 분포 편차는 과거 통계일 뿐 미래 출현을
   보장하지 않는다. UI는 이 한계를 명시한다(예측 보장 문구 금지).
