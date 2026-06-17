---
id: SPEC-LOTTO-090
title: 번호 합산 끝자리 분포 분석
status: Completed
version: 0.1.0
created: 2026-06-15
---

# SPEC-LOTTO-090: 번호 합산 끝자리 분포 분석

## 개요

각 회차 당첨번호(본번호 6개)의 합계를 구한 뒤, 그 합계의 **일의 자리(units digit)**
숫자(0~9)를 기준으로 회차를 분류하여 분포를 집계한다.

- `total_sum = sum(본번호 6개)`
- `last_digit = total_sum % 10`
- `key = str(last_digit)` → "0", "1", ..., "9" (10개 고정 키)

기존 SPEC-063 `get_last_digit_sum_stats`(개별 번호 끝자리 합을 low/mid/high 3구간으로
관측값만 집계)와 SPEC-079 `get_digit_sum_dist_stats`(6개 고정 키)와는 정의·출력 구조가
완전히 다른 별개 지표다.

## 요구사항 (EARS)

### Ubiquitous
- 시스템은 합계 일의 자리 분포를 항상 10개 고정 키("0"~"9")로 제공해야 한다(미관측 0 채움).
- 각 분포 항목은 `{count, pct}` 구조를 가져야 하며 pct는 소수 2자리로 반올림되어야 한다.

### Event-driven
- WHEN `/api/stats/sum_last_digit` 가 호출되면, 시스템은 200과 JSON 통계를 반환해야 한다.
- WHEN `/stats/sum-last-digit` 가 호출되면, 시스템은 200과 HTML 페이지를 반환해야 한다.

### State-driven
- WHILE draws가 비어있으면(빈 리스트/None), 시스템은 total_draws=0, avg_sum=0.0,
  most_common_digit="0", even_digit_pct=0.0, 10개 키 전부 0의 일관된 빈 구조를 반환해야 한다.

### Unwanted
- 시스템은 기존 함수(get_last_digit_sum_stats, get_digit_sum_dist_stats 등)를 수정하지
  않아야 한다.

## 요약 지표
- `most_common_digit` (str): 최빈 끝자리. 동률 시 가장 작은 키("0" < "1" < ...).
- `even_digit_pct` (float): 끝자리가 짝수(0,2,4,6,8)인 회차 비율(%), 소수 2자리.
- `avg_sum` (float): 전체 회차 평균 합계, 소수 2자리.

## 응답 구조
```python
{
    "total_draws": int,
    "avg_sum": float,
    "most_common_digit": str,
    "even_digit_pct": float,
    "sum_last_digit_distribution": {
        "0": {"count": int, "pct": float}, ..., "9": {"count": int, "pct": float}
    }
}
```

## 인터페이스
- Function: `get_sum_last_digit_stats(draws)`
- Cache: `_sum_last_digit_cache` (invalidate_cache로 무효화)
- API: GET /api/stats/sum_last_digit
- Page: GET /stats/sum-last-digit → sum_last_digit.html
- Nav: "합산끝자리"
