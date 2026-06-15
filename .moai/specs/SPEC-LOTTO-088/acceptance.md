# SPEC-LOTTO-088 인수 기준 (Acceptance Criteria)

대상 함수: `get_gap_variance_stats(draws)` / 헬퍼 `_gap_variance_bucket`, `_compute_gap_variance`
API: `GET /api/stats/gap_variance` / 페이지: `GET /stats/gap-variance`

## 빈 데이터

- **AC-01**: 빈 리스트 → total_draws=0, avg_variance=0.0, most_common_range="0-10", uniform_gap_pct=0.0.
- **AC-02**: None → 빈 구조, 분포 5개 키 포함.
- **AC-03**: 빈 데이터 → 5개 키 모두 count=0, pct=0.0, 키 순서 = `_GAP_VAR_KEYS`.

## 단일 회차 구간 분류

- **AC-04**: [1,2,3,4,5,6] gaps=[1,1,1,1,1] var=0 → "0-10".
- **AC-05**: [1,6,11,16,21,45] gaps=[5,5,5,5,24] var=57.76 → "30-60".
- **AC-06**: [1,2,30,31,40,45] gaps=[1,28,1,9,5] var=100.96 → "100+".
- **AC-07**: [5,10,15,20,25,30] gaps=[5,5,5,5,5] var=0 → "0-10".
- **AC-08**: [1,10,19,28,37,44] gaps=[9,9,9,9,7] var=0.64 → "0-10".

## 헬퍼 / 분산 계산

- **AC-09**: `_compute_gap_variance([1,6,11,16,21,45])` == 57.76.
- **AC-10**: `_compute_gap_variance([1,2,30,31,40,45])` == 100.96.

## 버킷 경계

- **AC-11**: var=9.9 → "0-10".
- **AC-12**: var=10.0 → "10-30".
- **AC-13**: var=29.9 → "10-30".
- **AC-14**: var=30.0 → "30-60".
- **AC-15**: var=59.9 → "30-60".
- **AC-16**: var=60.0 → "60-100".
- **AC-17**: var=99.9 → "60-100".
- **AC-18**: var=100.0 → "100+".

## 구조 / 집계

- **AC-19**: 분포는 정확히 5개 키.
- **AC-20**: 모든 count 합 == total_draws.
- **AC-21**: pct 소수 2자리 반올림.
- **AC-22**: most_common_range 동률 시 정의 순서상 앞선 구간.
- **AC-23**: uniform_gap_pct = 분산 < 10 구간("0-10") 비율만.
- **AC-24**: avg_variance 소수 2자리.

## 4-draw 픽스처

- **AC-25**: 픽스처 요약: total=4, avg_variance=39.68, most_common="0-10", uniform=50.0.
- **AC-26**: 픽스처 분포: 0-10=2, 10-30=0, 30-60=1, 60-100=0, 100+=1.

## 캐시

- **AC-27**: 동일 회차 수 재호출 시 동일 객체(캐시) 반환.
- **AC-28**: `invalidate_cache()` 가 `_gap_var_cache` 를 비운다.

## 라우트

- **AC-29**: GET /api/stats/gap_variance → 200 + 키 구조.
- **AC-30**: GET /api/stats/gap_variance → 데이터 없어도 200.
- **AC-31**: GET /stats/gap-variance → 200 HTML.
- **AC-32**: GET /stats/gap-variance → 데이터 없어도 200.
