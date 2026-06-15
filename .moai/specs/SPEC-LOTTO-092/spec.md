---
id: SPEC-LOTTO-092
title: 번호 군집 수 분포 분석
status: Completed
version: 1.0.0
created: 2026-06-16
---

# SPEC-LOTTO-092: 번호 군집 수 분포 분석

## 개요

각 회차의 본번호 6개(보너스 제외)를 오름차순 정렬한 뒤, 인접 번호 간 간격이 1인
연속 정수의 묶음("군집")이 몇 개 존재하는지를 집계한다. 군집은 길이 2 이상인 연속
정수 묶음만 인정하며(단일 고립 번호는 군집 아님), 한 회차당 군집 수는 0~3 범위로
캡(min(clusters, 3))한다.

기존의 연속 관련 지표와는 정의가 구별되는 별개 지표다:
- SPEC-069 `get_consecutive_pairs_stats`: 인접 쌍(diff=1) 개수 집계
- SPEC-062 `get_consecutive_pattern_stats`: 연속 쌍 개수(0~5) 분류
- SPEC-078 `get_triple_run_stats`: 길이 3 이상 연속 묶음(run) 집계
- 본 SPEC-092: 길이 2 이상 연속 묶음(군집)의 **개수**(0~3) 분류

## 요구사항 (EARS)

### Ubiquitous Requirements

- REQ-CL-001: 시스템은 각 회차 본번호 6개(보너스 제외)를 오름차순 정렬하여
  분석해야 한다.
- REQ-CL-002: 시스템은 인접 번호 간 간격이 1인 최대 연속 정수 묶음을 군집으로
  정의하며, 군집은 길이 2 이상이어야 한다(단일 고립 번호는 군집 아님).
- REQ-CL-003: 시스템은 한 회차의 군집 수를 0~3으로 캡(min(clusters, 3))해야 한다.
- REQ-CL-004: 시스템은 군집 수 분포를 4개 고정 키("0","1","2","3")로 항상
  제공해야 하며, 미관측 키는 0으로 채워야 한다.

### Event-driven Requirements

- REQ-CL-010: WHEN 신규 추첨 데이터가 적재되면, 시스템은 군집 수 분포 캐시를
  무효화해야 한다.
- REQ-CL-011: WHEN GET /api/stats/cluster_count 요청이 오면, 시스템은 군집 수
  분포 통계를 JSON으로 200 응답해야 한다.
- REQ-CL-012: WHEN GET /stats/cluster-count 요청이 오면, 시스템은 군집 수 분포
  분석 페이지를 HTML로 200 응답해야 한다.

### State-driven Requirements

- REQ-CL-020: WHILE draws가 비어있거나 None인 동안, 시스템은 total_draws=0,
  avg_cluster_count=0.0, most_common_count="0", has_cluster_pct=0.0,
  4개 키 전부 0의 일관된 빈 구조를 반환해야 한다.

### Optional Requirements

- REQ-CL-030: WHERE 동일한 회차 수로 재요청되면, 시스템은 캐시된 결과를 반환하여
  재계산을 피해야 한다.

## 응답 구조

```python
{
    "total_draws": int,
    "avg_cluster_count": float,   # 평균 군집 수, 소수 2자리
    "most_common_count": str,     # "0"~"3", 동률 시 가장 작은 키
    "has_cluster_pct": float,     # 군집 수 >= 1 비율(%), 소수 2자리
    "cluster_distribution": {
        "0": {"count": int, "pct": float},
        "1": {"count": int, "pct": float},
        "2": {"count": int, "pct": float},
        "3": {"count": int, "pct": float},
    },
}
```

## 비고

- Python 3.9 호환: walrus, zip(strict=True), match-case 미사용.
- `draw.numbers()`는 본번호 6개(1-45, 보너스 제외)를 반환한다.
- 기존 함수는 수정하지 않는다.
