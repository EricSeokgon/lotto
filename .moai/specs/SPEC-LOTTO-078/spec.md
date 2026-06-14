---
id: SPEC-LOTTO-078
title: 3연속 이상 번호 포함 분포 분석
status: Planned
version: 0.1.0
created: 2026-06-15
---

# SPEC-LOTTO-078: 3연속 이상 번호 포함 분포 분석

## 개요

각 회차의 본번호 6개(보너스 제외)에서 "3개 이상 연속된 번호 묶음(triple run)"이
몇 개 존재하는지를 집계하고, 전체 회차에 대한 0~2개 분포 통계를 제공한다.

triple run 은 3개 이상 연속한 정수의 그룹을 의미한다. 예: {5,6,7}, {1,2,3,4}.
한 회차는 6개 번호이므로 최대 묶음 수는 2(예: 3+3=6)이며, 분포 키는 "0","1","2"
3개로 고정된다.

예시:
- [1,2,3,4,5,6] → triple run 1개(전체가 1개의 연속), 최대 연속 길이 6
- [1,2,5,6,7,10] → triple run 1개({5,6,7}), 최대 연속 길이 3
- [1,5,10,20,30,40] → triple run 0개(모두 고립), 최대 연속 길이 1
- [1,2,3,7,8,9] → triple run 2개({1,2,3},{7,8,9}), 최대 연속 길이 3
- [3,4,10,20,30,40] → triple run 0개({3,4}는 2연속이라 미포함), 최대 연속 길이 2

SPEC-062(연속 패턴)·SPEC-069(연속 쌍)와는 집계 대상이 다른 별개 기능이다.
SPEC-062/069 는 연속 쌍/패턴을 다루며, 본 SPEC 은 "3개 이상" 연속 묶음 수에 집중한다.

## 요구사항 (EARS)

### Ubiquitous Requirements

- REQ-TR-001: 시스템은 항상 `triple_distribution`을 "0","1","2" 3개 고정 키로 제공해야 한다(미관측 키는 0으로 채움).
- REQ-TR-002: 시스템은 각 분포 항목을 `{count, pct}` 구조로 제공해야 한다.

### Event-driven Requirements

- REQ-TR-010: GET /api/stats/triple_run 요청 시, 시스템은 3연속 묶음 분포 통계 JSON을 200으로 반환해야 한다.
- REQ-TR-011: GET /stats/triple-run 요청 시, 시스템은 분포 분석 HTML 페이지를 200으로 반환해야 한다.
- REQ-TR-012: 신규 추첨 데이터 적재(invalidate_cache 호출) 시, 시스템은 3연속 묶음 분포 캐시를 무효화해야 한다.

### State-driven Requirements

- REQ-TR-020: 데이터가 존재하는 동안, 시스템은 `has_triple_pct`를 묶음 수가 1 이상인 회차 비율(%, 소수 2자리 반올림)로 산출해야 한다.
- REQ-TR-021: 데이터가 존재하는 동안, 시스템은 `most_common_group_count`를 빈도 최댓값 묶음 수로 산출하되 동률 시 더 작은 값을 선택해야 한다.
- REQ-TR-022: 데이터가 존재하는 동안, 시스템은 `avg_max_run`을 회차별 최대 연속 길이의 산술 평균(소수 2자리 반올림)으로 산출해야 한다.

### Unwanted Requirements

- REQ-TR-030: 시스템은 보너스 번호를 3연속 묶음 계산에 포함해서는 안 된다.
- REQ-TR-031: 시스템은 2개 이하의 연속 묶음을 triple run 으로 계산해서는 안 된다.
- REQ-TR-032: 시스템은 빈 입력(빈 리스트/None)에서 예외를 발생시켜서는 안 되며, total_draws=0의 일관된 zero 구조를 반환해야 한다.

### Optional Requirements

- REQ-TR-040: 가능하면, 시스템은 회차별 집계를 캐시에 보관하여 반복 요청 시 재계산을 피해야 한다.

## 응답 구조

```python
{
    "total_draws": int,
    "has_triple_pct": float,          # 묶음 수>=1 회차 비율(%), 소수 2자리
    "most_common_group_count": int,   # 0/1/2, 동률 시 작은 값
    "avg_max_run": float,             # 회차별 최대 연속 길이 평균, 소수 2자리
    "triple_distribution": {
        "0": {"count": int, "pct": float},
        "1": {"count": int, "pct": float},
        "2": {"count": int, "pct": float},
    }
}
```

## 범위 밖 (Out of Scope)

- 연속 쌍/연속 패턴 자체 분석 (SPEC-062, SPEC-069에서 다룸)
- 미래 출현 예측
