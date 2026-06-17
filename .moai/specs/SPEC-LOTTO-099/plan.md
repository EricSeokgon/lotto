# SPEC-LOTTO-099 Implementation Plan

## Overview
사분위 분포 분석 기능을 TDD(RED-GREEN-REFACTOR) 방법론으로 구현한다.

## Reference Implementations
- SPEC-LOTTO-098: `get_zone_coverage_stats()` → 구간 커버리지 패턴 (가장 유사한 구조)
- SPEC-LOTTO-094: `get_alternation_stats()` → 패턴 조합 딕셔너리 구조
- SPEC-LOTTO-095: `get_span_stats()` → 단순 분포 + 평균값 반환 패턴

## Task Breakdown

### Task 1: 테스트 파일 작성 (RED Phase)
**파일**: `tests/web/test_quartile_dist_stats.py`

테스트 구조:
```
TestGetQuartileDistStatsEmpty       (AC-001~004)
TestGetQuartileDistStatsBoundary    (AC-005~014)
TestGetQuartileDistStatsCalc        (AC-015~025)
TestGetQuartileDistStatsMostCommon  (AC-026)
TestGetQuartileDistStatsCache       (AC-027~028)
TestGetQuartileDistStatsEdge        (AC-029~030, 042~045)
```

픽스처 패턴 (기존 SPEC 준수):
```python
from lotto.web.data import DrawResult, get_quartile_dist_stats, invalidate_cache

def make_draw(nums: list[int]) -> DrawResult:
    # 기존 테스트 파일의 make_draw 패턴 활용
    ...
```

### Task 2: 데이터 함수 구현 (GREEN Phase)
**파일**: `lotto/web/data.py`

추가 위치: `get_zone_coverage_stats()` 함수 직후 (파일 말미)

추가 내용:
1. 캐시 변수: `_quartile_dist_cache: dict[str, dict] = {}`
2. `invalidate_cache()` 내 `_quartile_dist_cache.clear()` 추가
3. `get_quartile_dist_stats()` 함수 구현

구현 핵심 로직:
```python
_quartile_dist_cache: dict[str, dict] = {}

def get_quartile_dist_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    cache_key = str(len(draws) if draws else 0)
    cached = _quartile_dist_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        result = {
            "total_draws": 0,
            "avg_q1": 0.0, "avg_q2": 0.0, "avg_q3": 0.0, "avg_q4": 0.0,
            "most_common_combination": "0-0-0-0",
            "balanced_pct": 0.0,
            "skewed_pct": 0.0,
            "quartile_distribution": {},
        }
        _quartile_dist_cache[cache_key] = result
        return result

    total = len(draws)
    dist: dict[str, dict[str, Any]] = {}
    q_sums = [0, 0, 0, 0]
    balanced_count = 0
    skewed_count = 0

    for draw in draws:
        nums = draw.numbers()
        counts = [0, 0, 0, 0]
        for n in nums:
            if n <= 11:
                counts[0] += 1
            elif n <= 22:
                counts[1] += 1
            elif n <= 33:
                counts[2] += 1
            else:
                counts[3] += 1
        key = f"{counts[0]}-{counts[1]}-{counts[2]}-{counts[3]}"
        if key not in dist:
            dist[key] = {"count": 0, "pct": 0.0}
        dist[key]["count"] += 1
        for i in range(4):
            q_sums[i] += counts[i]
        if all(1 <= c <= 2 for c in counts):
            balanced_count += 1
        if any(c >= 4 for c in counts):
            skewed_count += 1

    for k in dist:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    max_cnt = max(v["count"] for v in dist.values())
    most_common = min(
        (k for k, v in dist.items() if v["count"] == max_cnt)
    )

    result = {
        "total_draws": total,
        "avg_q1": round(q_sums[0] / total, 2),
        "avg_q2": round(q_sums[1] / total, 2),
        "avg_q3": round(q_sums[2] / total, 2),
        "avg_q4": round(q_sums[3] / total, 2),
        "most_common_combination": most_common,
        "balanced_pct": round(balanced_count / total * 100, 2),
        "skewed_pct": round(skewed_count / total * 100, 2),
        "quartile_distribution": dist,
    }
    _quartile_dist_cache[cache_key] = result
    return result
```

### Task 3: API 엔드포인트 추가 (GREEN Phase)
**파일**: `lotto/web/routes/api.py`

위치: `@router.get("/stats/zone_coverage")` 직후

```python
@router.get("/stats/quartile_dist")
async def get_quartile_dist_stats_route(
    limit: int = 0,
) -> dict[str, Any]:
    """사분위 분포 통계 (SPEC-LOTTO-099).

    - quartile_distribution: 관측된 조합 {"{q1}-{q2}-{q3}-{q4}": {count, pct}}
    """
    draws = wd.get_draws(limit=limit if limit > 0 else None)
    return wd.get_quartile_dist_stats(draws)
```

### Task 4: 페이지 라우트 추가 (GREEN Phase)
**파일**: `lotto/web/pages.py`

위치: zone_coverage 페이지 라우트 직후

```python
@router.get("/quartile-dist")
async def quartile_dist_page(request: Request) -> HTMLResponse:
    """사분위 분포 페이지 (SPEC-LOTTO-099)."""
    draws = wd.get_draws()
    stats = wd.get_quartile_dist_stats(draws)
    return templates.TemplateResponse(
        "quartile_dist.html",
        {"request": request, "stats": stats},
    )
```

### Task 5: HTML 템플릿 생성 (GREEN Phase)
**파일**: `lotto/web/templates/quartile_dist.html`

기존 `zone_coverage.html` 구조를 참고하여 작성:
- 제목: "사분위 분포 분석"
- 핵심 통계 카드: avg_q1~q4, balanced_pct, skewed_pct, most_common_combination
- 분포 테이블: 상위 조합 목록 (조합 키, 횟수, 비율)
- 한국어 UI 라벨 사용

### Task 6: 사이드바 내비게이션 추가 (GREEN Phase)
**파일**: `lotto/web/templates/base.html`

위치: zone_coverage 링크 직후

```html
<a href="/stats/quartile-dist" ...>사분위 분포</a>
```

## File Change Summary

| 파일 | 변경 유형 | 예상 라인 수 |
|------|----------|-------------|
| `lotto/web/data.py` | 수정 | +~80줄 |
| `lotto/web/routes/api.py` | 수정 | +~15줄 |
| `lotto/web/pages.py` | 수정 | +~10줄 |
| `lotto/web/templates/quartile_dist.html` | 신규 | ~120줄 |
| `lotto/web/templates/base.html` | 수정 | +~3줄 |
| `tests/web/test_quartile_dist_stats.py` | 신규 | ~350줄 |

## TDD Execution Order

1. RED: `tests/web/test_quartile_dist_stats.py` 작성 (모두 실패 확인)
2. GREEN Task 2: `data.py`에 `get_quartile_dist_stats()` 구현 (데이터 테스트 통과)
3. GREEN Task 3: `api.py` 엔드포인트 추가
4. GREEN Task 4: `pages.py` 라우트 추가
5. GREEN Task 5: `quartile_dist.html` 템플릿 생성
6. GREEN Task 6: `base.html` 내비게이션 링크 추가
7. REFACTOR: 코드 정리, ruff 린트 통과 확인
8. 전체 테스트 실행 (`pytest tests/`) 통과 확인

## Quality Gates

- [ ] `pytest tests/web/test_quartile_dist_stats.py` 45개 이상 테스트 통과
- [ ] `pytest tests/` (전체, 기존 2618개 + 신규) 통과
- [ ] `ruff check lotto/web/data.py lotto/web/routes/api.py lotto/web/pages.py` 통과
- [ ] Python 3.9 호환성: match/case 미사용, zip(strict=True) 미사용
- [ ] `invalidate_cache()` 내 `_quartile_dist_cache.clear()` 추가 확인

## Dependencies

- DrawResult.numbers() 메서드 (기존 구현 활용)
- get_draws() 함수 (기존 구현 활용)
- invalidate_cache() 함수 (기존 구현 수정)
- Jinja2 템플릿 시스템 (기존 설정 활용)
