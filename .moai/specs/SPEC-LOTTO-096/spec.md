# SPEC-LOTTO-096: 최소 간격 구간 분포 분석 (Min Gap Distribution Analysis)

## Status
Completed

## Overview
각 회차 본번호 6개(보너스 제외)를 정렬한 뒤 인접 번호 간 5개 차이 중 최솟값(min_gap)을 구하여, 6개 고정 버킷("1","2","3","4-5","6-10","11+")으로 분류하고 분포 통계를 제공한다. min_gap=1은 연속번호 쌍이 존재함을 의미하며, 기존 `get_gap_stats`(SPEC-056)의 avg_min_gap 단일 수치와 `get_max_gap_dist_stats`(SPEC-080)의 최대 간격 구간 분포를 보완하는 최솟값 특화 분포 분석이다. API 엔드포인트(`/api/stats/min_gap_dist`)와 HTML 페이지(`/stats/min_gap_dist`)를 제공한다.

## Requirements (EARS Format)

### U (Ubiquitous)
- U1: 시스템은 본번호 6개만 사용하고 보너스 번호를 제외하여 min_gap을 산출하여야 한다.
- U2: 시스템은 6개 고정 버킷 키("1","2","3","4-5","6-10","11+")를 항상 응답에 포함하여야 한다.
- U3: 각 버킷 값은 `{"count": int, "pct": float}` 구조로 표현되어야 하며 pct는 소수 2자리 퍼센트이다.
- U4: `avg_min_gap`은 전체 회차 min_gap 합계를 total_draws로 나눈 소수 2자리 값이어야 한다.
- U5: `min1_pct`는 min_gap=1인 회차(연속번호 포함 회차)의 비율(%, 소수 2자리)이어야 한다.
- U6: `large_gap_pct`는 min_gap≥6인 회차 비율(%, 소수 2자리)이어야 한다.
- U7: `most_common_range`는 count 최댓값 버킷 키이며, 동률 시 버킷 정의 순서상 앞선 키를 선택하여야 한다.

### E (Event-driven)
- E1: GET /api/stats/min_gap_dist 요청을 수신하면 시스템은 전체 회차 대상 min_gap 분포 통계를 JSON으로 반환하여야 한다.
- E2: GET /stats/min_gap_dist 요청을 수신하면 시스템은 최소 간격 분포 분석 HTML 페이지를 반환하여야 한다.
- E3: invalidate_cache()가 호출되면 시스템은 `_min_gap_dist_cache`를 초기화하여야 한다.

### S (State-driven)
- S1: draws가 None 또는 빈 리스트인 경우 시스템은 total_draws=0, 6개 버킷 전부 count=0/pct=0.0, most_common_range="1", avg_min_gap=0.0, min1_pct=0.0, large_gap_pct=0.0의 빈 구조를 반환하여야 한다.
- S2: 캐시에 동일 len(draws) 키가 존재하면 시스템은 재계산 없이 캐시값을 반환하여야 한다.
- S3: 데이터가 존재하는 동안 시스템은 6개 버킷 pct 합계가 100.0에 근접(부동소수점 오차 허용)하도록 유지하여야 한다.

### N (Negative)
- N1: 시스템은 보너스 번호를 min_gap 계산에 포함하여서는 안 된다.
- N2: 시스템은 버킷 키를 "1", "2", "3", "4-5", "6-10", "11+" 이외의 다른 키로 응답하여서는 안 된다.
- N3: 시스템은 total_draws=0인 경우 avg_min_gap, min1_pct, large_gap_pct를 0.0 이외의 값으로 반환하여서는 안 된다.
- N4: 시스템은 pct 값을 소수 2자리를 초과하여 반환하여서는 안 된다.

### O (Optional)
- O1: 캐시가 비어 있는 경우 시스템은 회차 데이터를 1회 순회하여 min_gap을 집계하고 결과를 캐시에 저장할 수 있다.

## Response Structure

```json
{
  "total_draws": 1180,
  "avg_min_gap": 2.34,
  "most_common_range": "2",
  "min1_pct": 38.14,
  "large_gap_pct": 5.68,
  "min_gap_distribution": {
    "1":    {"count": 450, "pct": 38.14},
    "2":    {"count": 320, "pct": 27.12},
    "3":    {"count": 210, "pct": 17.80},
    "4-5":  {"count": 133, "pct": 11.27},
    "6-10": {"count": 57,  "pct": 4.83},
    "11+":  {"count": 10,  "pct": 0.85}
  }
}
```

## Technical Approach

### 버킷 정의 (`_MIN_GAP_KEYS`, `_min_gap_bucket`)

| 버킷 키 | min_gap 범위 | 의미 |
|---------|-------------|------|
| "1"     | min_gap == 1 | 연속번호 쌍 존재 |
| "2"     | min_gap == 2 | 1칸 띄운 최소 간격 |
| "3"     | min_gap == 3 | 2칸 띄운 최소 간격 |
| "4-5"   | 4 ≤ min_gap ≤ 5 | 중소 최소 간격 |
| "6-10"  | 6 ≤ min_gap ≤ 10 | 중대 최소 간격 |
| "11+"   | min_gap ≥ 11 | 대형 최소 간격 |

### 캐시 변수
```python
_min_gap_dist_cache: dict[str, dict] = {}
```
캐시 키: `str(len(draws))`. `invalidate_cache()`에서 `.clear()` 호출.

### 핵심 계산 로직
```python
nums = draw.numbers()  # 보너스 제외 본번호 6개 (정렬됨)
gaps = [b - a for a, b in zip(nums, nums[1:])]  # noqa: B905
min_gap = min(gaps)
```

### 기존 함수와의 구분
- `get_gap_stats` (SPEC-056): small/medium/large 3분류 + avg_min_gap·avg_max_gap 단일 수치
- `get_max_gap_dist_stats` (SPEC-080): max_gap을 6개 버킷으로 분류 (`"1-5","6-10","11-15","16-20","21-30","31+"`)
- `get_min_gap_dist_stats` (SPEC-096): min_gap을 6개 버킷으로 분류 (`"1","2","3","4-5","6-10","11+"`) — 본 SPEC

## Files to Modify
- `lotto/web/data.py`: `_min_gap_dist_cache`, `_MIN_GAP_KEYS`, `_min_gap_bucket`, `get_min_gap_dist_stats` 추가; `invalidate_cache()`에 캐시 초기화 추가
- `lotto/web/routes/api.py`: `GET /api/stats/min_gap_dist` 엔드포인트 추가
- `lotto/web/routes/pages.py`: `GET /stats/min_gap_dist` 페이지 엔드포인트 추가
- `lotto/web/templates/min_gap_dist.html`: 분석 결과 HTML 템플릿 (신규)
- `lotto/web/templates/base.html`: 내비게이션 탭에 "최소 간격 분포" 항목 추가
- `tests/test_min_gap_dist_stats.py`: TDD 테스트 파일 (신규, 목표 35개 이상)
