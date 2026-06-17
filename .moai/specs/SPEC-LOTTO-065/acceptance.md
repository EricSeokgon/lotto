---
id: SPEC-LOTTO-065
version: 0.1.0
status: Planned
created: 2026-06-10
updated: 2026-06-10
author: ircp
---

# SPEC-LOTTO-065 인수 기준 (Acceptance Criteria)

표준편차 분석 기능의 인수 기준. 모든 시나리오는 Given-When-Then 형식이며 각
항목에 추적성을 위해 관련 요구사항 ID를 표기한다.

## 검증용 픽스처 (손계산)

본번호 6개에 대해 mean = sum/6, variance = sum((n-mean)**2)/6,
std = variance ** 0.5, 회차당 std는 소수 둘째 자리 반올림.

| 회차 | 본번호 (6개) | mean | std (2dec) | 카테고리 | bucket |
|------|--------------|------|-----------|----------|--------|
| D1 | [1, 2, 3, 4, 5, 6] | 3.5 | 1.71 | low | 0-4 |
| D4 | [10, 15, 20, 25, 30, 35] | 22.5 | 8.54 | low | 8-12 |
| D6 | [5, 10, 15, 20, 25, 40] | 19.17 | 11.33 | mid | 8-12 |
| D2 | [1, 2, 3, 4, 5, 45] | 10.0 | 15.71 | high | 12-16 |

카테고리 경계: low = std < 10.0, mid = 10.0 ≤ std < 14.0, high = std ≥ 14.0.
bucket 경계: "a-b"는 a ≤ v < b, "20+"는 v ≥ 20.

4개 회차 [D1, D4, D6, D2] 전체 집계 기대값:

- total_draws = 4
- avg_std = round((1.71 + 8.54 + 11.33 + 15.71) / 4, 2) = round(37.29/4, 2) = 9.32
- min_std = 1.71
- max_std = 15.71
- low_std_count = 2 (D1, D4), mid_std_count = 1 (D6), high_std_count = 1 (D2)
- low_std_pct = 50.0, mid_std_pct = 25.0, high_std_pct = 25.0
- std_distribution = {"0-4": 1, "4-8": 0, "8-12": 2, "12-16": 1, "16-20": 0, "20+": 0}
- most_common_bucket = "8-12"

## 시나리오

### AC-01: 회차당 표준편차 계산 (REQ-SD-002, REQ-SD-012)

- Given: 본번호 [1, 2, 3, 4, 5, 6]인 회차 하나
- When: `get_std_stats([D1])`를 호출하면
- Then: 해당 회차의 std는 1.71(모표준편차, 6으로 나눔)로 계산되고
  avg_std/min_std/max_std 모두 1.71이다.

### AC-02: 양극단 회차의 높은 표준편차 (REQ-SD-002)

- Given: 본번호 [1, 2, 3, 4, 5, 45]인 회차 하나
- When: `get_std_stats([D2])`를 호출하면
- Then: std는 15.71로 계산되고 high 카테고리(≥14.0)에 속한다.

### AC-03: 평균 표준편차 집계 (REQ-SD-003)

- Given: 픽스처 4개 회차 [D1, D4, D6, D2]
- When: `get_std_stats(draws)`를 호출하면
- Then: avg_std는 9.32(=37.29/4, 2 decimals)이다.

### AC-04: 최소/최대 표준편차 (REQ-SD-004)

- Given: 픽스처 4개 회차
- When: 집계하면
- Then: min_std = 1.71(D1), max_std = 15.71(D2)이다.

### AC-05: 저/중/고 카테고리 분류 (REQ-SD-005)

- Given: 픽스처 4개 회차
- When: 집계하면
- Then: low_std_count = 2(D1, D4), mid_std_count = 1(D6),
  high_std_count = 1(D2)이고 세 합이 total_draws(4)와 같다.

### AC-06: 카테고리 비율 (REQ-SD-006)

- Given: 픽스처 4개 회차
- When: 집계하면
- Then: low_std_pct = 50.0, mid_std_pct = 25.0, high_std_pct = 25.0이다.

### AC-07: 카테고리 경계값 (REQ-SD-005)

- Given: std가 정확히 10.0인 회차와 정확히 14.0인 회차
- When: 분류하면
- Then: std == 10.0은 mid(low 아님), std == 14.0은 high(mid 아님)로 분류된다
  (low: <10.0, mid: 10.0~<14.0, high: ≥14.0).

### AC-08: std_distribution 고정 6키 항상 포함 (REQ-SD-007)

- Given: 픽스처 4개 회차
- When: 집계하면
- Then: std_distribution은 정확히 6개 키 "0-4","4-8","8-12","12-16","16-20","20+"를
  이 순서로 모두 포함하며 값은 {"0-4":1,"4-8":0,"8-12":2,"12-16":1,"16-20":0,"20+":0}이다
  (출현 없는 "4-8","16-20","20+"도 0으로 존재).

### AC-09: bucket 경계 할당 (REQ-SD-007)

- Given: std 값 v
- When: bucket을 배정하면
- Then: a ≤ v < b 규칙으로 "a-b"에 배정되고(예: v=8.54 → "8-12", v=11.33 → "8-12",
  v=15.71 → "12-16"), v ≥ 20이면 "20+"에 배정된다.

### AC-10: 최빈 구간 (REQ-SD-008)

- Given: 픽스처 4개 회차 (std_distribution의 최대값은 "8-12"=2)
- When: 집계하면
- Then: most_common_bucket = "8-12"이다.

### AC-11: 최빈 구간 동률 시 정의 순서 우선 (REQ-SD-008)

- Given: 두 bucket의 count가 동률로 최대인 회차 집합
- When: most_common_bucket을 결정하면
- Then: 정의된 순서("0-4" → "4-8" → ... → "20+") 중 먼저 오는 라벨이 선택된다.

### AC-12: 빈 데이터 처리 (REQ-SD-013)

- Given: 빈 draws (None 또는 [])
- When: `get_std_stats([])`를 호출하면
- Then: total_draws=0, avg_std=0.0, min_std=0.0, max_std=0.0,
  low_std_count=0, mid_std_count=0, high_std_count=0,
  low_std_pct=0.0, mid_std_pct=0.0, high_std_pct=0.0,
  std_distribution은 6키 모두 0, most_common_bucket="0-4"이다.

### AC-13: 본번호만 사용, 보너스 제외 (REQ-SD-011)

- Given: 보너스 번호가 포함된 회차
- When: std를 계산하면
- Then: 본번호 6개만으로 mean/variance/std가 계산되고 보너스는 전혀 반영되지
  않는다.

### AC-14: 입력 불변성 (REQ-SD-014)

- Given: 임의의 draws 리스트
- When: `get_std_stats(draws)`를 호출하면
- Then: 입력 draws 리스트와 각 원소는 변경되지 않는다.

### AC-15: 결정성 (REQ-SD-012)

- Given: 동일한 draws 입력
- When: `get_std_stats`를 두 번 호출하면
- Then: 두 결과 dict가 완전히 동일하다.

### AC-16: 캐시 동작 (REQ-SD-016)

- Given: 동일 길이의 draws
- When: 두 번 호출하면
- Then: 두 번째 호출은 `_std_cache[str(len(draws))]`에 저장된 결과를 반환하고,
  `invalidate_cache()` 호출 후에는 캐시가 비워져 재계산된다.

### AC-17: JSON API 200 응답 (REQ-SD-009)

- Given: 실행 중인 웹 앱
- When: `GET /api/stats/std`를 요청하면
- Then: 상태 코드 200과 함께 total_draws, avg_std, min_std, max_std,
  low/mid/high count·pct, std_distribution, most_common_bucket을 포함한 JSON이
  반환된다.

### AC-18: 빈 데이터에서도 API 200 (REQ-SD-009, REQ-SD-013)

- Given: 데이터가 없는 상태
- When: `GET /api/stats/std`를 요청하면
- Then: 상태 코드 200과 함께 모든 값이 0/0.0인 빈 상태 JSON
  (std_distribution 6키 모두 0, most_common_bucket="0-4")이 반환된다.

### AC-19: 통계 페이지 렌더링 (REQ-SD-010)

- Given: 실행 중인 웹 앱
- When: `GET /stats/std`를 요청하면
- Then: 상태 코드 200과 함께 평균/최소/최대 표준편차 요약 카드,
  저/중/고 카테고리 개수·비율, std_distribution bucket의 bar-like 표가 렌더된다.

### AC-20: 네비게이션 링크 (비기능 — base.html)

- Given: 모든 페이지의 공통 네비게이션
- When: 데스크톱/모바일 네비게이션을 확인하면
- Then: "표준편차" 텍스트의 `/stats/std` 링크가 양쪽 모두에 존재한다.

### AC-21: 6개 미만 회차 스킵 (REQ-SD-015)

- Given: 본번호가 6개 미만인 회차가 섞인 draws
- When: `get_std_stats(draws)`를 호출하면
- Then: 해당 회차는 집계에서 제외되고 예외가 발생하지 않으며 total_draws는
  유효 회차 수만 센다.

## Definition of Done

- [ ] `get_std_stats(draws)`가 REQ-SD-001~016을 모두 충족
- [ ] `GET /stats/std` + `GET /api/stats/std` 라우트 추가, 둘 다 빈 데이터에서 200
- [ ] `std_analysis.html` 템플릿 추가 (요약 카드 + bucket bar-like 표)
- [ ] `base.html` 데스크톱·모바일 네비에 "표준편차" → `/stats/std` 추가
- [ ] `tests/test_std_analysis.py`에 최소 20개 테스트, 전부 통과
- [ ] `mypy.ini`에 `test_std_analysis` override 등록, mypy 0건
- [ ] 기존 1480개 테스트 무회귀 (코어 `lotto/*.py` 미변경)
- [ ] Python 3.9 호환 (match/case·zip(strict=) 미사용)
