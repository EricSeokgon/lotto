# SPEC-LOTTO-088 구현 계획

## 방법론

TDD (RED → GREEN → REFACTOR). 기존 SPEC-087(중앙값 구간 분포)의
5개 키 분포 패턴을 그대로 따른다.

## 변경 파일

1. `lotto/web/data.py`
   - 상수 `_GAP_VAR_KEYS` 추가, 캐시 `_gap_var_cache` 추가.
   - 헬퍼 `_compute_gap_variance(numbers)`, `_gap_variance_bucket(numbers)` 추가.
   - 메인 `get_gap_variance_stats(draws)` 추가 (get_median_range_stats 뒤).
   - `invalidate_cache()` 에 `_gap_var_cache.clear()` 추가 + docstring 한 줄.

2. `lotto/web/routes/api.py`
   - `GET /stats/gap_variance` 엔드포인트 추가.

3. `lotto/web/routes/pages.py`
   - `GET /stats/gap-variance` 페이지 라우트 추가 (active_tab="gap_variance").

4. `lotto/web/templates/gap_variance.html`
   - median_range.html 패턴 기반 다크모드 Tailwind 템플릿.

5. `lotto/web/templates/base.html`
   - 데스크톱/모바일 nav 에 `("/stats/gap-variance", "gap_variance", "간격분산")` 추가.
   - active_tab 타이틀 분기 추가.

6. `tests/test_gap_variance_analysis.py`
   - ~27 테스트 (빈 데이터, 구간 분류, 경계, 구조/집계, 4-draw 픽스처, 캐시, 라우트).

## 핵심 로직

```python
def _compute_gap_variance(numbers):
    s = sorted(numbers)
    gaps = [s[i + 1] - s[i] for i in range(5)]
    mean = sum(gaps) / 5
    return sum((g - mean) ** 2 for g in gaps) / 5
```

## 제약

- Python 3.9: walrus/zip(strict)/match-case 금지.
- 기존 함수 수정 금지(invalidate_cache 의 추가 라인 제외).
- 모분산 사용(/5).
