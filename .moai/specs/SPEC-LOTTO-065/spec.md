---
id: SPEC-LOTTO-065
version: 0.1.0
status: Completed
created: 2026-06-10
updated: 2026-06-10
author: ircp
priority: medium
---

# SPEC-LOTTO-065: 번호 표준편차 분석 (Number Standard Deviation Analysis)

## 개요

각 회차의 본번호 6개(보너스 제외)가 얼마나 흩어져 있는지를 모표준편차
(population standard deviation)로 산출한다. 전체 회차에 걸친 평균/최소/최대
표준편차, 표준편차 크기에 따른 저/중/고 세 구간별 회차 수와 비율, 그리고
고정 구간(bucket) 분포와 최빈 구간을 서버 렌더링 테이블과 JSON API로 제공한다.

회차당 산출값:

- mean = sum(nums) / 6 (본번호 6개의 산술평균)
- variance = sum((n - mean)**2 for n in nums) / 6 (모분산, n=6으로 나눔)
- std = variance ** 0.5 (모표준편차)
- 각 회차의 std는 소수 둘째 자리로 반올림(2 decimals)한 뒤 집계에 사용한다.

번호 범위 1~45·서로 다른 6개라는 제약상 std의 이론적 범위는 약 1.7~18 정도이다
(예: 연속 [1..6]은 std≈1.71, 양극단 [1,2,3,4,5,45]는 std≈14대, 균등 분산
조합은 18 부근까지). 본 SPEC은 0~20+ 구간을 6개 bucket으로 나눠 분포를 표현한다.

## 배경

기존 통계(stats) 계열 기능은 합계(SPEC-LOTTO-049), 간격(SPEC-LOTTO-056),
AC값(SPEC-LOTTO-057), 소수/합성수(SPEC-LOTTO-058), 십의 자리 구간
(SPEC-LOTTO-059), 홀짝(SPEC-LOTTO-060), 고저(SPEC-LOTTO-061), 연속 패턴
(SPEC-LOTTO-062), 끝자리 합계(SPEC-LOTTO-063), 최솟값·최댓값(SPEC-LOTTO-064)
등을 다룬다. 본 SPEC은 이 "통계 분석(stats)" 계열의 일관된 패턴
(`get_<topic>_stats` 함수 + `str(len(draws))` 캐시 + 3계층 라우트)을 그대로
따른다.

### 기존 기능과의 구분 (혼동 방지)

코드베이스에는 "표준편차" 분석 기능이 아직 없다(grep 확인: std/표준편차/stddev
등 신규 라우트·함수·네비 없음). 단, 인접 개념과 혼동하지 말 것:

| 항목 | 기존 기능 | SPEC-065 표준편차 (본 SPEC) |
|------|-----------|------------------------------|
| 합계 분석 (SPEC-049) | 본번호 6개의 총합 | 다룸 아님 — 흩어진 정도(std)만 |
| 간격 분석 (SPEC-056) | 인접 번호 간 간격(gap) 분포 | std는 인접 간격이 아닌 평균 대비 분산의 제곱근 |
| 최대최소 분석 (SPEC-064) | 최솟값/최댓값/범위(max-min) | range는 양 끝 두 값만, std는 6개 전부의 분산 반영 |

본 SPEC은 기존 코드를 수정·병합·리팩터링하지 않으며 기존 `lotto/*.py` 코어
모듈도 수정하지 않고 `lotto/web/data.py`에 신규 함수만 추가한다(Exclusions 참조).

## 용어 정의

- 본번호: 회차당 보너스를 제외한 6개 메인 번호
- 평균(mean): 본번호 6개의 산술평균 sum(nums)/6
- 모분산(variance): sum((n-mean)**2 for n in nums)/6 (표본분산 아님, n으로 나눔)
- 모표준편차(std): variance ** 0.5, 회차당 소수 둘째 자리 반올림
- 저편차(low): std < 10.0
- 중편차(mid): 10.0 ≤ std < 14.0
- 고편차(high): std ≥ 14.0
- bucket: std 값을 고정 구간으로 나눈 라벨
  ("0-4", "4-8", "8-12", "12-16", "16-20", "20+")

## 요구사항 (EARS)

### Ubiquitous Requirements

- REQ-SD-001: The system SHALL provide `get_std_stats(draws)` returning
  total_draws, avg_std(2 decimals), min_std(2 decimals), max_std(2 decimals),
  low_std_count, mid_std_count, high_std_count, low_std_pct(2 decimals),
  mid_std_pct(2 decimals), high_std_pct(2 decimals), std_distribution,
  most_common_bucket.
- REQ-SD-002: For each draw the system SHALL compute mean as sum of the 6 main
  numbers divided by 6, variance as the mean of squared deviations
  (sum((n - mean)**2) / 6), and std as variance to the power 0.5; the per-draw
  std SHALL be rounded to 2 decimals before aggregation.
- REQ-SD-003: The avg_std SHALL be the mean of every draw's per-draw std across
  all aggregated draws, rounded to 2 decimals.
- REQ-SD-004: The min_std SHALL be the smallest per-draw std observed and the
  max_std the largest per-draw std observed, each rounded to 2 decimals.
- REQ-SD-005: The low_std_count SHALL be the number of draws with std < 10.0,
  mid_std_count the number with 10.0 ≤ std < 14.0, and high_std_count the number
  with std ≥ 14.0. The three counts SHALL partition all aggregated draws
  (low_std_count + mid_std_count + high_std_count == total_draws).
- REQ-SD-006: The low_std_pct, mid_std_pct, and high_std_pct SHALL be each
  category count divided by total_draws times 100, rounded to 2 decimals.
- REQ-SD-007: The std_distribution SHALL be a mapping {bucket_label: count} whose
  keys are EXACTLY the six labels "0-4", "4-8", "8-12", "12-16", "16-20", "20+"
  in that defined order, all six always present (count 0 if no draw falls in a
  bucket). A draw with std value v is assigned to bucket "a-b" when a ≤ v < b, and
  to "20+" when v ≥ 20.
- REQ-SD-008: The most_common_bucket SHALL be the bucket label with the highest
  count; ties SHALL be broken by the first label in the defined order. When there
  are no aggregated draws, most_common_bucket SHALL be "0-4".
- REQ-SD-009: The system SHALL expose `GET /api/stats/std` returning the standard
  deviation analysis as JSON (always 200).
- REQ-SD-010: The system SHALL expose `GET /stats/std` rendering a server-side
  page with summary cards (average / min / max std, low/mid/high category counts
  and percentages) and a bar-like table of the std_distribution buckets.

### Event-driven Requirements

- REQ-SD-011: WHEN analyzing a draw, the system SHALL use only the 6 main numbers
  and exclude the bonus number entirely.
- REQ-SD-012: WHEN computing per-draw std, the system SHALL use the population
  formula (divide squared deviations by 6, not by 5) so that results are
  deterministic and consistent across all draws.

### State-driven Requirements

- REQ-SD-013: WHILE no draw data is available, `get_std_stats` SHALL return
  total_draws=0, avg_std=0.0, min_std=0.0, max_std=0.0, low_std_count=0,
  mid_std_count=0, high_std_count=0, low_std_pct=0.0, mid_std_pct=0.0,
  high_std_pct=0.0, std_distribution with all six bucket keys set to 0, and
  most_common_bucket="0-4"; both endpoints SHALL still return 200 and the page
  SHALL render an empty state.

### Unwanted Behavior Requirements

- REQ-SD-014: The data layer SHALL NOT mutate the input draws list, SHALL NOT
  modify any existing `lotto/*.py` core module, and SHALL NOT modify, merge with,
  or refactor existing stats features (SPEC-049 합계, SPEC-056 간격, SPEC-064
  최대최소 등) or their helpers.
- REQ-SD-015: IF a draw exposes fewer than 6 main numbers, THEN the system SHALL
  skip that draw from aggregation rather than raising.

### Optional Requirements

- REQ-SD-016: Where a memory cache is used, the system SHALL store the computed
  result in `_std_cache: dict[str, Any]` keyed by `str(len(draws))` and clear it
  in `invalidate_cache()`, consistent with existing cache patterns in `data.py`
  (e.g. `_min_max_cache`, `_high_low_cache`).

## 비기능 요구사항

- Python 3.9 호환 (match/case 금지, `zip(strict=...)` 금지 — 필요 시 `# noqa: B905`)
- 서버 사이드 렌더링 전용 (JavaScript 사용 금지)
- 결정적 — 동일 입력에 동일 출력
- 테스트는 `tests/test_std_analysis.py`에 작성하고 최소 20개
- `mypy.ini` override 목록에 `test_std_analysis` 등록
- 네비게이션: `base.html`에 "표준편차" → `/stats/std` 링크를 데스크톱과
  모바일 네비게이션 양쪽에 추가
- 템플릿 파일명: `std_analysis.html`

## 인수 기준

acceptance.md 참조.

## Exclusions (What NOT to Build)

- 기존 stats 기능(합계 SPEC-049, 간격 SPEC-056, 최대최소 SPEC-064 등)의
  수정·병합·리팩터링 (본 SPEC은 신규 함수만 추가; 독립 공존)
- 표본표준편차(n-1로 나누는 sample std) — 본 SPEC은 모표준편차(n=6)만 사용
- 인접 번호 간격(gap) 분석 — SPEC-056에서 다룸
- 최솟값/최댓값/범위(max-min) 분석 — SPEC-064에서 다룸
- 본번호 합계 분석 — SPEC-049에서 다룸
- std_distribution bucket 키의 가변화 — 본 SPEC은 6개 고정 키를 항상 포함
  (출현 없는 구간도 0으로 유지)
- 보너스 번호를 포함한 7개 기준 std 계산 — 본번호 6개만 대상
- recent_n 최신 N회차 윈도잉 (본 SPEC은 전체 회차만 대상)
- 표준편차와 다른 지표(합계, 간격, 범위, 홀짝, 고저)의 상관관계 교차 분석
- 사용자 입력 조합의 std 평가 체커
- 추천 엔진과의 자동 연동(std 필터/가중치)
- 분포 시각화 차트(막대/그래프 이미지) — bar-like 표 형태만 제공
- 회차 시계열에 따른 추세(연도별/구간별 변화)
- JavaScript 기반 인터랙션 또는 클라이언트 측 계산
