# Implementation Plan: SPEC-LOTTO-098

## Overview
구간별 번호 선택 분포(Zone Coverage Distribution) 분석 기능을 TDD 방식으로 구현한다.
기존 SPEC-097 (gap_median_dist) 패턴을 그대로 따른다.

## Phase 1: RED — 테스트 작성

### 파일: `tests/test_zone_coverage_stats.py`

```
- AC-01~03: 빈 데이터 구조 검증 (None, [], 6개 키)
- AC-04~09: zones_covered 버킷 분류 테스트 (2,3,4,5,6구간)
- AC-10~13: 구간 경계 검증 ((num-1)//5 공식)
- AC-14~15: 다중 회차 집계 검증
- AC-16~17: avg_zones_covered 소수 반올림 검증
- AC-18: most_common_zones 동률 처리 검증
- AC-19~22: full_spread_pct / concentrated_pct 계산 검증
- AC-23~24: pct 소수 반올림 및 합계 검증
- AC-25~27: 캐시 동작 (동일 결과, invalidate, 복수 키)
- AC-28: limit 파라미터 동작
- AC-29~31: API 엔드포인트 응답 구조
- AC-32~34: 페이지 라우트 및 템플릿 렌더링
- AC-35: 보너스 번호 제외 확인
- AC-36~39: 타입 검증 (int, float, str)
- AC-40: 전 구간 분포 검증
- AC-43: 단일 회차 pct=100.0
- AC-44: 구간 인덱스 범위 (0~8)
- AC-45~46: invalidate_cache / _ZONE_COV_KEYS 상수
- AC-47: most_common_zones 타입 string
- AC-48~49: 경계값 및 전 구간 분포
- AC-50: base.html 링크 추가 확인
```

## Phase 2: GREEN — 최소 구현

### `lotto/web/data.py` 수정 사항

1. **상수 추가** (기존 `_GAP_MEDIAN_KEYS` 아래):
```python
# SPEC-LOTTO-098: 구간별 번호 선택 분포(zone_coverage) 버킷. 6개 고정 버킷.
# zones_covered: 본번호 6개가 점유하는 서로 다른 9개 구간([1-5],[6-10],...,[41-45]) 수 (1~6)
_ZONE_COV_KEYS = ["1", "2", "3", "4", "5", "6"]
_zone_coverage_cache: dict[str, dict] = {}
```

2. **`invalidate_cache()` 수정** (기존 함수에 추가):
```python
_zone_coverage_cache.clear()
```

3. **메인 함수 추가**:
```python
def get_zone_coverage_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """본번호 6개의 구간 커버리지(zone_coverage) 6개 버킷 분포를 반환한다 (SPEC-LOTTO-098).

    - 9개 구간: [1-5],[6-10],[11-15],[16-20],[21-25],[26-30],[31-35],[36-40],[41-45]
    - 구간 인덱스: (num - 1) // 5 (0~8)
    - zones_covered: 6개 본번호가 점유한 서로 다른 구간 수 (1~6)
    - 키: "1"/"2"/"3"/"4"/"5"/"6" (6개 고정 버킷)
    - full_spread_pct: zones_covered==6 비율
    - concentrated_pct: zones_covered<=3 비율
    """
    global _zone_coverage_cache
    if not draws:
        dist = {k: {"count": 0, "pct": 0.0} for k in _ZONE_COV_KEYS}
        return {
            "total_draws": 0,
            "avg_zones_covered": 0.0,
            "most_common_zones": "1",
            "full_spread_pct": 0.0,
            "concentrated_pct": 0.0,
            "zone_coverage_distribution": dist,
        }

    cache_key = str(len(draws))
    if cache_key in _zone_coverage_cache:
        return _zone_coverage_cache[cache_key]

    dist = {k: {"count": 0, "pct": 0.0} for k in _ZONE_COV_KEYS}
    total = len(draws)
    zones_list: list[int] = []
    for draw in draws:
        nums = draw.numbers()  # 정렬된 본번호 6개 (보너스 제외)
        zones = len(set((n - 1) // 5 for n in nums))
        zones_list.append(zones)
        dist[str(zones)]["count"] += 1

    for k in _ZONE_COV_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    avg = round(sum(zones_list) / total, 2)
    # 동률 시 _ZONE_COV_KEYS 정의 순서상 앞선(=더 작은) 버킷이 이기도록 순서대로 찾는다.
    max_cnt = max(dist[k]["count"] for k in _ZONE_COV_KEYS)
    most_common = next(k for k in _ZONE_COV_KEYS if dist[k]["count"] == max_cnt)
    full = sum(1 for z in zones_list if z == 6)
    conc = sum(1 for z in zones_list if z <= 3)

    result: dict[str, Any] = {
        "total_draws": total,
        "avg_zones_covered": avg,
        "most_common_zones": most_common,
        "full_spread_pct": round(full / total * 100, 2),
        "concentrated_pct": round(conc / total * 100, 2),
        "zone_coverage_distribution": dist,
    }
    _zone_coverage_cache[cache_key] = result
    return result
```

### `lotto/web/routes/api.py` 수정 사항

`/stats/gap_median_dist` 엔드포인트 직후에 추가:

```python
@router.get("/stats/zone_coverage")
async def get_zone_coverage_stats_route(
    limit: Optional[int] = Query(None, description="최근 N 회차만 분석 (미지정 시 전체)")  # noqa: UP045
) -> dict[str, Any]:
    """본번호 6개의 구간 커버리지(zone_coverage) 6개 버킷 분포를 반환합니다 (SPEC-LOTTO-098).

    - 9개 구간: [1-5],[6-10],[11-15],[16-20],[21-25],[26-30],[31-35],[36-40],[41-45]
    - 키: "1"/"2"/"3"/"4"/"5"/"6"
    - avg_zones_covered(평균 커버 구간 수) / most_common_zones(동률 시 키 순서상 앞선 것)
      / full_spread_pct(zones_covered==6 비율) / concentrated_pct(zones_covered<=3 비율)
      / zone_coverage_distribution 을 제공한다.
    - zone_coverage_distribution 은 6개 키를 항상 포함한다(미관측 0 유지).
    - 데이터 부재 시에도 200 으로 정상 응답 (total_draws=0).
    """
    draws = wd.get_draws()
    if limit is not None and draws:
        draws = draws[-limit:]
    return wd.get_zone_coverage_stats(draws)
```

### `lotto/web/routes/pages.py` 수정 사항

`gap_median_dist_page` 함수 직후에 추가:

```python
@router.get("/stats/zone-coverage")
async def zone_coverage_page(request: Request) -> TemplateResponse:
    """구간별 번호 선택 분포 페이지 (SPEC-LOTTO-098)."""
    draws = wd.get_draws()
    stats = wd.get_zone_coverage_stats(draws)
    return _render(request, "zone_coverage.html", {
        "active_tab": "zone_coverage",
        "stats": stats,
        "title": "구간별 번호 선택 분포",
    })
```

### `lotto/web/templates/zone_coverage.html` 신규 생성

`gap_median_dist.html`을 참고하여 구간 커버리지 분포 차트 및 통계 표시.
핵심 텍스트: "구간별 번호 선택 분포" 포함 필수.

템플릿 표시 항목:
- total_draws (총 분석 회차)
- avg_zones_covered (평균 커버 구간 수)
- most_common_zones (최빈 커버 구간 수)
- full_spread_pct (완전 분산 비율)
- concentrated_pct (집중 비율)
- zone_coverage_distribution (분포 차트: "1"~"6" 버킷)

### `lotto/web/templates/base.html` 수정 사항

두 개의 nav_items 리스트(desktop, mobile)에 각각 아래 항목 추가:
- `('/stats/zone-coverage', 'zone_coverage', '구간커버리지')`

위치: `('/stats/gap-median-dist', 'gap_median_dist', '간격 중앙값 구간 분포')` 직후

또한 active_tab == 'zone_coverage' 처리:
```
{% elif active_tab == 'zone_coverage' %}구간별 번호 선택 분포 분석
```

## Phase 3: REFACTOR — 정리

- 불필요한 코드 제거, 변수명 명확화
- ruff check / mypy 통과 확인
- 테스트 커버리지 85%+ 확인

## 구현 순서 (TDD)

1. `tests/test_zone_coverage_stats.py` 작성 → 전체 RED 확인
2. `lotto/web/data.py` 수정 → 단위 테스트 GREEN
3. `lotto/web/routes/api.py` 수정 → API 테스트 GREEN
4. `lotto/web/routes/pages.py` 수정 → 페이지 라우트 GREEN
5. `lotto/web/templates/zone_coverage.html` 생성 → 템플릿 테스트 GREEN
6. `lotto/web/templates/base.html` 수정 → 메뉴 링크 GREEN
7. 전체 테스트 실행 및 커버리지 확인

## 예상 신규 테스트 수

약 38~42개 (AC-01~50 기준, 일부 AC는 단일 assert, 일부는 다중 assert로 통합 가능)

## Python 3.9 호환 주의 사항

- `list[DrawResult] | None` → Python 3.10+ 문법이나, data.py 기존 코드가 이미 사용 중이므로 동일하게 적용
- `zip(strict=True)` 금지 → 이 SPEC에는 zip 미사용이므로 해당 없음
- `match/case` 금지 → if/elif/else 체인 사용
- `(n - 1) // 5` 정수 나눗셈 → Python 3.9 호환
