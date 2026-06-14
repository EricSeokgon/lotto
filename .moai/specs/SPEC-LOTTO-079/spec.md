---
id: SPEC-LOTTO-079
title: 끝자리 합계 분포 분석
status: Planned
version: 0.1.0
created: 2026-06-15
---

# SPEC-LOTTO-079: 끝자리 합계 분포 분석

## 개요

각 회차 당첨번호 6개(보너스 제외)의 끝자리(일의 자리, `n % 10`) 합계를 구하고,
그 합계를 6개 고정 구간 버킷으로 분류하여 분포를 분석한다.

기존 `get_last_digit_sum_stats`(SPEC-LOTTO-063)와는 **구조가 다르다**:
- SPEC-063: low/mid/high 3개 카테고리(<15 / 15~29 / >=30), `sum_distribution`은
  실제 관측된 합계 값만 키로 포함(zero-fill 없음).
- SPEC-079(본 SPEC): "0-9","10-14","15-19","20-24","25-29","30+" 6개 고정 구간 버킷,
  미관측 구간도 0으로 채운 `digit_sum_distribution` 제공.

두 기능은 동일한 끝자리 합 값을 계산 기반으로 쓰지만, 출력 구조·버킷·키가 완전히
독립적이며 SPEC-063 함수는 일절 수정하지 않는다.

## 정의

- 끝자리(last digit) = `n % 10` (일의 자리)
- 끝자리 합 = 회차 본번호 6개 끝자리의 합 (이론상 범위 0~54)
- 6개 구간 버킷:
  - `"0-9"`:   합 0 ~ 9
  - `"10-14"`: 합 10 ~ 14
  - `"15-19"`: 합 15 ~ 19
  - `"20-24"`: 합 20 ~ 24
  - `"25-29"`: 합 25 ~ 29
  - `"30+"`:   합 30 이상

## EARS 요구사항

### Ubiquitous (시스템 전반)

- REQ-DSD-001: 시스템은 회차별 본번호 6개(보너스 제외)의 끝자리 합을 산출한다.
- REQ-DSD-002: `digit_sum_distribution`은 항상 6개 고정 키를 모두 포함한다(미관측 0 채움).
- REQ-DSD-003: 각 분포 항목은 `count`와 `pct`(소수 2자리) 두 키를 가진다.

### Event-driven (트리거 기반)

- REQ-DSD-010: WHEN `/api/stats/digit_sum_dist` 요청 시, 시스템은 200과 JSON 통계를 반환한다.
- REQ-DSD-011: WHEN `/stats/digit-sum-dist` 요청 시, 시스템은 200과 HTML 페이지를 반환한다.
- REQ-DSD-012: WHEN 신규 추첨 데이터 적재(`invalidate_cache`) 시, 끝자리 합계 분포 캐시를 무효화한다.

### State-driven (상태 기반)

- REQ-DSD-020: WHILE `most_common_range` 산출 시 count 동률이면, `_DIGIT_SUM_KEYS`
  정의 순서상 앞선(=더 작은) 구간을 선택한다.

### Unwanted (금지)

- REQ-DSD-030: 시스템은 보너스 번호를 끝자리 합 계산에 포함하지 않는다.
- REQ-DSD-031: 시스템은 기존 `get_last_digit_sum_stats`(SPEC-063)를 수정하지 않는다.

### Optional (선택)

- REQ-DSD-040: WHERE 데이터 부재(빈/None) 시, 모든 수치 0과
  `most_common_range="0-9"`의 일관된 빈 구조를 반환한다.

## 응답 구조

```python
{
    "total_draws": int,
    "avg_digit_sum": float,          # 끝자리 합 평균 (소수 2자리)
    "most_common_range": str,        # 최빈 구간 (동률 시 작은 구간)
    "high_digit_sum_pct": float,     # 합 >= 25 비율 (소수 2자리)
    "digit_sum_distribution": {
        "0-9":   {"count": int, "pct": float},
        "10-14": {"count": int, "pct": float},
        "15-19": {"count": int, "pct": float},
        "20-24": {"count": int, "pct": float},
        "25-29": {"count": int, "pct": float},
        "30+":   {"count": int, "pct": float},
    },
}
```

## 기술 제약

- Python 3.9 호환 (walrus `:=`, `zip(strict=True)`, `match-case` 사용 금지)
- `draw.numbers()`는 본번호 6개(1~45, 보너스 제외)를 반환한다.
- FastAPI async 패턴.
- 캐시 키 `str(len(draws))`, `invalidate_cache()`로 무효화.
