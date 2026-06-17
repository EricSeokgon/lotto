---
id: SPEC-LOTTO-064
version: 0.1.0
status: Completed
created: 2026-06-10
updated: 2026-06-10
author: ircp
priority: medium
---

# SPEC-LOTTO-064: 최솟값·최댓값 분포 분석 (Min/Max Number Distribution Analysis)

## 개요

각 회차의 본번호 6개(보너스 제외)에서 최솟값(min_num), 최댓값(max_num),
그리고 범위(range_val = max_num - min_num)를 산출한다. 전체 회차에 걸친
평균 최솟값·평균 최댓값·평균 범위, 최솟값/최댓값/범위 각각의 분포와 최빈값,
그리고 좁은 범위(small, range < 30)·넓은 범위(large, range ≥ 30) 두 구간별
회차 수와 비율을 서버 렌더링 테이블과 JSON API로 제공한다.

회차당 산출값:

- min_num: 본번호 6개 중 최솟값. 번호 범위 1~45이므로 이론적 범위 1~40
  (최솟값이 41 이상이면 6개를 담을 수 없음).
- max_num: 본번호 6개 중 최댓값. 이론적 범위 6~45 (최댓값이 5 이하이면 6개
  서로 다른 번호 불가).
- range_val: max_num - min_num. 이론적 범위 5~44 (6개 연속 [1..6]이면 5,
  [1,2,3,4,5,45]면 44).

## 배경

기존 통계(stats) 계열 기능은 합계(SPEC-LOTTO-049), 간격(SPEC-LOTTO-056),
AC값(SPEC-LOTTO-057), 소수/합성수(SPEC-LOTTO-058), 십의 자리 구간
(SPEC-LOTTO-059), 홀짝(SPEC-LOTTO-060), 고저(SPEC-LOTTO-061), 연속 패턴
(SPEC-LOTTO-062), 끝자리 합계(SPEC-LOTTO-063) 등을 다룬다. 본 SPEC은 이
"통계 분석(stats)" 계열의 일관된 패턴(`get_<topic>_stats` 함수 +
`str(len(draws))` 캐시 + 3계층 라우트)을 그대로 따른다.

### 기존 기능과의 구분 (혼동 방지)

코드베이스에는 "최솟값·최댓값" 분석 기능이 아직 없다(grep 확인: min-max/
min_max/최대최소 등 신규 라우트·함수·네비 없음). 단, 인접 개념과 혼동하지 말 것:

| 항목 | 기존 기능 | SPEC-064 최대최소 (본 SPEC) |
|------|-----------|------------------------------|
| 합계 분석 (SPEC-049) | 본번호 6개의 총합 | 다룸 아님 — 최솟/최댓/범위만 |
| 간격 분석 (SPEC-056) | 인접 번호 간 간격(gap) 분포 | range는 인접 간격이 아닌 max-min |
| 고저 분석 (SPEC-061) | 저/고 경계(22/23) 개수 비율 | 절대 최솟/최댓값과 무관 |

본 SPEC은 기존 코드를 수정·병합·리팩터링하지 않으며 기존 `lotto/*.py` 코어
모듈도 수정하지 않고 `lotto/web/data.py`에 신규 함수만 추가한다(Exclusions 참조).

## 용어 정의

- 본번호: 회차당 보너스를 제외한 6개 메인 번호
- 최솟값(min_num): 한 회차 본번호 6개 중 가장 작은 값. 이론적 범위 1~40
- 최댓값(max_num): 한 회차 본번호 6개 중 가장 큰 값. 이론적 범위 6~45
- 범위(range_val): max_num - min_num. 이론적 범위 5~44
- 좁은 범위(small): range_val < 30
- 넓은 범위(large): range_val ≥ 30

## 요구사항 (EARS)

### Ubiquitous Requirements

- REQ-MM-001: The system SHALL provide `get_min_max_stats(draws)` returning
  total_draws, avg_min(2 decimals), avg_max(2 decimals), avg_range(2 decimals),
  min_distribution, max_distribution, range_distribution, most_common_min,
  most_common_max, most_common_range, small_range_count, large_range_count,
  small_range_pct(2 decimals), large_range_pct(2 decimals).
- REQ-MM-002: For each draw the system SHALL compute min_num as the minimum of
  the 6 main numbers, max_num as the maximum of the 6 main numbers, and
  range_val as (max_num - min_num).
- REQ-MM-003: The avg_min SHALL be the mean of every draw's min_num, avg_max the
  mean of every draw's max_num, and avg_range the mean of every draw's range_val
  across all aggregated draws, each rounded to 2 decimals.
- REQ-MM-004: The min_distribution SHALL be a mapping {number: count} over
  numbers 1..40 containing only min values that actually appear (no zero-filled
  keys).
- REQ-MM-005: The max_distribution SHALL be a mapping {number: count} over
  numbers 6..45 containing only max values that actually appear (no zero-filled
  keys).
- REQ-MM-006: The range_distribution SHALL be a mapping {range_val: count}
  containing only range values that actually appear (no zero-filled keys).
- REQ-MM-007: The most_common_min SHALL be the min value with the highest draw
  count, breaking ties by the smaller value first; it SHALL be 0 when there are
  no aggregated draws.
- REQ-MM-008: The most_common_max SHALL be the max value with the highest draw
  count, breaking ties by the smaller value first; it SHALL be 0 when there are
  no aggregated draws.
- REQ-MM-009: The most_common_range SHALL be the range value with the highest
  draw count, breaking ties by the smaller value first; it SHALL be 0 when there
  are no aggregated draws.
- REQ-MM-010: The small_range_count SHALL be the number of draws with
  range_val < 30 and large_range_count the number with range_val ≥ 30. The two
  counts SHALL partition all aggregated draws
  (small_range_count + large_range_count == total_draws).
- REQ-MM-011: The small_range_pct and large_range_pct SHALL be each category
  count divided by total_draws times 100, rounded to 2 decimals.
- REQ-MM-012: The system SHALL expose `GET /api/stats/min-max` returning the
  min/max analysis as JSON (always 200).
- REQ-MM-013: The system SHALL expose `GET /stats/min-max` rendering a
  server-side page with summary cards (average min / max / range, small/large
  range counts and percentages), a top-15 table of the most common min values,
  and a top-15 table of the most common max values.

### Event-driven Requirements

- REQ-MM-014: WHEN analyzing a draw, the system SHALL use only the 6 main
  numbers and exclude the bonus number entirely.
- REQ-MM-015: WHEN a draw is aggregated, the system SHALL derive min_num,
  max_num, and range_val from the same 6 main numbers so that
  range_val == max_num - min_num holds by construction.

### State-driven Requirements

- REQ-MM-016: WHILE no draw data is available, `get_min_max_stats` SHALL return
  total_draws=0, avg_min=0, avg_max=0, avg_range=0, min_distribution={},
  max_distribution={}, range_distribution={}, most_common_min=0,
  most_common_max=0, most_common_range=0, small_range_count=0,
  large_range_count=0, small_range_pct=0, large_range_pct=0; both endpoints
  SHALL still return 200 and the page SHALL render an empty state.

### Unwanted Behavior Requirements

- REQ-MM-017: The data layer SHALL NOT mutate the input draws list, SHALL NOT
  modify any existing `lotto/*.py` core module, and SHALL NOT modify, merge
  with, or refactor existing stats features (SPEC-049 합계, SPEC-056 간격,
  SPEC-061 고저 등) or their helpers.
- REQ-MM-018: IF a draw exposes fewer than 6 main numbers, THEN the system SHALL
  skip that draw from aggregation rather than raising.

### Optional Requirements

- REQ-MM-019: Where a memory cache is used, the system SHALL store the computed
  result in `_min_max_cache: dict[str, Any]` keyed by `str(len(draws))` and
  clear it in `invalidate_cache()`, consistent with existing cache patterns in
  `data.py` (e.g. `_odd_even_cache`, `_high_low_cache`).

## 비기능 요구사항

- Python 3.9 호환 (match/case 금지, `zip(strict=...)` 금지 — 필요 시 `# noqa: B905`)
- 서버 사이드 렌더링 전용 (JavaScript 사용 금지)
- 결정적 — 동일 입력에 동일 출력
- 테스트는 `tests/test_min_max_analysis.py`에 작성하고 최소 20개
- `mypy.ini` override 목록에 `test_min_max_analysis` 등록
- 네비게이션: `base.html`에 "최대최소" → `/stats/min-max` 링크를 데스크톱과
  모바일 네비게이션 양쪽에 추가
- 템플릿 파일명: `min_max.html`

## 인수 기준

acceptance.md 참조.

## Exclusions (What NOT to Build)

- 기존 stats 기능(합계 SPEC-049, 간격 SPEC-056, 고저 SPEC-061 등)의
  수정·병합·리팩터링 (본 SPEC은 신규 함수만 추가; 독립 공존)
- 인접 번호 간격(gap) 분석 — SPEC-056에서 다룸 (range는 max-min 단일 값)
- 본번호 합계 분석 — SPEC-049에서 다룸
- 저/고 경계 개수 비율 — SPEC-061에서 다룸
- min_distribution/max_distribution/range_distribution을 전 구간(1..40, 6..45,
  5..44) 키로 0-채움 — 본 SPEC은 출현한 값만 포함
- range_distribution의 페이지 표 노출 — 페이지는 최솟값 top-15, 최댓값 top-15
  두 표만 표시 (API는 세 분포 전체 반환)
- recent_n 최신 N회차 윈도잉 (본 SPEC은 전체 회차만 대상)
- 최솟값/최댓값/범위와 다른 지표(합계, 간격, AC, 홀짝, 고저)의 상관관계 교차 분석
- 사용자 입력 조합의 최솟/최댓/범위 평가 체커
- 추천 엔진과의 자동 연동(범위 필터/가중치)
- 분포 시각화 차트(막대/그래프) — 표 형태만 제공
- 회차 시계열에 따른 추세(연도별/구간별 변화)
- JavaScript 기반 인터랙션 또는 클라이언트 측 계산
