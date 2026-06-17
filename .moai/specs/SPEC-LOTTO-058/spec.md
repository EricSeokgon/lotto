---
id: SPEC-LOTTO-058
version: 0.1.0
status: completed
created: 2026-06-09
updated: 2026-06-09
author: ircp
priority: medium
---

# SPEC-LOTTO-058: 소수/합성수 분포 분석 (Prime/Composite Number Distribution Analysis)

## 개요

각 회차의 본번호 6개(보너스 제외)가 소수(prime), 합성수(composite), 그리고
숫자 1 중 어느 부류에 속하는지를 분류하여, 회차별 소수 개수·합성수 개수·1 등장
여부를 집계한다. 전체 회차에 걸친 평균 소수/합성수 개수, 개수별 분포(0..6)와
비율, 최빈 개수, 숫자 1을 포함한 회차 수와 비율을 서버 렌더링 테이블과
JSON API로 제공한다.

로또 번호 범위 1~45의 분류:

- 소수(14개): 2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43
- 합성수(30개): 4, 6, 8, 9, 10, 12, 14, 15, 16, 18, 20, 21, 22, 24, 25, 26,
  27, 28, 30, 32, 33, 34, 35, 36, 38, 39, 40, 42, 44, 45
- 어느 쪽도 아님(1개): 숫자 1 (소수도 합성수도 아님)

회차당 산출: prime_count(0..6), composite_count(0..6), one_count(0..1).
세 값의 합은 항상 6 (본번호 개수)이다.

## 배경

기존 통계 기능은 번호 출현 빈도(SPEC-LOTTO-001대), 합계 분포
(SPEC-LOTTO-049), 끝자리 분포(last-digit), 간격 패턴(SPEC-LOTTO-056),
AC값(SPEC-LOTTO-057) 등을 다룬다. 소수/합성수 분포는 번호를 정수론적 부류로
나눈다는 점에서 기존 지표들과 상보적이며, "당첨 조합에 소수가 평균 몇 개
포함되는가" 같은 직관적 질문에 답한다.

기존 `lotto/*.py` 코어 모듈은 수정하지 않고, `lotto/web/data.py`에 신규
분석 함수를 추가하는 기존 패턴(get_last_digit_stats, get_gap_stats,
get_ac_stats, sum_range_analysis 등)을 그대로 따른다.

## 용어 정의

- 본번호: 회차당 보너스를 제외한 6개 메인 번호
- 소수(prime): 1과 자기 자신만을 약수로 갖는 1보다 큰 정수. 1~45 범위에서
  {2,3,5,7,11,13,17,19,23,29,31,37,41,43} (14개)
- 합성수(composite): 1보다 크면서 소수가 아닌 정수. 1~45 범위에서 30개
- 숫자 1: 소수도 합성수도 아닌 유일한 본번호 후보 (neither)
- prime_count: 한 회차 본번호 중 소수의 개수 (0..6)
- composite_count: 한 회차 본번호 중 합성수의 개수 (0..6)
- one_count: 한 회차 본번호에 숫자 1이 포함되면 1, 아니면 0 (0..1)

## 요구사항 (EARS)

### Ubiquitous Requirements

- REQ-PR-001: The system SHALL provide `get_prime_stats(draws)` returning
  total_draws, avg_prime(2 decimals), avg_composite(2 decimals),
  prime_distribution, prime_distribution_pct, most_common_prime_count,
  composite_distribution, one_appeared_count, one_appeared_pct(2 decimals).
- REQ-PR-002: The system SHALL classify each main number into exactly one of
  three categories — prime, composite, or one (the number 1) — such that for
  every draw prime_count + composite_count + one_count == 6.
- REQ-PR-003: The avg_prime SHALL be the mean of every draw's prime_count
  across all aggregated draws, rounded to 2 decimals; avg_composite SHALL be
  the mean of every draw's composite_count, rounded to 2 decimals.
- REQ-PR-004: The prime_distribution SHALL be a mapping from each prime_count
  value 0..6 to the count of draws having that prime_count, with every key
  0..6 present (zero counts included).
- REQ-PR-005: The prime_distribution_pct SHALL be a mapping from each
  prime_count value 0..6 to (count / total_draws * 100) rounded to 2 decimals,
  with every key 0..6 present.
- REQ-PR-006: The most_common_prime_count SHALL be the prime_count value with
  the highest draw count, breaking ties by the smaller prime_count value first.
- REQ-PR-007: The composite_distribution SHALL be a mapping from each
  composite_count value 0..6 to the count of draws having that composite_count,
  with every key 0..6 present (zero counts included).
- REQ-PR-008: The one_appeared_count SHALL be the number of draws whose main
  numbers contain the number 1, and one_appeared_pct SHALL be
  one_appeared_count / total_draws * 100 rounded to 2 decimals.
- REQ-PR-009: The system SHALL expose `GET /api/stats/prime` returning the
  prime/composite analysis as JSON (always 200).
- REQ-PR-010: The system SHALL expose `GET /stats/prime` rendering a
  server-side page with summary cards and distribution tables (prime count and
  composite count, each with value, count, and percentage).

### Event-driven Requirements

- REQ-PR-011: WHEN classifying a draw, the system SHALL use only the 6 main
  numbers and exclude the bonus number entirely.
- REQ-PR-012: WHEN counting one_count for a draw, the system SHALL set it to 1
  if the number 1 is among the main numbers and 0 otherwise (never greater
  than 1).

### State-driven Requirements

- REQ-PR-013: WHILE no draw data is available, `get_prime_stats` SHALL return
  total_draws=0, avg_prime=0, avg_composite=0, prime_distribution with all keys
  0..6 mapped to 0, prime_distribution_pct with all keys 0..6 mapped to 0,
  most_common_prime_count=0, composite_distribution with all keys 0..6 mapped
  to 0, one_appeared_count=0, one_appeared_pct=0; both endpoints SHALL still
  return 200 and the page SHALL render an empty state.

### Unwanted Behavior Requirements

- REQ-PR-014: The data layer SHALL NOT mutate the input draws list nor modify
  any existing `lotto/*.py` core module.
- REQ-PR-015: IF a draw exposes fewer than 6 main numbers, THEN the system
  SHALL skip that draw from aggregation rather than raising.

### Optional Requirements

- REQ-PR-016: Where a memory cache is used, the system SHALL store the computed
  result in `_prime_cache: dict[str, Any]` keyed by `str(len(draws))` and clear
  it in `invalidate_cache()`, consistent with existing cache patterns in
  `data.py`.

## 비기능 요구사항

- Python 3.9 호환 (match/case 금지, `zip(strict=...)` 금지 — 필요 시 `# noqa: B905`)
- 서버 사이드 렌더링 전용 (JavaScript 사용 금지)
- 결정적 — 동일 입력에 동일 출력
- 테스트는 `tests/test_prime_analysis.py`에 작성하고 `mypy.ini` override 목록에 등록

## 인수 기준

acceptance.md 참조.

## Exclusions (What NOT to Build)

- 보너스 번호를 포함한 소수/합성수 분류 (본번호 6개만 대상)
- 회차 시계열에 따른 소수/합성수 추세(연도별 평균 변화)
- 사용자 입력 조합의 소수/합성수 평가 체커 (별도 SPEC으로 분리)
- 추천 엔진과의 자동 연동(소수 개수 필터/가중치)
- 소수/합성수 분포 시각화 차트(막대/그래프) — 표 형태만 제공
- 소수 개수와 다른 지표(합계, 간격, AC)의 상관관계 교차 분석
- 1~45 범위를 벗어난 일반 정수에 대한 소수 판정 라이브러리화
- JavaScript 기반 인터랙션 또는 클라이언트 측 계산
