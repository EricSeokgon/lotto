---
id: SPEC-LOTTO-056
version: 0.1.0
status: Completed
created: 2026-06-09
updated: 2026-06-09
author: ircp
priority: medium
---

# SPEC-LOTTO-056: 번호 간격 패턴 분석 (Number Gap Pattern Analysis)

## 개요

각 회차의 본번호 6개를 오름차순 정렬한 뒤, 인접한 번호 사이의 간격(차이)
5개를 산출하여 당첨 조합의 구조적 패턴을 분석한다. 예를 들어 조합
[3, 12, 21, 33, 40, 45]의 간격은 [9, 9, 12, 7, 5]이다.

전체 회차에 걸친 간격 분포(소/중/대), 최빈 간격값, 회차별 평균/최소/최대
간격, 위치별 평균 간격을 집계하여 서버 렌더링 테이블과 JSON API로 제공한다.

## 배경

기존 통계 기능은 번호 출현 빈도(SPEC-LOTTO-001대), 합계 분포
(SPEC-LOTTO-049), 끝자리 분포(last-digit) 등 "값" 중심 분석에 집중되어 있다.
본 SPEC은 조합 내부의 "간격 구조"라는 새로운 관점을 추가한다. 간격 분석은
번호들이 얼마나 고르게/뭉쳐서 분포하는지를 드러내며, 추천 조합의 자연스러움
판단 근거로 활용될 수 있다.

기존 `lotto/*.py` 코어 모듈은 수정하지 않고, `lotto/web/data.py`에 신규
분석 함수를 추가하는 기존 패턴(get_last_digit_stats, sum_range_analysis 등)을
그대로 따른다.

## 용어 정의

- 본번호: 회차당 보너스를 제외한 6개 메인 번호
- 간격(gap): 오름차순 정렬된 본번호에서 `sorted[i+1] - sorted[i]` (회차당 5개)
- 소간격(small): 1~5, 중간격(medium): 6~10, 대간격(large): 11 이상
- 위치별 간격: 1→2, 2→3, 3→4, 4→5, 5→6의 5개 인접 쌍

## 요구사항 (EARS)

### Ubiquitous Requirements

- REQ-GAP-001: The system SHALL provide `get_gap_stats(draws)` returning
  total_draws, avg_gap(2 decimals), gap_size_distribution, most_common_gaps,
  avg_min_gap(2 decimals), avg_max_gap(2 decimals), position_avg_gaps.
- REQ-GAP-002: The avg_gap SHALL be the mean of all per-draw gap values across
  all draws (total of 5 gaps per draw), rounded to 2 decimals.
- REQ-GAP-003: The gap_size_distribution SHALL classify every gap into exactly
  one of three buckets — small(1-5), medium(6-10), large(11+) — and report each
  bucket as {count, ratio(4 decimals)} where ratio is count divided by the total
  number of gaps observed.
- REQ-GAP-004: The most_common_gaps SHALL list up to the top 10 gap values in
  descending count order, each as {gap, count}, breaking count ties by the
  smaller gap value first.
- REQ-GAP-005: The avg_min_gap SHALL be the mean of each draw's minimum gap and
  avg_max_gap SHALL be the mean of each draw's maximum gap, each over all draws,
  rounded to 2 decimals.
- REQ-GAP-006: The position_avg_gaps SHALL be a list of 5 entries (positions
  1→2 through 5→6) in fixed order, each as {position, label, avg_gap(2 decimals)}
  where avg_gap is the mean gap at that sorted position across all draws.
- REQ-GAP-007: The system SHALL expose `GET /api/stats/gap` returning the gap
  analysis as JSON (always 200).
- REQ-GAP-008: The system SHALL expose `GET /stats/gap` rendering a
  server-side page with summary cards, a gap-size distribution table, a
  most-common-gaps table, and a per-position average gap table.

### Event-driven Requirements

- REQ-GAP-009: WHEN computing gaps for a draw, the system SHALL sort the 6 main
  numbers ascending and exclude the bonus number entirely.
- REQ-GAP-010: WHEN `most_common_gaps` has fewer than 10 distinct gap values,
  the system SHALL return all observed gap values (not padded to 10).

### State-driven Requirements

- REQ-GAP-011: WHILE no draw data is available, `get_gap_stats` SHALL return
  total_draws=0, avg_gap=0, all three size buckets {count:0, ratio:0},
  most_common_gaps=[], avg_min_gap=0, avg_max_gap=0, and position_avg_gaps with
  all 5 positions avg_gap=0; both endpoints SHALL still return 200 and the page
  SHALL render an empty state.

### Unwanted Behavior Requirements

- REQ-GAP-012: The data layer SHALL NOT mutate the input draws list nor modify
  any existing `lotto/*.py` core module.
- REQ-GAP-013: IF a draw exposes fewer than 6 main numbers, THEN the system
  SHALL skip that draw from gap aggregation rather than raising.

### Optional Requirements

- REQ-GAP-014: Where a memory cache is used, the system SHALL store the computed
  result in `_gap_cache: dict[str, GapStats]` and clear it in `invalidate_cache()`,
  consistent with existing cache patterns in `data.py`.

## 비기능 요구사항

- Python 3.9 호환 (match/case 금지, `zip(strict=...)` 금지 — 필요 시 `# noqa: B905`)
- 서버 사이드 렌더링 전용 (JavaScript 사용 금지)
- 결정적 — 동일 입력에 동일 출력
- 테스트는 `tests/test_gap_analysis.py`에 작성하고 `mypy.ini` override 목록에 등록

## 인수 기준

acceptance.md 참조.

## Exclusions (What NOT to Build)

- 보너스 번호를 포함한 간격 분석 (본번호 6개만 대상)
- 회차 시계열에 따른 간격 추세(연도별 평균 간격 변화)
- 사용자 입력 조합의 간격 평가 체커 (별도 SPEC으로 분리)
- 추천 엔진과의 자동 연동(간격 필터)
- 간격 분포 시각화 차트(막대/그래프) — 표 형태만 제공
- JavaScript 기반 인터랙션 또는 클라이언트 측 계산
