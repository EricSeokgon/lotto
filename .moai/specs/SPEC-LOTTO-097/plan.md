# Implementation Plan: SPEC-LOTTO-097

## Overview
번호 간격 중앙값 구간 분포 분석 기능을 TDD 방식으로 구현한다.
기존 SPEC-096(min_gap_dist), SPEC-080(max_gap_dist) 패턴을 그대로 따른다.

## Phase 1: RED — 테스트 작성

### 파일: `tests/test_gap_median_dist_stats.py`

```
- AC-01~03: 빈 데이터 구조 검증 테스트
- AC-04~15: gap_median 버킷 분류 테스트 (각 버킷별)
- AC-16~18: 중앙값 계산 정확성 테스트
- AC-19~22: 다중 회차 집계 테스트
- AC-23~24: most_common_range 선택 테스트
- AC-25~27: low_median_pct / high_median_pct 테스트
- AC-28~29: 캐시 동작 테스트
- AC-30~31: 소수점 반올림 테스트
- AC-32~34: API / 페이지 엔드포인트 테스트
- AC-35, 47: 템플릿 렌더링 테스트
- AC-36~46: _gap_median_bucket() 단위 테스트
- AC-48~49: 경계 및 전구간 분포 테스트
```

## Phase 2: GREEN — 최소 구현

### `lotto/web/data.py` 수정 사항

1. **상수 추가** (기존 `_MIN_GAP_KEYS` 근처):
```python
# SPEC-LOTTO-097: 번호 간격 중앙값(gap_median) 구간 버킷. 6개 고정 버킷.
_GAP_MEDIAN_KEYS = ["1-2", "3-4", "5-6", "7-8", "9-10", "11+"]
_gap_median_dist_cache: dict[str, dict] = {}
```

2. **`invalidate_cache()` 수정**:
```python
_gap_median_dist_cache.clear()
```

3. **버킷 함수 추가**:
```python
def _gap_median_bucket(g: int) -> str:
    """간격 중앙값 g를 6개 고정 구간 버킷 라벨로 변환한다 (SPEC-LOTTO-097)."""
    if g <= 2:
        return "1-2"
    elif g <= 4:
        return "3-4"
    elif g <= 6:
        return "5-6"
    elif g <= 8:
        return "7-8"
    elif g <= 10:
        return "9-10"
    else:
        return "11+"
```

4. **메인 함수 추가**:
```python
def get_gap_median_dist_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개의 인접 간격 중앙값(gap_median) 구간 분포를 분석합니다 (SPEC-LOTTO-097)."""
    cache_key = str(len(draws) if draws else 0)
    cached = _gap_median_dist_cache.get(cache_key)
    if cached is not None:
        return cached
    
    dist = {k: {"count": 0, "pct": 0.0} for k in _GAP_MEDIAN_KEYS}
    
    if not draws:
        empty_result = {
            "total_draws": 0,
            "avg_gap_median": 0.0,
            "most_common_range": "1-2",
            "low_median_pct": 0.0,
            "high_median_pct": 0.0,
            "gap_median_distribution": dist,
        }
        _gap_median_dist_cache[cache_key] = empty_result
        return empty_result
    
    total = len(draws)
    medians: list[int] = []
    for draw in draws:
        nums = draw.numbers()
        gaps = sorted([nums[i+1] - nums[i] for i in range(len(nums) - 1)])  # noqa: B905
        gm = gaps[len(gaps) // 2]  # 5개 간격의 중앙값 (인덱스 2)
        medians.append(gm)
        dist[_gap_median_bucket(gm)]["count"] += 1
    
    for k in _GAP_MEDIAN_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)
    
    avg = round(sum(medians) / total, 2)
    max_cnt = max(dist[k]["count"] for k in _GAP_MEDIAN_KEYS)
    most_common = next(k for k in _GAP_MEDIAN_KEYS if dist[k]["count"] == max_cnt)
    low = sum(1 for gm in medians if gm <= 4)
    high = sum(1 for gm in medians if gm >= 9)
    
    result = {
        "total_draws": total,
        "avg_gap_median": avg,
        "most_common_range": most_common,
        "low_median_pct": round(low / total * 100, 2),
        "high_median_pct": round(high / total * 100, 2),
        "gap_median_distribution": dist,
    }
    _gap_median_dist_cache[cache_key] = result
    return result
```

### `lotto/web/routes/api.py` 수정 사항

기존 `/stats/min_gap_dist` 엔드포인트 패턴을 복제:
```python
@router.get("/stats/gap_median_dist")
def api_gap_median_dist_stats(limit: int = 0):
    draws = _get_draws(limit)
    return get_gap_median_dist_stats(draws)
```

### `lotto/web/routes/pages.py` 수정 사항

```python
@router.get("/stats/gap-median-dist")
def page_gap_median_dist(request: Request):
    draws = data.get_all_draws()
    stats = data.get_gap_median_dist_stats(draws)
    return templates.TemplateResponse(
        "gap_median_dist.html",
        {"request": request, "stats": stats}
    )
```

### `lotto/web/templates/gap_median_dist.html` 신규 생성

기존 `min_gap_dist.html` 또는 `span_stats.html` 패턴을 따름:
- 제목: "번호 간격 중앙값 구간 분포"
- 요약 카드: total_draws, avg_gap_median, most_common_range, low_median_pct, high_median_pct
- 분포 테이블: 6개 구간별 count, pct 표시
- 차트: 막대 차트 (JavaScript)
- 한국어 레이블

### `lotto/web/templates/base.html` 수정 사항

사이드바 stats 섹션에 추가:
```html
<a href="/stats/gap-median-dist">간격 중앙값 구간 분포</a>
```

## Phase 3: REFACTOR — 정리

- docstring 완성 (함수 목적, Args, Returns, 연관 SPEC 명시)
- `# @MX:NOTE: [AUTO] SPEC-LOTTO-097` 어노테이션 추가
- `# @MX:SPEC: SPEC-LOTTO-097 REQ-GMD-xxx` 마킹
- 코드 중복 제거 (버킷 함수 패턴 일관성 확인)

## 테스트 실행 명령

```bash
cd /home/sklee/moai/lotto
python -m pytest tests/test_gap_median_dist_stats.py -v
```

## 완료 기준

- [ ] 49개 AC 모두 통과
- [ ] 기존 2498개 테스트 회귀 없음
- [ ] Python 3.9 호환 (`zip(strict=True)` 미사용, `match/case` 미사용)
- [ ] `get_gap_median_dist_stats` 함수 완성
- [ ] API 엔드포인트 `/api/stats/gap_median_dist` 동작
- [ ] 페이지 라우트 `/stats/gap-median-dist` 동작
- [ ] `gap_median_dist.html` 템플릿 렌더링
- [ ] `base.html` 사이드바 링크 추가
