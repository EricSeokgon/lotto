---
id: SPEC-LOTTO-084
title: 홀짝 전환 횟수 분포 분석
status: Planned
version: 0.1.0
created: 2026-06-15
---

# SPEC-LOTTO-084: 홀짝 전환 횟수 분포 분석

## 개요

회차별 본번호 6개를 오름차순 정렬한 뒤, 인접한 두 번호 사이에서 홀짝(odd/even)
패리티가 전환되는 횟수를 집계한다. 6개 번호는 5개의 인접 쌍을 가지므로 전환
횟수는 0~5 범위이다. 전환 횟수를 6개 고정 키("0"~"5")로 분류하여 분포·평균·
최빈값·고빈도 교차 비율을 제공한다.

본 기능은 SPEC-060(홀짝 개수 비율, odd/even count)과는 완전히 다른 별개 지표다.
SPEC-060은 회차 내 홀수/짝수의 "개수"를 세지만, 본 SPEC은 정렬된 번호열에서
패리티가 "전환되는 횟수"를 센다.

## 정의

- 6개 번호를 오름차순 정렬한다.
- transitions = (is_odd(sorted[i]) != is_odd(sorted[i+1])) 인 i의 개수.
- 범위: 0 ~ 5 (6개 번호의 인접 쌍 5개).
- 분포 키: "0", "1", "2", "3", "4", "5" (항상 모두 존재, zero-fill).

예시:
- [1,2,3,5,6,8] → 1→2(O→E), 2→3(E→O), 3→5(O→O), 5→6(O→E), 6→8(E→E) → 3회
- [1,3,5,7,9,11] → 전부 홀수 → 0회
- [2,4,6,8,10,12] → 전부 짝수 → 0회
- [1,2,3,4,5,6] → O,E,O,E,O,E (완전 교차) → 5회
- [1,3,5,7,9,10] → O,O,O,O,O,E → 1회

## EARS 요구사항

### Ubiquitous (항상)
- REQ-PT-001: 시스템은 회차별 본번호 6개(보너스 제외)를 정렬하여 홀짝 전환 횟수를 산출한다.
- REQ-PT-002: 시스템은 전환 횟수를 6개 고정 키("0"~"5")로 분류하며 미관측 키는 0으로 채운다.
- REQ-PT-003: 시스템은 parity_transition_distribution의 각 항목에 count·pct를 포함한다.
- REQ-PT-004: 시스템은 모든 pct를 소수 2자리로 반올림한다.

### Event-driven (이벤트 발생 시)
- REQ-PT-010: 분석이 요청되면 시스템은 total_draws, avg_transitions,
  most_common_transitions, high_alternation_pct, parity_transition_distribution을 반환한다.
- REQ-PT-011: 신규 추첨 데이터 적재(invalidate_cache 호출) 시 홀짝 전환 캐시를 무효화한다.

### State-driven (조건 충족 시)
- REQ-PT-020: most_common_transitions 동률 시 더 작은 키를 선택한다.
- REQ-PT-021: high_alternation_pct는 전환 횟수가 4 이상인 회차 비율(소수 2자리)이다.

### Unwanted (금지)
- REQ-PT-030: 시스템은 기존 함수(get_odd_even_stats 등)를 수정하지 않는다.

### Optional (선택)
- REQ-PT-040: 가능하면 동일 입력 재호출 시 캐시된 결과를 재사용한다.

## 응답 구조

```python
{
    "total_draws": int,
    "avg_transitions": float,            # 평균, 소수 2자리
    "most_common_transitions": int,      # 0-5, 동률 시 작은 키
    "high_alternation_pct": float,       # 전환 >= 4 비율, 소수 2자리
    "parity_transition_distribution": {
        "0": {"count": int, "pct": float},
        ...
        "5": {"count": int, "pct": float},
    }
}
```

빈 draws: 모든 값 0, most_common_transitions=0, 6개 키 zero-fill.

## 인터페이스

- 함수: `get_parity_transition_stats(draws)`
- 헬퍼: `_count_parity_transitions(numbers)`
- 캐시: `_parity_trans_cache`
- API: GET /api/stats/parity_transition
- 페이지: GET /stats/parity-transition → parity_transition.html
- 내비게이션: "홀짝전환"
