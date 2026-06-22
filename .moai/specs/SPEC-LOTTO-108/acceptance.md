# SPEC-LOTTO-108 인수 기준 (Acceptance Criteria)

## 손계산 픽스처 (4 draws)

| 회차 | 추첨일 | 월 | 본번호(sorted) |
|------|--------|----|----------------|
| D1 | 2024-01-06 | 1 (Jan) | 1, 2, 3, 4, 5, 6 |
| D2 | 2024-01-13 | 1 (Jan) | 1, 7, 8, 9, 10, 11 |
| D3 | 2024-03-02 | 3 (Mar) | 2, 12, 13, 14, 15, 16 |
| D4 | 2024-06-01 | 6 (Jun) | 3, 17, 18, 19, 20, 21 |

- `total_draws = 4`
- 월별 회차 수: Jan=2, Mar=1, Jun=1, 그 외 0
- Jan 번호 카운트: 1×2, 2/3/4/5/6/7/8/9/10/11 각 ×1 (draw_count=2)
- Mar 번호 카운트: 2/12/13/14/15/16 각 ×1 (draw_count=1)
- Jun 번호 카운트: 3/17/18/19/20/21 각 ×1 (draw_count=1)

`month_name` 순서: `["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]`

---

## 핵심 계산 (Data Layer)

- **AC-MD-001**: `get_monthly_distribution(fixture_4())["total_draws"] == 4`
- **AC-MD-002**: 반환 dict가 `{total_draws, top_n, monthly_summary, top_numbers_by_month, top_months_by_number, disclaimer}` 키를 포함한다.
- **AC-MD-003**: `monthly_summary` 길이 12, index 0의 `month==1`·`month_name=="Jan"`, index 11의 `month==12`·`month_name=="Dec"`.
- **AC-MD-004**: `monthly_summary[0].draw_count == 2` (Jan), `[2].draw_count == 1` (Mar), `[5].draw_count == 1` (Jun).
- **AC-MD-005**: `monthly_summary[1].draw_count == 0` (Feb, 회차 없음).
- **AC-MD-006**: `monthly_summary`의 모든 `month_name`이 정확한 약어 순서를 따른다.

## top_numbers_by_month (top_n=3)

- **AC-MD-007**: `top_numbers_by_month["1"]`(top_n=3) == `[{number:1,count:2,pct:100.0},{number:2,count:1,pct:50.0},{number:3,count:1,pct:50.0}]`.
- **AC-MD-008**: `top_numbers_by_month["3"]`(top_n=3) == `[{number:2,count:1,pct:100.0},{number:12,count:1,pct:100.0},{number:13,count:1,pct:100.0}]`.
- **AC-MD-009**: `top_numbers_by_month["2"]`(Feb) == `[]` (회차 없음).
- **AC-MD-010**: 키가 "1"~"12" 12개 모두 존재한다.
- **AC-MD-011**: `top_numbers_by_month["6"]`(top_n=3) 첫 항목 `{number:3,count:1,pct:100.0}`.

## top_months_by_number

- **AC-MD-012**: `top_months_by_number` 길이 45, index 0의 `number==1`, index 44의 `number==45`.
- **AC-MD-013**: 번호 1 → `best_month==1`, `best_month_count==2`, `best_month_pct==100.0`.
- **AC-MD-014**: 번호 2 → 동률(Jan·Mar 각 1회) → `best_month==1` (가장 작은 월).
- **AC-MD-015**: 번호 3 → 동률(Jan·Jun 각 1회) → `best_month==1`.
- **AC-MD-016**: 번호 22(미출현) → `best_month==0`, `best_month_count==0`, `best_month_pct==0.0`.

## 엣지 케이스

- **AC-MD-017**: `get_monthly_distribution(None)` → `total_draws==0`, `monthly_summary` 12개 모두 `draw_count==0`, 모든 `top_numbers_by_month` 값 `[]`, `top_months_by_number` 45개 모두 `best_month==0`/`count==0`.
- **AC-MD-018**: `get_monthly_distribution([])` → None과 동일한 0 채움 구조.
- **AC-MD-019**: `top_n` 캐시 키 분리 — `top_n=3`과 `top_n=5` 호출이 서로 다른 길이를 반환한다.

## API

- **AC-MD-020**: `GET /api/stats/monthly` → 200, 핵심 키 포함, 기본 `top_n==5`.
- **AC-MD-021**: `GET /api/stats/monthly?top_n=0` → 422, `?top_n=46` → 422, `?top_n=1`·`?top_n=45` → 200.

## 페이지

- **AC-MD-022**: `GET /stats/monthly` → 200, "월별" 문자열 포함.
- **AC-MD-023**: 데이터 부재(`get_draws`가 None) 시에도 `GET /stats/monthly` → 200.
