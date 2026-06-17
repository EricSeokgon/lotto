---
id: SPEC-LOTTO-051
version: 0.1.0
status: completed
created: 2026-06-05
updated: 2026-06-09
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-051: 주차 선택 주의 알림 (Cross-Strategy Consensus Alert)

## HISTORY

- 2026-06-05 (v0.1.0): 최초 작성 (draft). research.md 기반으로 Option A(서버사이드
  요청별 전체 전략 스캔) 채택. 추천 표시에 전략 합의도(consensus) 오버레이를
  추가하는 읽기 전용 분석 기능으로 정의.

## 개요

추천 페이지가 추천 결과를 표시할 때, 추천된 각 번호가 11개 전략 중 몇 개에
포함되는지(합의도, consensus count)를 함께 보여준다. 합의도가 임계값(4개) 이상인
번호에는 시각적 주의 표시(주의 배지/하이라이트)를 부여하고, 모든 번호에 대해
합의도 카운트를 노출한다.

본 기능은 **읽기 전용 분석 오버레이**이다. 추천 로직 자체는 변경하지 않고
표시(display)만 풍부하게 만든다.

## 배경

`lotto/recommender.py`에는 11개 전략(`STRATEGY_LABELS`)이 정의되어 있으며
`LottoRecommender.recommend_by_strategy(label)`로 전략별 추천을 호출할 수 있다.
SPEC-LOTTO-032(`strategy_compare`)는 이미 11개 전략을 순차 호출하는 패턴을
프로덕션에서 검증했다(`lotto/web/data.py`). 본 SPEC은 이 검증된 패턴을 재사용하여,
"현재 통계 스냅샷 기준으로 각 번호가 몇 개 전략의 추천에 등장하는가"를 집계해
사용자에게 합의 강도(consensus strength) 지표를 제공한다.

추천 엔진은 `Statistics`만 사용하고 원본 추첨 데이터(raw draws)에는 접근하지
않는다(계층 분리). 본 기능 역시 이 경계를 준수한다.

## 용어

- **합의도(consensus count)**: 특정 번호가 11개 전략 추천 중 등장한 전략 수 (0~11).
- **주의 임계값(caution threshold)**: 합의도 >= 4. 이 값 이상이면 주의 배지 표시.
- **타깃 번호(target numbers)**: 추천 결과(`Recommendation.numbers`)에 포함된 번호들.

## 요구사항 (EARS)

### Ubiquitous Requirements

- REQ-CONS-001: The system SHALL provide
  `get_cross_strategy_consensus(recommender, target_numbers)` returning a mapping
  `{number: count}` where `count` is the number of the 11 strategies whose
  recommendation includes that number, for every number in `target_numbers`
  (count range 0..11).
- REQ-CONS-002: The system SHALL compute the consensus mapping by calling
  `recommender.recommend_by_strategy(label)` once for each label in
  `STRATEGY_LABELS` (11 calls), and SHALL NOT recompute scores directly.
- REQ-CONS-003: WHEN consensus data is available, the recommendation display
  SHALL annotate every recommended number with its consensus count (`N/11`).

### Event-driven Requirements

- REQ-CONS-004: WHEN the recommendation page (`GET /recommend`) loads and
  recommendations exist, the system SHALL compute cross-strategy consensus for the
  displayed recommendations and pass it to the template context.
- REQ-CONS-005: WHEN `GET /api/recommendations` returns recommendations, each
  recommendation object in the JSON response SHALL include a `consensus` field
  mapping each of its numbers to its cross-strategy count.

### State-driven Requirements

- REQ-CONS-006: WHILE a recommended number's consensus count is >= 4 (caution
  threshold), the display SHALL render a caution badge/highlight on that number.
- REQ-CONS-007: WHILE no statistics data is available (recommendations are None),
  the system SHALL skip consensus computation and the page SHALL still render
  with HTTP 200 (no consensus panel).

### Unwanted Behavior Requirements

- REQ-CONS-008: The system SHALL NOT re-implement recommendation logic;
  consensus computation MUST go through `recommend_by_strategy()` and MUST NOT
  call `_strategy_scores`, `_pick_set`, or otherwise duplicate scoring.
- REQ-CONS-009: The consensus computation SHALL NOT access raw draws; it SHALL
  operate only via the `recommender` object (which uses `Statistics` only).
- REQ-CONS-010: The feature SHALL NOT modify the `Recommendation` dataclass nor
  add a new recommendation strategy; it is display-only enrichment.

### Optional Requirements

- REQ-CONS-011: WHERE possible, the system SHALL compute the all-strategy scan
  once per page request and reuse the result for all displayed numbers, avoiding
  redundant repeated 11-strategy scans within a single request.

## 인수 기준

acceptance.md 참조.

## 범위 밖 (Out of Scope) / Exclusions

본 SPEC 범위에서 **명시적으로 제외**되는 항목 (구현 금지):

1. **추천 코어 로직 변경 금지** — `recommender.py`의 `STRATEGY_LABELS`,
   `_strategy_scores`, `_pick_set` 등 코어 로직을 수정하지 않는다. 호출만 한다.
2. **원본 추첨 데이터 노출 금지** — 웹 계층에 raw draws를 전달하지 않는다.
   합의도 계산은 `recommender`/`Statistics`만 사용한다.
3. **신규 전략 추가 금지** — 새로운 추천 전략을 만들지 않는다. 표시용 보강만 한다.
4. **JavaScript 불필요** — 서버사이드 렌더링으로 처리한다(클라이언트 스크립트 추가 안 함).
5. **`Recommendation` 데이터클래스 변경 금지** — 기존 dataclass 필드를 수정/추가하지 않는다.
