# SPEC-LOTTO-089 구현 계획

## 방법론

TDD (RED → GREEN → REFACTOR). `quality.yaml` development_mode: tdd.

## 변경 파일

1. `lotto/web/data.py`
   - 상수 `_LOW_HIGH_KEYS`, `_LOW_HIGH_BOUNDARY`, 캐시 `_low_high_cache` 추가.
   - 헬퍼 `_low_high_combo(numbers)` 추가.
   - 집계 함수 `get_low_high_stats(draws)` 추가 (SPEC-088 `get_gap_variance_stats` 패턴).
   - `invalidate_cache()`에 `_low_high_cache.clear()` 추가.
2. `lotto/web/routes/api.py`
   - GET `/stats/low_high` 엔드포인트 추가 (`get_low_high_stats_endpoint`).
3. `lotto/web/routes/pages.py`
   - GET `/stats/low-high` 페이지 라우트 추가 (`low_high_page`).
4. `lotto/web/templates/low_high.html`
   - `median_range.html`/`gap_variance.html` 다중 키 분포 패턴 (다크모드 Tailwind).
5. `lotto/web/templates/base.html`
   - 데스크탑/모바일 nav에 "저고균형" 링크, active_tab 제목 블록 추가.
6. `tests/test_low_high_analysis.py`
   - 약 27개 테스트 (빈/단일/경계/구조/픽스처/캐시/라우트).

## 핵심 로직

```python
def _low_high_combo(numbers: list) -> str:
    low_count = sum(1 for n in numbers if n <= 22)
    high_count = 6 - low_count
    return f"{low_count}저{high_count}고"
```

most_common_combo 동률 처리: `_LOW_HIGH_KEYS` 정의 순서대로 순회하여
첫 최대 count 키 선택(정의 순서상 앞선 = "0저6고"이 먼저).

## 충돌 검토 결과

- 기존 SPEC-061: `get_high_low_stats`, `_high_low_cache`, `/stats/high-low`, `high_low.html`.
- 신규 SPEC-089: `get_low_high_stats`, `_low_high_cache`, `/stats/low-high`(page) ·
  `/stats/low_high`(api), `low_high.html`.
- 함수/캐시/라우트/템플릿 이름 모두 구분됨 → 네이밍 충돌 없음.

## 제약

- Python 3.9 (walrus/zip(strict)/match 금지).
- 기존 함수 수정 금지 (invalidate_cache 한 줄 추가 제외).
