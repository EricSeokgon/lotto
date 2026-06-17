---
id: SPEC-LOTTO-057
version: 0.1.0
status: completed
created: 2026-06-09
updated: 2026-06-09
author: ircp
priority: medium
---

# SPEC-LOTTO-057: AC값(산술 복잡도) 분석 (Arithmetic Complexity Analysis)

## 개요

각 회차의 본번호 6개(보너스 제외)에 대해 AC값(Arithmetic Complexity, 산술
복잡도)을 산출하여 당첨 조합이 얼마나 "분산"되어 있는지를 정량화한다.

AC값 계산 절차:
1. 본번호 6개를 오름차순 정렬한다.
2. 모든 쌍의 차이를 구한다 — i < j에 대해 `numbers[j] - numbers[i]`,
   총 C(6,2) = 15개의 차이.
3. 서로 다른(unique) 차이의 개수를 센다 → U.
4. AC = U - 5.

AC값 범위는 0(모든 간격이 동일)부터 10(15개 차이가 모두 서로 다름)까지이다.

예시: [2, 6, 13, 16, 32, 38]
- 정렬: [2, 6, 13, 16, 32, 38]
- 서로 다른 차이: {3,4,6,7,10,11,14,16,19,22,25,26,30,32,36} → U=15
- AC = 15 - 5 = 10

전체 회차에 걸친 평균 AC, AC값별 분포(0..10)와 비율, 최빈 AC값, 고AC(>=7)/
저AC(<=3) 회차 수와 비율을 집계하여 서버 렌더링 테이블과 JSON API로 제공한다.

## 배경

기존 통계 기능은 번호 출현 빈도(SPEC-LOTTO-001대), 합계 분포
(SPEC-LOTTO-049), 끝자리 분포(last-digit), 간격 패턴(SPEC-LOTTO-056) 등을
다룬다. AC값은 조합 내부 차이의 "다양성"을 단일 지표로 압축한다는 점에서
간격 분석과 상보적이다. 동일한 간격 구조(예: 등차수열)는 낮은 AC를, 불규칙한
분포는 높은 AC를 갖는다.

기존 `lotto/*.py` 코어 모듈은 수정하지 않고, `lotto/web/data.py`에 신규
분석 함수를 추가하는 기존 패턴(get_last_digit_stats, get_gap_stats,
sum_range_analysis 등)을 그대로 따른다.

## 용어 정의

- 본번호: 회차당 보너스를 제외한 6개 메인 번호
- 쌍 차이(pairwise difference): 정렬된 본번호에서 i < j인 모든 쌍의
  `sorted[j] - sorted[i]` (회차당 C(6,2)=15개)
- U: 한 회차의 서로 다른 쌍 차이 개수 (5 ≤ U ≤ 15)
- AC: U - 5 (0 ≤ AC ≤ 10)
- 고AC(high AC): AC >= 7
- 저AC(low AC): AC <= 3

## 요구사항 (EARS)

### Ubiquitous Requirements

- REQ-AC-001: The system SHALL provide `get_ac_stats(draws)` returning
  total_draws, avg_ac(2 decimals), ac_distribution, ac_distribution_pct,
  most_common_ac, high_ac_count, high_ac_pct(2 decimals), low_ac_count,
  low_ac_pct(2 decimals).
- REQ-AC-002: The system SHALL compute a single draw's AC as
  `(count of unique pairwise differences among the 6 sorted main numbers) - 5`,
  yielding an integer in the closed range [0, 10].
- REQ-AC-003: The avg_ac SHALL be the mean of every draw's AC across all
  aggregated draws, rounded to 2 decimals.
- REQ-AC-004: The ac_distribution SHALL be a mapping from each AC value 0..10
  to the count of draws having that AC value, with every key 0..10 present
  (zero counts included).
- REQ-AC-005: The ac_distribution_pct SHALL be a mapping from each AC value
  0..10 to (count / total_draws * 100) rounded to 2 decimals, with every key
  0..10 present.
- REQ-AC-006: The most_common_ac SHALL be the AC value with the highest draw
  count, breaking ties by the smaller AC value first.
- REQ-AC-007: The high_ac_count SHALL be the number of draws with AC >= 7 and
  high_ac_pct SHALL be high_ac_count / total_draws * 100 rounded to 2 decimals.
- REQ-AC-008: The low_ac_count SHALL be the number of draws with AC <= 3 and
  low_ac_pct SHALL be low_ac_count / total_draws * 100 rounded to 2 decimals.
- REQ-AC-009: The system SHALL expose `GET /api/stats/ac` returning the AC
  analysis as JSON (always 200).
- REQ-AC-010: The system SHALL expose `GET /stats/ac` rendering a server-side
  page with summary cards and an AC value distribution table (AC value, count,
  percentage).

### Event-driven Requirements

- REQ-AC-011: WHEN computing AC for a draw, the system SHALL sort the 6 main
  numbers ascending and exclude the bonus number entirely.
- REQ-AC-012: WHEN forming pairwise differences, the system SHALL include all
  C(6,2)=15 ordered pairs (i < j) before counting unique values.

### State-driven Requirements

- REQ-AC-013: WHILE no draw data is available, `get_ac_stats` SHALL return
  total_draws=0, avg_ac=0, ac_distribution with all keys 0..10 mapped to 0,
  ac_distribution_pct with all keys 0..10 mapped to 0, most_common_ac=0,
  high_ac_count=0, high_ac_pct=0, low_ac_count=0, low_ac_pct=0; both endpoints
  SHALL still return 200 and the page SHALL render an empty state.

### Unwanted Behavior Requirements

- REQ-AC-014: The data layer SHALL NOT mutate the input draws list nor modify
  any existing `lotto/*.py` core module.
- REQ-AC-015: IF a draw exposes fewer than 6 main numbers, THEN the system
  SHALL skip that draw from AC aggregation rather than raising.

### Optional Requirements

- REQ-AC-016: Where a memory cache is used, the system SHALL store the computed
  result in `_ac_cache: dict[str, Any]` keyed by `str(len(draws))` and clear it
  in `invalidate_cache()`, consistent with existing cache patterns in `data.py`.

## 비기능 요구사항

- Python 3.9 호환 (match/case 금지, `zip(strict=...)` 금지 — 필요 시 `# noqa: B905`)
- 서버 사이드 렌더링 전용 (JavaScript 사용 금지)
- 결정적 — 동일 입력에 동일 출력
- 테스트는 `tests/test_ac_analysis.py`에 작성하고 `mypy.ini` override 목록에 등록

## 인수 기준

acceptance.md 참조.

## Exclusions (What NOT to Build)

- 보너스 번호를 포함한 AC값 분석 (본번호 6개만 대상)
- 회차 시계열에 따른 AC 추세(연도별 평균 AC 변화)
- 사용자 입력 조합의 AC 평가 체커 (별도 SPEC으로 분리)
- 추천 엔진과의 자동 연동(AC 필터/가중치)
- AC 분포 시각화 차트(막대/그래프) — 표 형태만 제공
- AC와 다른 지표(합계, 간격)의 상관관계 교차 분석
- JavaScript 기반 인터랙션 또는 클라이언트 측 계산
