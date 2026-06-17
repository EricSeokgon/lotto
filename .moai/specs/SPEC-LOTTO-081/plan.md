# SPEC-LOTTO-081 구현 계획

## 방법론
TDD (RED-GREEN-REFACTOR). 기존 SPEC-080(max_gap_dist), SPEC-078(triple_run) 패턴 재사용.

## 대상 파일
1. `lotto/web/data.py`
   - 상수 `_EVEN_RUN_KEYS = ["0", "1", "2", "3"]`
   - 캐시 `_even_run_cache: dict[str, Any] = {}`
   - 헬퍼 `_count_even_runs(numbers)`
   - 함수 `get_even_run_stats(draws)`
   - `invalidate_cache()`에 `_even_run_cache.clear()` 추가
2. `lotto/web/routes/api.py` — GET /stats/even_run (router prefix /api)
3. `lotto/web/routes/pages.py` — GET /stats/even-run → even_run.html
4. `lotto/web/templates/even_run.html` — triple_run.html 기반 4키 분포 페이지
5. `lotto/web/templates/base.html` — 내비 2곳 + active_tab 타이틀 블록
6. `tests/test_even_run_analysis.py` — 약 27개 테스트

## 알고리즘
정렬된 짝수 리스트에서 인접 차이 2인 연속 구간(길이>=2)의 수를 센다.

## 제약
- Python 3.9 호환 (walrus/match-case/zip strict 금지)
- 기존 함수 무수정
- 캐시 격리: conftest autouse 픽스처가 invalidate_cache 호출

## 검증
- `/home/sklee/.local/bin/pytest tests/test_even_run_analysis.py`
- `/home/sklee/.local/bin/ruff check`
