---
id: SPEC-LOTTO-109
version: 0.1.0
status: completed
created: 2026-06-22
updated: 2026-06-22
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-109: 번호 출현 간격 상세 분포 분석 (Appearance Gap Distribution Analysis)

## 개요

각 번호(1~45)의 역대 연속 출현 간격(두 출현 사이의 회차 수)을 모두 수집하여
상세 통계(min/max/avg/median/std)와 간격 구간별 분포(히스토그램)를 제공한다.
기존 SPEC-LOTTO-104 recency_analysis의 avg_interval(연속 출현 사이 실제 간격
평균) 또는 SPEC-LOTTO-047 cycle_analysis의 avg_cycle(단순 비율 추정치)을 넘어,
간격 표본의 **다양성과 분포**(히스토그램 + 표준편차)를 시각화하는 데 목적이 있다.

### Gap(간격) 정의

번호 X가 회차 A와 회차 B에서 **연속으로** 출현했을 때(그 사이의 어느 회차에도
X가 없음), `gap = B.drwNo - A.drwNo` 이다. draws는 `get_draws()` 반환값 기준으로
`drwNo` 오름차순으로 정렬되어 있다고 가정한다(안전을 위해 함수 내부에서도 정렬).

> 주의: 본 프로젝트의 `DrawResult` 회차 필드명은 `drwNo`(camelCase)이며
> `draw_no`가 아니다. 구현·테스트는 `draw.drwNo`를 사용한다.

## 기존 기능과의 차별점 (중복 아님)

| 기능 | SPEC | 지표 | 축 |
|------|------|------|----|
| cycle_analysis | 047 | avg_cycle = total/appearances (비율 추정) | 번호별 단일 추정치 |
| recency_analysis | 104 | avg_interval = mean(실제 간격), last_seen_ago | 번호별 마지막 출현·평균 간격 |
| **gap_distribution** | **109** | **간격 표본 전체의 min/max/avg/median/std + 6버킷 히스토그램** | **번호별 간격 표본 분포** |

gap_distribution은 cycle/recency를 호출·수정하지 않으며, "간격이 얼마나 고르게
또는 들쭉날쭉하게 분포하는가"(std, 히스토그램)를 새로 제공한다.

## EARS 요구사항

- **REQ-GAP-001**: When SYSTEM이 drwNo 오름차순 정렬된 draws를 받으면, it SHALL
  각 번호 1~45에 대해 모든 연속 출현 간격을 수집한다. 번호가 연속한 두 출현
  (draws[i], draws[j]) (그 사이 회차에 해당 번호 없음)에서
  `gap = draws[j].drwNo - draws[i].drwNo`.
- **REQ-GAP-002**: It SHALL 번호별로 다음을 계산한다: gaps 리스트, count
  (간격 수 = appearance_count - 1, 0/1회 출현이면 0), avg_gap
  (round(mean,2), count=0이면 None), median_gap (round(median,2), count=0이면
  None), min_gap (int, count=0이면 None), max_gap (int, count=0이면 None),
  std_gap (round(stdev,2), count<2면 None), appearance_count (총 출현 횟수).
- **REQ-GAP-003**: It SHALL 번호별 gap_histogram을 계산한다:
  `{"1-10": int, "11-20": int, "21-30": int, "31-40": int, "41-50": int, "51+": int}`
  각 간격이 속한 구간을 카운트한다. (경계: 1~10, 11~20, …, 41~50, 51 이상)
- **REQ-GAP-004**: It SHALL overall_summary를 계산한다:
  `{avg_gap_all: float (전체 번호의 모든 간격 평균, round 2),
  max_gap_ever: int (발견된 최대 단일 간격), max_gap_number: int,
  min_gap_ever: int, min_gap_number: int}`.
  동률 시 더 작은 번호를 우선한다. 간격이 하나도 없으면 모든 값 None.
- **REQ-GAP-005**: When draws가 None이거나 비어 있으면, it SHALL 0 채움 구조를
  반환한다(total_draws=0, overall_summary 모두 None, numbers 45개 모두 None
  통계/0 히스토그램).
- **REQ-GAP-006**: When 번호가 0회 또는 1회만 출현하면, it SHALL count=0, 모든
  통계 None, 히스토그램 전부 0으로 둔다(appearance_count는 실제 출현 횟수).
- **REQ-GAP-007**: API `GET /api/stats/gap-distribution` (top_n 파라미터 없음;
  항상 45개 번호 전부 반환).
- **REQ-GAP-008**: Page `GET /stats/gap-distribution`, active_tab="gap_dist",
  컨텍스트: result.
- **REQ-GAP-009**: 회고 분석 면책 고지(disclaimer)를 포함한다.

## 반환 구조

```python
{
  "total_draws": int,
  "overall_summary": {
    "avg_gap_all": float | None,   # 간격이 전혀 없으면 None
    "max_gap_ever": int | None,
    "max_gap_number": int | None,
    "min_gap_ever": int | None,
    "min_gap_number": int | None,
  },
  "numbers": [  # 45개, index 0 = 번호 1
    {
      "number": int,
      "appearance_count": int,
      "count": int,              # 간격 수 = max(appearance_count - 1, 0)
      "avg_gap": float | None,
      "median_gap": float | None,
      "min_gap": int | None,
      "max_gap": int | None,
      "std_gap": float | None,   # count < 2 이면 None
      "gap_histogram": {
        "1-10": int, "11-20": int, "21-30": int,
        "31-40": int, "41-50": int, "51+": int,
      }
    }
    # ... 45개
  ],
  "disclaimer": str
}
```

## 비기능 요구사항

- Python 3.9 호환(match/case 금지, zip(strict=True) 금지).
- `draw.numbers()` 메서드 호출(본번호 6개, 보너스 제외), `draw.drwNo` 속성 사용.
- 표준 라이브러리 `statistics`(mean/median/stdev)만 사용.
- 코어 모듈(lotto/models.py, lotto/analysis 등) 불변.
- 프로세스 수명 캐시(`_gap_dist_cache`) + `invalidate_cache()`에서 무효화.
- top_n 파라미터 없음 — 항상 45개 번호 전부 반환.

## 수용 기준

자세한 항목은 acceptance.md 참고 (18개 AC).
