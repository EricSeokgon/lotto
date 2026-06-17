---
id: SPEC-LOTTO-095
title: 번호 스팬 분포 분석
status: completed
version: 1.0.0
created: 2026-06-16
---

# SPEC-LOTTO-095: 번호 스팬 분포 분석

## 개요

각 회차의 본번호 6개(보너스 제외)에서 최댓값과 최솟값의 차이를
"스팬(span = max - min)"으로 정의하고, 스팬 값을 7개 구간 버킷으로
분류하여 분포를 분석한다.

스팬은 번호열이 얼마나 좁게 또는 넓게 퍼져 있는지를 나타내는 단일
폭(spread) 지표이며, 범위는 최소 5(예: 1,2,3,4,5,6)에서
최대 44(예: 1,2,3,4,5,45)까지이다.

7개 버킷:
"10 이하"(≤10), "11-20", "21-25", "26-30", "31-35", "36-40", "41 이상"(≥41).

예) [1,2,3,4,5,6] → span=5 → "10 이하",
[3,11,22,30,38,44] → span=41 → "41 이상".

## 배경 / 동기

SPEC-064(get_min_max_stats: 최솟값·최댓값 개별 값/범위 통계)나
SPEC-093(get_first_last_zone_stats: 최소/최대 소속 3구간 밴드 조합 분포)와는
출력 구조와 요약 지표가 다른 별개 시각이다. SPEC-093은 max-min을
`avg_span` 보조 지표로만 노출하고 주 분포는 구간 밴드 조합(AA~CC)인 반면,
본 SPEC은 스팬 값 자체를 7개 폭 구간으로 버킷화하여 "좁은 조합/넓은 조합"
비율과 최빈 구간을 한국어 키로 직관적으로 제공하는 것이 목적이다.

## 용어 정의

- 스팬(span): 한 회차 본번호 6개의 `max(numbers) - min(numbers)`. 범위 5~44.
- 좁은 회차(narrow): 스팬 ≤ 20 인 회차.
- 넓은 회차(wide): 스팬 ≥ 36 인 회차.
- 버킷(bucket): 스팬 값을 분류하는 7개 고정 구간 키.

## EARS 요구사항

### Ubiquitous (항상)

- U1: 시스템은 `span_distribution` 에 항상 7개 고정 키
  ("10 이하","11-20","21-25","26-30","31-35","36-40","41 이상")를 포함하며,
  미관측 버킷은 count=0, pct=0.0 으로 채운다.
- U2: 시스템은 각 회차의 본번호 6개에서 스팬(max - min)을 산출한 뒤
  해당 스팬이 속하는 버킷에 1을 누적한다.

### Event-driven (이벤트 기반)

- E1: GET /api/stats/span 요청 시 시스템은 스팬 분포 통계를 JSON 으로 반환한다.
- E2: GET /stats/span 요청 시 시스템은 span.html 페이지를 렌더링한다.

### State-driven (상태 기반)

- S1: draws 가 비어 있으면(또는 None) 시스템은 total_draws=0,
  avg_span=0.0, most_common_range="10 이하", narrow_pct=0.0, wide_pct=0.0,
  그리고 7개 키 전부 0 으로 채운 일관된 빈 구조를 반환한다.

### Unwanted Behavior (비정상 동작 방지)

- N1: 스팬이 버킷 경계값(예: 10, 20, 25, 30, 35, 40, 41)일 때 시스템은
  중복 카운트하거나 누락하지 않고 정확히 하나의 버킷에만 배정한다.

### Optional (선택)

- O1: 동일 길이(len(draws)) 재요청 시 시스템은 캐시된 결과를 재사용할 수 있다.

## 버킷 경계 규칙

| 버킷 키 | 스팬 범위 |
|---------|-----------|
| "10 이하"  | span ≤ 10 |
| "11-20"   | 11 ≤ span ≤ 20 |
| "21-25"   | 21 ≤ span ≤ 25 |
| "26-30"   | 26 ≤ span ≤ 30 |
| "31-35"   | 31 ≤ span ≤ 35 |
| "36-40"   | 36 ≤ span ≤ 40 |
| "41 이상"  | span ≥ 41 |

- narrow_pct = (스팬 ≤ 20 회차 수) / total × 100 ("10 이하" + "11-20" 버킷)
- wide_pct = (스팬 ≥ 36 회차 수) / total × 100 ("36-40" + "41 이상" 버킷)

## 응답 구조

```python
{
    "total_draws": int,
    "avg_span": float,                    # 회차당 평균 스팬(소수 2자리)
    "most_common_range": str,             # 7개 버킷 중 최빈, 동률 시 키 정의 순서상 앞선 값
    "narrow_pct": float,                  # 스팬 ≤ 20 회차 비율(%, 소수 2자리)
    "wide_pct": float,                    # 스팬 ≥ 36 회차 비율(%, 소수 2자리)
    "span_distribution": {
        "10 이하": {"count": int, "pct": float},
        "11-20": {"count": int, "pct": float},
        "21-25": {"count": int, "pct": float},
        "26-30": {"count": int, "pct": float},
        "31-35": {"count": int, "pct": float},
        "36-40": {"count": int, "pct": float},
        "41 이상": {"count": int, "pct": float},
    }
}
```

## 비기능 요구사항

- Python 3.9 호환(match/case·zip(strict=) 금지).
- 서버 렌더링 전용(클라이언트 JS 금지).
- 결정적(동일 입력 → 동일 출력), 코어 모듈 `lotto/*.py` 미수정.
- 테스트는 `tests/test_span.py`, mypy 통과.

## 인수 기준

상세 인수 기준은 [acceptance.md](acceptance.md) 참조.

## 비범위 (Out of Scope) / Exclusions (What NOT to Build)

- SPEC-064(최솟값·최댓값 개별 값/범위 통계), SPEC-093(최소·최대 구간 밴드
  조합 AA~CC 분포)는 본 SPEC과 무관하며 수정·병합하지 않는다. SPEC-093의
  `get_first_last_zone_stats` 내 `avg_span` 보조 지표는 그대로 두고
  본 SPEC은 독립 함수 `compute_span_distribution`을 신설한다.
- 버킷 경계나 개수를 사용자가 동적으로 조정하는 기능은 만들지 않는다(7개 고정).
- 미래 출현 예측은 본 SPEC 범위가 아니며, 과거 통계 제공에 한정한다.
- 보너스 번호는 스팬 계산에 포함하지 않는다(본번호 6개만).
