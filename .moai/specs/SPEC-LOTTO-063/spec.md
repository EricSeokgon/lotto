---
id: SPEC-LOTTO-063
version: 0.1.0
status: completed
created: 2026-06-10
updated: 2026-06-10
author: ircp
priority: medium
---

# SPEC-LOTTO-063: 끝자리 합계 분석 (Last Digit Sum Analysis)

## 개요

각 회차의 본번호 6개(보너스 제외)에 대해 각 번호의 끝자리(`n % 10`)를 더한
"끝자리 합계(last_digit_sum)"를 회차별로 산출한다. 끝자리 합계의 평균·최소·최대,
출현한 합계값의 분포, 최빈 합계값, 그리고 저(low, <15)·중(mid, 15~29)·고(high, ≥30)
세 구간별 회차 수와 비율을 서버 렌더링 테이블과 JSON API로 제공한다.

회차당 산출값:

- last_digit_sum: 본번호 6개 각각의 (n % 10)을 모두 더한 값. 이론적 범위는 0~54
  (6 × 최대 끝자리 9). 단, 1~45 번호 제약상 실제 분포는 더 좁다.

## 배경

기존 통계 기능은 끝자리 분포(SPEC-LOTTO-055), 번호 간격(SPEC-LOTTO-056),
AC값(SPEC-LOTTO-057), 소수/합성수(SPEC-LOTTO-058), 십의 자리 구간
(SPEC-LOTTO-059), 홀짝 비율(SPEC-LOTTO-060), 고저 비율(SPEC-LOTTO-061),
연속 번호 패턴(SPEC-LOTTO-062) 등을 다룬다. 본 SPEC은 이 "통계 분석(stats)"
계열의 일관된 패턴(`get_<topic>_stats` 함수 + `str(len(draws))` 캐시 + 3계층
라우트)을 그대로 따른다.

### SPEC-LOTTO-055와의 관계 (혼동 방지)

코드베이스에는 이미 SPEC-LOTTO-055에서 구현한 "끝자리 분포" 분석이 존재하며
라우트 `/stats/last-digit`, 네비게이션 "끝자리 분포"를 사용한다. 본 SPEC-063은
SPEC-055와 **별개**이며 함께 공존한다:

| 항목 | SPEC-055 끝자리 분포 (`/stats/last-digit`) | SPEC-063 끝자리 합계 (본 SPEC) |
|------|-------------------------------------------|--------------------------------|
| 집계 단위 | 끝자리(0~9)별 출현 빈도 | 회차별 끝자리 합계(0~54) |
| 주요 질문 | "어떤 끝자리가 자주 나오는가" | "한 회차의 끝자리 총합은 얼마인가" |
| 라우트 | `/stats/last-digit` | `/stats/last-digit-sum` |
| 네비 | "끝자리 분포" | "끝합 분석" |

본 SPEC은 SPEC-055 코드를 수정·병합·리팩터링하지 않는다(Exclusions 참조).
기존 `lotto/*.py` 코어 모듈도 수정하지 않고 `lotto/web/data.py`에 신규 함수만
추가한다.

## 용어 정의

- 본번호: 회차당 보너스를 제외한 6개 메인 번호
- 끝자리(last digit): 한 번호의 일의 자리 값 = `n % 10` (예: 33 → 3, 40 → 0)
- 끝자리 합계(last_digit_sum): 한 회차 본번호 6개의 끝자리를 모두 더한 값.
  이론적 범위 0~54
- 저 구간(low): last_digit_sum < 15
- 중 구간(mid): 15 ≤ last_digit_sum ≤ 29
- 고 구간(high): last_digit_sum ≥ 30

## 요구사항 (EARS)

### Ubiquitous Requirements

- REQ-LDS-001: The system SHALL provide `get_last_digit_sum_stats(draws)`
  returning total_draws, avg_sum(2 decimals), min_sum, max_sum,
  sum_distribution, most_common_sum, low_sum_count, mid_sum_count,
  high_sum_count, low_sum_pct(2 decimals), mid_sum_pct(2 decimals),
  high_sum_pct(2 decimals).
- REQ-LDS-002: For each draw the system SHALL compute last_digit_sum as the sum
  of (n % 10) over the 6 main numbers.
- REQ-LDS-003: The avg_sum SHALL be the mean of every draw's last_digit_sum
  across all aggregated draws, rounded to 2 decimals.
- REQ-LDS-004: The min_sum SHALL be the minimum last_digit_sum observed and
  max_sum SHALL be the maximum last_digit_sum observed across all aggregated
  draws.
- REQ-LDS-005: The sum_distribution SHALL be a mapping {sum_value: count}
  containing only sum values that actually appear (no zero-filled keys).
- REQ-LDS-006: The most_common_sum SHALL be the sum value with the highest draw
  count, breaking ties by the smaller sum value first.
- REQ-LDS-007: The low_sum_count SHALL be the number of draws with
  last_digit_sum < 15, mid_sum_count the number with 15 ≤ last_digit_sum ≤ 29,
  and high_sum_count the number with last_digit_sum ≥ 30. The three counts SHALL
  partition all aggregated draws (low + mid + high == total_draws).
- REQ-LDS-008: The low_sum_pct, mid_sum_pct, high_sum_pct SHALL be each category
  count divided by total_draws times 100, rounded to 2 decimals.
- REQ-LDS-009: The system SHALL expose `GET /api/stats/last-digit-sum`
  returning the last digit sum analysis as JSON (always 200).
- REQ-LDS-010: The system SHALL expose `GET /stats/last-digit-sum` rendering a
  server-side page with summary cards (average / min / max sum, low/mid/high
  category counts and percentages) and a distribution table of the top-20 most
  frequent sum values.

### Event-driven Requirements

- REQ-LDS-011: WHEN analyzing a draw, the system SHALL use only the 6 main
  numbers and exclude the bonus number entirely.
- REQ-LDS-012: WHEN computing the last digit of a number, the system SHALL use
  `n % 10` so that numbers ending in 0 (e.g. 10, 20, 30, 40) contribute 0.

### State-driven Requirements

- REQ-LDS-013: WHILE no draw data is available, `get_last_digit_sum_stats` SHALL
  return total_draws=0, avg_sum=0, min_sum=0, max_sum=0, sum_distribution={},
  most_common_sum=0, low_sum_count=0, mid_sum_count=0, high_sum_count=0,
  low_sum_pct=0, mid_sum_pct=0, high_sum_pct=0; both endpoints SHALL still
  return 200 and the page SHALL render an empty state.

### Unwanted Behavior Requirements

- REQ-LDS-014: The data layer SHALL NOT mutate the input draws list, SHALL NOT
  modify any existing `lotto/*.py` core module, and SHALL NOT modify, merge
  with, or refactor the existing SPEC-LOTTO-055 last-digit distribution feature
  or its helpers.
- REQ-LDS-015: IF a draw exposes fewer than 6 main numbers, THEN the system
  SHALL skip that draw from aggregation rather than raising.

### Optional Requirements

- REQ-LDS-016: Where a memory cache is used, the system SHALL store the computed
  result in `_last_digit_sum_cache: dict[str, Any]` keyed by `str(len(draws))`
  and clear it in `invalidate_cache()`, consistent with existing cache patterns
  in `data.py` (e.g. `_odd_even_cache`, `_high_low_cache`).

## 비기능 요구사항

- Python 3.9 호환 (match/case 금지, `zip(strict=...)` 금지 — 필요 시 `# noqa: B905`)
- 서버 사이드 렌더링 전용 (JavaScript 사용 금지)
- 결정적 — 동일 입력에 동일 출력
- 테스트는 `tests/test_last_digit_sum_analysis.py`에 작성하고 최소 20개
- `mypy.ini` override 목록에 `test_last_digit_sum_analysis` 등록
- 네비게이션: `base.html`에 "끝합 분석" → `/stats/last-digit-sum` 링크를
  데스크톱과 모바일 네비게이션 양쪽에 추가
- 템플릿 파일명: `last_digit_sum.html` (기존 SPEC-055 끝자리 분포 템플릿과 구별)

## 인수 기준

acceptance.md 참조.

## Exclusions (What NOT to Build)

- SPEC-LOTTO-055 끝자리 분포 기능(`/stats/last-digit`)의 수정·병합·리팩터링
  (두 기능은 독립적으로 공존; 본 SPEC은 신규 함수만 추가)
- 끝자리(0~9)별 출현 빈도 분석 — SPEC-055에서 다룸
- recent_n 최신 N회차 윈도잉 (본 SPEC은 전체 회차만 대상)
- sum_distribution을 전 구간(0~54) 키로 0-채움 — 본 SPEC은 출현한 값만 포함
- 끝자리 합계 분포 전체 표(top-20 초과) — 페이지는 최빈 20개 합계값만 표시
  (API는 전체 sum_distribution 반환)
- 본번호 합계(번호 자체의 합, SPEC-049 합계 분석)와의 혼동/병합 — 본 SPEC은
  끝자리 합계만 대상
- 끝자리 합계와 다른 지표(합계, 간격, AC, 홀짝, 고저, 연속)의 상관관계 교차 분석
- 사용자 입력 조합의 끝자리 합계 평가 체커
- 추천 엔진과의 자동 연동(끝자리 합계 필터/가중치)
- 끝자리 합계 분포 시각화 차트(막대/그래프) — 표 형태만 제공
- 회차 시계열에 따른 끝자리 합계 추세(연도별/구간별 변화)
- JavaScript 기반 인터랙션 또는 클라이언트 측 계산
