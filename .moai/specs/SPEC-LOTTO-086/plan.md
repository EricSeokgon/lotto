# SPEC-LOTTO-086 구현 계획

## 대상 파일

1. `lotto/web/data.py`
   - 상수: `_SUM_RANGE_KEYS`, 캐시 `_sum_range_cache`
   - 헬퍼: `_sum_range_bucket(s: int) -> str`
   - 공개 함수: `get_sum_range_stats(draws) -> dict[str, Any]`
   - `invalidate_cache()`에 `_sum_range_cache.clear()` 추가
2. `lotto/web/routes/api.py`
   - `GET /stats/sum_range` (언더스코어)
3. `lotto/web/routes/pages.py`
   - `GET /stats/sum-range-detailed` → `sum_range_detailed.html`
4. `lotto/web/templates/sum_range_detailed.html` (신규)
5. `lotto/web/templates/base.html` — nav "합계구간" 추가 (데스크탑/모바일 2곳)
6. `tests/test_sum_range_analysis.py` (신규, ~27 테스트)

## 버킷 정의 (비균등)

```
s <= 60   → "21-60"
s <= 100  → "61-100"
s <= 130  → "101-130"
s <= 160  → "131-160"
s <= 200  → "161-200"
else      → "201-255"
```

## 충돌 검토 결과

- `get_sum_range_stats` / `_sum_range_cache`: 미존재 → 사용 가능
- `/api/stats/sum_range`(언더스코어): 미존재 → 사용 가능 (기존 `/api/stats/sum-range` 하이픈과 구별)
- `/stats/sum-range`(하이픈): SPEC-049 페이지 존재 → 페이지는 `/stats/sum-range-detailed` 사용
- `sum_range.html`: SPEC-049 존재 → `sum_range_detailed.html` 사용

## TDD 절차

RED → GREEN → REFACTOR. Python 3.9 호환(walrus/match/zip-strict 금지).
