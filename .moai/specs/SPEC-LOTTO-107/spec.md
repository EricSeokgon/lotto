---
id: SPEC-LOTTO-107
version: 1.0.0
status: completed
created: 2026-06-22
updated: 2026-06-22
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-107: 기간별 번호 빈도 추이 분석 (Period Trend Analysis)

## 개요 (Overview)

전체 회차 이력을 3개 구간(초기/중기/최근)으로 균등 분할하여 각 번호(1-45)의 구간별
출현 횟수·비율을 비교하고, 최근 구간 기준으로 빈도가 증가/감소/유지되는 번호를
분류한다. 기존 `hot_cold_analysis`(최근 N회 vs 전체 단순 비교)와 달리 3구간 시계열
변화 추이(rising/falling/stable)를 제공한다.

분석은 과거 데이터 관찰용 참고 자료이며 미래 당첨 예측력을 보장하지 않는다.
로또는 매 회차 독립적인 무작위 추첨이다.

## 기존 분석과의 구분 (Non-overlap)

- SPEC-030 hot_cold_analysis: 최근 N회 vs 전체의 단일 비교 (2구간, 단순 비교)
- **SPEC-107 period_trend: 초기/중기/최근 3구간 균등 분할 시계열 추이 (3구간, 방향성)**
- 두 기능은 별개의 축이며 병합하지 않는다.

## 구간 분할 규칙 (FROZEN formula)

`n = len(draws)` 일 때 파이썬 슬라이스 형식을 **엄격히** 적용한다:

- `early  = draws[0:n//3]`
- `middle = draws[n//3:2*n//3]`
- `recent = draws[2*n//3:]`

이 슬라이스 공식이 단일 진실 원천(single source of truth)이다. 산문 설명과 충돌할
경우 슬라이스 공식이 우선한다. 특히 작은 n에서의 결과는 다음과 같다:

- n=1: `n//3=0`, `2*n//3=0` → early=draws[0:0]=[], middle=draws[0:0]=[], recent=draws[0:]=[draws[0]]
  - (단일 회차는 recent 구간에 배치되며 early/middle은 빈 구간이 된다 — 공식 결과)
- n=2: `n//3=0`, `2*n//3=1` → early=draws[0:0]=[], middle=draws[0:1]=[draws[0]], recent=draws[1:2]=[draws[1]]

> 주의: 본 SPEC은 슬라이스 공식을 권위 있는 정의로 채택한다. REQ-PT-005의 산문
> ("초기 구간에 배치")은 공식 결과(recent 배치)로 대체된다.

## 요구사항 (EARS Requirements)

### Ubiquitous Requirements

- **REQ-PT-001**: When SYSTEM receives draws data, it SHALL divide draws into 3
  equal-sized periods (`early=draws[0:n//3]`, `middle=draws[n//3:2*n//3]`,
  `recent=draws[2*n//3:]`) and compute, for each number 1-45:
  `count_early`, `count_middle`, `count_recent`,
  `pct_early`, `pct_middle`, `pct_recent`
  (pct = count / period_total_draws * 100, rounded to 2 decimal places;
  0.0 when the period has no draws), and
  `trend` ("rising" if count_recent > count_early, "falling" if count_recent <
  count_early, "stable" if equal).

- **REQ-PT-002**: It SHALL produce `top_rising` (top_n numbers with the highest
  `delta = count_recent - count_early`, sorted by delta desc then number asc) and
  `top_falling` (top_n numbers with the lowest delta, sorted by delta asc then
  number desc). Each item: `{number, count_early, count_middle, count_recent,
  delta, trend}`.

- **REQ-PT-003**: It SHALL return `period_sizes`:
  `{early: int, middle: int, recent: int}` showing the actual draw counts per
  period (i.e. `len(early)`, `len(middle)`, `len(recent)`).

### Event-driven / Unwanted Requirements

- **REQ-PT-004**: When draws is None or empty, the SYSTEM SHALL return a
  zero-filled structure: `total_draws=0`, `period_sizes` all 0, 45 numbers each
  with all counts 0, all pct 0.0, delta 0, trend "stable", `top_rising=[]`,
  `top_falling=[]`, plus disclaimer.

- **REQ-PT-005**: When draws has 1 draw (n=1), the strict slice formula applies:
  early=[], middle=[], recent=[draws[0]]. Thus `period_sizes` = {early:0,
  middle:0, recent:1}; numbers appearing in the single draw have count_recent=1,
  count_early=0, delta=1, trend="rising".

- **REQ-PT-006**: When draws has 2 draws (n=2), the strict slice formula applies:
  early=draws[0:0]=[], middle=draws[0:1]=[draws[0]], recent=draws[1:2]=[draws[1]].
  Thus `period_sizes` = {early:0, middle:1, recent:1}.

### API / UI Requirements

- **REQ-PT-007**: The SYSTEM SHALL expose `GET /api/stats/period-trend?top_n=10`
  where `top_n` is `Query(ge=1, le=45, default=10)`; out-of-range values
  (`top_n=0` or `top_n=46`) return HTTP 422.

- **REQ-PT-008**: The SYSTEM SHALL expose `GET /stats/period-trend` rendering
  `period_trend.html` with `active_tab="period_trend"` and context keys `result`
  and `top_n`. The page accepts `?top_n` (validated 1-45) and renders
  server-side without client JS dependency.

- **REQ-PT-009**: The result SHALL include a `disclaimer` string clarifying the
  analysis is statistical reference material with no predictive guarantee.

### Non-functional Requirements

- **REQ-PT-NFR-001**: Python 3.9 compatible (no match/case, no
  `zip(strict=True)`).
- **REQ-PT-NFR-002**: `draw.numbers()` is called as a method returning a sorted
  `list[int]` of the 6 main numbers (bonus excluded).
- **REQ-PT-NFR-003**: Core modules (`lotto/models.py`, data collection) remain
  unchanged; the feature is additive in `lotto/web/`.
- **REQ-PT-NFR-004**: Deterministic — identical input yields identical output.
- **REQ-PT-NFR-005**: Process-lifetime cache keyed by `f"{len(draws)}:{top_n}"`;
  invalidated via `invalidate_cache()`. The cache key includes `top_n` because
  `top_rising`/`top_falling` depend on it.

## 반환 구조 (Return Structure)

```python
{
  "total_draws": int,
  "top_n": int,
  "period_sizes": {"early": int, "middle": int, "recent": int},
  "numbers": [  # 45 items, index 0 = number 1
    {
      "number": int,           # 1-45
      "count_early": int,
      "count_middle": int,
      "count_recent": int,
      "pct_early": float,      # round(count_early/period_sizes.early*100, 2), 0.0 if period empty
      "pct_middle": float,
      "pct_recent": float,
      "delta": int,            # count_recent - count_early (can be negative)
      "trend": str             # "rising" | "falling" | "stable"
    }
  ],
  "top_rising": [...],   # top_n items, sorted: delta desc, then number asc
  "top_falling": [...],  # top_n items, sorted: delta asc, then number desc
  "disclaimer": str
}
```

## 범위 밖 (Out of Scope)

- 구간 개수를 3 외의 값으로 설정하는 기능
- 구간 크기 가중치 / 비균등 분할
- 미래 예측·신뢰구간 계산
- 코어 모델/수집기 변경

## 추적성 (Traceability)

- 구현: `lotto/web/data.py` `get_period_trend()`
- API: `lotto/web/routes/api.py` `GET /api/stats/period-trend`
- 페이지: `lotto/web/routes/pages.py` `GET /stats/period-trend`
- 템플릿: `lotto/web/templates/period_trend.html`
- 내비게이션: `lotto/web/templates/base.html`
- 테스트: `tests/test_period_trend.py`
- 인수 기준: `acceptance.md` (AC-PT-001 ~ AC-PT-020)
