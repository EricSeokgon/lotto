# SPEC-LOTTO-095 구현 계획

## 대상 파일

- `lotto/web/data.py`
  - 상수 `_SPAN_KEYS = ["10 이하","11-20","21-25","26-30","31-35","36-40","41 이상"]`,
    캐시 `_span_cache: dict[str, Any] = {}` 추가 (`_alternation_cache` 인근)
  - 헬퍼 `_span_bucket(span)` 추가 (스팬 정수 → 7개 버킷 키 중 하나)
  - 집계 `compute_span_distribution(draws)` 추가 (SPEC-094
    `get_alternation_stats` 뒤에 삽입)
  - `invalidate_cache()` 에 `_span_cache.clear()` 추가
- `lotto/web/routes/api.py`
  - GET /stats/span 엔드포인트 추가 (prefix /api → /api/stats/span)
- `lotto/web/routes/pages.py`
  - GET /stats/span 페이지 라우트 추가 → span.html
- `lotto/web/templates/span.html` 신규 생성 (다크모드 Tailwind, JS 없음)
- `lotto/web/templates/base.html`
  - 데스크탑/모바일 nav 에 "번호스팬" → /stats/span 추가
  - active_tab 제목 블록에 'span' → "번호 스팬 분포 분석" 추가
- `tests/conftest.py` 는 invalidate_cache 로 캐시 격리하므로 자동 처리됨

## 알고리즘

`_span_bucket(span)`: 경계 비교를 키 정의 순서대로 수행한다.
- span ≤ 10 → "10 이하"
- span ≤ 20 → "11-20"
- span ≤ 25 → "21-25"
- span ≤ 30 → "26-30"
- span ≤ 35 → "31-35"
- span ≤ 40 → "36-40"
- 그 외(span ≥ 41) → "41 이상"

각 버킷은 상한 비교를 순차로 적용하므로 경계값(10/20/25/30/35/40/41)이
정확히 하나의 버킷에만 배정된다(N1).

`compute_span_distribution(draws)`:
1. cache_key = str(len(draws) if draws else 0) 조회
2. 7개 키 전부 {count:0, pct:0.0} 로 dist 초기화
3. 빈 입력(None/[]) → total_draws=0, avg_span=0.0,
   most_common_range="10 이하", narrow_pct=0.0, wide_pct=0.0,
   dist 그대로의 일관된 빈 구조 반환 + 캐시
4. 각 회차: nums = draw.numbers() (본번호 6개), span = max(nums) - min(nums),
   total_span 누적, dist[_span_bucket(span)]["count"] += 1
5. pct = round(count/total*100, 2)
6. most_common_range = 동률 시 `_SPAN_KEYS` 순서상 앞선 값
   (max_cnt 산출 후 next(k for k in _SPAN_KEYS if count==max_cnt))
7. narrow_pct = ("10 이하" + "11-20" count) / total * 100, 소수 2자리
8. wide_pct = ("36-40" + "41 이상" count) / total * 100, 소수 2자리
9. avg_span = round(total_span/total, 2)
10. 캐시 후 반환

## 기존 기능과의 관계

SPEC-093(`get_first_last_zone_stats`)은 max-min을 `avg_span` 보조 지표로
노출하지만 주 분포는 3구간 밴드 조합(AA~CC)이며 버킷화하지 않는다.
SPEC-064(`get_min_max_stats`)는 최소/최대 개별 값 통계다. 본 SPEC은
스팬 값을 7개 폭 구간으로 버킷화하는 독립 계약(`span_distribution`,
narrow_pct/wide_pct, most_common_range)을 가지며 기존 함수는 수정하지 않는다.

## TDD 절차

RED: `tests/test_span.py` 작성 (~51 tests, AC-01~AC-51) → 실패 확인
GREEN: data.py / api.py / pages.py / 템플릿 / base.html nav 구현 → 통과
REFACTOR: 중복 제거 및 docstring 정리, 전체 회귀 확인 (2412 → 2412+ tests)

## 검증

- `python -m pytest tests/test_span.py -v`
- `python -m pytest` (전체 회귀, 기존 통과 유지)
- mypy: `tests/test_span.py` override 등록 후 통과 확인
- 수동: GET /api/stats/span → 200 JSON 7키, GET /stats/span → 200 text/html
