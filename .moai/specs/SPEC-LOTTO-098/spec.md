# SPEC-LOTTO-098: 구간별 번호 선택 분포 분석 (Zone Coverage Distribution)

## Status
Completed

## Overview
로또 6/45 각 회차에서 본번호 6개가 1-45 범위를 9개 구간([1-5],[6-10],[11-15],[16-20],[21-25],[26-30],[31-35],[36-40],[41-45])으로 나눌 때 몇 개 구간을 커버하는지 분석한다. 커버 구간 수(zones_covered)는 최소 1에서 최대 6(본번호 6개이므로 7개 이상 구간 동시 커버는 불가)까지 가능하며, 분포를 통해 번호 분산 패턴을 파악한다. 웹 UI에서 구간 커버리지 분포 차트와 핵심 통계를 제공한다.

## Requirements (EARS Format)

### U (Ubiquitous)
- U1: 시스템은 본번호 6개(보너스 번호 제외)만을 사용하여 구간 커버리지를 계산해야 한다.
- U2: 9개 구간은 고정 값이며, 각 구간은 5개 번호(1-5, 6-10, ..., 41-45)로 구성된다.
- U3: 번호 n이 속한 구간 인덱스는 `(n - 1) // 5` 공식으로 산출한다(0~8).
- U4: zones_covered는 6개 본번호가 점유한 서로 다른 구간의 수이며 1~6 사이의 정수이다.
- U5: 분포 버킷은 `"1"`, `"2"`, `"3"`, `"4"`, `"5"`, `"6"` 6개 고정 키를 항상 포함한다.
- U6: 각 버킷은 `{"count": int, "pct": float}` 형태를 유지한다.
- U7: `most_common_zones`는 count 최댓값 버킷이며, 동률 시 `_ZONE_COV_KEYS` 정의 순서상 앞선(=더 작은) 값을 선택한다.
- U8: 캐시 키는 `str(len(draws))`이며, `invalidate_cache()` 호출 시 무효화된다.

### E (Event-driven)
- E1: When `GET /api/stats/zone_coverage` is called with optional `limit` query param, the system shall return JSON with `total_draws`, `avg_zones_covered`, `most_common_zones`, `full_spread_pct`, `concentrated_pct`, and `zone_coverage_distribution` fields.
- E2: When `GET /stats/zone-coverage` page is requested, the system shall render `zone_coverage.html` template with distribution data.
- E3: When `invalidate_cache()` is called, the system shall clear `_zone_coverage_cache`.

### S (State-driven)
- S1: While draws list is None or empty, the system shall return `total_draws=0`, `avg_zones_covered=0.0`, `most_common_zones="1"`, `full_spread_pct=0.0`, `concentrated_pct=0.0`, and all 6 bucket values as `{"count": 0, "pct": 0.0}`.
- S2: While cache exists for the same draw count key, the system shall return the cached result without recomputation.

### N (Negative)
- N1: The system shall NOT include the bonus number in zone coverage calculations.
- N2: The system shall NOT use `zip(strict=True)` — Python 3.9 호환을 위해 `# noqa: B905` 주석을 사용한다.
- N3: The system shall NOT use `match`/`case` syntax — Python 3.9 호환을 위해 `if/elif/else` 체인을 사용한다.
- N4: zones_covered는 반드시 1 이상 6 이하 정수여야 하며, 6개 번호로는 7개 이상 구간 커버가 불가능하다.

### O (Optional)
- O1: Where `limit` query parameter is provided, the system shall use only the most recent `limit` draws for analysis.

## Response Structure

```json
{
  "total_draws": 1180,
  "avg_zones_covered": 4.52,
  "most_common_zones": "5",
  "full_spread_pct": 8.31,
  "concentrated_pct": 12.46,
  "zone_coverage_distribution": {
    "1": {"count": 0, "pct": 0.0},
    "2": {"count": 12, "pct": 1.02},
    "3": {"count": 135, "pct": 11.44},
    "4": {"count": 312, "pct": 26.44},
    "5": {"count": 623, "pct": 52.80},
    "6": {"count": 98, "pct": 8.31}
  }
}
```

**필드 정의:**
- `total_draws`: 분석 대상 회차 수 (int)
- `avg_zones_covered`: 회차 평균 커버 구간 수 (float, 소수 2자리)
- `most_common_zones`: 최빈 커버 구간 수 라벨 (string, "1"~"6")
- `full_spread_pct`: 6개 구간 커버(완전 분산) 비율 (float, 소수 2자리)
- `concentrated_pct`: 3개 이하 구간 커버(집중) 비율 (float, 소수 2자리)
- `zone_coverage_distribution`: 커버 구간 수별 분포 딕셔너리 (6개 고정 버킷)

## UI Labels (Korean)

| 항목 | 한국어 라벨 |
|------|------------|
| 페이지 제목 | 구간별 번호 선택 분포 |
| avg_zones_covered | 평균 커버 구간 수 |
| most_common_zones | 최빈 커버 구간 수 |
| full_spread_pct | 완전 분산 비율 (6구간) |
| concentrated_pct | 집중 비율 (3구간 이하) |
| zone_coverage_distribution | 커버 구간 수 분포 |

## Implementation Notes

- 구간 판별: `zone_idx = (num - 1) // 5` → 0~8
- zones_covered: `len(set(zone_idx for num in numbers))`
- 완전 분산: zones_covered == 6
- 집중: zones_covered <= 3
- 구현 참고: SPEC-097 (gap_median_dist) 패턴과 동일 구조

## Files to Modify

| 파일 | 변경 내용 |
|------|---------|
| `lotto/web/data.py` | `_ZONE_COV_KEYS`, `_zone_coverage_cache`, `get_zone_coverage_stats()` 추가, `invalidate_cache()` 수정 |
| `lotto/web/routes/api.py` | `GET /api/stats/zone_coverage` 엔드포인트 추가 |
| `lotto/web/pages.py` | `GET /stats/zone-coverage` 페이지 라우트 추가 |
| `lotto/web/templates/zone_coverage.html` | 새 템플릿 파일 생성 |
| `lotto/web/templates/base.html` | 사이드바 메뉴 링크 추가 |
| `tests/test_zone_coverage_stats.py` | 새 테스트 파일 생성 |
