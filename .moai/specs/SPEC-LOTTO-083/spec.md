---
id: SPEC-LOTTO-083
title: 홀수 연속 포함 분포 분석
status: Planned
version: 0.1.0
created: 2026-06-15
---

# SPEC-LOTTO-083: 홀수 연속 포함 분포 분석

## 개요

각 회차의 본번호 6개(보너스 제외) 중 홀수만 추출·정렬하여, 간격이 정확히 2인
연속 홀수 묶음(길이 >= 2)이 몇 개나 존재하는지를 집계하고 그 분포를 분석한다.

SPEC-LOTTO-081(짝수 연속 묶음, 간격=2)의 홀수 대응 기능이다. 추출 대상이
홀수(`n % 2 == 1`)라는 점만 다르고, 묶음 산출 로직(간격 2, 길이 >= 2)과 출력
구조는 동일하다.

## 배경

- 홀수 번호(1, 3, 5, ...)가 +2 간격으로 연이어 출현하는 패턴(예: 3,5,7)의
  빈도를 통계적으로 관찰한다.
- SPEC-060(홀짝 비율, 개수)·SPEC-069(연속 쌍, 간격1)와는 정의·출력이 다른
  별개 지표이다.

## 정의

- 홀수 추출: `odds = sorted(n for n in numbers if n % 2 == 1)`
- 연속 홀수 묶음: 정렬된 홀수에서 인접 차이가 정확히 2인 구간(길이 >= 2).
  - 예) `[1,3,5,7,9,11]` → `{1,3,5,7,9,11}` 1개 묶음.
  - 예) `[1,3,9,11]` → `{1,3}`, `{9,11}` 2개 묶음.
  - 예) `[1,5,9,13,17,21]` → 간격 4 → 0개 묶음.
  - 단일 홀수(길이 1)는 묶음으로 계산하지 않는다.
- 묶음 수는 4개 고정 키 `"0","1","2","3"`로 분류한다(3 이상은 3으로 캡).
  - 본번호 6개 모두 홀수일 때 최대 묶음 수는 3개이므로 캡 동작은 방어적이다.

## EARS 요구사항

### Ubiquitous (항상 적용)

- REQ-OR-001: 시스템은 한 회차 본번호 6개 중 홀수만 추출·정렬하여 간격 2 연속
  홀수 묶음(길이 >= 2)의 수를 산출한다.
- REQ-OR-002: 시스템은 묶음 수를 4개 고정 키 `"0","1","2","3"`로 분류하며,
  미관측 키도 count=0, pct=0.0 으로 항상 포함한다.
- REQ-OR-003: 시스템은 산출된 묶음 수가 3을 초과하면 3으로 캡(cap)한다.
- REQ-OR-004: `odd_run_distribution` 의 모든 항목은 `count`, `pct` 키를 가진다.

### Event-driven (요청 발생 시)

- REQ-OR-010: GET `/api/stats/odd_run` 요청 시 시스템은 200 과 함께 분포 통계
  JSON 을 반환한다.
- REQ-OR-011: GET `/stats/odd-run` 요청 시 시스템은 200 과 함께 HTML 페이지를
  렌더링한다.
- REQ-OR-012: 신규 추첨 데이터 적재(invalidate_cache 호출) 시 시스템은 홀수
  연속 분포 캐시를 무효화한다.

### State-driven (조건부)

- REQ-OR-020: 데이터가 없을 때(빈 리스트/None) 시스템은 예외 없이
  `total_draws=0`, `has_odd_run_pct=0.0`, `most_common_group_count=0`,
  `avg_odd_run_count=0.0`, 4개 키가 모두 0 인 일관된 빈 구조를 반환한다.

### Optional (파생 지표)

- REQ-OR-030: 시스템은 `has_odd_run_pct`(묶음 >= 1 회차 비율, %), 소수 2자리
  반올림을 제공한다.
- REQ-OR-031: 시스템은 `most_common_group_count`(최빈 묶음 수)를 제공하며,
  동률 시 정의 순서상 더 작은 키를 선택한다.
- REQ-OR-032: 시스템은 `avg_odd_run_count`(회차당 평균 묶음 수), 소수 2자리
  반올림을 제공한다.

## 응답 구조

```python
{
    "total_draws": int,
    "has_odd_run_pct": float,          # 묶음 >= 1 비율, 소수 2자리
    "most_common_group_count": int,    # 0~3, 동률 시 작은 키
    "avg_odd_run_count": float,        # 회차당 평균, 소수 2자리
    "odd_run_distribution": {
        "0": {"count": int, "pct": float},
        "1": {"count": int, "pct": float},
        "2": {"count": int, "pct": float},
        "3": {"count": int, "pct": float},
    },
}
```

## 범위 밖 (Out of Scope)

- 기존 함수(get_even_run_stats 등) 수정.
- 짝수 연속(SPEC-081), 홀짝 개수(SPEC-060)와의 통합 지표 산출.

## 관련 SPEC

- SPEC-LOTTO-081: 짝수 연속 포함 분포 분석 (본 기능의 짝수 대응).
- SPEC-LOTTO-060: 홀짝 비율 분석.
- SPEC-LOTTO-069: 연속 쌍 분석(간격 1).
