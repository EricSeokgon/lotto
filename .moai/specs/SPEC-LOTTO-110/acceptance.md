# SPEC-LOTTO-110 인수 기준 (Acceptance Criteria)

## 손계산 픽스처 (Hand-Calculated Fixture)

`draw.date`는 `datetime.date` 객체이며 `.year`는 속성(int)으로 접근한다.

| 회차 | 추첨일                  | 연도 | 본번호                 |
|------|-------------------------|------|------------------------|
| D1   | date(2020, 3, 7)        | 2020 | 1, 2, 3, 4, 5, 6       |
| D2   | date(2020, 3, 14)       | 2020 | 1, 7, 8, 9, 10, 11     |
| D3   | date(2021, 5, 1)        | 2021 | 2, 12, 13, 14, 15, 16  |
| D4   | date(2023, 1, 7)        | 2023 | 3, 17, 18, 19, 20, 21  |

### 손계산 값

- total_draws = 4
- total_years = 3 (2020, 2021, 2023)
- yearly_summary (연도 오름차순):
  - [{year:2020, draw_count:2}, {year:2021, draw_count:1}, {year:2023, draw_count:1}]
- top_numbers_by_year["2020"] (top_n=3): 번호 1은 2회(count=2, pct=100.0),
  나머지(2,3,4,5,6,7,8,9,10,11)는 1회. count desc, 동률은 번호 asc →
  [{1,2,100.0}, {2,1,50.0}, {3,1,50.0}]
- top_numbers_by_year["2021"] (top_n=3):
  [{2,1,100.0}, {12,1,100.0}, {13,1,100.0}]
- top_years_by_number[0] (번호 1): 2020에서 2회 → best_year=2020, count=2, pct=100.0
- top_years_by_number[1] (번호 2): 2020(1회), 2021(1회) 동률 → 이른 연도 →
  best_year=2020, count=1, pct=50.0
- top_years_by_number[2] (번호 3): 2020(1회), 2023(1회) 동률 → best_year=2020
- top_years_by_number[44] (번호 45): 미출현 → best_year=None, count=0, pct=0.0

## 인수 항목 (Acceptance Items)

- **AC-YD-001**: `total_draws == 4`.
- **AC-YD-002**: 반환 dict는 핵심 키(total_draws, total_years, top_n,
  yearly_summary, top_numbers_by_year, top_years_by_number, disclaimer)를 포함한다.
- **AC-YD-003**: `total_years == 3`.
- **AC-YD-004**: `yearly_summary` 길이 3, 연도 오름차순(2020, 2021, 2023).
- **AC-YD-005**: yearly_summary 회차 수 — 2020:2, 2021:1, 2023:1.
- **AC-YD-006**: `top_numbers_by_year` 키는 연도 문자열("2020","2021","2023")이며
  데이터 있는 연도만 포함한다.
- **AC-YD-007**: top_numbers_by_year["2020"] 첫 항목은 {number:1, count:2, pct:100.0}.
- **AC-YD-008**: top_numbers_by_year["2020"] 동률(count=1)은 번호 오름차순 →
  2번째·3번째가 번호 2, 3.
- **AC-YD-009**: top_n 파라미터가 각 연도 리스트 길이를 제한한다(top_n=3 → 최대 3개).
- **AC-YD-010**: top_numbers_by_year["2021"]는 모두 pct=100.0(연도 회차 1).
- **AC-YD-011**: `top_years_by_number` 길이 45, index 0 = 번호 1.
- **AC-YD-012**: top_years_by_number[0] = {number:1, best_year:2020,
  best_year_count:2, best_year_pct:100.0}.
- **AC-YD-013**: top_years_by_number[1](번호 2) 동률 시 이른 연도 → best_year=2020,
  count=1, pct=50.0.
- **AC-YD-014**: top_years_by_number[2](번호 3) 동률(2020,2023) → best_year=2020.
- **AC-YD-015**: top_years_by_number[44](번호 45) 미출현 → best_year=None,
  best_year_count=0, best_year_pct=0.0.
- **AC-YD-016**: None/빈 리스트 입력 시 0 채움 구조 — total_draws=0, total_years=0,
  yearly_summary=[], top_numbers_by_year={}, top_years_by_number 45개 모두
  best_year=None.
- **AC-YD-017**: API `GET /api/stats/yearly`는 200과 분석 결과를 반환한다.
  top_n=0 또는 46은 422.
- **AC-YD-018**: 페이지 `GET /stats/yearly`는 200·HTML을 반환하며 disclaimer를
  포함한다. 빈 데이터에서도 200.
