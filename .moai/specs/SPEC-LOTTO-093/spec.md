---
id: SPEC-LOTTO-093
title: 첫·마지막 번호 구간 조합 분포 분석
status: Planned
version: 0.1.0
created: 2026-06-16
---

# SPEC-LOTTO-093: 첫·마지막 번호 구간 조합 분포 분석

## 개요

각 회차의 본번호 6개(보너스 제외) 중 최솟값(첫 번호)과 최댓값(마지막 번호)이
각각 어느 3구간 밴드에 속하는지를 판정하고, 두 구간의 조합으로 회차를 분류한다.

- 구간 A: 1~15
- 구간 B: 16~30
- 구간 C: 31~45

조합 키 = f"{min_zone}{max_zone}" (예: "AC" → 최솟값 A구간, 최댓값 C구간).
min ≤ max 이므로 가능한 조합은 AA, AB, AC, BB, BC, CC 6가지뿐이다
(BA/CA/CB는 불가능).

기존 SPEC-064(get_min_max_stats: 최솟값·최댓값 값/범위)와는 다른 별개 지표다.
본 지표는 구간 밴드 조합 분포를 다룬다.

## 요구사항 (EARS)

### Ubiquitous Requirements

- REQ-FLZ-001: 시스템은 각 회차 본번호 6개의 최솟값과 최댓값이 속한
  구간(A/B/C)을 조합한 키(AA~CC, 6개)별 분포를 항상 제공해야 한다.
- REQ-FLZ-002: 시스템은 6개 조합 키를 항상 모두 포함하되 미관측 키는
  count=0, pct=0.0으로 채워야 한다.
- REQ-FLZ-003: 구간 판정은 n≤15→A, 16≤n≤30→B, 31≤n→C 규칙을 따라야 한다.

### Event-driven Requirements

- REQ-FLZ-010: 신규 추첨 데이터 적재 시(invalidate_cache 호출 시) 첫·마지막
  구간 조합 분포 캐시도 무효화되어야 한다.

### State-driven Requirements

- REQ-FLZ-020: draws가 비어 있으면 total_draws=0, avg_span=0.0,
  most_common_combo="AA", wide_span_pct=0.0, 6개 키 전부 0의 일관된 빈 구조를
  반환해야 한다.

### Optional Requirements

- REQ-FLZ-030: API GET /api/stats/first_last_zone 및 웹 페이지
  GET /stats/first-last-zone 를 제공해야 한다.

## 응답 구조

```python
{
    "total_draws": int,
    "avg_span": float,                   # 평균 (max-min), 소수 2자리
    "most_common_combo": str,            # "AA"~"CC", 동률 시 키 순서상 앞선 것
    "wide_span_pct": float,              # 조합이 "AC"인 회차 비율(%), 소수 2자리
    "first_last_zone_distribution": {
        "AA": {"count": int, "pct": float},
        "AB": {"count": int, "pct": float},
        "AC": {"count": int, "pct": float},
        "BB": {"count": int, "pct": float},
        "BC": {"count": int, "pct": float},
        "CC": {"count": int, "pct": float},
    }
}
```

## 요약 통계 정의

- most_common_combo: 최빈 조합. 동률 시 키 순서상 앞선 것
  ("AA" < "AB" < "AC" < "BB" < "BC" < "CC").
- wide_span_pct: 조합이 "AC"(가능한 최대 폭)인 회차 비율, 소수 2자리.
- avg_span: 모든 회차의 (max - min) 평균, 소수 2자리.

## 제약 조건

- Python 3.9 호환 (walrus/match-case/zip(strict) 미사용)
- draw.numbers()는 본번호 6개(1-45, 보너스 제외)를 반환
- 기존 함수 수정 금지
- 캐시 키는 str(len(draws)), invalidate_cache()로 무효화
