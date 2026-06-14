---
id: SPEC-LOTTO-080
title: 번호 간격 최대값 분포 분석
status: Completed
version: 1.0.0
created: 2026-06-15
updated: 2026-06-15
author: ircp
---

# SPEC-LOTTO-080: 번호 간격 최대값 분포 분석

## 개요

각 회차의 정렬된 본번호 6개에서 인접한 번호 간 최대 간격(max gap)을 구하고,
이를 6개 고정 구간으로 분류하여 분포를 분석한다.

기존 `get_gap_stats`(SPEC-LOTTO-056)는 인접 간격 전체를 small/medium/large로
분류하고 평균/위치별 평균/최빈 간격을 집계하며, `avg_max_gap`(회차별 최대 간격의
평균)만 단일 수치로 제공한다. 본 SPEC은 회차별 **최대 간격값 자체를 구간 버킷으로
분류한 분포**를 제공하는 별개 기능이다.

## 용어 정의

- **max_gap**: 한 회차의 정렬된 본번호 6개(보너스 제외)에서 인접 차이 5개 중 최댓값.
  - 예) [1,2,10,20,30,40] → 정렬 간격 [1,8,10,10,10] → max_gap = 10
  - 예) [1,2,3,4,5,6] → 간격 [1,1,1,1,1] → max_gap = 1
  - 예) [1,2,3,40,41,42] → 간격 [1,1,37,1,1] → max_gap = 37
- **구간(bucket)**: max_gap을 6개 고정 구간으로 분류.
  - "1-5", "6-10", "11-15", "16-20", "21-30", "31+"

## 요구사항 (EARS)

### Ubiquitous Requirements

- **REQ-MGD-001**: 시스템은 각 회차의 정렬된 본번호 6개(보너스 제외)에서 인접 차이의
  최댓값(max_gap)을 산출해야 한다.
- **REQ-MGD-002**: 시스템은 max_gap을 6개 고정 구간
  ("1-5","6-10","11-15","16-20","21-30","31+")으로 분류해야 한다.
- **REQ-MGD-003**: max_gap_distribution은 미관측 구간을 포함하여 항상 6개 키를
  포함해야 한다(zero-fill).
- **REQ-MGD-004**: 각 분포 항목은 count와 pct(소수 2자리)를 포함해야 한다.
- **REQ-MGD-005**: 시스템은 avg_max_gap(회차별 max_gap의 평균, 소수 2자리)을
  제공해야 한다.
- **REQ-MGD-006**: 시스템은 most_common_range(최빈 구간)를 제공해야 한다.
- **REQ-MGD-007**: 시스템은 high_gap_pct(max_gap >= 21 인 회차 비율, 소수 2자리)을
  제공해야 한다.

### Event-driven Requirements

- **REQ-MGD-008**: 사용자가 GET /api/stats/max_gap_dist 를 호출하면 시스템은 JSON
  통계를 200으로 반환해야 한다.
- **REQ-MGD-009**: 사용자가 GET /stats/max-gap-dist 를 호출하면 시스템은 HTML
  페이지를 200으로 반환해야 한다.

### State-driven Requirements

- **REQ-MGD-010**: while 동일 입력으로 반복 호출되는 동안, 시스템은 캐시된 결과를
  재사용해야 한다.

### Unwanted Requirements

- **REQ-MGD-011**: 시스템은 보너스 번호를 max_gap 계산에 포함해서는 안 된다.
- **REQ-MGD-012**: 빈 입력(빈 리스트/None)에서도 시스템은 예외를 발생시켜서는 안 되며,
  total_draws=0, 6개 키 전부 0, most_common_range="1-5" 의 일관된 구조를 반환해야 한다.

### Optional Requirements

- **REQ-MGD-013**: most_common_range 동률 시, 가능하면 정의 순서상 앞선(더 작은)
  구간을 선택한다.

## 비고

- Python 3.9 호환 (walrus/match-case/zip(strict=True) 미사용).
- `draw.numbers()`는 정렬된 본번호 6개(보너스 제외)를 반환한다.
