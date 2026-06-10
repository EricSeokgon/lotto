---
id: SPEC-LOTTO-060
version: 0.1.0
status: Planned
created: 2026-06-10
updated: 2026-06-10
author: ircp
priority: medium
---

# SPEC-LOTTO-060: 홀짝 비율 분석 (Odd/Even Ratio Analysis)

## 개요

각 회차의 본번호 6개(보너스 제외)가 홀수(odd)인지 짝수(even)인지 분류하여,
회차별 홀수 개수·짝수 개수를 집계한다. 전체 회차에 걸친 평균 홀수/짝수 개수,
개수별 분포(0..6)와 비율, 최빈 개수, 균형 회차(홀수==짝수, 즉 3:3) 수와 비율을
서버 렌더링 테이블과 JSON API로 제공한다.

로또 번호 범위 1~45의 분류:

- 홀수(23개): 1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33,
  35, 37, 39, 41, 43, 45
- 짝수(22개): 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34,
  36, 38, 40, 42, 44

회차당 산출: odd_count(0..6), even_count(0..6).
두 값의 합은 항상 6 (본번호 개수)이며 even_count == 6 - odd_count이다.

## 배경

기존 통계 기능은 끝자리 분포(SPEC-LOTTO-055), 번호 간격(SPEC-LOTTO-056),
AC값(SPEC-LOTTO-057), 소수/합성수(SPEC-LOTTO-058), 십의 자리 구간
(SPEC-LOTTO-059) 등을 다룬다. 홀짝 비율은 번호를 패리티(parity) 두 부류로
나눈다는 점에서 기존 지표들과 상보적이며, "당첨 조합의 홀짝 균형은 어떤가",
"홀짝 3:3 균형 조합이 얼마나 자주 나오는가" 같은 직관적 질문에 답한다.

기존 `lotto/*.py` 코어 모듈은 수정하지 않고, `lotto/web/data.py`에 신규
분석 함수를 추가하는 기존 패턴(get_last_digit_stats, get_gap_stats,
get_ac_stats, get_prime_stats, get_decade_stats 등)을 그대로 따른다.

## 용어 정의

- 본번호: 회차당 보너스를 제외한 6개 메인 번호
- 홀수(odd): 2로 나눈 나머지가 1인 정수. 1~45 범위에서 23개
  {1,3,5,...,43,45}
- 짝수(even): 2로 나눈 나머지가 0인 정수. 1~45 범위에서 22개
  {2,4,6,...,44}
- odd_count: 한 회차 본번호 중 홀수의 개수 (0..6)
- even_count: 한 회차 본번호 중 짝수의 개수 (0..6), 항상 6 - odd_count
- balanced(균형) 회차: 홀수 개수와 짝수 개수가 같은 회차, 즉 정확히 홀 3 / 짝 3
  인 회차

## 요구사항 (EARS)

### Ubiquitous Requirements

- REQ-OE-001: The system SHALL provide `get_odd_even_stats(draws)` returning
  total_draws, avg_odd(2 decimals), avg_even(2 decimals), odd_distribution,
  even_distribution, most_common_odd_count, most_common_even_count,
  balanced_count, balanced_pct(2 decimals), odd_distribution_pct,
  even_distribution_pct.
- REQ-OE-002: The system SHALL classify each main number as either odd or even
  such that for every draw odd_count + even_count == 6 and
  even_count == 6 - odd_count.
- REQ-OE-003: The avg_odd SHALL be the mean of every draw's odd_count across
  all aggregated draws, rounded to 2 decimals; avg_even SHALL be the mean of
  every draw's even_count, rounded to 2 decimals.
- REQ-OE-004: The odd_distribution SHALL be a mapping from each odd_count value
  0..6 to the count of draws having that odd_count, with every key 0..6 present
  (zero counts included).
- REQ-OE-005: The even_distribution SHALL be a mapping from each even_count
  value 0..6 to the count of draws having that even_count, with every key 0..6
  present (zero counts included).
- REQ-OE-006: The odd_distribution_pct SHALL be a mapping from each odd_count
  value 0..6 to (count / total_draws * 100) rounded to 2 decimals, with every
  key 0..6 present; even_distribution_pct SHALL be the analogous mapping for
  even_count.
- REQ-OE-007: The most_common_odd_count SHALL be the odd_count value with the
  highest draw count, breaking ties by the smaller odd_count value first;
  most_common_even_count SHALL be the analogous value for even_count.
- REQ-OE-008: The balanced_count SHALL be the number of draws where
  odd_count == even_count (i.e. exactly 3 odd and 3 even), and balanced_pct
  SHALL be balanced_count / total_draws * 100 rounded to 2 decimals.
- REQ-OE-009: The system SHALL expose `GET /api/stats/odd-even` returning the
  odd/even analysis as JSON (always 200).
- REQ-OE-010: The system SHALL expose `GET /stats/odd-even` rendering a
  server-side page with summary cards and a distribution table (odd count
  0..6 with count and percentage), a balanced-draw highlight, and average
  odd/even values.

### Event-driven Requirements

- REQ-OE-011: WHEN classifying a draw, the system SHALL use only the 6 main
  numbers and exclude the bonus number entirely.
- REQ-OE-012: WHEN counting even_count for a draw, the system SHALL derive it
  as 6 - odd_count rather than independently classifying, ensuring the sum
  invariant holds for any 6-number draw.

### State-driven Requirements

- REQ-OE-013: WHILE no draw data is available, `get_odd_even_stats` SHALL
  return total_draws=0, avg_odd=0, avg_even=0, odd_distribution with all keys
  0..6 mapped to 0, even_distribution with all keys 0..6 mapped to 0,
  odd_distribution_pct with all keys 0..6 mapped to 0, even_distribution_pct
  with all keys 0..6 mapped to 0, most_common_odd_count=0,
  most_common_even_count=0, balanced_count=0, balanced_pct=0; both endpoints
  SHALL still return 200 and the page SHALL render an empty state.

### Unwanted Behavior Requirements

- REQ-OE-014: The data layer SHALL NOT mutate the input draws list nor modify
  any existing `lotto/*.py` core module.
- REQ-OE-015: IF a draw exposes fewer than 6 main numbers, THEN the system
  SHALL skip that draw from aggregation rather than raising.

### Optional Requirements

- REQ-OE-016: Where a memory cache is used, the system SHALL store the computed
  result in `_odd_even_cache: dict[str, Any]` keyed by `str(len(draws))` and
  clear it in `invalidate_cache()`, consistent with existing cache patterns in
  `data.py`.

## 비기능 요구사항

- Python 3.9 호환 (match/case 금지, `zip(strict=...)` 금지 — 필요 시 `# noqa: B905`)
- 서버 사이드 렌더링 전용 (JavaScript 사용 금지)
- 결정적 — 동일 입력에 동일 출력
- 테스트는 `tests/test_odd_even_analysis.py`에 작성하고 `mypy.ini` override
  목록에 `test_odd_even_analysis` 등록
- 네비게이션: `base.html`에 "홀짝 분석" → `/stats/odd-even` 링크 추가

## 인수 기준

acceptance.md 참조.

## Exclusions (What NOT to Build)

- 보너스 번호를 포함한 홀짝 분류 (본번호 6개만 대상)
- 회차 시계열에 따른 홀짝 비율 추세(연도별 평균 변화)
- 사용자 입력 조합의 홀짝 균형 평가 체커 (별도 SPEC으로 분리)
- 추천 엔진과의 자동 연동(홀짝 비율 필터/가중치)
- 홀짝 분포 시각화 차트(막대/그래프) — 표 형태만 제공
- 홀짝 비율과 다른 지표(합계, 간격, AC, 소수)의 상관관계 교차 분석
- "홀:짝 = N:M" 패턴별 조합 추천 또는 생성
- JavaScript 기반 인터랙션 또는 클라이언트 측 계산
