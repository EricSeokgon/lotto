---
id: SPEC-LOTTO-052
version: 0.1.0
status: Completed
created: 2026-06-09
updated: 2026-06-09
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-052: 전략 백테스팅 분석기 (Strategy Backtesting Analyzer)

## HISTORY

- 2026-06-09 (v0.1.0): 최초 작성 (Planned). 11개 추천 전략을 과거 실제 추첨
  결과에 대해 백테스트하여 전략별 적중 성능을 객관적으로 비교하는 읽기 전용
  분석 기능으로 정의. look-ahead bias 제거를 핵심 제약으로 채택.

## 개요

11개 추천 전략(`STRATEGY_LABELS`) 각각이 과거 실제 추첨 결과에 대해 얼마나 잘
적중했는지를 백테스트하여 전략별 성능 지표를 산출하고 비교한다. 최근 N개 회차
(기본 50개)를 대상으로, 각 회차를 평가할 때 **그 회차 이전의 추첨 데이터만**
사용하여 통계를 재구성하고(look-ahead bias 제거) 추천을 실행한 뒤, 추천한 6개
번호를 해당 회차의 실제 당첨 번호와 비교하여 적중 개수(0~6)를 기록한다.

본 기능은 **읽기 전용 분석 기능**이다. 추천 로직과 통계 분석 로직을 변경하지 않고
기존 검증된 호출 경로(`LottoAnalyzer.analyze` → `LottoRecommender`)를 재사용하여
성능 평가만 추가한다. 결과는 메모리에 캐시하며 DB에 영속화하지 않는다.

## 배경

- `lotto/recommender.py`에 11개 전략(`STRATEGY_LABELS`: 고빈도, 저빈도, 균형,
  최근편향, 동반패턴, 홀짝균형, 번호대균형, 핫콜드혼합, 갭분석, 앙상블,
  데이터스마트)이 정의되어 있으며 `LottoRecommender.recommend_by_strategy(label)`로
  전략별 추천(`Recommendation(numbers, strategy_label)`)을 호출할 수 있다.
- `lotto/simulator.py`는 이미 **look-ahead bias가 없는 회차별 평가 패턴**을
  프로덕션에서 검증했다: 평가 대상 회차 #k에 대해 #1..#k-1만으로
  `LottoAnalyzer().analyze(prior_draws)`를 호출하여 `Statistics`를 재구성하고
  `LottoRecommender(stats)`로 추천을 만든다. 본 SPEC은 이 패턴을 재사용한다.
- SPEC-LOTTO-048(시뮬레이션 결과 저장)은 무작위 시뮬레이션을 DB에 저장하지만,
  "각 전략이 과거 실제 결과에 대해 얼마나 적중했는가"는 평가하지 못한다.
- SPEC-LOTTO-051(전략 합의도 오버레이)은 현재 스냅샷 기준 전략 간 합의만 보여줄
  뿐, 전략의 **과거 적중 성능(품질)**을 평가하지 못한다.

본 SPEC은 이 공백을 메워, 사용자가 전략 품질을 객관적 지표로 비교할 수 있게 한다.

## 용어

- **백테스트(backtest)**: 과거 실제 추첨 결과에 대해 전략을 소급 적용하여 성능을
  측정하는 행위.
- **과거 회차 수(n_past)**: 백테스트 대상이 되는 최근 회차 개수(기본 50).
- **적중 개수(match count)**: 전략이 추천한 6개 번호 중 해당 회차 실제 당첨 번호와
  일치하는 번호의 수(0~6). 보너스 번호는 적중 계산에서 제외한다.
- **look-ahead bias**: 평가 대상 회차의 결과(또는 이후 회차)를 통계에 포함시켜
  미래 정보가 추천에 누설되는 오류. 본 SPEC은 이를 엄격히 금지한다.
- **prior_draws**: 평가 대상 회차 #k 직전까지의 추첨 목록(#1..#k-1).
- **composite score(종합 점수)**: 전략의 평균 적중 + 고적중(3+ 매치) 가중치를
  반영한 비교용 점수(높을수록 우수).

## 요구사항 (EARS)

### Ubiquitous Requirements

- REQ-BT-001: The system SHALL provide
  `run_backtest(draws: list[DrawResult], n_past: int = 50) -> dict[str, BacktestResult]`
  in `lotto/web/data.py`, returning a mapping from each of the 11 strategy labels
  in `STRATEGY_LABELS` to its `BacktestResult`.
- REQ-BT-002: For each backtested draw #k, the system SHALL reconstruct statistics
  using ONLY draws strictly before #k (prior_draws = #1..#k-1), reusing the
  `LottoAnalyzer().analyze(prior_draws)` → `LottoRecommender(stats)` path proven
  in `lotto/simulator.py`. No draw at index >= k may influence the recommendation.
- REQ-BT-003: For each backtested draw and each of the 11 strategies, the system
  SHALL call `recommend_by_strategy(label)` and compute the match count as the size
  of the intersection between the recommended 6 numbers and the draw's actual 6
  winning numbers (`DrawResult.numbers()`), excluding the bonus number.
- REQ-BT-004: Each `BacktestResult` SHALL expose: `match_counts` (a mapping
  `{0..6: int}` counting how many backtested draws yielded each match count),
  `avg_match` (float), `best_draw` (a record with `round`, `matched`,
  `recommended`, `actual`), and `score` (composite float, higher is better).
- REQ-BT-005: The `match_counts` mapping for each strategy SHALL contain all keys
  0 through 6, and the sum of its values SHALL equal the number of draws actually
  backtested (the evaluated window size).

### Event-driven Requirements

- REQ-BT-006: WHEN `GET /backtest` loads and at least the minimum number of draws
  exist, the system SHALL run the backtest (using the cached result if available)
  and render a page listing the 11 strategies with their performance metrics,
  sorted by `score` descending.
- REQ-BT-007: WHEN `GET /api/backtest?n=<N>` is called and sufficient draws exist,
  the system SHALL return a JSON object mapping each strategy label to its
  serialized `BacktestResult` (match_counts, avg_match, best_draw, score).
- REQ-BT-008: WHEN a backtest has already been computed for a given `n_past` during
  the process lifetime, a subsequent request with the same `n_past` SHALL return
  the in-memory cached result instead of recomputing.

### State-driven Requirements

- REQ-BT-009: WHILE the available draw count is below the minimum threshold (20
  draws), the system SHALL NOT run the backtest and SHALL return an error result
  (page renders an explanatory message; API returns an error payload).
- REQ-BT-010: WHILE `n_past` exceeds the number of draws available for evaluation
  (draws beyond the minimum prior-history requirement), the system SHALL clamp the
  evaluated window to the maximum feasible number of draws rather than erroring,
  and `match_counts` totals SHALL reflect the clamped window (per REQ-BT-005).
- REQ-BT-011: WHILE results for a given `n_past` are cached, invalidating the cache
  (new draw data ingested) SHALL cause the next request to recompute.

### Unwanted Behavior Requirements

- REQ-BT-012: The system SHALL NOT introduce look-ahead bias: under no condition
  may the draw being evaluated, or any later draw, contribute to the statistics or
  recommendation used to predict that draw. (See REQ-BT-002.)
- REQ-BT-013: The system SHALL NOT modify recommendation or analysis core logic
  (`recommender.py` `STRATEGY_LABELS`/`_strategy_scores`/`_pick_set`,
  `analyzer.py` `LottoAnalyzer.analyze`); it SHALL only call existing public APIs.
- REQ-BT-014: The system SHALL NOT persist backtest results to the database or any
  on-disk store; results live only in the in-memory cache and are recomputed on
  demand.
- REQ-BT-015: The system SHALL NOT count the bonus number as a match when computing
  match counts (only the 6 main winning numbers are compared).

### Optional Requirements

- REQ-BT-016: WHERE feasible, the backtest SHALL reuse a single reconstructed
  `Statistics`/`LottoRecommender` per evaluated draw across all 11 strategies
  (rebuild statistics once per draw, not once per strategy), to meet the
  performance budget.
- REQ-BT-017: WHERE the page and API need a default window, the system SHALL use
  `n_past = 50`.

## 성능 요구사항

- REQ-BT-018: Backtesting 50 draws × 11 strategies SHALL complete in under 30
  seconds on the reference environment.

## 인수 기준

acceptance.md 참조.

## 범위 밖 (Out of Scope) / Exclusions

본 SPEC 범위에서 **명시적으로 제외**되는 항목 (구현 금지):

1. **추천/분석 코어 로직 변경 금지** — `recommender.py`의 `STRATEGY_LABELS`,
   `_strategy_scores`, `_pick_set` 및 `analyzer.py`의 `LottoAnalyzer.analyze`를
   수정하지 않는다. 기존 공개 API 호출만 한다. (REQ-BT-013)
2. **DB 영속화 금지** — 백테스트 결과를 데이터베이스나 파일에 저장하지 않는다.
   메모리 캐시만 사용하며 요청 시 재계산한다. SPEC-LOTTO-048의 저장 경로를
   재사용하지 않는다. (REQ-BT-014)
3. **look-ahead 허용 금지** — 성능을 이유로 전체 통계를 한 번만 만들어 모든 회차에
   재사용하는 방식은 금지한다. 회차마다 prior_draws로 통계를 재구성해야 한다.
   (REQ-BT-002, REQ-BT-012)
4. **신규 전략 추가 금지** — 새로운 추천 전략을 만들지 않는다. 11개 기존 전략의
   성능 평가만 한다.
5. **보너스 번호 적중 평가 금지** — 보너스 번호 일치를 별도 등급/매치로 집계하지
   않는다. 본 SPEC은 6개 메인 번호 적중 개수만 다룬다. (REQ-BT-015)
6. **예측 보장/투자 권유 금지** — 백테스트는 과거 성능 측정일 뿐, 미래 적중을
   보장하지 않는다. UI는 이 한계를 명시한다(예측 보장 문구 금지).
7. **JavaScript 기반 인터랙티브 차트 불필요** — 서버사이드 렌더링 표/리스트로
   처리한다. 신규 클라이언트 스크립트 의존성을 추가하지 않는다.
