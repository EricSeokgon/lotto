---
id: SPEC-LOTTO-108
version: 0.1.0
status: completed
created: 2026-06-22
updated: 2026-06-22
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-108: 번호 월별 출현 분포 분석 (Monthly Distribution Analysis)

## 1. 개요 (Overview)

`DrawResult.date`(datetime.date)를 활용하여 1월~12월 각 달(月, calendar month)에서
번호(1~45)의 출현 빈도를 분석한다. 추첨일의 `date.month`(1=January … 12=December)로
회차를 그룹화하고, 각 월에서 번호별 출현 횟수·비율을 집계한다.

기존 분석과의 차별점:
- `trend_heatmap`/`rolling`(SPEC-LOTTO-054): 회차 인덱스 기준 롤링 윈도우(기간별 추세).
- `period_trend`(SPEC-LOTTO-107): 전체 회차를 초기/중기/최근 3구간으로 균등 분할.
- 본 SPEC: **달력 기반(1~12월) 주기성** 패턴을 분석한다. 회차 인덱스가 아니라
  실제 추첨 날짜의 "월"을 축으로 삼는다.

코어 모듈(`lotto/analysis.py` 등)은 수정하지 않으며, 웹 데이터 레이어
(`lotto/web/data.py`)에 읽기 전용 집계 함수를 추가한다.

## 2. 목표 (Goals)

- 월(1~12)별 회차 수와 번호별 출현 횟수·비율 집계
- 월별 상위 N 번호(`top_numbers_by_month`)
- 번호별 최빈 월(`top_months_by_number`)
- 12개월 요약(`monthly_summary`)
- API·웹 페이지·내비게이션 제공

## 3. 요구사항 (EARS Requirements)

- **REQ-MD-001**: When SYSTEM이 draws 데이터를 수신하면, it SHALL `draw.date.month`(1=1월 … 12=12월)
  기준으로 회차를 월별 그룹화하고, 각 월에 대해 `draw_count`(해당 월 회차 수)와 번호 1~45
  각각의 `count`(출현 횟수), `pct`(`round(count/draw_count*100, 2)`, `draw_count==0`이면 `0.0`)를 산출한다.
- **REQ-MD-002**: It SHALL `top_numbers_by_month`를 생성한다 — 각 월(1~12)에 대해 `count` 내림차순,
  동률은 번호 오름차순으로 정렬한 상위 `top_n` 번호. 각 항목은 `{number, count, pct}`.
- **REQ-MD-003**: It SHALL `top_months_by_number`를 생성한다 — 각 번호 1~45에 대해 출현 횟수가
  가장 많은 월. 항목은 `{number, best_month, best_month_count, best_month_pct}`. 동률 시 가장 작은 월 번호를 택한다.
- **REQ-MD-004**: It SHALL `monthly_summary`를 생성한다 — 12개 항목 `{month: int, month_name: str
  (Jan/Feb/Mar/Apr/May/Jun/Jul/Aug/Sep/Oct/Nov/Dec), draw_count: int}`. index 0 = 1월.
- **REQ-MD-005**: When draws가 None이거나 비어 있으면, it SHALL 0 채움 구조(모든 count 0,
  모든 pct 0.0, 모든 월 draw_count 0, top_numbers_by_month 각 월 빈 리스트)를 반환한다.
- **REQ-MD-006**: API `GET /api/stats/monthly?top_n=5`를 제공한다 — `top_n`은 `Query(ge=1, le=45, default=5)`,
  `top_n=0` 또는 `top_n=46`이면 FastAPI가 422를 반환한다.
- **REQ-MD-007**: 페이지 `GET /stats/monthly`를 제공한다 — `active_tab="monthly"`, 컨텍스트에 `result`, `top_n` 포함.
- **REQ-MD-008**: 결과에 면책 고지(`disclaimer`)를 포함한다.
- **REQ-MD-009**: When `top_n`을 변경하면, it SHALL `top_numbers_by_month`의 각 월 리스트 길이가
  `min(top_n, 출현 번호 수)`가 되도록 한다(없는 월은 빈 리스트). 캐시 키는 `top_n`을 포함한다.
- **REQ-MD-010**: It SHALL 결과 최상위에 `total_draws`(전체 회차 수), `top_n`을 포함한다.
- **REQ-MD-011**: `top_months_by_number`는 45개 항목이며 index 0 = 번호 1, index 44 = 번호 45.
  한 번도 출현하지 않은 번호는 `best_month=0`(또는 출현 없음 표시), `best_month_count=0`, `best_month_pct=0.0`로 채운다.
- **REQ-MD-012**: 페이지·API는 데이터 부재 시에도 200으로 정상 응답한다(REQ-MD-005 구조).

## 4. 반환 구조 (Return Structure)

```python
{
  "total_draws": int,
  "top_n": int,
  "monthly_summary": [  # 12개, index 0 = 1월
    {"month": int, "month_name": str, "draw_count": int}
  ],
  "top_numbers_by_month": {  # 키 "1"~"12"
    "1": [{"number": int, "count": int, "pct": float}, ...],  # 1월 상위 top_n
    ...
    "12": [...]
  },
  "top_months_by_number": [  # 45개, index 0 = 번호 1
    {"number": int, "best_month": int, "best_month_count": int, "best_month_pct": float}
  ],
  "disclaimer": str
}
```

## 5. 비기능 요구사항 (Non-Functional)

- Python 3.9 호환 (match/case 미사용, `zip(strict=True)` 미사용)
- `draw.date.month` 속성 접근(메서드 아님), `draw.numbers()` 메서드 호출
- 코어 모듈 불변, 결정론적(deterministic) 출력
- 프로세스 수명 캐시(`invalidate_cache()`로 무효화), 캐시 키에 `top_n` 포함

## 6. 범위 외 (Out of Scope)

- 요일·주차 단위 분석
- 연도×월 교차 분석
- 통계적 유의성 검정(카이제곱 등)
