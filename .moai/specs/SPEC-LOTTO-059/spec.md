---
id: SPEC-LOTTO-059
version: 0.1.0
status: Completed
created: 2026-06-10
updated: 2026-06-10
author: ircp
priority: medium
---

# SPEC-LOTTO-059: 십의 자리 구간 분포 분석 (Decade Distribution Analysis)

## 개요

각 회차의 본번호 6개(보너스 제외)가 십의 자리(tens digit)를 기준으로 한 5개
구간 그룹 중 어디에 속하는지를 분류하여, 회차별로 각 구간에 몇 개의 번호가
들어가는지를 집계한다. 전체 회차에 걸친 구간별 평균 개수, 이론적 기댓값과의
편차, 개수별 분포(0..6)를 산출하고, 평균 개수가 가장 높은 구간과 가장 낮은
구간을 서버 렌더링 테이블과 JSON API로 제공한다.

로또 번호 범위 1~45의 5개 십의 자리 구간:

- "01-09": 번호 1~9 (9개)
- "10-19": 번호 10~19 (10개)
- "20-29": 번호 20~29 (10개)
- "30-39": 번호 30~39 (10개)
- "40-45": 번호 40~45 (6개)

구간 크기 합계: 9 + 10 + 10 + 10 + 6 = 45 (전체 번호 수와 일치).
회차당 산출: 각 구간의 count(0..6). 다섯 구간 count의 합은 항상 6(본번호 개수)이다.

## 배경

기존 통계 기능은 번호 출현 빈도(SPEC-LOTTO-001대), 합계 분포
(SPEC-LOTTO-049), 끝자리 분포(last-digit), 간격 패턴(SPEC-LOTTO-056),
AC값(SPEC-LOTTO-057), 소수/합성수 분포(SPEC-LOTTO-058) 등을 다룬다. 십의 자리
구간 분포는 번호를 십의 자리 기준 구간으로 나눈다는 점에서 끝자리 분포와
상보적이며, "당첨 조합이 특정 십의 자리 대(예: 10번대)에 얼마나 몰리는가" 같은
직관적 질문에 답한다.

기존 `lotto/*.py` 코어 모듈은 수정하지 않고, `lotto/web/data.py`에 신규 분석
함수를 추가하는 기존 패턴(get_last_digit_stats, get_gap_stats, get_ac_stats,
get_prime_stats 등)을 그대로 따른다.

## 용어 정의

- 본번호: 회차당 보너스를 제외한 6개 메인 번호
- 십의 자리 구간(decade group): 번호를 십의 자리 기준으로 나눈 5개 구간
  - "01-09"(번호 1~9, size 9), "10-19"(10~19, size 10), "20-29"(20~29, size 10),
    "30-39"(30~39, size 10), "40-45"(40~45, size 6)
- size: 해당 구간에 속하는 로또 번호의 개수 (9, 10, 10, 10, 6)
- count: 한 회차 본번호 중 해당 구간에 속하는 번호의 개수 (0..6)
- avg_count: 전체 회차에 걸친 해당 구간 count의 평균 (2 decimals)
- expected_avg: 이론적 기댓값 = (size / 45) * 6 (2 decimals)
- deviation: avg_count - expected_avg (2 decimals)
- distribution: 해당 구간 count 값(0..6)별 회차 수 매핑

## 요구사항 (EARS)

### Ubiquitous Requirements

- REQ-DC-001: The system SHALL provide `get_decade_stats(draws)` returning
  total_draws, groups (list of 5 group dicts), most_frequent_group, and
  least_frequent_group.
- REQ-DC-002: The system SHALL classify each main number into exactly one of
  five decade groups by tens-digit range — "01-09"(1-9), "10-19"(10-19),
  "20-29"(20-29), "30-39"(30-39), "40-45"(40-45) — such that for every draw the
  sum of all five group counts == 6.
- REQ-DC-003: Each group dict SHALL contain label, size, avg_count(2 decimals),
  expected_avg(2 decimals), deviation(2 decimals), and distribution, in the
  fixed group order: "01-09", "10-19", "20-29", "30-39", "40-45".
- REQ-DC-004: The size SHALL be the fixed count of lotto numbers in each group
  (9, 10, 10, 10, 6 respectively).
- REQ-DC-005: The avg_count for a group SHALL be the mean of every draw's count
  for that group across all aggregated draws, rounded to 2 decimals.
- REQ-DC-006: The expected_avg for a group SHALL be (size / 45) * 6 rounded to
  2 decimals (i.e., 1.2, 1.33, 1.33, 1.33, 0.8).
- REQ-DC-007: The deviation for a group SHALL be (avg_count - expected_avg)
  computed from the unrounded means and rounded to 2 decimals.
- REQ-DC-008: The distribution for a group SHALL be a mapping from each count
  value 0..6 to the number of draws having that count for the group, with every
  key 0..6 present (zero counts included).
- REQ-DC-009: The most_frequent_group SHALL be the label of the group with the
  highest avg_count, breaking ties by the earlier group in the fixed group
  order; least_frequent_group SHALL be the label with the lowest avg_count,
  breaking ties by the earlier group in the fixed group order.
- REQ-DC-010: The system SHALL expose `GET /api/stats/decade` returning the
  decade distribution analysis as JSON (always 200).
- REQ-DC-011: The system SHALL expose `GET /stats/decade` rendering a
  server-side page with a per-group table (label, size, avg_count,
  expected_avg, deviation) and a per-group count distribution table.

### Event-driven Requirements

- REQ-DC-012: WHEN classifying a draw, the system SHALL use only the 6 main
  numbers and exclude the bonus number entirely.
- REQ-DC-013: WHEN assigning a number to a group, the system SHALL place
  numbers 1-9 in "01-09", 10-19 in "10-19", 20-29 in "20-29", 30-39 in
  "30-39", and 40-45 in "40-45".

### State-driven Requirements

- REQ-DC-014: WHILE no draw data is available, `get_decade_stats` SHALL return
  total_draws=0, groups containing all 5 groups with avg_count=0, deviation
  equal to (0 - expected_avg) rounded to 2 decimals, distribution with all keys
  0..6 mapped to 0, and most_frequent_group / least_frequent_group set to the
  first group label ("01-09"); both endpoints SHALL still return 200 and the
  page SHALL render an empty state.

### Unwanted Behavior Requirements

- REQ-DC-015: The data layer SHALL NOT mutate the input draws list nor modify
  any existing `lotto/*.py` core module.
- REQ-DC-016: IF a draw exposes fewer than 6 main numbers, THEN the system
  SHALL skip that draw from aggregation rather than raising.

### Optional Requirements

- REQ-DC-017: Where a memory cache is used, the system SHALL store the computed
  result in `_decade_cache: dict[str, Any]` keyed by `str(len(draws))` and clear
  it in `invalidate_cache()`, consistent with existing cache patterns in
  `data.py`.

## 비기능 요구사항

- Python 3.9 호환 (match/case 금지, `zip(strict=...)` 금지 — 필요 시 `# noqa: B905`)
- 서버 사이드 렌더링 전용 (JavaScript 사용 금지)
- 결정적 — 동일 입력에 동일 출력
- 테스트는 `tests/test_decade_analysis.py`에 작성하고 `mypy.ini` override 목록에 등록

## 인수 기준

acceptance.md 참조.

## Exclusions (What NOT to Build)

- 보너스 번호를 포함한 구간 분류 (본번호 6개만 대상)
- 회차 시계열에 따른 구간 분포 추세(연도별 평균 변화)
- 사용자 입력 조합의 구간 분포 평가 체커 (별도 SPEC으로 분리)
- 추천 엔진과의 자동 연동(구간 분포 필터/가중치)
- 구간 분포 시각화 차트(막대/그래프) — 표 형태만 제공
- 구간 분포와 다른 지표(합계, 간격, AC, 끝자리)의 상관관계 교차 분석
- 구간 경계 커스터마이즈(사용자 정의 구간 폭) — 5개 고정 구간만 제공
- 카이제곱 등 통계적 유의성 검정 — 평균/편차 수치만 제공
- JavaScript 기반 인터랙션 또는 클라이언트 측 계산
