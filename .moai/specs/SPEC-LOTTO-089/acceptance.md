# SPEC-LOTTO-089 인수 기준 (Acceptance Criteria)

## 빈 데이터

- **AC-01**: `get_low_high_stats([])` → total_draws=0, avg_low_count=0.0,
  most_common_combo="0저6고", balanced_pct=0.0.
- **AC-02**: `get_low_high_stats(None)` → 빈 구조, low_high_distribution 7개 키.
- **AC-03**: 빈 draws → 7개 키 모두 count=0, pct=0.0, 키 순서는 `_LOW_HIGH_KEYS`.

## 헬퍼 `_low_high_combo`

- **AC-04**: `_low_high_combo([1,2,3,4,5,6])` == "6저0고" (전부 저).
- **AC-05**: `_low_high_combo([23,24,25,26,27,28])` == "0저6고" (전부 고).
- **AC-06**: `_low_high_combo([1,2,3,23,24,25])` == "3저3고".
- **AC-07**: `_low_high_combo([1,22,23,24,25,45])` == "2저4고" (저 1,22 / 고 23,24,25,45).
- **AC-08**: 경계 — `_low_high_combo([1,2,22,23,24,25])` == "3저3고" (22는 저, 23은 고).
- **AC-09**: `_low_high_combo([1,2,3,4,22,23])` == "5저1고" (저 5 / 고 1).

## 단일 회차 분류 (집계 경로)

- **AC-10**: [1,2,3,4,5,6] → "6저0고" count=1.
- **AC-11**: [23,24,25,26,27,28] → "0저6고" count=1.
- **AC-12**: [1,2,3,23,24,25] → "3저3고" count=1.
- **AC-13**: [1,22,23,24,25,45] → "2저4고" count=1.

## 구조 / 집계

- **AC-14**: low_high_distribution 키는 정확히 7개.
- **AC-15**: 모든 count 합 == total_draws.
- **AC-16**: pct는 소수 2자리 (예: 1/3 → 33.33).
- **AC-17**: most_common_combo 동률 시 키 정의 순서상 앞선 조합("0저6고").
- **AC-18**: balanced_pct = "3저3고" 조합 회차 비율만 (소수 2자리).
- **AC-19**: avg_low_count는 소수 2자리.

## 4-draw 픽스처

D1 [1,2,3,4,5,6]="6저0고"(low=6), D2 [23,24,25,26,27,28]="0저6고"(low=0),
D3 [1,2,3,23,24,25]="3저3고"(low=3), D4 [1,22,23,24,25,45]="2저4고"(low=2).

- **AC-20**: total_draws=4.
- **AC-21**: avg_low_count = (6+0+3+2)/4 = 2.75.
- **AC-22**: most_common_combo = "0저6고" (동률 count=1, 키 순서상 앞선).
- **AC-23**: balanced_pct = 1/4*100 = 25.0.
- **AC-24**: 분포 — "0저6고"=1, "1저5고"=0, "2저4고"=1, "3저3고"=1,
  "4저2고"=0, "5저1고"=0, "6저0고"=1.

## 캐시

- **AC-25**: 동일 회차 수 재호출 시 캐시 결과 반환(동일 객체).
- **AC-26**: `invalidate_cache()`가 `_low_high_cache`를 비운다.

## 라우트

- **AC-27**: GET `/api/stats/low_high` → 200 + 키 구조.
- **AC-28**: GET `/api/stats/low_high` 데이터 없어도 200 (total_draws=0).
- **AC-29**: GET `/stats/low-high` → 200 (HTML).
- **AC-30**: GET `/stats/low-high` 데이터 없어도 200.
