---
id: SPEC-LOTTO-081
title: 짝수 연속 포함 분포 분석
status: Planned
version: 0.1.0
created: 2026-06-15
---

# SPEC-LOTTO-081: 짝수 연속 포함 분포 분석

## 개요

각 회차의 본번호 6개(보너스 제외)에서 "짝수 연속 묶음(even run)"이 몇 개나 존재하는지
집계하고, 전체 회차에 대한 분포를 분석한다.

**짝수 연속 묶음(even run)** 정의: 간격이 정확히 2인 짝수 번호 2개 이상의 연속 그룹.
예) {2,4}, {4,6,8}, {10,12}. 간격이 4 이상인 짝수(예: 2,6)는 연속 짝수가 아니다.

기존 SPEC와의 차이:
- SPEC-074(짝수 포함 개수): 짝수의 "총 개수"를 센다.
- SPEC-069(연속 쌍): 임의 번호 간 인접 차이 1인 쌍을 센다.
- SPEC-081(이 SPEC): 간격 2인 짝수 연속 묶음의 "수"를 센다 (별개 기능).

6개 번호 모두 짝수일 때 최대 짝수 연속 묶음 수는 3개({2,4},{8,10},{14,16})이므로
분포 키는 "0","1","2","3" 4개 고정이다.

## EARS 요구사항

### Ubiquitous (상시)

- REQ-ER-001: 시스템은 각 회차 본번호 6개(보너스 제외) 중 짝수만 추출하여,
  간격이 정확히 2인 연속 짝수 묶음(길이>=2)의 수를 산출해야 한다.
- REQ-ER-002: 시스템은 짝수 연속 묶음 수를 "0","1","2","3" 4개 고정 키로 분류해야 한다.
- REQ-ER-003: even_run_distribution은 4개 키를 항상 포함해야 한다(미관측은 0으로 채움).
- REQ-ER-004: 각 분포 항목은 count(정수)와 pct(소수 2자리)를 포함해야 한다.
- REQ-ER-005: 모든 분포 count의 합은 total_draws와 같아야 한다.

### Event-driven (이벤트)

- REQ-ER-010: 사용자가 GET /api/stats/even_run 을 요청하면 시스템은 200과 JSON 통계를
  반환해야 한다.
- REQ-ER-011: 사용자가 GET /stats/even-run 을 요청하면 시스템은 200과 HTML 페이지를
  반환해야 한다.
- REQ-ER-012: 신규 추첨 데이터 적재로 invalidate_cache()가 호출되면 시스템은
  _even_run_cache를 비워야 한다.

### State-driven (상태)

- REQ-ER-020: draws가 비어 있거나 None이면 시스템은 예외 없이 total_draws=0,
  has_even_run_pct=0.0, most_common_group_count=0, avg_even_run_count=0.0,
  4개 키 전부 0 의 일관된 구조를 반환해야 한다.

### Unwanted (금지)

- REQ-ER-030: 시스템은 간격이 2가 아닌 짝수(예: 2,6 간격 4)를 연속 짝수로 계산하지
  않아야 한다.
- REQ-ER-031: 시스템은 길이 1의 단일 짝수를 묶음으로 계산하지 않아야 한다.
- REQ-ER-032: 시스템은 기존 함수의 동작을 변경하지 않아야 한다.

### Optional (선택)

- REQ-ER-040: most_common_group_count 동률 시 더 작은 키가 선택되어야 한다(tie-break).

## 응답 구조

```python
{
    "total_draws": int,
    "has_even_run_pct": float,         # >= 1 묶음 회차 비율(%, 소수 2자리)
    "most_common_group_count": int,    # 0~3, 동률 시 작은 값
    "avg_even_run_count": float,       # 회차당 평균 묶음 수(소수 2자리)
    "even_run_distribution": {
        "0": {"count": int, "pct": float},
        "1": {"count": int, "pct": float},
        "2": {"count": int, "pct": float},
        "3": {"count": int, "pct": float},
    }
}
```

## 함수/라우트

- 데이터: `get_even_run_stats(draws)`, 헬퍼 `_count_even_runs(numbers)`
- 캐시: `_even_run_cache` (키 str(len(draws)))
- API: GET /api/stats/even_run
- 페이지: GET /stats/even-run → even_run.html
- 내비: "짝수연속"
