---
id: SPEC-LOTTO-087
title: 번호 중앙값 구간 분포 분석
status: Planned
version: 0.1.0
created: 2026-06-15
---

# SPEC-LOTTO-087: 번호 중앙값 구간 분포 분석

## 개요

각 회차 본번호 6개(보너스 제외)를 오름차순 정렬한 뒤 3·4번째 수의 평균(중앙값)을
산출하고, 그 값이 속하는 10단위 구간(5개)의 분포를 집계한다.

- 중앙값 = (sorted[2] + sorted[3]) / 2 (float)
- 구간(5개): "1-9"(<10), "10-19"(<20), "20-29"(<30), "30-39"(<40), "40-45"(>=40)

SPEC-071(중앙값 9구간 "1-5".."41-45")과는 버킷 정의가 완전히 다른 별개 지표다.
헬퍼 충돌을 피하기 위해 본 SPEC의 버킷 헬퍼는 `_median_range_bucket`으로 명명한다.

## 요구사항 (EARS)

### Ubiquitous
- THE 시스템 SHALL 각 회차 본번호 6개의 중앙값을 (정렬 후 3·4번째 평균)으로 산출한다.
- THE 시스템 SHALL 중앙값을 5개 10단위 구간 키로 분류한다.
- THE 시스템 SHALL median_range_distribution에 5개 키를 항상 포함하고 미관측 구간은 0으로 채운다.

### Event-driven
- WHEN `get_median_range_stats(draws)`가 호출되면, THE 시스템 SHALL
  {total_draws, avg_median, most_common_range, central_median_pct,
  median_range_distribution} 매핑을 반환한다.
- WHEN 신규 추첨 데이터가 적재되면, THE 시스템 SHALL `invalidate_cache()`로
  `_median_range_cache`를 무효화한다.

### State-driven
- WHILE draws가 빈 리스트/None이면, THE 시스템 SHALL total_draws=0, avg_median=0.0,
  most_common_range="1-9", central_median_pct=0.0, 5개 키 전부 0을 반환한다.

### Optional
- WHERE 동일 회차 수로 재호출되면, THE 시스템 SHALL 캐시 결과를 반환한다.

## API / Web

- GET /api/stats/median_range → JSON 통계
- GET /stats/median-range → median_range.html 페이지
- 네비게이션: "중앙값구간"

## 비고

- Python 3.9 호환(walrus/zip(strict)/match 미사용)
- 기존 함수 수정 금지
