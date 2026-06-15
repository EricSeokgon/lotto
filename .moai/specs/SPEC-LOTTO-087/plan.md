# SPEC-LOTTO-087 구현 계획

## 대상 파일
- `lotto/web/data.py`: `_MEDIAN_RANGE_KEYS`, `_median_range_cache`,
  `_median_range_bucket`, `get_median_range_stats` 추가 + `invalidate_cache`에 캐시 clear 추가
- `lotto/web/routes/api.py`: GET /api/stats/median_range
- `lotto/web/routes/pages.py`: GET /stats/median-range
- `lotto/web/templates/median_range.html`: 신규 페이지 (sum_range_detailed.html 패턴)
- `lotto/web/templates/base.html`: "중앙값구간" 네비 링크 + 타이틀 매핑
- `tests/test_median_range_analysis.py`: ~27 테스트

## 충돌 회피
- 기존 `_median_bucket`(SPEC-071, 9구간)과 충돌 → 신규 헬퍼는 `_median_range_bucket`.

## 핵심 로직
```
def _median_range_bucket(numbers):
    s = sorted(numbers)
    median = (s[2] + s[3]) / 2
    if median < 10: return "1-9"
    if median < 20: return "10-19"
    if median < 30: return "20-29"
    if median < 40: return "30-39"
    return "40-45"
```

## 응답 구조
- total_draws, avg_median(2dp), most_common_range(동률 시 키 순서 앞선 것),
  central_median_pct("20-29" 비율 2dp), median_range_distribution(5키).

## TDD 순서
RED(테스트 작성) → GREEN(data.py + 라우트 + 템플릿) → REFACTOR(검증).
