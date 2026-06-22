# SPEC-LOTTO-107 구현 계획 (Implementation Plan)

## 목표

전체 회차를 초기/중기/최근 3구간으로 균등 분할하여 번호별 구간 출현 횟수·비율·델타·
추세(rising/falling/stable)를 산출하는 `get_period_trend()` 함수와 API·페이지·템플릿·
내비게이션을 추가한다. 코어 모듈은 변경하지 않는다.

## 파일 영향도 (File Impact)

| 파일 | 변경 유형 | 내용 |
|------|-----------|------|
| `lotto/web/data.py` | 추가 | `_period_trend_cache`, `_PERIOD_TREND_DISCLAIMER`, 헬퍼, `get_period_trend()`; `invalidate_cache()`에 캐시 클리어 1줄 |
| `lotto/web/routes/api.py` | 추가 | `GET /api/stats/period-trend` 라우트 (top_n 1~45) |
| `lotto/web/routes/pages.py` | 추가 | `GET /stats/period-trend` 페이지 라우트 |
| `lotto/web/templates/period_trend.html` | 신규 | 상승/하락 상위 테이블, 구간 요약, top_n 선택기, disclaimer |
| `lotto/web/templates/base.html` | 추가 | desktop_nav_items·nav_items에 '추이 분석' 탭, 타이틀 블록 |
| `tests/test_period_trend.py` | 신규 | RED 단계 ~20개 테스트 |

## 알고리즘 (Algorithm)

1. None/빈 입력 가드 → 0 채움 구조 반환 (REQ-PT-004).
2. `n=len(draws)`; `early=draws[0:n//3]`, `middle=draws[n//3:2*n//3]`,
   `recent=draws[2*n//3:]` (FROZEN 슬라이스 공식).
3. 각 구간에서 번호 1~45 출현 횟수 집계 (`draw.numbers()` 메서드 호출).
4. pct = 구간이 비면 0.0, 아니면 round(count/len(period)*100, 2).
5. delta = count_recent - count_early; trend = rising/falling/stable.
6. top_rising = sorted(numbers, key=(-delta, number))[:top_n].
7. top_falling = sorted(numbers, key=(delta, -number))[:top_n].

## 테스트 전략 (Test Strategy)

- 손계산 9회차 픽스처(검증 완료)로 핵심 값·정렬·분포 검증.
- 엣지: None, [], n=1, n=2.
- API: 200/422/기본 top_n; 페이지: 200/라벨/빈 데이터 200.
- 실행: `pytest tests/test_period_trend.py -v --no-cov`.
- 린트: `ruff check` 대상 파일 clean.

## 캐시 격리 (Cache Isolation)

- 모듈 레벨 `_period_trend_cache`는 conftest `_isolate_data_cache` autouse
  픽스처가 `invalidate_cache()`를 호출하여 테스트 간 격리한다.
- 캐시 키에 top_n 포함 — 서로 다른 top_n은 서로 다른 top_rising/top_falling.

## TDD 단계

1. RED: `tests/test_period_trend.py` 작성 → 실패 확인.
2. GREEN: `get_period_trend()` 구현 → 통과.
3. API/페이지/템플릿/내비 추가 → 전체 통과.
4. ruff clean 확인.
5. 커밋 (feat) → 문서 동기화 커밋 (docs).
