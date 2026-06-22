---
id: SPEC-LOTTO-110
version: 1.0.0
status: completed
created: 2026-06-22
updated: 2026-06-22
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-110: 번호 연도별 출현 분포 분석 (Yearly Distribution Analysis)

## 개요 (Overview)

`draw.date.year`(속성, int)를 활용해 각 연도별로 번호(1~45)의 출현 빈도를 분석한다.
SPEC-107(기간별 3등분 추이), SPEC-108(월별 계절성)과 달리 실제 달력 연도
(2002년~현재) 단위의 장기 변화 패턴을 제공한다. 연도별로 가장 많이 나온 번호,
번호별 최빈 연도, 연도별 회차 수를 집계한다.

기존 기능과의 차이:
- SPEC-107 period_trend: 회차 인덱스 기준 3등분 시계열 (데이터 분할)
- SPEC-108 monthly: 달력 월(1~12) 기준 계절성 (12 고정 버킷)
- **SPEC-110 yearly: 실제 달력 연도(가변 개수) 기준 장기 추세**

세 기능은 분석 축이 모두 다르며 절대 병합하지 않는다. 코어 모듈은 수정하지 않는다.

## EARS 요구사항 (Requirements)

- **REQ-YD-001**: When SYSTEM receives draws data, it SHALL group draws by
  calendar year (`draw.date.year`, integer) and for each year compute:
  draw_count (total draws in that year), and for each number 1-45:
  count (appearances), pct (round(count/draw_count*100, 2) if draw_count > 0
  else 0.0).
- **REQ-YD-002**: It SHALL produce `top_numbers_by_year`: for each year in data,
  top_n numbers sorted by count desc, ties broken by number asc; each item:
  {number, count, pct}.
- **REQ-YD-003**: It SHALL produce `top_years_by_number`: for each number 1-45,
  the year with highest count; {number, best_year: int or None,
  best_year_count: int, best_year_pct: float}. If number never appeared,
  best_year=None, count=0, pct=0.0.
- **REQ-YD-004**: It SHALL produce `yearly_summary`: list of dicts
  {year: int, draw_count: int}, sorted by year ascending.
- **REQ-YD-005**: It SHALL produce `total_years`: int (number of distinct years
  in data).
- **REQ-YD-006**: When draws is None or empty: return zero-filled structure
  (total_draws=0, total_years=0, yearly_summary=[], top_numbers_by_year={},
  top_years_by_number with all best_year=None).
- **REQ-YD-007**: Ties in `top_years_by_number`: when multiple years have the
  same max count for a number, pick the earliest year (smallest year int).
- **REQ-YD-008**: API `GET /api/stats/yearly?top_n=5`
  (top_n: Query(ge=1, le=45, default=5)), 422 for out-of-range.
- **REQ-YD-009**: Page `GET /stats/yearly`, active_tab="yearly",
  context: result, top_n.
- **REQ-YD-010**: Include disclaimer.
- **REQ-YD-011**: Cache key must include top_n; cache cleared in
  `invalidate_cache()`.

## 반환 구조 (Return Structure)

```python
{
  "total_draws": int,
  "total_years": int,
  "top_n": int,
  "yearly_summary": [   # sorted by year asc
    {"year": int, "draw_count": int},
    ...
  ],
  "top_numbers_by_year": {  # keys are year as string
    "2002": [{"number": int, "count": int, "pct": float}, ...],  # top_n items
    ...
  },
  "top_years_by_number": [  # 45 items, index 0 = number 1
    {"number": int, "best_year": int | None, "best_year_count": int,
     "best_year_pct": float}
  ],
  "disclaimer": str
}
```

## 비기능 요구사항 (Non-Functional)

- Python 3.9 호환 (match/case 금지, zip(strict=True) 금지)
- `draw.date.year`(속성, int 접근), `draw.numbers()`(메서드 호출)
- 코어 모듈(`lotto/`의 분석/모델) 불변 — `lotto/web/data.py` 래퍼만 추가
- 결정론적(deterministic) — 동일 입력에 동일 출력
- 프로세스 수명 캐시 + `invalidate_cache()` 무효화 등록

## 추적성 (Traceability)

- 구현: `lotto/web/data.py::get_yearly_distribution`
- API: `GET /api/stats/yearly`
- 페이지: `GET /stats/yearly`
- 템플릿: `lotto/web/templates/yearly_distribution.html`
- 테스트: `tests/test_yearly_distribution.py`
