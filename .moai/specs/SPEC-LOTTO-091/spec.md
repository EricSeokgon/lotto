---
id: SPEC-LOTTO-091
title: 소수 이웃 번호 포함 분포 분석
status: completed
version: 0.1.0
created: 2026-06-16
---

# SPEC-LOTTO-091: 소수 이웃 번호 포함 분포 분석

## 개요

각 회차의 본번호 6개(보너스 제외) 중 "소수 이웃(prime neighbor)"에 해당하는 번호가
몇 개 포함되는지(0~6)를 집계한다. 소수 이웃이란 1~45 범위에서 자기 자신이 소수이거나
소수와 인접(소수±1)한 번호를 말한다.

### 소수 이웃 정의

- 1~45 소수: 2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43
- 번호 n(1~45)이 다음 중 하나면 소수 이웃이다:
  - n 이 소수이거나
  - n-1 이 소수(1~45 범위)이거나
  - n+1 이 소수(1~45 범위)
- 소수 이웃 집합(34개):
  1,2,3,4,5,6,7,8,10,11,12,13,14,16,17,18,19,20,22,23,24,28,29,30,31,32,
  36,37,38,40,41,42,43,44
- 소수 이웃이 아닌 번호(11개): 9,15,21,25,26,27,33,34,35,39,45

이는 SPEC-058(소수 개수만 세는 `get_prime_count_stats`/`get_prime_stats`)와는
정의가 다른 별개 지표다.

## EARS 요구사항

### Ubiquitous

- REQ-PN-001: 시스템은 각 회차 본번호 6개 중 소수 이웃 집합에 포함된 번호 개수(0~6)를
  집계해야 한다.
- REQ-PN-002: 분포 키는 "0"~"6"의 7개를 항상 포함해야 하며 미관측 키는 0으로 채운다.
- REQ-PN-003: 시스템은 `prime_neighbor_distribution`의 각 키에 대해 count와 pct를
  제공해야 한다.

### Event-driven

- REQ-PN-010: 신규 추첨 데이터 적재로 `invalidate_cache()`가 호출되면 시스템은
  소수 이웃 분포 캐시(`_prime_neighbor_cache`)를 비워야 한다.
- REQ-PN-011: GET /api/stats/prime_neighbor 요청 시 시스템은 200과 JSON 분포를
  반환해야 한다.
- REQ-PN-012: GET /stats/prime-neighbor 요청 시 시스템은 200과 HTML 페이지를
  반환해야 한다.

### State-driven

- REQ-PN-020: draws가 비어있거나 None인 동안 시스템은 total_draws=0,
  avg_neighbor_count=0.0, most_common_count="0", high_neighbor_pct=0.0,
  7개 키 전부 0의 일관된 빈 구조를 반환해야 한다.

### Optional

- REQ-PN-030: 가능하면 시스템은 동일 회차 수 재요청 시 캐시된 결과를 재사용해야 한다.

## 요약 통계 정의

- avg_neighbor_count: 회차 평균 소수 이웃 개수(소수 2자리).
- most_common_count: 최빈 개수 키("0"~"6"). 동률 시 가장 작은 키.
- high_neighbor_pct: 소수 이웃 개수가 5 이상(5,6)인 회차 비율(%, 소수 2자리).

## 응답 구조

```python
{
    "total_draws": int,
    "avg_neighbor_count": float,
    "most_common_count": str,
    "high_neighbor_pct": float,
    "prime_neighbor_distribution": {
        "0": {"count": int, "pct": float},
        ...
        "6": {"count": int, "pct": float},
    },
}
```
