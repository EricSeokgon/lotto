---
id: SPEC-LOTTO-061
version: 0.1.0
status: Completed
created: 2026-06-10
updated: 2026-06-10
author: ircp
priority: medium
---

# SPEC-LOTTO-061: 고저 비율 분석 (High/Low Number Ratio Analysis)

## 개요

각 회차의 본번호 6개(보너스 제외)가 저(low)번호인지 고(high)번호인지 분류하여,
회차별 저번호 개수·고번호 개수를 집계한다. 전체 회차에 걸친 평균 저/고 개수,
개수별 분포(0..6)와 비율, 최빈 개수, 균형 회차(저==고, 즉 3:3) 수와 비율을
서버 렌더링 테이블과 JSON API로 제공한다.

로또 번호 범위 1~45의 분류:

- 저번호(low, 22개): 1, 2, 3, ..., 22
- 고번호(high, 23개): 23, 24, 25, ..., 45

회차당 산출: low_count(0..6), high_count(0..6).
두 값의 합은 항상 6 (본번호 개수)이며 high_count == 6 - low_count이다.

## 배경

기존 통계 기능은 끝자리 분포(SPEC-LOTTO-055), 번호 간격(SPEC-LOTTO-056),
AC값(SPEC-LOTTO-057), 소수/합성수(SPEC-LOTTO-058), 십의 자리 구간
(SPEC-LOTTO-059), 홀짝 비율(SPEC-LOTTO-060) 등을 다룬다. 고저 비율은 번호를
번호 크기 기준 두 부류로 나눈다는 점에서 홀짝(패리티)·구간 분포(십의 자리)와
상보적이며, "당첨 조합의 고저 균형은 어떤가", "저:고 3:3 균형 조합이 얼마나 자주
나오는가" 같은 직관적 질문에 답한다.

기존 `lotto/*.py` 코어 모듈은 수정하지 않고, `lotto/web/data.py`에 신규
분석 함수를 추가하는 기존 패턴(get_last_digit_stats, get_gap_stats,
get_ac_stats, get_prime_stats, get_decade_stats, get_odd_even_stats 등)을
그대로 따른다.

## 용어 정의

- 본번호: 회차당 보너스를 제외한 6개 메인 번호
- 저번호(low): 1 이상 22 이하의 정수. 1~45 범위에서 22개 {1,2,...,22}
- 고번호(high): 23 이상 45 이하의 정수. 1~45 범위에서 23개 {23,24,...,45}
- low_count: 한 회차 본번호 중 저번호의 개수 (0..6)
- high_count: 한 회차 본번호 중 고번호의 개수 (0..6), 항상 6 - low_count
- balanced(균형) 회차: 저번호 개수와 고번호 개수가 같은 회차, 즉 정확히
  저 3 / 고 3 인 회차

## 요구사항 (EARS)

### Ubiquitous Requirements

- REQ-HL-001: The system SHALL provide `get_high_low_stats(draws)` returning
  total_draws, avg_low(2 decimals), avg_high(2 decimals), low_distribution,
  high_distribution, most_common_low_count, most_common_high_count,
  balanced_count, balanced_pct(2 decimals), low_distribution_pct,
  high_distribution_pct.
- REQ-HL-002: The system SHALL classify each main number as either low (1..22)
  or high (23..45) such that for every draw low_count + high_count == 6 and
  high_count == 6 - low_count.
- REQ-HL-003: The avg_low SHALL be the mean of every draw's low_count across
  all aggregated draws, rounded to 2 decimals; avg_high SHALL be the mean of
  every draw's high_count, rounded to 2 decimals.
- REQ-HL-004: The low_distribution SHALL be a mapping from each low_count value
  0..6 to the count of draws having that low_count, with every key 0..6 present
  (zero counts included).
- REQ-HL-005: The high_distribution SHALL be a mapping from each high_count
  value 0..6 to the count of draws having that high_count, with every key 0..6
  present (zero counts included).
- REQ-HL-006: The low_distribution_pct SHALL be a mapping from each low_count
  value 0..6 to (count / total_draws * 100) rounded to 2 decimals, with every
  key 0..6 present; high_distribution_pct SHALL be the analogous mapping for
  high_count.
- REQ-HL-007: The most_common_low_count SHALL be the low_count value with the
  highest draw count, breaking ties by the smaller low_count value first;
  most_common_high_count SHALL be the analogous value for high_count.
- REQ-HL-008: The balanced_count SHALL be the number of draws where
  low_count == high_count (i.e. exactly 3 low and 3 high), and balanced_pct
  SHALL be balanced_count / total_draws * 100 rounded to 2 decimals.
- REQ-HL-009: The system SHALL expose `GET /api/stats/high-low` returning the
  high/low analysis as JSON (always 200).
- REQ-HL-010: The system SHALL expose `GET /stats/high-low` rendering a
  server-side page with summary cards and a distribution table (low count
  0..6 with count and percentage), a balanced-draw highlight, and average
  low/high values.

### Event-driven Requirements

- REQ-HL-011: WHEN classifying a draw, the system SHALL use only the 6 main
  numbers and exclude the bonus number entirely.
- REQ-HL-012: WHEN counting high_count for a draw, the system SHALL derive it
  as 6 - low_count rather than independently classifying, ensuring the sum
  invariant holds for any 6-number draw.

### State-driven Requirements

- REQ-HL-013: WHILE no draw data is available, `get_high_low_stats` SHALL
  return total_draws=0, avg_low=0, avg_high=0, low_distribution with all keys
  0..6 mapped to 0, high_distribution with all keys 0..6 mapped to 0,
  low_distribution_pct with all keys 0..6 mapped to 0, high_distribution_pct
  with all keys 0..6 mapped to 0, most_common_low_count=0,
  most_common_high_count=0, balanced_count=0, balanced_pct=0; both endpoints
  SHALL still return 200 and the page SHALL render an empty state.

### Unwanted Behavior Requirements

- REQ-HL-014: The data layer SHALL NOT mutate the input draws list nor modify
  any existing `lotto/*.py` core module.
- REQ-HL-015: IF a draw exposes fewer than 6 main numbers, THEN the system
  SHALL skip that draw from aggregation rather than raising.

### Optional Requirements

- REQ-HL-016: Where a memory cache is used, the system SHALL store the computed
  result in `_high_low_cache: dict[str, Any]` keyed by `str(len(draws))` and
  clear it in `invalidate_cache()`, consistent with existing cache patterns in
  `data.py`.

## 비기능 요구사항

- Python 3.9 호환 (match/case 금지, `zip(strict=...)` 금지 — 필요 시 `# noqa: B905`)
- 서버 사이드 렌더링 전용 (JavaScript 사용 금지)
- 결정적 — 동일 입력에 동일 출력
- 테스트는 `tests/test_high_low_analysis.py`에 작성하고 `mypy.ini` override
  목록에 `test_high_low_analysis` 등록
- 네비게이션: `base.html`에 "고저 분석" → `/stats/high-low` 링크를 데스크톱과
  모바일 네비게이션 양쪽에 추가

## 인수 기준

acceptance.md 참조.

## Exclusions (What NOT to Build)

- 보너스 번호를 포함한 고저 분류 (본번호 6개만 대상)
- 저/고 경계값(1-22 vs 23-45) 외 다른 분할 기준(예: 1-15/16-30/31-45 3분할)
  — 3분할은 십의 자리 구간(SPEC-LOTTO-059)에서 별도로 다룸
- 회차 시계열에 따른 고저 비율 추세(연도별 평균 변화)
- 사용자 입력 조합의 고저 균형 평가 체커 (별도 SPEC으로 분리)
- 추천 엔진과의 자동 연동(고저 비율 필터/가중치)
- 고저 분포 시각화 차트(막대/그래프) — 표 형태만 제공
- 고저 비율과 다른 지표(합계, 간격, AC, 소수, 홀짝)의 상관관계 교차 분석
- "저:고 = N:M" 패턴별 조합 추천 또는 생성
- JavaScript 기반 인터랙션 또는 클라이언트 측 계산
