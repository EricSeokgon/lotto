---
id: SPEC-LOTTO-094
title: 홀짝 교차 패턴 분포 분석
status: Planned
version: 0.1.0
created: 2026-06-16
---

# SPEC-LOTTO-094: 홀짝 교차 패턴 분포 분석

## 개요

각 회차의 본번호 6개(보너스 제외)를 오름차순 정렬한 뒤, 인접한 두 번호의
홀짝(parity)이 서로 다른 "교차"가 몇 번 발생하는지(0~5회)를 세어
교차 단계("교차0"~"교차5")별 분포를 분석한다.

정렬된 6개 번호에는 인접 쌍이 5개이므로 교차 횟수는 0~5 범위이다.
예) [1,2,3,4,5,6] → O,E,O,E,O,E → 5회 교차 → "교차5" (완전 교차),
[1,3,5,7,9,11] → 전부 홀수 → 0회 교차 → "교차0".

## 배경 / 동기

회차 내 홀짝 "개수"(SPEC-060)나 홀짝 "전환 횟수 + 고빈도(>=4) 비율"(SPEC-084)과는
출력 구조와 요약 지표가 다른 별개 시각이다. 본 SPEC은 "완전 교차(교차5)" 비율과
교차 단계 평균에 초점을 맞춰, 번호열의 홀짝 배열이 얼마나 규칙적으로 교차하는지를
"교차0"~"교차5" 한국어 키로 직관적으로 제공한다.

## EARS 요구사항

### Ubiquitous (항상)

- U1: 시스템은 `alternation_distribution` 에 항상 6개 고정 키
  ("교차0"~"교차5")를 포함하며, 미관측 단계는 count=0, pct=0.0 으로 채운다.
- U2: 시스템은 각 회차의 본번호 6개를 오름차순 정렬한 뒤 인접 쌍의 홀짝 교차
  횟수(0~5)를 산출한다.

### Event-driven (이벤트 기반)

- E1: GET /api/stats/alternation 요청 시 시스템은 교차 단계 분포 통계를 JSON 으로 반환한다.
- E2: GET /stats/alternation 요청 시 시스템은 alternation.html 페이지를 렌더링한다.

### State-driven (상태 기반)

- S1: draws 가 비어 있으면(또는 None) 시스템은 total_draws=0,
  avg_alternation=0.0, most_common_level="교차0", full_alternation_pct=0.0,
  그리고 6개 키 전부 0 으로 채운 일관된 빈 구조를 반환한다.

### Optional (선택)

- O1: 동일 길이(len(draws)) 재요청 시 시스템은 캐시된 결과를 재사용할 수 있다.

## 응답 구조

```python
{
    "total_draws": int,
    "avg_alternation": float,             # 회차당 평균 교차 횟수(소수 2자리)
    "most_common_level": str,             # "교차0"~"교차5", 동률 시 키 정의 순서상 앞선 값
    "full_alternation_pct": float,        # "교차5"(완전 교차) 비율(%, 소수 2자리)
    "alternation_distribution": {
        "교차0": {"count": int, "pct": float},
        "교차1": {"count": int, "pct": float},
        "교차2": {"count": int, "pct": float},
        "교차3": {"count": int, "pct": float},
        "교차4": {"count": int, "pct": float},
        "교차5": {"count": int, "pct": float},
    }
}
```

## 비범위 (Out of Scope)

- SPEC-060(홀짝 개수 비율), SPEC-084(홀짝 전환 횟수 + 고빈도 비율)는 본 SPEC과 무관.
- 미래 출현 예측은 본 SPEC 범위가 아니며, 과거 통계 제공에 한정한다.
