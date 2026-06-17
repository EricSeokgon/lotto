---
id: SPEC-LOTTO-049
version: 0.1.0
status: Planned
created: 2026-06-02
updated: 2026-06-02
author: ircp
priority: medium
---

# SPEC-LOTTO-049: 합계 범위 분석 (Sum Range Analysis)

## 개요

각 회차 본번호 6개의 합계 분포를 분석한다. 합계는 최소 21(1+2+3+4+5+6)부터
최대 255(40+41+42+43+44+45)까지 분포한다. 폭 20의 12개 버킷으로 분류하여
최빈 구간, 평균/최소/최대 합계를 산출하고, 사용자가 입력한 조합의 합계가
"공통 영역"(p10~p90)에 드는지 확인할 수 있는 체커를 제공한다.

## 배경

기존 `pattern_analysis`(SPEC-LOTTO-019)는 합계를 10단위 동적 버킷으로 집계하나
관측된 합계만 키로 노출되어 분포 비교나 공통 영역 판정에는 부적합하다. 본 SPEC은
고정 12버킷·공통 영역·조합 평가를 갖춘 전용 분석을 추가한다(중복 없이 신규 함수로 구현).

## 요구사항 (EARS)

### Ubiquitous Requirements

- REQ-SUM-001: The system SHALL provide `sum_range_analysis(draws)` returning total_draws,
  avg_sum(2 decimals), min_sum, max_sum, most_common_range, distribution(12 buckets), common_zone.
- REQ-SUM-002: The distribution SHALL always list all 12 buckets in ascending order
  (21-40, 41-60, ..., 221-240, 241-255) including zero-count buckets, each with
  {range, low, high, count, ratio(4 decimals)}.
- REQ-SUM-003: The common_zone SHALL be the [p10, p90] of observed sums computed via
  nearest-rank percentile (rank = ceil(p/100 * N), clamped to [1, N]), inclusive integer bounds.
- REQ-SUM-004: The system SHALL provide `evaluate_sum(numbers, draws)` returning
  {sum, in_common_zone, common_zone, percentile(4 decimals)} where percentile is the fraction
  of historical draws with sum <= the input sum.
- REQ-SUM-005: The system SHALL expose `GET /api/stats/sum-range` returning the analysis (always 200).
- REQ-SUM-006: The system SHALL expose `GET /stats/sum-range` rendering a distribution bar chart,
  detail table, summary cards, and a combination sum checker form.

### Event-driven Requirements

- REQ-SUM-007: WHEN `most_common_range` has a tie in count, the system SHALL select the lower range.
- REQ-SUM-008: WHEN `GET /api/stats/sum-range/evaluate` receives the `n` parameter,
  the system SHALL validate exactly 6 distinct integers in 1..45 and SHALL return 422 otherwise.

### State-driven Requirements

- REQ-SUM-009: WHILE no draw data is available, `sum_range_analysis` SHALL return total_draws=0,
  avg/min/max=0, most_common_range=null, all 12 buckets count 0, common_zone {low:0, high:0},
  and the page SHALL render an empty state while both endpoints return 200.

### Unwanted Behavior Requirements

- REQ-SUM-010: The data layer SHALL NOT raise on invalid `numbers` input to `evaluate_sum`;
  validation is the API layer's responsibility (data layer is lenient and simply sums).

## 인수 기준

acceptance.md 참조.

## 범위 밖 (Out of Scope)

- 보너스 번호를 포함한 7개 합계 분석
- 합계 시계열 추세(연도별 평균 합계 변화)
- 추천 엔진과의 자동 연동(합계 필터)
