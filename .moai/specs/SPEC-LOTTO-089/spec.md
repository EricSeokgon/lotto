---
id: SPEC-LOTTO-089
title: 저·고 번호 균형 분포 분석
status: completed
version: 1.0.0
created: 2026-06-15
updated: 2026-06-15
---

# SPEC-LOTTO-089: 저·고 번호 균형 분포 분석

## 개요

각 회차 본번호 6개(보너스 제외)를 저번호(1~22)와 고번호(23~45)로 분류하여,
한 회차의 저/고 개수 조합(`{low}저{high}고`)이 어떤 분포를 이루는지 집계한다.
저번호와 고번호의 균형(3저3고)이 얼마나 자주 나타나는지를 중심으로 통계를 제공한다.

기존 SPEC-LOTTO-061(고저 비율 분석, `get_high_low_stats`, `/stats/high-low`)과는
출력 구조가 다른 별개 지표다. SPEC-061은 저/고 개수(0~6) 정수 키 분포를 제공하는 반면,
본 SPEC은 조합 문자열("0저6고"~"6저0고") 7개 키 분포와 균형 비율(balanced_pct)을 제공한다.

## 분류 규칙

- 저(low): 1~22 (n <= 22, 경계 22는 저).
- 고(high): 23~45 (n >= 23, 경계 23은 고).
- low_count = 본번호 중 저(n <= 22) 개수 (0~6).
- high_count = 6 - low_count.
- combo key = `f"{low_count}저{high_count}고"` (예: "3저3고", "4저2고").

분포 키(7개, 정의 순서가 동률 시 우선순위):
`["0저6고", "1저5고", "2저4고", "3저3고", "4저2고", "5저1고", "6저0고"]`

## 요구사항 (EARS)

### Ubiquitous Requirements

- **REQ-LH-001**: 시스템은 각 회차 본번호 6개에서 저번호(n <= 22) 개수를 세어
  조합 문자열("{low}저{high}고")로 분류해야 한다.
- **REQ-LH-002**: 시스템은 분포에 항상 7개 키("0저6고"~"6저0고")를 포함하되,
  미관측 조합은 count=0, pct=0.0으로 채워야 한다.
- **REQ-LH-003**: 시스템은 high_count를 6 - low_count로 파생하여 합 불변식을 보장해야 한다.

### Event-driven Requirements

- **REQ-LH-004**: GET `/api/stats/low_high` 요청 시, 시스템은 저·고 균형 분포 통계를
  JSON으로 200 응답해야 한다.
- **REQ-LH-005**: GET `/stats/low-high` 요청 시, 시스템은 저·고 균형 분포 분석 페이지를
  HTML로 200 응답해야 한다.
- **REQ-LH-006**: 신규 추첨 데이터 적재로 `invalidate_cache()`가 호출되면,
  시스템은 저·고 균형 분포 캐시(`_low_high_cache`)를 무효화해야 한다.

### State-driven Requirements

- **REQ-LH-007**: 데이터가 없는 동안(빈 리스트/None) 시스템은 total_draws=0,
  avg_low_count=0.0, most_common_combo="0저6고", balanced_pct=0.0,
  7개 키 전부 0의 일관된 빈 구조를 반환해야 한다.

### Optional Requirements

- **REQ-LH-008**: 가능한 경우 시스템은 동일 회차 수 재요청에 대해 캐시된 결과를 반환하여
  재계산을 피해야 한다.

## 응답 구조

```python
{
    "total_draws": int,
    "avg_low_count": float,              # 저번호(1~22) 평균 개수, 소수 2자리
    "most_common_combo": str,            # "3저3고" 등, 동률 시 키 정의 순서상 앞선 조합
    "balanced_pct": float,               # "3저3고" 회차 비율(%), 소수 2자리
    "low_high_distribution": {
        "0저6고": {"count": int, "pct": float},
        "1저5고": {"count": int, "pct": float},
        "2저4고": {"count": int, "pct": float},
        "3저3고": {"count": int, "pct": float},
        "4저2고": {"count": int, "pct": float},
        "5저1고": {"count": int, "pct": float},
        "6저0고": {"count": int, "pct": float},
    }
}
```

## 비목표 (Non-goals)

- SPEC-061(고저 비율, 정수 키 분포)을 대체하거나 수정하지 않는다.
- 미래 출현 예측을 제공하지 않는다 (과거 통계 집계만 수행).
