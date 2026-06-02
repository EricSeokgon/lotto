---
id: SPEC-LOTTO-046
version: 0.1.0
status: Planned
created: 2026-06-02
updated: 2026-06-02
author: ircp
priority: medium
---

# SPEC-LOTTO-046: 당첨금 연도별 비교 (Yearly Prize Comparison)

## 개요

역대 로또 1등 당첨금을 연도(DrawResult.date.year)별로 집계하여
연도 간 평균/최대/최소/당첨자 합계를 비교할 수 있는 분석 뷰를 제공한다.
막대 차트와 통계 테이블로 시각화하며, 최고/최저 평균 연도를 강조한다.

## 배경 / 동기

기존 통계 대시보드(SPEC-LOTTO-038)는 연도별 평균 당첨금을 라인 차트의 보조 요소로만
노출한다. 사용자는 "어느 해에 당첨금이 가장 높았는가"를 한눈에 비교하기 어렵다.
본 SPEC은 연도별 1등 당첨금 통계를 독립 페이지로 분리하여 비교 가시성을 높인다.

## EARS 요구사항

### Ubiquitous (상시)

- **REQ-YP-001**: 시스템은 `yearly_prize_comparison(draws)` 함수를 통해 연도별 1등
  당첨금 통계를 집계하여 단일 dict 구조로 반환해야 한다.
- **REQ-YP-002**: 시스템은 연도별 통계에서 `prize1Amount is not None`인 회차만
  평균/최대/최소 집계 대상으로 삼아야 한다.
- **REQ-YP-003**: 시스템은 `total_draws`를 해당 연도의 prize 유무와 무관한 전체
  회차 수로 집계해야 한다.
- **REQ-YP-004**: 시스템은 `years` 리스트를 연도 오름차순으로 정렬해야 한다.
- **REQ-YP-005**: 시스템은 `overall_avg_prize1`을 prize 보유 전체 회차의 정수
  평균(floor)으로 계산해야 한다.

### Event-driven (이벤트 기반)

- **REQ-YP-010**: GET `/api/stats/yearly-prize` 요청을 받으면, 시스템은 전체 회차를
  분석하여 연도별 비교 결과를 HTTP 200 JSON으로 반환해야 한다.
- **REQ-YP-011**: GET `/stats/yearly-prize` 요청을 받으면, 시스템은 막대 차트와
  통계 테이블을 포함한 HTML 페이지를 HTTP 200으로 반환해야 한다.

### State-driven (상태 기반)

- **REQ-YP-020**: prize 데이터가 있는 연도가 존재하는 동안, 시스템은
  `highest_avg_year`/`lowest_avg_year`를 평균이 가장 높은/낮은 연도로 산출해야 한다
  (동률 시 낮은 연도 우선).
- **REQ-YP-021**: 연도 내 prize 데이터가 없는 경우, 시스템은 해당 연도의
  avg/max/min_prize1과 prize_draws를 0으로 채워야 한다.

### Unwanted (금지)

- **REQ-YP-030**: 데이터가 부재(None)하거나 빈 리스트인 경우, 시스템은 예외를
  발생시키지 않고 `total_years=0`, `overall_avg_prize1=0`,
  `highest_avg_year=null`, `lowest_avg_year=null`, `years=[]`의 빈 구조를
  반환해야 한다.
- **REQ-YP-031**: 시스템은 `prize1Winners`가 None인 회차에 대해 예외 없이 0으로
  합산해야 한다.

### Optional (선택)

- **REQ-YP-040**: 가능하면 시스템은 최고/최저 평균 연도를 테이블에서 시각적으로
  강조 표시한다.

## 반환 구조

```json
{
  "total_years": 2,
  "overall_avg_prize1": 4500,
  "highest_avg_year": "2023",
  "lowest_avg_year": "2022",
  "years": [
    {"year": "2022", "total_draws": 2, "prize_draws": 2,
     "avg_prize1": 2000, "max_prize1": 3000, "min_prize1": 1000, "total_winners": 4},
    {"year": "2023", "total_draws": 2, "prize_draws": 2,
     "avg_prize1": 7000, "max_prize1": 9000, "min_prize1": 5000, "total_winners": 4}
  ]
}
```

## 범위 밖 (Out of Scope)

- 연도별 당첨자 수 추세 예측
- 인플레이션 보정 당첨금 환산
- 월/분기 단위 집계 (SPEC-LOTTO-026 트렌드 히트맵이 담당)
