---
id: SPEC-LOTTO-086
title: 번호 합계 구간 세분화 분포 분석
status: completed
version: 0.1.0
created: 2026-06-15
---

# SPEC-LOTTO-086: 번호 합계 구간 세분화 분포 분석

## 개요

당첨번호 6개의 합계를 기존(SPEC-049 폭 20 버킷)보다 의미 중심의 비균등 10단위
세분화 구간(6개 버킷)으로 분류하여 분포를 분석한다. 중앙 구간(101-160)을
130/131에서 분할하여 "정상 분포 중심"을 포착하는 것이 핵심이다.

- 합계 범위: 최소 21(1+2+3+4+5+6), 최대 255(40+41+42+43+44+45)
- 버킷(6개, 비균등):
  - "21-60", "61-100", "101-130", "131-160", "161-200", "201-255"

본 기능은 SPEC-049(`sum_range_analysis`, 폭 20 버킷 + 공통 영역)와는 버킷 정의 및
출력 구조가 완전히 다른 별개의 지표다.

## 충돌 회피 결정

- 함수명: `get_sum_range_stats` (기존 미존재 → 그대로 사용)
- API: `GET /api/stats/sum_range` (언더스코어 — 기존 `/api/stats/sum-range` 하이픈과 구별)
- 페이지: `GET /stats/sum-range-detailed` (SPEC-049 `/stats/sum-range`와 충돌 회피)
- 템플릿: `sum_range_detailed.html` (SPEC-049 `sum_range.html`과 충돌 회피)
- 캐시: `_sum_range_cache`

## EARS 요구사항

### Ubiquitous

- THE SYSTEM SHALL 6개 합계 구간 키를 항상 포함하여(미관측 0 채움) 반환한다.
- THE SYSTEM SHALL 합계 분류 시 본번호 6개(보너스 제외)만 사용한다.

### Event-driven

- WHEN `get_sum_range_stats(draws)`가 호출되면, THE SYSTEM SHALL total_draws,
  avg_sum, most_common_range, middle_range_pct, sum_range_distribution을 반환한다.
- WHEN `GET /api/stats/sum_range`가 호출되면, THE SYSTEM SHALL 200 JSON을 반환한다.
- WHEN `GET /stats/sum-range-detailed`가 호출되면, THE SYSTEM SHALL 200 HTML을 반환한다.

### State-driven

- WHILE draws가 비어 있으면(None/빈 리스트), THE SYSTEM SHALL 모든 값 0,
  most_common_range="21-60", 6개 키 모두 0을 반환한다.

### Optional

- WHERE 동일 회차 수로 재요청되면, THE SYSTEM SHALL 캐시된 결과를 반환한다.

## 응답 구조

```python
{
    "total_draws": int,
    "avg_sum": float,            # 평균 합계, 소수 2자리
    "most_common_range": str,    # 동률 시 키 정의 순서상 앞선 구간
    "middle_range_pct": float,   # "101-130"+"131-160" 합산 비율, 소수 2자리
    "sum_range_distribution": {
        "21-60":   {"count": int, "pct": float},
        "61-100":  {"count": int, "pct": float},
        "101-130": {"count": int, "pct": float},
        "131-160": {"count": int, "pct": float},
        "161-200": {"count": int, "pct": float},
        "201-255": {"count": int, "pct": float},
    }
}
```
