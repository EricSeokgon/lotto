---
id: SPEC-LOTTO-082
title: 10단위 다양성 분포 분석
status: Completed
version: 1.0.0
created: 2026-06-15
---

# SPEC-LOTTO-082: 10단위 다양성 분포 분석

## 개요

각 회차의 본번호 6개가 **서로 다른 10단위 그룹(decade)을 몇 개나 커버하는지**를
집계하여 다양성 분포를 분석한다.

10단위 그룹은 1~45 범위를 5개로 나눈다.

- decade 1: 1~9 (1자리)
- decade 2: 10~19
- decade 3: 20~29
- decade 4: 30~39
- decade 5: 40~45

정의: `decade_count` = 한 회차의 본번호 6개가 커버하는 서로 다른 10단위 그룹의 수.
값의 범위는 1~5 (본번호 6개이므로 최소 1, 최대 5).

예시:
- [1,11,21,31,41,42] → {1,2,3,4,5} → 5
- [1,2,3,4,5,6] → {1} → 1
- [1,2,10,11,20,21] → {1,2,3} → 3

## 기존 기능과의 구분 (중요)

- SPEC-LOTTO-059 `get_decade_stats`: 각 10단위 **구간별로 6개 중 몇 개가 들어가는지**
  (구간당 출현 개수 0~6)를 집계한다. 본 SPEC과 출력 구조와 정의가 완전히 다르다.
- 본 SPEC `get_decade_diversity_stats`: 한 회차가 **커버하는 서로 다른 구간 수**(1~5)를
  집계한다. 기존 함수는 일절 수정하지 않는다.

## 요구사항 (EARS)

### Ubiquitous

- U1: 시스템은 항상 `decade_diversity_distribution`에 "1"~"5" 5개 키를 모두 포함한다(zero-fill).
- U2: 시스템은 항상 모든 비율(pct)을 소수 2자리로 반올림한다.

### Event-driven

- E1: WHEN `/api/stats/decade_diversity` 요청을 받으면, 시스템은 JSON 통계를 200으로 반환한다.
- E2: WHEN `/stats/decade-diversity` 요청을 받으면, 시스템은 HTML 페이지를 200으로 반환한다.
- E3: WHEN 신규 추첨 데이터가 적재되면, 시스템은 `invalidate_cache()`로 다양성 캐시를 무효화한다.

### State-driven

- S1: WHILE 분석 대상 회차가 없으면, 시스템은 모든 값을 0으로,
  `most_common_count`는 1로 반환한다.

### Optional

- O1: WHERE 동일 길이 회차 집합이 반복 요청되면, 시스템은 캐시된 결과를 재사용한다.

## 응답 구조

```python
{
    "total_draws": int,
    "avg_decade_count": float,        # 회차당 평균 커버 구간 수, 소수 2자리
    "most_common_count": int,         # 1~5, 동률 시 작은 키 우선
    "full_coverage_pct": float,       # decade_count==5 비율(%), 소수 2자리
    "decade_diversity_distribution": {
        "1": {"count": int, "pct": float},
        "2": {"count": int, "pct": float},
        "3": {"count": int, "pct": float},
        "4": {"count": int, "pct": float},
        "5": {"count": int, "pct": float},
    },
}
```
