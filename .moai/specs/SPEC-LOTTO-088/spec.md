---
id: SPEC-LOTTO-088
title: 번호 간격 분산 분포 분석
status: Planned
version: 0.1.0
created: 2026-06-15
---

# SPEC-LOTTO-088: 번호 간격 분산 분포 분석

## 개요

각 회차의 본번호 6개를 오름차순 정렬한 뒤 인접한 번호 간 5개 간격(gap)의
**모분산(population variance)** 을 산출하고, 그 분산값을 5개 구간으로 분류하여
전체 회차의 분포를 분석한다. 간격 분산은 번호가 얼마나 균등하게(uniform)
퍼져 있는지를 나타내는 지표로, 분산이 작을수록 번호가 등간격에 가깝고
분산이 클수록 한쪽에 몰리거나 큰 간격이 존재함을 의미한다.

SPEC-056(간격 패턴: min/max gap 분류)·SPEC-079(최대 간격 분포)와는
산출 대상(간격의 분산 vs 간격 자체)이 다른 별개 지표다.

## 용어 정의

- **gap(간격)**: 정렬된 6개 번호에서 `sorted[i+1] - sorted[i]` (i=0..4), 총 5개.
- **간격 분산**: 5개 gap 의 모분산 = `sum((g - mean)**2) / 5`, `mean = sum(gaps)/5`.

## EARS 요구사항

### Ubiquitous (상시)

- **REQ-GV-001**: 시스템은 각 회차 본번호 6개(보너스 제외)를 정렬하여 5개 간격을
  산출하고 그 모분산을 계산해야 한다.
- **REQ-GV-002**: 시스템은 간격 분산을 다음 5개 구간으로 분류해야 한다.
  - `"0-10"`: 분산 < 10
  - `"10-30"`: 10 <= 분산 < 30
  - `"30-60"`: 30 <= 분산 < 60
  - `"60-100"`: 60 <= 분산 < 100
  - `"100+"`: 분산 >= 100
- **REQ-GV-003**: `gap_variance_distribution` 은 항상 5개 키를 정의 순서대로 포함하며
  미관측 구간은 count=0, pct=0.0 으로 채워야 한다.

### Event-driven (이벤트 기반)

- **REQ-GV-010**: `GET /api/stats/gap_variance` 요청 시 통계를 JSON 으로 반환해야 한다.
- **REQ-GV-011**: `GET /stats/gap-variance` 요청 시 분석 페이지(HTML)를 반환해야 한다.
- **REQ-GV-012**: 신규 추첨 데이터 적재로 `invalidate_cache()` 호출 시
  `_gap_var_cache` 를 비워야 한다.

### State-driven (상태 기반)

- **REQ-GV-020**: 데이터가 없을 때(빈 리스트/None) total_draws=0, avg_variance=0.0,
  most_common_range="0-10", uniform_gap_pct=0.0 의 일관된 빈 구조를 반환해야 한다.

### Optional (선택)

- **REQ-GV-030**: 동일 회차 수 재요청 시 캐시된 결과를 반환하여 재계산을 피한다.

## 요약 통계 정의

- **avg_variance**: 전체 회차 간격 분산 평균(소수 2자리). 데이터 없으면 0.0.
- **most_common_range**: count 최대 구간. 동률 시 키 정의 순서상 앞선 구간.
- **uniform_gap_pct**: 분산 < 10("0-10", 균등 간격) 회차 비율(%, 소수 2자리).

## 응답 구조

```python
{
    "total_draws": int,
    "avg_variance": float,
    "most_common_range": str,
    "uniform_gap_pct": float,
    "gap_variance_distribution": {
        "0-10":   {"count": int, "pct": float},
        "10-30":  {"count": int, "pct": float},
        "30-60":  {"count": int, "pct": float},
        "60-100": {"count": int, "pct": float},
        "100+":   {"count": int, "pct": float},
    }
}
```

## 비목표 (Out of Scope)

- 간격 분산 기반 번호 추천/예측은 다루지 않는다.
- 표본분산(sample variance, n-1) 은 사용하지 않는다(모분산만).
