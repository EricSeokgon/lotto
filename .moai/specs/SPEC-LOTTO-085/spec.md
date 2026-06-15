---
id: SPEC-LOTTO-085
title: 일의 자리 중복 분포 분석
status: Planned
version: 0.1.0
created: 2026-06-15
---

# SPEC-LOTTO-085: 일의 자리 중복 분포 분석

## 개요

회차별 본번호 6개(보너스 제외) 각각의 일의 자리(units digit = n % 10)를 추출하고,
같은 일의 자리를 공유하는 번호가 2개 이상인 "그룹"의 수를 집계한다. 6개 번호와
10개의 가능한 일의 자리가 있으므로, 2개 이상이 같은 일의 자리를 공유하는 그룹의
현실적 최댓값은 3이다. 그룹 수를 4개 고정 키("0"~"3")로 분류(3 초과는 3으로 상한)
하여 분포·평균·최빈값·중복쌍 포함 비율을 제공한다.

본 기능은 다음 기존 기능과 완전히 다른 별개 지표다.
- SPEC-063(get_digit_sum_dist_stats): 끝자리 합계 분포(번호 일의 자리의 합).
- SPEC-079(get_digit_sum_dist_stats 계열): 끝자리 합계 분포.
- get_last_digit_stats(SPEC-055): 모든 번호의 끝자리별 누적 빈도.
본 SPEC은 "같은 일의 자리를 가진 번호가 2개 이상인 그룹의 수"를 센다.

## 정의

- 회차의 본번호 6개를 일의 자리(n % 10)별로 그룹화한다.
- 그룹 내 번호가 2개 이상인 일의 자리 값의 개수를 센다(=중복 그룹 수).
- "쌍의 개수"가 아니라 "2개 이상을 가진 서로 다른 일의 자리 값의 개수"이다.
- 범위: 0 ~ 3 (3 초과 시 3으로 상한).
- 분포 키: "0", "1", "2", "3" (항상 모두 존재, zero-fill).

예시:
- [1,11,21,31,41,2] → 1→{1,11,21,31,41}(5개), 2→{2}(1개) → 1그룹 → 1
- [1,2,3,4,5,6] → 모두 다른 일의 자리 → 0그룹 → 0
- [1,11,2,12,3,13] → 1→{1,11}, 2→{2,12}, 3→{3,13} → 3그룹 → 3
- [5,15,25,6,16,26] → 5→{5,15,25}, 6→{6,16,26} → 2그룹 → 2
- [1,11,2,22,3,4] → 1→{1,11}, 2→{2,22} → 2그룹 → 2

## EARS 요구사항

### Ubiquitous (항상)
- REQ-LP-001: 시스템은 회차별 본번호 6개(보너스 제외)를 일의 자리별로 그룹화하여 중복 그룹 수를 산출한다.
- REQ-LP-002: 시스템은 중복 그룹 수를 4개 고정 키("0"~"3")로 분류하며 미관측 키는 0으로 채운다.
- REQ-LP-003: 시스템은 last_digit_pair_distribution의 각 항목에 count·pct를 포함한다.
- REQ-LP-004: 시스템은 모든 pct를 소수 2자리로 반올림한다.
- REQ-LP-005: 시스템은 중복 그룹 수가 3을 초과하면 3으로 상한 처리한다.

### Event-driven (이벤트 발생 시)
- REQ-LP-010: 분석이 요청되면 시스템은 total_draws, has_pair_pct,
  most_common_pair_count, avg_pair_count, last_digit_pair_distribution을 반환한다.
- REQ-LP-011: 신규 추첨 데이터 적재(invalidate_cache 호출) 시 일의 자리 중복 캐시를 무효화한다.

### State-driven (조건 충족 시)
- REQ-LP-020: most_common_pair_count 동률 시 더 작은 키를 선택한다.
- REQ-LP-021: has_pair_pct는 중복 그룹 수가 1 이상인 회차 비율(소수 2자리)이다.

### Unwanted (금지)
- REQ-LP-030: 시스템은 기존 함수(get_digit_sum_dist_stats, get_last_digit_stats 등)를 수정하지 않는다.

### Optional (선택)
- REQ-LP-040: 가능하면 동일 입력 재호출 시 캐시된 결과를 재사용한다.

## 응답 구조

```python
{
    "total_draws": int,
    "has_pair_pct": float,             # 중복 그룹 수 >= 1 비율(소수 2자리)
    "most_common_pair_count": int,     # 0~3, 동률 시 작은 키
    "avg_pair_count": float,           # 회차당 평균 그룹 수(소수 2자리)
    "last_digit_pair_distribution": {
        "0": {"count": int, "pct": float},
        "1": {"count": int, "pct": float},
        "2": {"count": int, "pct": float},
        "3": {"count": int, "pct": float},
    }
}
```

- 4개 키("0"~"3")는 항상 모두 존재한다(zero-fill).
- 빈 draws: 모두 0, most_common_pair_count=0.

## 엔드포인트

- 데이터 함수: `get_last_digit_pair_stats(draws)`
- 헬퍼: `_count_last_digit_pairs(numbers)`
- 캐시: `_last_digit_pair_cache`
- API: GET /api/stats/last_digit_pair
- 페이지: GET /stats/last-digit-pair → last_digit_pair.html
- 내비게이션: "끝자리쌍"
