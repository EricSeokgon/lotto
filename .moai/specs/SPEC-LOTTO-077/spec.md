---
id: SPEC-LOTTO-077
title: 1자리 번호 포함 개수 분포 분석
status: Planned
version: 0.1.0
created: 2026-06-12
---

# SPEC-LOTTO-077: 1자리 번호 포함 개수 분포 분석

## 개요

각 회차의 본번호 6개(보너스 제외) 중 1자리 번호(1~9)가 몇 개 포함되는지를
집계하고, 전체 회차에 대한 0~6개 분포 통계를 제공한다.

1~45 중 1자리 번호는 {1, 2, 3, 4, 5, 6, 7, 8, 9} 9개이다.
한 회차 6개 번호 중 1자리 개수는 0(없음)~6(전부) 범위를 가진다.

SPEC-073(3의 배수)·SPEC-074(짝수)·SPEC-075(5의 배수)·SPEC-076(4의 배수)와는
계산 대상이 다른 별개 기능이다.

## 요구사항 (EARS)

### Ubiquitous Requirements

- REQ-SD-001: 시스템은 항상 `single_distribution`을 "0".."6" 7개 고정 키로 제공해야 한다(미관측 키는 0으로 채움).
- REQ-SD-002: 시스템은 각 분포 항목을 `{count, pct}` 구조로 제공해야 한다.

### Event-driven Requirements

- REQ-SD-010: GET /api/stats/single_digit 요청 시, 시스템은 1자리 개수 분포 통계 JSON을 200으로 반환해야 한다.
- REQ-SD-011: GET /stats/single-digit 요청 시, 시스템은 분포 분석 HTML 페이지를 200으로 반환해야 한다.
- REQ-SD-012: 신규 추첨 데이터 적재(invalidate_cache 호출) 시, 시스템은 1자리 개수 분포 캐시를 무효화해야 한다.

### State-driven Requirements

- REQ-SD-020: 데이터가 존재하는 동안, 시스템은 `avg_single_count`를 회차별 1자리 개수의 산술 평균(소수 2자리 반올림)으로 산출해야 한다.
- REQ-SD-021: 데이터가 존재하는 동안, 시스템은 `most_common_count`를 빈도 최댓값 개수로 산출하되 동률 시 더 작은 개수를 선택해야 한다.
- REQ-SD-022: 데이터가 존재하는 동안, 시스템은 `high_single_pct`를 1자리 개수가 3 이상인 회차 비율(%, 소수 2자리 반올림)로 산출해야 한다.

### Unwanted Requirements

- REQ-SD-030: 시스템은 보너스 번호를 1자리 개수 계산에 포함해서는 안 된다.
- REQ-SD-031: 시스템은 빈 입력(빈 리스트/None)에서 예외를 발생시켜서는 안 되며, total_draws=0의 일관된 zero 구조를 반환해야 한다.

### Optional Requirements

- REQ-SD-040: 가능하면, 시스템은 회차별 집계를 캐시에 보관하여 반복 요청 시 재계산을 피해야 한다.

## 응답 구조

```python
{
    "total_draws": int,
    "avg_single_count": float,     # 회차별 1자리 개수 평균, 소수 2자리
    "most_common_count": int,      # 최빈 개수, 동률 시 작은 값
    "high_single_pct": float,      # 1자리 개수>=3 회차 비율(%), 소수 2자리
    "single_distribution": {
        "0": {"count": int, "pct": float},
        # ... "6"까지 7개 키 항상 존재
    }
}
```

## 범위 밖 (Out of Scope)

- 1자리 번호 자체의 출현 빈도 분석 (별개 기능)
- 미래 출현 예측
