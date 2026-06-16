# SPEC-LOTTO-094 구현 계획

## 대상 파일

- `lotto/web/data.py`
  - 상수 `_ALTERNATION_KEYS = ["교차0".."교차5"]`, 캐시 `_alternation_cache` 추가
  - 헬퍼 `_count_alternations(numbers)` 추가 (정렬 후 인접 쌍 홀짝 교차 횟수 0~5)
  - 집계 `get_alternation_stats(draws)` 추가 (SPEC-093 `get_first_last_zone_stats` 뒤에 삽입)
  - `invalidate_cache()` 에 `_alternation_cache.clear()` 추가
- `lotto/web/routes/api.py`
  - GET /stats/alternation 엔드포인트 추가 (prefix /api → /api/stats/alternation)
- `lotto/web/routes/pages.py`
  - GET /stats/alternation 페이지 라우트 추가 → alternation.html
- `lotto/web/templates/alternation.html` 신규 생성 (다크모드 Tailwind, JS 없음)
- `lotto/web/templates/base.html`
  - 데스크탑/모바일 nav 에 "홀짝교차" → /stats/alternation 추가
  - active_tab 제목 블록에 'alternation' → "홀짝 교차 패턴 분포 분석" 추가
- `tests/conftest.py` 는 invalidate_cache 로 캐시 격리하므로 자동 처리됨

## 알고리즘

`_count_alternations`: sorted(numbers) 후 i in range(5) 동안
(sorted[i] % 2) != (sorted[i+1] % 2) 이면 +1 → 0~5 반환.

`get_alternation_stats`:
1. cache_key = str(len(draws)) 조회
2. 빈 입력 → 일관된 빈 구조 반환
3. 각 회차 교차 횟수 누적, dist[f"교차{alt}"] 카운트
4. pct = round(count/total*100, 2)
5. most_common_level = 동률 시 키 순서상 앞선 값
6. full_alternation_pct = "교차5" 비율
7. avg_alternation = round(total_alt/total, 2)
8. 캐시 후 반환

## 기존 기능과의 관계

SPEC-084(`get_parity_transition_stats`)는 동일한 교차/전환 횟수 산출 로직을 쓰지만
출력 구조(정수 키 "0"~"5", high_alternation_pct=전환>=4 비율, most_common 정수)가
완전히 다르다. 본 SPEC은 한국어 키("교차0"~"교차5"), full_alternation_pct(=교차5 비율),
most_common_level(문자열) 의 독립 계약을 가진다. 기존 함수는 수정하지 않는다.

## TDD 절차

RED: `tests/test_alternation_analysis.py` 작성 (~28 tests) → 실패 확인
GREEN: data.py / api.py / pages.py / 템플릿 구현 → 통과
REFACTOR: 중복 제거 및 docstring 정리, 전체 회귀 확인
