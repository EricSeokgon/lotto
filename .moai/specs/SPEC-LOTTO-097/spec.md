# SPEC-LOTTO-097: 번호 간격 중앙값 구간 분포 분석

## Status
Completed

## Overview
로또 6/45 각 회차에서 정렬된 본번호 6개의 인접 간격 5개를 산출하고, 그 중앙값(median: 5개 간격을 정렬했을 때 3번째 값)을 6개 구간으로 분류하여 분포를 분석한다. 기존의 최솟값(SPEC-096), 최댓값(SPEC-080), 분산(SPEC-089) 분석과 함께 간격 분포의 중심 경향을 파악할 수 있다. 웹 UI에서 간격 중앙값 구간 분포 차트와 핵심 통계를 제공한다.

## Requirements (EARS Format)

### U (Ubiquitous)
- U1: 시스템은 본번호 6개(보너스 번호 제외)만을 사용하여 인접 간격을 계산해야 한다.
- U2: 인접 간격은 정렬된 본번호 연속 두 값의 차이로 정의하며, 5개 간격이 산출된다.
- U3: 간격 중앙값(gap median)은 5개 인접 간격을 오름차순 정렬했을 때 3번째(인덱스 2) 값으로 정의한다.
- U4: 구간 버킷은 `"1-2"`, `"3-4"`, `"5-6"`, `"7-8"`, `"9-10"`, `"11+"` 6개 고정 키를 항상 포함한다.
- U5: 각 구간 버킷은 `{"count": int, "pct": float}` 형태를 유지한다.
- U6: `most_common_range`는 count 최댓값 구간이며, 동률 시 _GAP_MEDIAN_KEYS 정의 순서상 앞선(=더 작은) 구간을 선택한다.
- U7: 캐시 키는 `str(len(draws))` 이며, `invalidate_cache()` 호출 시 무효화된다.

### E (Event-driven)
- E1: When `GET /api/stats/gap_median_dist` is called with optional `limit` query param, the system shall return JSON with `total_draws`, `avg_gap_median`, `most_common_range`, `low_median_pct`, `high_median_pct`, and `gap_median_distribution` fields.
- E2: When `GET /stats/gap-median-dist` page is requested, the system shall render `gap_median_dist.html` template with distribution data.
- E3: When `invalidate_cache()` is called, the system shall clear `_gap_median_dist_cache`.

### S (State-driven)
- S1: While draws list is None or empty, the system shall return `total_draws=0`, `avg_gap_median=0.0`, `most_common_range="1-2"`, `low_median_pct=0.0`, `high_median_pct=0.0`, and all 6 bucket values as `{"count": 0, "pct": 0.0}`.
- S2: While cache exists for the same draw count key, the system shall return the cached result without recomputation.

### N (Negative)
- N1: The system shall NOT include the bonus number in gap calculations.
- N2: The system shall NOT use `zip(strict=True)` — Python 3.9 호환을 위해 `# noqa: B905` 주석을 사용한다.
- N3: The system shall NOT use `match`/`case` syntax — Python 3.9 호환을 위해 `if/elif/else` 체인을 사용한다.

### O (Optional)
- O1: Where `limit` query parameter is provided, the system shall use only the most recent `limit` draws for analysis.

## Response Structure

```json
{
  "total_draws": 1180,
  "avg_gap_median": 6.42,
  "most_common_range": "5-6",
  "low_median_pct": 23.47,
  "high_median_pct": 18.22,
  "gap_median_distribution": {
    "1-2": {"count": 45, "pct": 3.81},
    "3-4": {"count": 232, "pct": 19.66},
    "5-6": {"count": 320, "pct": 27.12},
    "7-8": {"count": 289, "pct": 24.49},
    "9-10": {"count": 195, "pct": 16.53},
    "11+": {"count": 99, "pct": 8.39}
  }
}
```

**필드 정의:**
- `total_draws`: 분석 대상 회차 수 (int)
- `avg_gap_median`: 회차 평균 간격 중앙값 (float, 소수 2자리)
- `most_common_range`: 최빈 구간 라벨 (string)
- `low_median_pct`: gap_median <= 4인 회차 비율 (float, %, 소수 2자리) — 간격이 조밀한 회차
- `high_median_pct`: gap_median >= 9인 회차 비율 (float, %, 소수 2자리) — 간격이 넓은 회차
- `gap_median_distribution`: 6개 구간 분포 (항상 6개 키 포함)

**구간 경계:**
- `"1-2"`: gap_median <= 2
- `"3-4"`: gap_median <= 4
- `"5-6"`: gap_median <= 6
- `"7-8"`: gap_median <= 8
- `"9-10"`: gap_median <= 10
- `"11+"`: gap_median >= 11

## Technical Approach

### 핵심 알고리즘
```
numbers = sorted(draw.numbers())  # 본번호 6개 (보너스 제외)
gaps = [numbers[i+1] - numbers[i] for i in range(5)]
gaps.sort()
gap_median = gaps[2]  # 5개 간격 중 3번째 (중앙값)
```

### 캐시 구조
```python
_GAP_MEDIAN_KEYS = ["1-2", "3-4", "5-6", "7-8", "9-10", "11+"]
_gap_median_dist_cache: dict[str, dict] = {}
```

### 버킷 함수
```python
def _gap_median_bucket(g: int) -> str:
    if g <= 2: return "1-2"
    elif g <= 4: return "3-4"
    elif g <= 6: return "5-6"
    elif g <= 8: return "7-8"
    elif g <= 10: return "9-10"
    else: return "11+"
```

## Files to Modify

- `lotto/web/data.py` — `_GAP_MEDIAN_KEYS`, `_gap_median_dist_cache`, `_gap_median_bucket()`, `get_gap_median_dist_stats()` 추가, `invalidate_cache()` 에 캐시 clear 추가
- `lotto/web/routes/api.py` — `GET /api/stats/gap_median_dist` 엔드포인트 추가
- `lotto/web/routes/pages.py` — `GET /stats/gap-median-dist` 페이지 라우트 추가
- `lotto/web/templates/gap_median_dist.html` — 신규 템플릿 (다른 stats 템플릿 패턴 따름)
- `lotto/web/templates/base.html` — 사이드바 메뉴 항목 추가
- `tests/test_gap_median_dist_stats.py` — 신규 테스트 파일 (최소 35개 AC)
