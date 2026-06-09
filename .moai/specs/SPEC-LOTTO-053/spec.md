---
id: SPEC-LOTTO-053
version: 0.1.0
status: Completed
created: 2026-06-09
updated: 2026-06-09
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-053: 번호 동시 출현 분석기 (Number Co-occurrence Analyzer)

## HISTORY

- 2026-06-09 (v0.1.0): 최초 작성 (Planned). 개별 번호(1~45) 쌍이 같은 회차에
  함께 출현한 빈도를 원시 동시 출현 행렬(co-occurrence matrix)로 노출하는 읽기
  전용 분석 기능으로 정의. SPEC-LOTTO-044(번호 궁합 추천기)가 "추천 조합"을
  생성하는 것과 달리, 본 SPEC은 가공 없는 쌍별 동시 출현 카운트를 그대로 보여주는
  것에 초점을 둔다.

## 개요

전체 추첨 이력에서 번호 쌍 (i, j) (단 i < j)이 같은 회차에 함께 출현한 횟수를
집계하여 동시 출현 행렬을 구성한다. 이를 통해 사용자는 "어떤 번호들이 함께
나오는 경향이 있는가"라는 원시 동시 출현 관계를 직접 탐색할 수 있다.

본 기능은 **읽기 전용 분석 기능**이다. 추천/분석 코어 로직을 변경하지 않고,
기존 데이터 접근 레이어(`lotto/web/data.py`)에 신규 함수를 추가하여 동시 출현
행렬과 상위 쌍, 특정 번호의 동반 파트너 목록을 산출한다. 결과는 메모리에 캐시하며
DB나 파일에 영속화하지 않는다.

## 배경

- `lotto/analyzer.py`의 `Statistics`로 과거 추첨 데이터에 접근할 수 있고,
  `DrawResult.numbers()`로 회차별 정렬된 본번호 6개(보너스 제외)를 얻는다.
- `lotto/recommender.py`에는 11개 추천 전략(`STRATEGY_LABELS`)이 있으며
  `LottoRecommender`로 추천을 생성한다.
- SPEC-LOTTO-044(`/numbers/affinity`)는 대상 번호의 동반 출현을 분석하지만, 그
  결과물은 **추천 조합(recommended set)**이다 — 원시 쌍별 동시 출현 행렬이 아니다.
- SPEC-LOTTO-052(`/backtest`)는 전략 적중 성능을 평가할 뿐, 번호 간 동시 출현
  관계를 다루지 않는다.
- 현재 사용자가 개별 번호 간 **원시 동시 출현 관계**(어떤 번호들이 같은 회차에
  함께 나오는가)를 행렬/목록 형태로 탐색할 방법이 없다.

본 SPEC은 이 공백을 메워, 가공되지 않은 쌍별 동시 출현 데이터를 표와 목록으로
제공한다.

## 용어

- **동시 출현(co-occurrence)**: 두 번호가 같은 회차의 당첨 본번호 6개에 함께
  포함되는 사건.
- **쌍(pair)**: 서로 다른 두 번호 (i, j) (단 i < j). 순서 없는 조합이며 이중
  집계하지 않는다.
- **동시 출현 행렬(co-occurrence matrix)**: 모든 가능한 쌍 (i, j)에 대한
  {(i, j): count} 매핑. count는 두 번호가 함께 나온 회차 수.
- **상위 쌍(top co-occurrences)**: count 내림차순 상위 N개 쌍.
- **동반 파트너(partner)**: 특정 번호 N에 대해, N과 같은 회차에 함께 나온 다른
  번호. N 자신은 파트너에서 제외한다.
- **백분율(pct)**: 쌍이 함께 나온 회차 비율 = count / total_draws × 100
  (float, 소수 2자리).

## 요구사항 (EARS)

### Ubiquitous Requirements

- REQ-CO-001: The system SHALL provide
  `get_cooccurrence_matrix(draws: list[DrawResult]) -> dict[tuple[int, int], int]`
  in `lotto/web/data.py`, returning a mapping from each unordered pair `(i, j)`
  with `i < j` that co-occurred at least once to its co-occurrence count across
  all draws.
- REQ-CO-002: The system SHALL iterate each pair only once per draw using `i < j`
  ordering, so that no pair is double-counted and `(j, i)` keys never appear.
- REQ-CO-003: Co-occurrence counting SHALL use only the 6 main winning numbers of
  each draw (`DrawResult.numbers()`); the bonus number SHALL NOT contribute to any
  pair count.
- REQ-CO-004: The system SHALL provide
  `get_top_cooccurrences(draws: list[DrawResult], n: int = 20) -> list[dict]`,
  returning the top `n` pairs by co-occurrence count, where each dict has keys
  `pair` (a `tuple[int, int]` with `i < j`), `count` (int), and `pct` (float, the
  percentage of total draws containing both numbers, 2 decimal places).
- REQ-CO-005: The system SHALL provide
  `get_number_partners(draws: list[DrawResult], number: int, top_k: int = 10) -> list[dict]`,
  returning the top `top_k` partners of `number` sorted by co-occurrence count
  descending, where each dict has keys `number` (the partner), `count` (int), and
  `pct` (float, 2 decimal places).
- REQ-CO-006: The `pct` value in all results SHALL equal
  `count / total_draws × 100` rounded to 2 decimal places, where `total_draws` is
  the number of draws analyzed; when `total_draws` is 0, `pct` SHALL be `0.0`.

### Event-driven Requirements

- REQ-CO-007: WHEN `GET /numbers/cooccurrence` loads without a `number` query
  parameter, the system SHALL render a page showing the top 20 co-occurring pairs
  in a table with columns: pair, count, and percentage of draws.
- REQ-CO-008: WHEN `GET /numbers/cooccurrence?number=N` (with `1 <= N <= 45`) is
  requested, the system SHALL render a page showing the top 10 partners for number
  `N` (pair-partner, count, percentage), instead of the overall top-pairs view.
- REQ-CO-009: WHEN `GET /api/numbers/cooccurrence?number=N&top=T` is called with a
  `number` parameter, the system SHALL return a JSON object containing the top `T`
  partners for that number.
- REQ-CO-010: WHEN `GET /api/numbers/cooccurrence?top=T` is called without a
  `number` parameter, the system SHALL return a JSON object containing the top `T`
  pairs overall (default `T = 20`).

### State-driven Requirements

- REQ-CO-011: WHILE draw data is unavailable (no draws or empty list), the system
  SHALL return empty results without error — the matrix is empty, top lists are
  empty, partner lists are empty, and the page renders an explanatory empty state
  with HTTP 200.
- REQ-CO-012: WHILE a `number` query parameter is present, the page SHALL show the
  partner view for that number; otherwise it SHALL show the overall top-pairs view.
- REQ-CO-013: WHILE results for the co-occurrence matrix are cached in memory,
  invalidating the cache (via the existing `invalidate_cache`) SHALL cause the next
  request to recompute.

### Unwanted Behavior Requirements

- REQ-CO-014: The system SHALL NOT double-count any pair; counting `(i, j)` and
  `(j, i)` separately, or counting a pair twice within the same draw, is
  prohibited. (See REQ-CO-002.)
- REQ-CO-015: The system SHALL NOT include the bonus number in any co-occurrence
  count. (See REQ-CO-003.)
- REQ-CO-016: The system SHALL NOT persist the co-occurrence matrix or any derived
  results to the database or any on-disk store; results live only in the in-memory
  cache and are recomputed on demand.
- REQ-CO-017: The system SHALL NOT add any new recommendation strategy; it provides
  only raw co-occurrence data, not recommended number sets.
- REQ-CO-018: The system SHALL NOT introduce any new client-side JavaScript
  dependency; the page is rendered server-side as static tables/lists.

### Optional Requirements

- REQ-CO-019: WHERE feasible, the system SHALL build the full co-occurrence matrix
  once per request (single O(D × 15) pass, where D = draw count and 15 = C(6,2)
  pairs per draw) and derive top-pairs and partner lists from that single matrix
  rather than re-scanning draws for each query.
- REQ-CO-020: WHERE the co-occurrence matrix can be memoized, the system SHALL
  cache it at module level (like existing `lotto/web/data.py` caches) so repeated
  requests within the process lifetime reuse the computed matrix.

## 성능 요구사항

- REQ-CO-021: Building the co-occurrence matrix over the full draw history SHALL
  complete in under 5 seconds on the reference environment (each draw contributes
  exactly C(6,2) = 15 pairs).

## 인수 기준

acceptance.md 참조.

## 범위 밖 (Out of Scope) / Exclusions

본 SPEC 범위에서 **명시적으로 제외**되는 항목 (구현 금지):

1. **추천 전략 추가 금지** — 새로운 추천 전략을 만들지 않는다. 본 SPEC은 원시
   동시 출현 데이터만 제공하며 추천 조합(recommended set)을 생성하지 않는다.
   SPEC-LOTTO-044의 추천 조합 기능과 중복하지 않는다. (REQ-CO-017)
2. **DB/파일 영속화 금지** — 동시 출현 행렬이나 파생 결과를 데이터베이스나 파일에
   저장하지 않는다. 메모리 캐시만 사용하며 요청 시 재계산한다. (REQ-CO-016)
3. **보너스 번호 집계 금지** — 보너스 번호를 동시 출현 카운트에 포함하지 않는다.
   본번호 6개 기준으로만 쌍을 집계한다. (REQ-CO-003, REQ-CO-015)
4. **이중 집계 금지** — 쌍을 (i, j)와 (j, i)로 따로 세거나 같은 회차에서 한 쌍을
   두 번 세지 않는다. i < j 순서로 각 쌍을 정확히 한 번만 순회한다.
   (REQ-CO-002, REQ-CO-014)
5. **JavaScript 인터랙티브 시각화 불필요** — 히트맵 등 클라이언트 스크립트 기반
   시각화를 추가하지 않는다. 서버사이드 렌더링 표/목록으로 처리하며 신규 클라이언트
   스크립트 의존성을 추가하지 않는다. (REQ-CO-018)
6. **추천/분석 코어 로직 변경 금지** — `recommender.py`와 `analyzer.py`의 기존
   로직을 수정하지 않는다. `lotto/web/data.py`에 신규 함수만 추가한다.
7. **예측 보장/투자 권유 금지** — 동시 출현 빈도는 과거 통계일 뿐 미래 출현을
   보장하지 않는다. UI는 이 한계를 명시한다(예측 보장 문구 금지).
